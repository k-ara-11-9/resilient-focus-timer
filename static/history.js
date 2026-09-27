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
                    let dateDisplay = "Unknown";
                    let timeDisplay = "";
                    const durationSecs = session.duration || 1500; // stored in seconds
                    const duration = Math.round(durationSecs / 60); // convert to minutes for display
                    let startTimestamp = 0;
                    
                    if (session.date && session.start_time) {
                        const sessionDate = new Date(`${session.date}T${session.start_time}Z`);
                        if (!isNaN(sessionDate.getTime())) {
                            startTimestamp = sessionDate.getTime();
                            const localDateStr = `${sessionDate.getFullYear()}-${pad(sessionDate.getMonth()+1)}-${pad(sessionDate.getDate())}`;
                            
                            const formatTime = (d) => {
                                let h = d.getHours();
                                const m = pad(d.getMinutes());
                                const ampm = h >= 12 ? 'PM' : 'AM';
                                h = h % 12;
                                h = h ? h : 12; 
                                return `${h}:${m} ${ampm}`;
                            };

                            const startTimeStr = formatTime(sessionDate);
                            const endDate = new Date(sessionDate.getTime() + durationSecs * 1000);
                            const endTimeStr = formatTime(endDate);
                            timeDisplay = `${startTimeStr} - ${endTimeStr}`;
                            
                            if (localDateStr === todayStr) {
                                dateDisplay = `Today`;
                            } else if (localDateStr === yesterdayStr) {
                                dateDisplay = `Yesterday`;
                            } else {
                                dateDisplay = `${monthNames[sessionDate.getMonth()]} ${sessionDate.getDate()}`;
                            }
                        } else {
                            dateDisplay = session.date;
                            timeDisplay = session.start_time;
                        }
                    }
                    
                    const interrupts = session.interruption_count;
                    const interruptText = interrupts === 1 ? '1 interruption' : `${interrupts} interruptions`;
                    
                    const card = document.createElement('div');
                    card.className = 'history-card';
                    card.style.cursor = 'pointer';
                    card.innerHTML = `
                        <div class="history-date">${dateDisplay} <span style="font-size: 0.8em; color: #888; margin-left: 8px;">${timeDisplay}</span></div>
                        <div class="history-details">${duration} min - ${interruptText}</div>
                        <div class="timeline-container" style="display: none; margin-top: 12px; padding-top: 12px; border-top: 1px solid #333;">
                        </div>
                    `;
                    
                    let expanded = false;
                    let loaded = false;
                    card.addEventListener('click', async () => {
                        const container = card.querySelector('.timeline-container');
                        if (expanded) {
                            container.style.display = 'none';
                            expanded = false;
                            return;
                        }
                        
                        container.style.display = 'block';
                        expanded = true;
                        
                        if (loaded) return;
                        
                        container.innerHTML = '<div style="font-size: 0.85em; color: #888;">Loading timeline...</div>';
                        try {
                            const iRes = await fetch(`/sessions/${session.sessionID}/interruptions`, { credentials: 'include' });
                            if (iRes.status === 401) { window.location.href = '/login'; return; }
                            if (iRes.ok) {
                                const intData = await iRes.json();
                                loaded = true;
                                
                                let timelineHTML = '<div style="position: relative; height: 12px; background: #333; border-radius: 6px; margin: 12px 0;">';
                                
                                if (intData.length === 0) {
                                    container.innerHTML = timelineHTML + '</div><div style="font-size: 0.8em; color: #888; text-align: center;">no interruptions</div>';
                                    return;
                                }
                                
                                intData.forEach(inv => {
                                    const invTime = inv.timestamp.includes('T') 
                                        ? new Date(inv.timestamp).getTime() 
                                        : new Date(`${session.date}T${inv.timestamp}Z`).getTime();
                                    let percent = 0;
                                    if (startTimestamp > 0 && durationSecs > 0) {
                                        percent = ((invTime - startTimestamp) / (durationSecs * 1000)) * 100;
                                        if (percent < 0) {
                                            percent = (((invTime + 24*3600*1000) - startTimestamp) / (durationSecs * 1000)) * 100;
                                        }
                                    }
                                    if (percent < 0) percent = 0;
                                    if (percent > 100) percent = 100;
                                    
                                    timelineHTML += `<div style="position: absolute; left: ${percent}%; top: 50%; transform: translate(-50%, -50%); width: 4px; height: 16px; background: #e76f51; border-radius: 2px; box-shadow: 0 0 4px rgba(0,0,0,0.5);"></div>`;
                                });
                                
                                timelineHTML += '</div>';
                                container.innerHTML = timelineHTML;
                            } else {
                                container.innerHTML = '<div style="font-size: 0.85em; color: #e76f51;">Error loading interruptions</div>';
                            }
                        } catch(e) {
                            container.innerHTML = '<div style="font-size: 0.85em; color: #e76f51;">Network error</div>';
                        }
                    });
                    
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
            if (!Array.isArray(data) || data.length === 0 || data.every(d => d.count === 0)) {
                heatDiv.innerHTML = '<div class="empty-state">no data yet</div>';
            } else {
                let html = '<ul style="list-style-type: none; padding: 0; margin: 0;">';
                data.forEach(d => {
                    const hourLabel = `${d.hour % 12 || 12} ${d.hour < 12 ? 'AM' : 'PM'}`;
                    html += `<li style="display: flex; justify-content: space-between; padding: 4px 0; border-bottom: 1px solid #333;"><span>${hourLabel}</span> <span>${d.count} sessions</span></li>`;
                });
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
