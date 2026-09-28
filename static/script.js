const actionBtn = document.getElementById('actionBtn');
const intrusionBtn = document.getElementById('intrusionBtn');
const intrusionCountDisplay = document.getElementById('intrusionCount');
const timeDisplay = document.getElementById('timeDisplay');
const statusDisplay = document.getElementById('statusDisplay');
const progressCircle = document.querySelector('.progress-ring__circle');
const notificationSound = document.getElementById('notificationSound');
const stopEarlyBtn = document.getElementById('stopEarlyBtn');
const durationSelect = document.getElementById('durationSelect');
const warningBanner = document.getElementById('warningBanner');

const DEFAULT_DURATION_MS = 25 * 60 * 1000;
const CIRCUMFERENCE = 2 * Math.PI * 45;

let state = 'idle';
let elapsedMs = 0;
let sessionEndTime = null;
let animationFrameId = null;
let currentSessionId = null;
let interruptionCount = 0;
let patchInFlight = false;
let currentFocusDurationMs = DEFAULT_DURATION_MS;

progressCircle.style.strokeDasharray = CIRCUMFERENCE;
progressCircle.style.strokeDashoffset = 0;

function hideWarning() {
    if (warningBanner) {
        warningBanner.style.display = 'none';
    }
}

function showWarning(msg) {
    if (warningBanner) {
        warningBanner.style.display = 'block';
        warningBanner.innerHTML = `
            <span>${msg}</span>
            <button onclick="document.getElementById('warningBanner').style.display='none'">Dismiss</button>
        `;
    }
}

function getSelectedDurationMs() {
    if (durationSelect && durationSelect.value) {
        const minutes = parseInt(durationSelect.value, 10);
        if (!isNaN(minutes) && minutes > 0) {
            return minutes * 60 * 1000;
        }
    }
    return DEFAULT_DURATION_MS;
}

if (durationSelect) {
    const savedMinutes = localStorage.getItem('focusTimer_preferredMinutes');
    if (savedMinutes) {
        durationSelect.value = savedMinutes;
    }
    currentFocusDurationMs = getSelectedDurationMs();
    durationSelect.addEventListener('change', () => {
        const mins = parseInt(durationSelect.value, 10);
        if (!isNaN(mins)) {
            localStorage.setItem('focusTimer_preferredMinutes', mins.toString());
        }
        if (state === 'idle' || state === 'completed') {
            currentFocusDurationMs = getSelectedDurationMs();
            updateUI(currentFocusDurationMs);
        }
    });
}

