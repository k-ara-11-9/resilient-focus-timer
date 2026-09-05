document.addEventListener('DOMContentLoaded', async () => {
    const historyList = document.getElementById('historyList');
    
    try {
        const res = await fetch('/sessions');
        if (res.ok) {
            const sessions = await res.json();
            
            if (sessions.length === 0) {
                historyList.innerHTML = '<div class="empty-state">No completed sessions yet. Get focused!</div>';
                document.querySelector('.more-sessions').style.display = 'none';
                return;
            }
            
            sessions.forEach(session => {
                // SQLite dates are YYYY-MM-DD. Parsing directly with new Date('YYYY-MM-DD') 
                // in JS gives UTC, which aligns correctly with getUTCDate().
                let dateStr = "Unknown";
                if (session.date) {
                    const now = new Date();
                    const pad = n => n.toString().padStart(2, '0');
                    const todayStr = `${now.getFullYear()}-${pad(now.getMonth()+1)}-${pad(now.getDate())}`;
                    
                    const yesterday = new Date(now);
                    yesterday.setDate(yesterday.getDate() - 1);
                    const yesterdayStr = `${yesterday.getFullYear()}-${pad(yesterday.getMonth()+1)}-${pad(yesterday.getDate())}`;
                    
                    if (session.date === todayStr) {
                        dateStr = "Today";
                    } else if (session.date === yesterdayStr) {
                        dateStr = "Yesterday";
                    } else {
                        const dateObj = new Date(session.date);
                        const monthNames = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
                        const month = monthNames[dateObj.getUTCMonth()];
                        const day = dateObj.getUTCDate();
                        dateStr = `${month} ${day}`;
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
        } else {
            historyList.innerHTML = '<div class="empty-state">Error loading history.</div>';
        }
    } catch (e) {
        console.error("Failed to load history:", e);
        historyList.innerHTML = '<div class="empty-state">Failed to reach server.</div>';
    }
});
