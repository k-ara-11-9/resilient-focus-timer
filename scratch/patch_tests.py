import os

tests_dir = 'tests'
for filename in os.listdir(tests_dir):
    if filename.startswith('test_e2e') and filename.endswith('.py'):
        filepath = os.path.join(tests_dir, filename)
        with open(filepath, 'r') as f:
            content = f.read()
        
        # Replace focus_timer.db with temp_db for sqlite3.connect
        content = content.replace("sqlite3.connect('focus_timer.db')", "sqlite3.connect(temp_db)")
        content = content.replace("sqlite3.connect(DB_PATH)", "sqlite3.connect(temp_db)")
        
        # Add login block right after page.goto
        if 'page.goto(' in content and "page.locator('#username')" not in content:
            login_block = """
            time.sleep(1)
            if '/login' in page.url:
                page.locator('#username').fill('testuser')
                page.locator('#password').fill('testpass')
                page.locator('button[type="submit"]').click()
                time.sleep(1)
            """
            
            lines = content.split('\n')
            new_lines = []
            for line in lines:
                new_lines.append(line)
                if 'page.goto(' in line:
                    indent = len(line) - len(line.lstrip())
                    indented_login = '\n'.join([' ' * indent + l.strip() for l in login_block.strip().split('\n')])
                    new_lines.append(indented_login)
            content = '\n'.join(new_lines)

        with open(filepath, 'w') as f:
            f.write(content)
        print(f'Updated {filename}')