async function loadState() {
    const savedState = localStorage.getItem('focusTimer_state');
    const savedDuration = parseInt(localStorage.getItem('focusTimer_focusDurationMs'), 10);
    if (!isNaN(savedDuration) && savedDuration > 0) {
        currentFocusDurationMs = savedDuration;
    }
    if (savedState) {
        state = savedState;
        elapsedMs = parseInt(localStorage.getItem('focusTimer_elapsedMs'), 10) || 0;
        const savedEndTime = localStorage.getItem('focusTimer_sessionEndTime');
        sessionEndTime = savedEndTime ? parseInt(savedEndTime, 10) : null;
        currentSessionId = localStorage.getItem('focusTimer_sessionId');
        interruptionCount = parseInt(localStorage.getItem('focusTimer_interruptionCount'), 10) || 0;
        updateIntrusionCountUI();

        if (state === 'running') {
            resyncNow();
            tick();
        } else {
            updateUI(state === 'completed' ? 0 : currentFocusDurationMs - elapsedMs);
        }
    } else {
        currentFocusDurationMs = getSelectedDurationMs();
        updateUI(currentFocusDurationMs);
    }

    try {
        const res = await fetch('/sessions?status=running', { credentials: 'include' });
        if (res.status === 401) {
            window.location.href = '/login';
            return;
        }
        if (res.ok) {
            const data = await res.json();
            const serverIsRunning = data.length > 0;

            if (serverIsRunning) {
                const serverSession = data[0];
                const serverFocusMs = serverSession.focus_duration ? serverSession.focus_duration * 1000 : DEFAULT_DURATION_MS;
                const serverPausedMs = serverSession.paused_ms || 0;
                const serverStatus = serverSession.status;

                currentFocusDurationMs = serverFocusMs;
                currentSessionId = serverSession.sessionID;

                const startTimestamp = new Date(`${serverSession.date}T${serverSession.start_time}Z`).getTime();
                const nowTs = Date.now();
                const wallClockElapsed = nowTs - startTimestamp;
                const trueElapsedMs = Math.max(0, wallClockElapsed - serverPausedMs);

                if (serverStatus === 'paused') {
                    state = 'paused';
                    elapsedMs = Math.min(trueElapsedMs, currentFocusDurationMs);
                    sessionEndTime = null;
                    if (animationFrameId) {
                        cancelAnimationFrame(animationFrameId);
                        animationFrameId = null;
                    }
                    hideWarning();
                    saveState();
                    updateUI(currentFocusDurationMs - elapsedMs);
                } else {
                    state = 'running';
                    elapsedMs = Math.min(trueElapsedMs, currentFocusDurationMs);
                    sessionEndTime = startTimestamp + currentFocusDurationMs + serverPausedMs;

                    if (localStorage.getItem('focusTimer_warned_reload') !== '1') {
                        showWarning('Recovered running session from server. Pause state and client ticks did not survive reload — synced from server.');
                        localStorage.setItem('focusTimer_warned_reload', '1');
                    } else {
                        hideWarning();
                    }
                    saveState();
                    resyncNow();
                    tick();
                }
            } else {
                if (state === 'running') {
                    let legitimatelyEnded = false;
                    if (currentSessionId) {
                        const sessionRes = await fetch(`/sessions/${currentSessionId}`, { credentials: 'include' });
                        if (sessionRes.status === 401) { window.location.href = '/login'; return; }
                        if (sessionRes.ok) {
                            const sessionData = await sessionRes.json();
                            if (sessionData.status === 'completed' || sessionData.status === 'stopped_early') {
                                legitimatelyEnded = true;
                            }
                        }
                    }

                    if (legitimatelyEnded) {
                        if (animationFrameId) {
                            cancelAnimationFrame(animationFrameId);
                            animationFrameId = null;
                        }
                        resetTimer();
                        showToast("This session was ended on another device");
                    } else {
                        state = 'paused';
                        if (animationFrameId) {
                            cancelAnimationFrame(animationFrameId);
                            animationFrameId = null;
                        }
                        saveState();
                        updateUI(currentFocusDurationMs - (sessionEndTime ? Math.max(0, sessionEndTime - Date.now()) : 0));
                    }
                }
            }
        }
    } catch (e) {
        console.error("Server sync failed:", e);
        showToast("can't reach server", true);
    }
}

function saveState() {
    localStorage.setItem('focusTimer_state', state);
    localStorage.setItem('focusTimer_elapsedMs', elapsedMs.toString());
    localStorage.setItem('focusTimer_focusDurationMs', currentFocusDurationMs.toString());
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
    localStorage.setItem('focusTimer_interruptionCount', interruptionCount.toString());
}

function updateIntrusionCountUI() {
    if (interruptionCount > 0) {
        intrusionCountDisplay.style.display = 'inline-block';
        intrusionCountDisplay.textContent = interruptionCount;
    } else {
        intrusionCountDisplay.style.display = 'none';
        intrusionCountDisplay.textContent = '0';
    }
}

function formatTime(ms) {
    const totalSeconds = Math.ceil(Math.max(0, ms) / 1000);
    const minutes = Math.floor(totalSeconds / 60);
    const seconds = totalSeconds % 60;
    return `${minutes.toString().padStart(2, '0')}:${seconds.toString().padStart(2, '0')}`;
}

