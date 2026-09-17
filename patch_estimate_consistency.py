from pathlib import Path
p=Path('app.py'); s=p.read_text()

# Formal artifacts must use the exact same single-estimate prompt and preserve the current instruction.
old='estimate_text=ai(single_estimate_prompt(clean)+"\\n\\n【募集図面の読取結果】\\n"+media_summary,uid,cid)'
new='estimate_text=ai(single_estimate_prompt(clean)+"\\n\\n【最優先：今回のユーザー指示】\\n"+clean+"\\nこの指示（入居日、仲介手数料の金額・無料・半額・月数等）を必ず計算に反映する。\\n\\n【募集図面の読取結果】\\n"+media_summary,uid,cid)'
if old in s:s=s.replace(old,new,1)
elif '【最優先：今回のユーザー指示】' not in s:raise SystemExit('estimate generation target missing')

# Current app uses marker-based artifact delivery. For PDF requests, show the rendered
# estimate image natively in LINE first, then provide the temporary PDF URL.
old='''def reply_estimate_artifact(tok,base,key,marker):
    image_url=f"{base}/estimate-file/{key}.png"
    pdf_url=f"{base}/estimate-file/{key}.pdf"
    msgs=[]
    if marker in ("__ESTIMATE_IMAGE__","__ESTIMATE_BOTH__"):
        msgs.append({"type":"image","originalContentUrl":image_url,"previewImageUrl":image_url})
    if marker in ("__ESTIMATE_PDF__","__ESTIMATE_BOTH__"):
        # LINE Messaging API has no outbound file-message type; deliver the temporary PDF URL as text.
        msgs.append({"type":"text","text":"見積もり概算書PDFはこちら\\n"+pdf_url})
    try:
        r=requests.post("https://api.line.me/v2/bot/message/reply",headers={"Authorization":f"Bearer {TOKEN}","Content-Type":"application/json"},json={"replyToken":tok,"messages":msgs[:5]},timeout=30)
        if not r.ok: print("LINE estimate artifact",r.status_code,r.text[:1000],flush=True)
        return r.ok
    except Exception as x: print("reply_estimate_artifact",repr(x),flush=True); return False'''
new='''def reply_estimate_artifact(tok,base,key,marker):
    image_url=f"{base}/estimate-file/{key}.png"
    pdf_url=f"{base}/estimate-file/{key}.pdf"
    msgs=[]
    # Any explicit artifact request gets the finished estimate image directly in LINE.
    if marker in ("__ESTIMATE_IMAGE__","__ESTIMATE_PDF__","__ESTIMATE_BOTH__"):
        msgs.append({"type":"image","originalContentUrl":image_url,"previewImageUrl":image_url})
    if marker in ("__ESTIMATE_PDF__","__ESTIMATE_BOTH__"):
        # LINE Messaging API has no outbound arbitrary-PDF file message type.
        msgs.append({"type":"text","text":"見積もり概算書PDFはこちら\\n"+pdf_url})
    try:
        sender=globals().get("HTTP",requests)
        r=sender.post("https://api.line.me/v2/bot/message/reply",headers={"Authorization":f"Bearer {TOKEN}","Content-Type":"application/json"},json={"replyToken":tok,"messages":msgs[:5]},timeout=20)
        if not r.ok: print("LINE estimate artifact",r.status_code,r.text[:1000],flush=True)
        return r.ok
    except Exception as x: print("reply_estimate_artifact",repr(x),flush=True); return False'''
if old in s:s=s.replace(old,new,1)
elif 'Any explicit artifact request gets the finished estimate image directly in LINE.' not in s:raise SystemExit('artifact reply target missing')

p.write_text(s)
