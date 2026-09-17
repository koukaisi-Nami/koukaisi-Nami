"""One-shot source patch: make batch estimates reply as one LINE message per property."""
from pathlib import Path
p=Path('app.py')
s=p.read_text()
old='''def reply(tok,text):
    chunks=[text[i:i+4900] for i in range(0,len(text),4900)][:5]
    try:
        r=requests.post("https://api.line.me/v2/bot/message/reply",
          headers={"Authorization":f"Bearer {TOKEN}","Content-Type":"application/json"},
          json={"replyToken":tok,"messages":[{"type":"text","text":x} for x in chunks]},timeout=30)'''
new='''def reply(tok,text):
    # Batch estimates use a stable delimiter so each property becomes its own LINE bubble.
    if "\\n<<<PROPERTY_BREAK>>>\\n" in text:
        chunks=[x.strip() for x in text.split("\\n<<<PROPERTY_BREAK>>>\\n") if x.strip()][:5]
    else:
        chunks=[text[i:i+4900] for i in range(0,len(text),4900)][:5]
    try:
        r=requests.post("https://api.line.me/v2/bot/message/reply",
          headers={"Authorization":f"Bearer {TOKEN}","Content-Type":"application/json"},
          json={"replyToken":tok,"messages":[{"type":"text","text":x[:4900]} for x in chunks]},timeout=30)'''
if old not in s: raise SystemExit('reply target not found')
s=s.replace(old,new,1)
p.write_text(s)
