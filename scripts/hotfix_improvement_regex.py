from pathlib import Path

p = Path('app.py')
s = p.read_text(encoding='utf-8')
old = 'r"(?:反映|マージ|デプロイ).{0,16}(?:していい|してよい|して)",'
new = 'r"(?:反映|マージ|デプロイ).{0,16}(?:していい|してよい|して))",'
if old not in s:
    raise SystemExit('target improvement regex not found')
s = s.replace(old, new, 1)
p.write_text(s, encoding='utf-8')
print('fixed improvement_intent regex')
