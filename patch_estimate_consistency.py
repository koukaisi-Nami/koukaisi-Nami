from pathlib import Path
p=Path('app.py'); s=p.read_text()

# Formal artifacts must use the exact same single-estimate prompt and preserve the current instruction.
old='estimate_text=ai(single_estimate_prompt(clean)+"\\n\\n【募集図面の読取結果】\\n"+media_summary,uid,cid)'
new='estimate_text=ai(single_estimate_prompt(clean)+"\\n\\n【最優先：今回のユーザー指示】\\n"+clean+"\\nこの指示（入居日、仲介手数料の金額・無料・半額・月数等）を必ず計算に反映する。\\n\\n【募集図面の読取結果】\\n"+media_summary,uid,cid)'
if old in s:s=s.replace(old,new,1)
elif '【最優先：今回のユーザー指示】' not in s:raise SystemExit('estimate generation target missing')

# LINE cannot reliably send arbitrary PDF file messages. Image is native; PDF is an HTTPS link.
old='''def reply_estimate_artifact(tok,key,wants_image,wants_pdf):
    base=os.getenv("PUBLIC_BASE_URL","https://koukaisi-nami.onrender.com").rstrip('/')
    messages=[]
    if wants_image:
        u=f"{base}/estimate-image/{key}"
        messages.append({"type":"image","originalContentUrl":u,"previewImageUrl":u})
    if wants_pdf:
        u=f"{base}/estimate-pdf/{key}"
        messages.append({"type":"text","text":f"見積もり概算書PDFはこちら\\n{u}"})
    if not messages:return False
    try:
        r=requests.post("https://api.line.me/v2/bot/message/reply",headers={"Authorization":f"Bearer {TOKEN}","Content-Type":"application/json"},json={"replyToken":tok,"messages":messages[:5]},timeout=30)
        if not r.ok: print("LINE estimate doc",r.status_code,r.text[:1000],flush=True)
        return r.ok
    except Exception as x: print("reply_estimate_doc",repr(x),flush=True); return False'''
new='''def reply_estimate_artifact(tok,key,wants_image,wants_pdf):
    base=os.getenv("PUBLIC_BASE_URL","https://koukaisi-nami.onrender.com").rstrip('/')
    messages=[]
    # Always show the finished estimate inside LINE when an artifact is requested.
    # This makes PDF requests useful without forcing the user to open a browser first.
    if wants_image or wants_pdf:
        u=f"{base}/estimate-image/{key}"
        messages.append({"type":"image","originalContentUrl":u,"previewImageUrl":u})
    if wants_pdf:
        u=f"{base}/estimate-pdf/{key}"
        messages.append({"type":"text","text":f"見積もり概算書PDFはこちら\\n{u}"})
    if not messages:return False
    try:
        sender=globals().get("HTTP",requests)
        r=sender.post("https://api.line.me/v2/bot/message/reply",headers={"Authorization":f"Bearer {TOKEN}","Content-Type":"application/json"},json={"replyToken":tok,"messages":messages[:5]},timeout=20)
        if not r.ok: print("LINE estimate doc",r.status_code,r.text[:1000],flush=True)
        return r.ok
    except Exception as x: print("reply_estimate_doc",repr(x),flush=True); return False'''
if old in s:s=s.replace(old,new,1)
elif 'Always show the finished estimate inside LINE' not in s:raise SystemExit('artifact reply target missing')

p.write_text(s)
