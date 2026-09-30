def e2e_login(page):
    """Log in through the HTML/React form if it is visible."""
    try:
        page.wait_for_selector('#username', timeout=2000)
    except Exception:
        return
    page.locator('#username').fill('testuser')
    page.locator('#password').fill('testpass')
    with page.expect_response(lambda r: '/auth/login' in r.url, timeout=15000):
        page.locator('form button[type="submit"]').click()
    try:
        page.wait_for_selector('#username', state='hidden', timeout=15000)
    except Exception:
        pass
