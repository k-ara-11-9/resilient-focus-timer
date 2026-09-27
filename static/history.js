document.addEventListener('DOMContentLoaded', async () => {
    const historyList = document.getElementById('historyList');
    
    try {
        const res = await fetch('/sessions', { credentials: 'include' });
        if (res.status === 401) {
            window.location.href = '/login';
            return;
        }
        if (res.ok) {
            const sessions = await res.json();
            
            if (sessions.length === 0) {
                historyList.innerHTML = '<div class="empty-state">No completed sessions yet. Get focused!</div>';
            } else {
                historyList.innerHTML = '';
                
                const monthNames = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
                const now = new Date();
                const pad = n => n.toString().padStart(2, '0');
                const todayStr = `${now.getFullYear()}-${pad(now.getMonth()+1)}-${pad(now.getDate())}`;
                
                const yesterday = new Date(now);
                yesterday.setDate(yesterday.getDate() - 1);
                const yesterdayStr = `${yesterday.getFullYear()}-${pad(yesterday.getMonth()+1)}-${pad(yesterday.getDate())}`;

                sessions.forEach(session => {
                    let dateStr = "Unknown";
                    if (session.date && session.start_time) {
                        const sessionDate = new Date(`${session.date}T${session.start_time}Z`);
                        if (!isNaN(sessionDate.getTime())) {
                            const localDateStr = `${sessionDate.getFullYear()}-${pad(sessionDate.getMonth()+1)}-${pad(sessionDate.getDate())}`;
                            
                            let hours = sessionDate.getHours();
                            const minutes = pad(sessionDate.getMinutes());
                            const ampm = hours >= 12 ? 'PM' : 'AM';
                            hours = hours % 12;
                            hours = hours ? hours : 12; 
                            const timeStr = `${hours}:${minutes} ${ampm}`;

                            if (localDateStr === todayStr) {
                                dateStr = `Today, ${timeStr}`;
                            } else if (localDateStr === yesterdayStr) {
                                dateStr = `Yesterday, ${timeStr}`;
                            } else {
                                dateStr = `${monthNames[sessionDate.getMonth()]} ${sessionDate.getDate()}, ${timeStr}`;
                            }
                        } else {
                            dateStr = session.date;
                        }
                    }
                    
                    const duration = session.duration || 25;
                    const interrupts = session.interruption_count;
                    const interruptText = interrupts === 1 ? '1 interruption' : `${interrupts} interruptions`;
                    
                    const card = document.createElement('div');
                    card.className = 'history-card';
                    card.innerHTML = `
                        <div class="history-date">${dateStr}</div>
                        <div class="history-details">${duration} min - ${interruptText}</div>
                    `;
                    
                    historyList.appendChild(card);
                });
                
                if (sessions.length > 5) {
                    const moreDiv = document.createElement('div');
                    moreDiv.className = 'more-sessions';
                    moreDiv.textContent = 'more sessions below';
                    document.querySelector('.history-main').insertBefore(moreDiv, document.getElementById('dailyAnalytics').previousElementSibling);
                }
            }
        } else {
            historyList.innerHTML = '<div class="empty-state">Error loading history.</div>';
        }
    } catch (e) {
        console.error("Failed to load history:", e);
        historyList.innerHTML = '<div class="empty-state">can\'t reach server</div>';
    }

    // Load Daily Analytics
    try {
        const dailyRes = await fetch('/analytics/daily', { credentials: 'include' });
        const dailyDiv = document.getElementById('dailyAnalytics');
        if (dailyRes.status === 401) { window.location.href = '/login'; return; }
        if (dailyRes.ok) {
            const data = await dailyRes.json();
            if (data.length === 0 || data.every(d => d.focus_minutes === 0 && d.interruptions === 0)) {
                dailyDiv.innerHTML = '<div class="empty-state">no data yet</div>';
            } else {
                let html = '<table style="width: 100%; border-collapse: collapse;">';
                html += '<tr><th style="text-align:left; border-bottom:1px solid #333; padding-bottom:4px;">Date</th><th style="text-align:right; border-bottom:1px solid #333; padding-bottom:4px;">Minutes</th><th style="text-align:right; border-bottom:1px solid #333; padding-bottom:4px;">Interruptions</th></tr>';
                data.forEach(row => {
                    html += `<tr><td style="padding: 4px 0;">${row.date}</td><td style="text-align:right;">${row.focus_minutes}</td><td style="text-align:right;">${row.interruptions}</td></tr>`;
                });
                html += '</table>';
                dailyDiv.innerHTML = html;
            }
        } else {
            dailyDiv.innerHTML = `<div class="empty-state">Error: ${dailyRes.statusText}</div>`;
        }
    } catch (e) {
        document.getElementById('dailyAnalytics').innerHTML = '<div class="empty-state">can\'t reach server</div>';
    }

    // Load Heatmap Analytics
    try {
        const heatRes = await fetch('/analytics/heatmap', { credentials: 'include' });
        const heatDiv = document.getElementById('heatmapAnalytics');
        if (heatRes.status === 401) { window.location.href = '/login'; return; }
        if (heatRes.status === 404) {
            heatDiv.innerHTML = '<div class="empty-state">Endpoint not found (404)</div>';
        } else if (heatRes.ok) {
            const data = await heatRes.json();
            if (Object.keys(data).length === 0 || Object.values(data).every(v => v === 0)) {
                heatDiv.innerHTML = '<div class="empty-state">no data yet</div>';
            } else {
                let html = '<ul style="list-style-type: none; padding: 0; margin: 0;">';
                for (const [date, minutes] of Object.entries(data)) {
                    html += `<li style="display: flex; justify-content: space-between; padding: 4px 0; border-bottom: 1px solid #333;"><span>${date}</span> <span>${minutes} mins</span></li>`;
                }
                html += '</ul>';
                heatDiv.innerHTML = html;
            }
        } else {
            heatDiv.innerHTML = `<div class="empty-state">Error: ${heatRes.statusText}</div>`;
        }
    } catch (e) {
        document.getElementById('heatmapAnalytics').innerHTML = '<div class="empty-state">can\'t reach server</div>';
    }
});

function logout() {
    fetch('/auth/logout', { method: 'POST', credentials: 'include' })
        .then(res => {
            if (res.ok) {
                window.location.href = '/login';
            } else {
                alert("Logout failed");
            }
        })
        .catch(e => alert("can't reach server"));
}
