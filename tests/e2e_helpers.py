def e2e_login(page):
    """Log in through the HTML form if the browser was redirected to /login."""
    if '/login' not in page.url:
        return
    page.locator('#username').fill('testuser')
    page.locator('#password').fill('testpass')
    with page.expect_response(lambda r: '/auth/login' in r.url, timeout=15000):
        page.locator('#loginForm button[type="submit"]').click()
    try:
        page.wait_for_url(lambda u: '/login' not in u, timeout=15000)
    except Exception:
        pass