function updateUI(remainingMs) {
    remainingMs = Math.max(0, remainingMs);
    const timeStr = formatTime(remainingMs);
    timeDisplay.textContent = timeStr;
    statusDisplay.textContent = state;

    if (state === 'running' || state === 'paused') {
        document.title = `${timeStr} - Focus Timer`;
    } else {
        document.title = "Resilient Focus Timer";
    }

    const progress = currentFocusDurationMs > 0
        ? (currentFocusDurationMs - remainingMs) / currentFocusDurationMs
        : 0;
    const offset = Math.max(0, Math.min(1, progress)) * CIRCUMFERENCE;
    progressCircle.style.strokeDashoffset = offset;

    if (state === 'paused') {
        progressCircle.classList.add('paused');
    } else {
        progressCircle.classList.remove('paused');
    }

    if (durationSelect) {
        if (state === 'idle' || state === 'completed') {
            durationSelect.disabled = false;
        } else {
            durationSelect.disabled = true;
        }
    }

    if (state === 'idle') {
        actionBtn.textContent = 'Start Timer';
        intrusionBtn.disabled = true;
        if (stopEarlyBtn) stopEarlyBtn.style.display = 'none';
    } else if (state === 'running') {
        actionBtn.textContent = 'Pause';
        intrusionBtn.disabled = false;
        if (stopEarlyBtn) stopEarlyBtn.style.display = 'inline-block';
    } else if (state === 'paused') {
        actionBtn.textContent = 'Resume';
        intrusionBtn.disabled = true;
        if (stopEarlyBtn) stopEarlyBtn.style.display = 'inline-block';
    } else if (state === 'completed') {
        actionBtn.textContent = 'Start New';
        intrusionBtn.disabled = true;
        if (stopEarlyBtn) stopEarlyBtn.style.display = 'none';
    }
}

function resyncNow() {
    if (state === 'running' && sessionEndTime) {
        const now = Date.now();
        let remainingMs = sessionEndTime - now;
        if (remainingMs <= 0) {
            remainingMs = 0;
            completeSession();
            return;
        }
        updateUI(remainingMs);
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
    const initialState = state;
    const sessionIdToResume = currentSessionId;
    const elapsedMsToResume = elapsedMs;
    const pausedSnapshotBeforeResume = parseInt(localStorage.getItem('focusTimer_serverPausedMs'), 10) || 0;

    if (initialState === 'idle' || initialState === 'completed') {
        currentFocusDurationMs = getSelectedDurationMs();
        const startTimeIso = new Date().toISOString();
        const focusDurationSecs = Math.round(currentFocusDurationMs / 1000);

        try {
            const res = await fetch('/sessions', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ start_time: startTimeIso, focus_duration: focusDurationSecs }),
                credentials: 'include'
            });
            if (res.status === 401) { window.location.href = '/login'; return; }
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
            localStorage.setItem('focusTimer_serverPausedMs', '0');
        } catch (e) {
            console.error("Failed to reach server:", e);
            showToast("can't reach server", true);
            return;
        }
    } else if (initialState === 'paused') {
        try {
            const res = await fetch(`/sessions/${sessionIdToResume}`, {
                method: 'PATCH',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    status: 'running',
                    paused_ms: pausedSnapshotBeforeResume,
                    last_pause_start_iso: null
                }),
                credentials: 'include'
            });
            if (res.status === 401) { window.location.href = '/login'; return; }
            if (!res.ok) {
                console.error("Error resuming session");
                return;
            }
        } catch (e) {
            console.error("Failed to reach server:", e);
            showToast("can't reach server", true);
            return;
        }
    }

    state = 'running';
    sessionEndTime = Date.now() + currentFocusDurationMs - (initialState === 'paused' ? elapsedMsToResume : 0);
    hideWarning();
    localStorage.removeItem('focusTimer_warned_reload');
    saveState();
    updateUI(currentFocusDurationMs - (initialState === 'paused' ? elapsedMsToResume : 0));
    tick();
}

