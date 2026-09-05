const actionBtn = document.getElementById('actionBtn');
const intrusionBtn = document.getElementById('intrusionBtn');
const timeDisplay = document.getElementById('timeDisplay');
const statusDisplay = document.getElementById('statusDisplay');
const progressCircle = document.querySelector('.progress-ring__circle');
const notificationSound = document.getElementById('notificationSound');

const DURATION_MS = 25 * 60 * 1000;
const CIRCUMFERENCE = 2 * Math.PI * 45; // ~282.7

let state = 'idle'; // 'idle', 'running', 'paused', 'completed'
let elapsedMs = 0;
let sessionEndTime = null;
let animationFrameId = null;
let currentSessionId = null;
let patchInFlight = false; // Prevent race conditions

progressCircle.style.strokeDasharray = CIRCUMFERENCE;
progressCircle.style.strokeDashoffset = 0;

// Load from local storage
async function loadState() {
    const savedState = localStorage.getItem('focusTimer_state');
    if (savedState) {
        state = savedState;
        elapsedMs = parseInt(localStorage.getItem('focusTimer_elapsedMs'), 10) || 0;
        const savedEndTime = localStorage.getItem('focusTimer_sessionEndTime');
        sessionEndTime = savedEndTime ? parseInt(savedEndTime, 10) : null;
        currentSessionId = localStorage.getItem('focusTimer_sessionId');
        
        if (state === 'running') {
            tick();
        } else {
            updateUI(state === 'completed' ? 0 : DURATION_MS - elapsedMs);
        }
    } else {
        updateUI(DURATION_MS);
    }

    // Verify button state with server
    try {
        const res = await fetch('/sessions?status=running');
        if (res.ok) {
            const data = await res.json();
            const serverIsRunning = data.length > 0;
            
            if (serverIsRunning) {
                const serverSession = data[0];
                if (state !== 'running' || currentSessionId != serverSession.sessionID) {
                    state = 'running';
                    currentSessionId = serverSession.sessionID;
                    if (!sessionEndTime) {
                        sessionEndTime = Date.now() + DURATION_MS;
                        elapsedMs = 0;
                    }
                    saveState();
                    tick();
                }
            } else {
                if (state === 'running') {
                    // Server has no running session; fix local state
                    state = 'paused'; 
                    if (animationFrameId) {
                        cancelAnimationFrame(animationFrameId);
                        animationFrameId = null;
                    }
                    saveState();
                    updateUI(DURATION_MS - (sessionEndTime ? sessionEndTime - Date.now() : 0));
                }
            }
        }
    } catch (e) {
        console.error("Server sync failed:", e);
    }
}

function saveState() {
    localStorage.setItem('focusTimer_state', state);
    localStorage.setItem('focusTimer_elapsedMs', elapsedMs.toString());
    if (sessionEndTime) {
        localStorage.setItem('focusTimer_sessionEndTime', sessionEndTime.toString());
    } else {
        localStorage.removeItem('focusTimer_sessionEndTime');
    }
    if (currentSessionId) {
        localStorage.setItem('focusTimer_sessionId', currentSessionId.toString());
    } else {
        localStorage.removeItem('focusTimer_sessionId');
    }
}

function formatTime(ms) {
    const totalSeconds = Math.ceil(ms / 1000);
    const minutes = Math.floor(totalSeconds / 60);
    const seconds = totalSeconds % 60;
    return `${minutes.toString().padStart(2, '0')}:${seconds.toString().padStart(2, '0')}`;
}

function updateUI(remainingMs) {
    timeDisplay.textContent = formatTime(remainingMs);
    statusDisplay.textContent = state;
    
    const progress = (DURATION_MS - remainingMs) / DURATION_MS;
    const offset = progress * CIRCUMFERENCE;
    progressCircle.style.strokeDashoffset = offset;

    if (state === 'idle') {
        actionBtn.textContent = 'Start Timer';
        intrusionBtn.disabled = true;
    } else if (state === 'running') {
        actionBtn.textContent = 'Pause';
        intrusionBtn.disabled = false;
    } else if (state === 'paused') {
        actionBtn.textContent = 'Resume';
        intrusionBtn.disabled = true;
    } else if (state === 'completed') {
        actionBtn.textContent = 'Start New';
        intrusionBtn.disabled = true;
    }
}

