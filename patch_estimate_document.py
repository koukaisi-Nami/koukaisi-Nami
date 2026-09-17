from pathlib import Path
p=Path('app.py'); s=p.read_text()

imp='from estimate_document import make_estimate_document, make_estimate_image'
if imp not in s:
    flask='from flask import Flask, request, abort, Response, render_template_string, send_file'
    if flask not in s: raise SystemExit('flask import target missing')
    s=s.replace(flask,flask+'\n'+imp,1)

# Explicit output only. Generic 見積/見積書 remains the normal text estimate.
s=s.replace('wants_image=kind=="estimate" and bool(re.search(r"(画像|イメージ|一枚|1枚|写真にして)",clean,re.I))','wants_image=kind=="estimate" and bool(re.search(r"(画像|イメージ|jpg|jpeg|png|一枚|1枚|写真にして)",clean,re.I))',1)
s=s.replace('wants_pdf=bool(re.search(r"(PDF|pdf|書類|発行)",clean))','wants_pdf=kind=="estimate" and bool(re.search(r"(PDF|pdf)",clean,re.I)) or (kind!="estimate" and bool(re.search(r"(PDF|pdf|書類|発行)",clean,re.I)))',1)

old='''    if kind=="estimate" and wants_image:\n        if not media_summary:return "見積もり画像を作る募集図面がないよ。図面の画像/PDFにリプライして『ナミ、見積もり画像作って』と送って。"\n        return ("__ESTIMATE_IMAGE__",media_summary)\n    if kind=="estimate":\n        if not media_summary:return "見積書を作る募集図面がないよ。図面にリプライして送って。"\n        return ("__PDF__","見積り書",{"title":"見積もり概算書","description":media_summary,"notes":"本書は概算の見積もりです。詳細は別途ご案内いたします。"})'''
new='''    if kind=="estimate" and (wants_image or wants_pdf):\n        if not media_summary:return "見積書を作る募集図面がないよ。図面の画像/PDFにリプライして送って。"\n        estimate_text=ai(single_estimate_prompt(clean)+"\\n\\n【募集図面の読取結果】\\n"+media_summary,uid,cid)\n        marker="__ESTIMATE_BOTH__" if (wants_image and wants_pdf) else ("__ESTIMATE_IMAGE__" if wants_image else "__ESTIMATE_PDF__")\n        return (marker,estimate_text)'''
if old in s:
    s=s.replace(old,new,1)
elif '__ESTIMATE_PDF__' not in s:
    raise SystemExit('estimate artifact target missing')

anchor='''@app.get("/")\ndef health():return "航海士ナミ FINAL 部長モード OK",200'''
if 'def estimate_file_download(' not in s:
    insert='''ESTIMATE_CACHE={}\n\n@app.get("/estimate-file/<key>.<ext>")\ndef estimate_file_download(key,ext):\n    row=ESTIMATE_CACHE.get(key)\n    if not row:return "not found",404\n    created,text=row\n    if time.time()-created>600:\n        ESTIMATE_CACHE.pop(key,None); return "expired",404\n    if ext=="pdf": return send_file(make_estimate_document(text),mimetype="application/pdf",as_attachment=True,download_name="見積もり概算書.pdf")\n    if ext=="png": return send_file(make_estimate_image(text),mimetype="image/png")\n    return "not found",404\n\ndef reply_estimate_artifact(tok,base,key,marker):\n    image_url=f"{base}/estimate-file/{key}.png"\n    pdf_url=f"{base}/estimate-file/{key}.pdf"\n    msgs=[]\n    if marker in ("__ESTIMATE_IMAGE__","__ESTIMATE_BOTH__"):\n        msgs.append({"type":"image","originalContentUrl":image_url,"previewImageUrl":image_url})\n    if marker in ("__ESTIMATE_PDF__","__ESTIMATE_BOTH__"):\n        # LINE Messaging API has no outbound file-message type; deliver the temporary PDF URL as text.\n        msgs.append({"type":"text","text":"見積もり概算書PDFはこちら\\n"+pdf_url})\n    try:\n        r=requests.post("https://api.line.me/v2/bot/message/reply",headers={"Authorization":f"Bearer {TOKEN}","Content-Type":"application/json"},json={"replyToken":tok,"messages":msgs[:5]},timeout=30)\n        if not r.ok: print("LINE estimate artifact",r.status_code,r.text[:1000],flush=True)\n        return r.ok\n    except Exception as x: print("reply_estimate_artifact",repr(x),flush=True); return False\n\n'''+anchor
    if anchor not in s: raise SystemExit('health anchor missing')
    s=s.replace(anchor,insert,1)

# Replace the current quick_doc artifact branch by boundaries instead of brittle exact-text matching.
start="            if isinstance(quick_doc,tuple) and quick_doc[0]=='__ESTIMATE_IMAGE__':"
end="            else:ans=quick_doc"
if start in s:
    a=s.index(start); b=s.index(end,a)+len(end)
    replacement='''            if isinstance(quick_doc,tuple) and quick_doc[0] in ('__ESTIMATE_IMAGE__','__ESTIMATE_PDF__','__ESTIMATE_BOTH__'):\n                estimate_text=quick_doc[1]\n                key=hashlib.sha256((eid+str(time.time())).encode()).hexdigest()[:24]\n                ESTIMATE_CACHE[key]=(time.time(),estimate_text)\n                base=os.getenv("PUBLIC_BASE_URL","https://koukaisi-nami.onrender.com").rstrip('/')\n                save_msg("assistant:"+eid,cid,"bot","航海士ナミ","assistant",estimate_text)\n                reply_estimate_artifact(e.get("replyToken"),base,key,quick_doc[0])\n                continue\n            elif isinstance(quick_doc,tuple) and quick_doc[0]=='__PDF__':\n                _,pdf_kind,pdf_data=quick_doc;make_pdf(pdf_kind,pdf_data)\n                ans=pdf_kind+'の内容を作成したよ🧭\\n'+pdf_data.get('description','')\n            else:ans=quick_doc'''
    s=s[:a]+replacement+s[b:]
elif 'reply_estimate_artifact(e.get("replyToken")' not in s:
    raise SystemExit('handler target missing')

p.write_text(s)