async function pauseTimer() {
    const sessionIdToPause = currentSessionId;
    const endTimeToPause = sessionEndTime;

    const nowTs = Date.now();
    state = 'paused';
    elapsedMs = currentFocusDurationMs - Math.max(0, (endTimeToPause || (nowTs + currentFocusDurationMs)) - nowTs);
    if (animationFrameId) {
        cancelAnimationFrame(animationFrameId);
        animationFrameId = null;
    }

    const lastPauseIso = new Date(nowTs).toISOString();
    const priorPaused = parseInt(localStorage.getItem('focusTimer_serverPausedMs'), 10) || 0;
    const justPausedForMs = endTimeToPause ? Math.max(0, nowTs - (endTimeToPause + elapsedMs - currentFocusDurationMs)) : 0;
    const accumulatedPausedMs = priorPaused + (justPausedForMs > 0 ? justPausedForMs : 0);
    localStorage.setItem('focusTimer_serverPausedMs', accumulatedPausedMs.toString());

    saveState();
    updateUI(currentFocusDurationMs - elapsedMs);

    try {
        const res = await fetch(`/sessions/${sessionIdToPause}`, {
            method: 'PATCH',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                status: 'paused',
                paused_ms: accumulatedPausedMs,
                last_pause_start_iso: lastPauseIso
            }),
            credentials: 'include'
        });
        if (res.status === 401) { window.location.href = '/login'; return; }
        if (res.ok) {
            const updated = await res.json();
            if (typeof updated.paused_ms === 'number') {
                localStorage.setItem('focusTimer_serverPausedMs', updated.paused_ms.toString());
            }
        }
    } catch (e) {
        console.error("Failed to pause session on server:", e);
        showToast("can't reach server", true);
    }
}

async function completeSession() {
    if (state === 'completed' || patchInFlight) return;

    const sessionIdToComplete = currentSessionId;
    const endTimeToRecord = new Date(sessionEndTime || Date.now());
    const durationSecs = Math.round(currentFocusDurationMs / 1000);
    const pausedForServer = parseInt(localStorage.getItem('focusTimer_serverPausedMs'), 10) || 0;

    patchInFlight = true;
    state = 'completed';
    if (animationFrameId) {
        cancelAnimationFrame(animationFrameId);
        animationFrameId = null;
    }
    saveState();

    try {
        await notificationSound.play();
    } catch (e) {
        console.log('Audio play failed', e);
    }

    if ("Notification" in window && Notification.permission === "granted") {
        try {
            new Notification("Focus session complete!");
        } catch (e) {
            console.error("Desktop notification failed", e);
            showFallbackBanner();
        }
    } else {
        showFallbackBanner();
    }

    updateUI(0);

    const endTimeIso = endTimeToRecord.toISOString().split('T')[1].split('.')[0];

    try {
        const res = await fetch(`/sessions/${sessionIdToComplete}`, {
            method: 'PATCH',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                status: 'completed',
                end_time: endTimeIso,
                duration: durationSecs,
                paused_ms: pausedForServer,
                last_pause_start_iso: null
            }),
            credentials: 'include'
        });
        if (res.status === 401) { window.location.href = '/login'; return; }
    } catch (e) {
        console.error("Failed to complete session on server:", e);
        showToast("can't reach server", true);
    } finally {
        patchInFlight = false;
        localStorage.removeItem('focusTimer_serverPausedMs');
    }
}

function resetTimer() {
    state = 'idle';
    elapsedMs = 0;
    sessionEndTime = null;
    currentSessionId = null;
    interruptionCount = 0;
    currentFocusDurationMs = getSelectedDurationMs();
    localStorage.removeItem('focusTimer_serverPausedMs');
    localStorage.removeItem('focusTimer_warned_reload');
    updateIntrusionCountUI();
    saveState();
    updateUI(currentFocusDurationMs);
}

let audioUnlocked = false;

actionBtn.addEventListener('click', async () => {
    if (!audioUnlocked) {
        notificationSound.play().catch(() => {});
        notificationSound.pause();
        notificationSound.currentTime = 0;
        audioUnlocked = true;
    }

    if ("Notification" in window && Notification.permission === "default") {
        Notification.requestPermission().catch(e => console.error("Notification permission request failed", e));
    }

    actionBtn.disabled = true;
    try {
        if (state === 'idle' || state === 'completed') {
            if (state === 'completed') resetTimer();
            await startTimer();
        } else if (state === 'running') {
            await pauseTimer();
        } else if (state === 'paused') {
            await startTimer();
        }
    } finally {
        actionBtn.disabled = false;
    }
});

