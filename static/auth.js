function logout() {
    Object.keys(localStorage).forEach(key => {
        if (key.startsWith('focusTimer_')) {
            localStorage.removeItem(key);
        }
    });
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