function tick() {
    if (state !== 'running') return;

    const now = Date.now();
    let remainingMs = sessionEndTime - now;

    if (remainingMs <= 0) {
        remainingMs = 0;
        completeSession();
    } else {
        updateUI(remainingMs);
        animationFrameId = requestAnimationFrame(tick);
    }
}

async function startTimer() {
    // If starting a fresh session
    if (state === 'idle' || state === 'completed') {
        const startTimeIso = new Date().toISOString();
        
        try {
            const res = await fetch('/sessions', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ start_time: startTimeIso })
            });
            const data = await res.json();
            
            if (res.status === 409) {
                alert("A session is already running on this server. Please complete or stop it first.");
                return;
            } else if (!res.ok) {
                console.error("Error creating session:", data);
                return;
            }
            
            currentSessionId = data.sessionID;
            elapsedMs = 0;
        } catch (e) {
            console.error("Failed to reach server:", e);
            return;
        }
    } else if (state === 'paused') {
        // Resuming from pause
        try {
            const res = await fetch(`/sessions/${currentSessionId}`, {
                method: 'PATCH',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ status: 'running' })
            });
            if (!res.ok) {
                console.error("Error resuming session");
                return;
            }
        } catch (e) {
            console.error("Failed to reach server:", e);
            return;
        }
    }

    state = 'running';
    sessionEndTime = Date.now() + DURATION_MS - elapsedMs;
    saveState();
    updateUI(DURATION_MS - elapsedMs);
    tick();
}

async function pauseTimer() {
    state = 'paused';
    // Freeze elapsed time accurately based on Date.now()
    elapsedMs = DURATION_MS - (sessionEndTime - Date.now());
    if (animationFrameId) {
        cancelAnimationFrame(animationFrameId);
        animationFrameId = null;
    }
    saveState();
    updateUI(DURATION_MS - elapsedMs);
    
    try {
        await fetch(`/sessions/${currentSessionId}`, {
            method: 'PATCH',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ status: 'paused' })
        });
    } catch (e) {
        console.error("Failed to pause session on server:", e);
    }
}

async function completeSession() {
    // Prevent double-firing race condition
    if (state === 'completed' || patchInFlight) return;
    
    patchInFlight = true;
    state = 'completed';
    if (animationFrameId) {
        cancelAnimationFrame(animationFrameId);
        animationFrameId = null;
    }
    saveState();
    
    // Attempt to play sound
    notificationSound.play().catch(e => console.log('Audio play failed', e));
    updateUI(0);
    
    const endTimeIso = new Date().toISOString().split('T')[1].split('.')[0];
    const durationMins = 25;

    try {
        await fetch(`/sessions/${currentSessionId}`, {
            method: 'PATCH',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ 
                status: 'completed',
                end_time: endTimeIso,
                duration: durationMins
            })
        });
    } catch (e) {
        console.error("Failed to complete session on server:", e);
    } finally {
        patchInFlight = false;
    }
}

function resetTimer() {
    state = 'idle';
    elapsedMs = 0;
    sessionEndTime = null;
    currentSessionId = null;
    saveState();
    updateUI(DURATION_MS);
}

actionBtn.addEventListener('click', () => {
    if (state === 'idle' || state === 'completed') {
        if (state === 'completed') resetTimer();
        startTimer();
    } else if (state === 'running') {
        pauseTimer();
    } else if (state === 'paused') {
        startTimer(); // Actually it resumes
    }
});

intrusionBtn.addEventListener('click', async () => {
    if (state !== 'running' || !currentSessionId) return;

    const timestampIso = new Date().toISOString();
    try {
        const res = await fetch(`/sessions/${currentSessionId}/interruptions`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ timestamp: timestampIso })
        });
        if (!res.ok) {
            console.error("Failed to log intrusion:", await res.json());
        } else {
            // Optional visual feedback could go here, but requirements say:
            // "without pausing or resetting. ... feel like a background action."
        }
    } catch (e) {
        console.error("Failed to reach server for intrusion logging:", e);
    }
});

// Handle visibility changes to resync the timer when returning to tab
// This fulfills the reliability requirement and prevents race conditions
document.addEventListener('visibilitychange', () => {
    if (document.visibilityState === 'visible' && state === 'running') {
        tick();
    }
});

// Initialize UI from local storage
loadState();