function showToast(message, isError = false) {
    let container = document.querySelector('.toast-container');
    if (!container) {
        container = document.createElement('div');
        container.className = 'toast-container';
        document.body.appendChild(container);
    }
    const toast = document.createElement('div');
    toast.className = 'toast' + (isError ? ' error' : '');
    toast.textContent = message;
    container.appendChild(toast);

    setTimeout(() => {
        toast.style.opacity = '0';
        setTimeout(() => toast.remove(), 300);
    }, 2500);
}

if (stopEarlyBtn) {
    stopEarlyBtn.addEventListener('click', async () => {
        if (!currentSessionId || (state !== 'running' && state !== 'paused')) return;

        const sessionIdToStop = currentSessionId;
        const elapsedMsToStop = (state === 'running' && sessionEndTime)
            ? currentFocusDurationMs - Math.max(0, sessionEndTime - Date.now())
            : elapsedMs;
        const pausedForServer = parseInt(localStorage.getItem('focusTimer_serverPausedMs'), 10) || 0;

        stopEarlyBtn.disabled = true;
        try {
            const trueEndTime = new Date();
            const endTimeIso = trueEndTime.toISOString().split('T')[1].split('.')[0];
            const durationSecs = Math.round(elapsedMsToStop / 1000);

            const res = await fetch(`/sessions/${sessionIdToStop}`, {
                method: 'PATCH',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    status: 'stopped_early',
                    end_time: endTimeIso,
                    duration: durationSecs,
                    paused_ms: pausedForServer,
                    last_pause_start_iso: null
                }),
                credentials: 'include'
            });

            if (res.status === 401) { window.location.href = '/login'; return; }
            if (res.ok) {
                if (animationFrameId) {
                    cancelAnimationFrame(animationFrameId);
                    animationFrameId = null;
                }
                resetTimer();
            } else {
                console.error("Failed to stop early:", await res.json());
                showToast("Failed to stop session early", true);
            }
        } catch (e) {
            console.error("Failed to reach server to stop early:", e);
            showToast("can't reach server", true);
        } finally {
            stopEarlyBtn.disabled = false;
        }
    });
}

let intrusionInFlight = false;
intrusionBtn.addEventListener('click', async () => {
    if (state !== 'running' || !currentSessionId || intrusionInFlight) return;

    const sessionIdToInterrupt = currentSessionId;

    intrusionInFlight = true;
    setTimeout(() => { intrusionInFlight = false; }, 500);

    const timestampIso = new Date().toISOString();
    try {
        const res = await fetch(`/sessions/${sessionIdToInterrupt}/interruptions`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ timestamp: timestampIso }),
            credentials: 'include'
        });
        if (res.status === 401) { window.location.href = '/login'; return; }
        if (!res.ok) {
            console.error("Failed to log intrusion:", await res.json());
            showToast("Failed to log interruption", true);
        } else {
            interruptionCount++;
            updateIntrusionCountUI();
            saveState();
            showToast("Interruption logged");
        }
    } catch (e) {
        console.error("Failed to reach server for intrusion logging:", e);
        showToast("can't reach server", true);
    }
});

document.addEventListener('visibilitychange', () => {
    if (document.visibilityState === 'visible') {
        if (state === 'running') {
            resyncNow();
            tick();
        } else if (state === 'paused') {
            updateUI(currentFocusDurationMs - elapsedMs);
        }
    }
});

setInterval(() => {
    if (state === 'running') {
        if (document.visibilityState === 'hidden') {
            const now = Date.now();
            let remainingMs = sessionEndTime ? sessionEndTime - now : 0;
            if (remainingMs <= 0) {
                remainingMs = 0;
                completeSession();
            } else {
                const timeStr = formatTime(remainingMs);
                document.title = `${timeStr} - Focus Timer`;
                timeDisplay.textContent = timeStr;
            }
        } else {
            resyncNow();
        }
    }
}, 1000);

loadState();

function showFallbackBanner() {
    let banner = document.getElementById('completionBanner');
    if (!banner) {
        banner = document.createElement('div');
        banner.id = 'completionBanner';
        banner.className = 'completion-banner';
        banner.innerHTML = `
            <span>Focus session complete!</span>
            <button onclick="this.parentElement.remove()">Dismiss</button>
        `;
        document.body.appendChild(banner);
    }
}
