document.addEventListener('DOMContentLoaded', async () => {
    const historyList = document.getElementById('historyList');
    
    try {
        const res = await fetch('/sessions');
        if (res.ok) {
            const sessions = await res.json();
            
            if (sessions.length === 0) {
                historyList.innerHTML = '<div class="empty-state">No completed sessions yet. Get focused!</div>';
                return;
            }

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
                    // Combine date and time as UTC to get local equivalent
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
                        // Fallback
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
                document.querySelector('.history-main').appendChild(moreDiv);
            }
        } else {
            historyList.innerHTML = '<div class="empty-state">Error loading history.</div>';
        }
    } catch (e) {
        console.error("Failed to load history:", e);
        historyList.innerHTML = '<div class="empty-state">Failed to reach server.</div>';
    }
});
