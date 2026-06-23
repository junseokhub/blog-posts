import sys

date, src, dst = sys.argv[1], sys.argv[2], sys.argv[3]
content = open(src, encoding='utf-8').read()

# date 주입
if content.startswith('---\n'):
    fm_end = content.find('\n---\n', 4)
    fm = content[4:fm_end] if fm_end != -1 else ''
    if 'date:' not in fm:
        content = content.replace('---\n', f'---\ndate: {date}\n', 1)
else:
    content = f'---\ndate: {date}\n---\n\n{content}'

open(dst, 'w', encoding='utf-8').write(content)
