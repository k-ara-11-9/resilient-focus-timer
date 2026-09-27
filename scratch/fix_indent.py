import os

tests_dir = 'tests'
for filename in os.listdir(tests_dir):
    if filename.startswith('test_e2e') and filename.endswith('.py'):
        filepath = os.path.join(tests_dir, filename)
        with open(filepath, 'r') as f:
            content = f.read()
        
        # We need to fix the indentation.
        # Find "if '/login' in page.url:" and indent the following 4 lines by 4 more spaces.
        lines = content.split('\n')
        new_lines = []
        in_if = False
        lines_to_indent = 0
        for line in lines:
            if "if '/login' in page.url:" in line:
                new_lines.append(line)
                lines_to_indent = 4
                continue
            
            if lines_to_indent > 0:
                # Add 4 spaces of indentation
                new_lines.append('    ' + line)
                lines_to_indent -= 1
            else:
                new_lines.append(line)
        
        with open(filepath, 'w') as f:
            f.write('\n'.join(new_lines))
        print(f'Fixed {filename}')
