from pathlib import Path
p=Path('app.py'); s=p.read_text()
s=s.replace('from flask import Flask, request, abort, Response, render_template_string, send_file','from flask import Flask, request, abort, Response, render_template_string, send_file\nfrom estimate_document import make_estimate_document')
# Recognize explicit document/PDF request as estimate-document, while preserving normal estimate chat.
old='''    wants_image=bool(re.search(r"(画像|イメージ|jpg|jpeg|png)",clean,re.I))\n    wants_pdf=bool(re.search(r"(PDF|pdf|書類|見積書)",clean,re.I))'''
new='''    wants_image=bool(re.search(r"(画像|イメージ|jpg|jpeg|png)",clean,re.I))\n    wants_pdf=bool(re.search(r"(PDF|pdf|書類|見積書|概算書)",clean,re.I))'''
if old in s:s=s.replace(old,new,1)
# In estimate PDF path, first generate the same customer-facing estimate text; marker will be rendered as formal PDF.
old='''    if kind=="estimate":\n        if not media_summary:return "見積書を作る募集図面がないよ。図面にリプライして送って。"\n        return ("__PDF__","見積り書",{"title":"見積もり概算書","description":media_summary,"notes":"本書は概算の見積もりです。詳細は別途ご案内いたします。"})'''
new='''    if kind=="estimate":\n        if not media_summary:return "見積書を作る募集図面がないよ。図面にリプライして送って。"\n        estimate_text=ai(single_estimate_prompt(clean)+"\\n\\n【募集図面の読取結果】\\n"+media_summary,uid,cid)\n        return ("__ESTIMATE_PDF__",estimate_text)'''
if old not in s: raise SystemExit('estimate pdf target missing')
s=s.replace(old,new,1)
# Add temporary signed-ish public PDF endpoint backed by in-memory cache for LINE file delivery.
anchor='''@app.get("/")\ndef health():return "航海士ナミ FINAL 部長モード OK",200'''
insert='''PDF_CACHE={}\n\n@app.get("/estimate-pdf/<key>")\ndef estimate_pdf_download(key):\n    row=PDF_CACHE.get(key)\n    if not row:return "not found",404\n    created,text=row\n    if time.time()-created>600:\n        PDF_CACHE.pop(key,None); return "expired",404\n    return send_file(make_estimate_document(text),mimetype="application/pdf",as_attachment=True,download_name="見積もり概算書.pdf")\n\ndef reply_file(tok,url,name="見積もり概算書.pdf"):\n    try:\n        r=requests.post("https://api.line.me/v2/bot/message/reply",headers={"Authorization":f"Bearer {TOKEN}","Content-Type":"application/json"},json={"replyToken":tok,"messages":[{"type":"file","originalContentUrl":url,"fileName":name}]},timeout=30)\n        if not r.ok: print("LINE file reply",r.status_code,r.text[:1000],flush=True)\n        return r.ok\n    except Exception as x:\n        print("reply_file",repr(x),flush=True); return False\n\n'''+anchor
if anchor not in s: raise SystemExit('health anchor missing')
s=s.replace(anchor,insert,1)
# Handle marker before generic __PDF__. PUBLIC_BASE_URL defaults to Render service URL.
old='''            if isinstance(quick_doc,tuple) and quick_doc[0]=='__ESTIMATE_IMAGE__':\n                ans='見積もり画像用の内容を作成したよ🧭\\n'+quick_doc[1]+'\\n※画像は固定テンプレート描画で金額を変えずに生成する仕様です。\n            elif isinstance(quick_doc,tuple) and quick_doc[0]=='__PDF__':'''
new='''            if isinstance(quick_doc,tuple) and quick_doc[0]=='__ESTIMATE_IMAGE__':\n                ans='見積もり画像用の内容を作成したよ🧭\\n'+quick_doc[1]+'\\n※画像は固定テンプレート描画で金額を変えずに生成する仕様です。\n            elif isinstance(quick_doc,tuple) and quick_doc[0]=='__ESTIMATE_PDF__':\n                estimate_text=quick_doc[1]\n                key=hashlib.sha256((eid+str(time.time())).encode()).hexdigest()[:24]\n                PDF_CACHE[key]=(time.time(),estimate_text)\n                base=os.getenv("PUBLIC_BASE_URL","https://koukaisi-nami.onrender.com").rstrip('/')\n                file_url=f"{base}/estimate-pdf/{key}"\n                save_msg("assistant:"+eid,cid,"bot","航海士ナミ","assistant",estimate_text)\n                reply_file(e.get("replyToken"),file_url)\n                continue\n            elif isinstance(quick_doc,tuple) and quick_doc[0]=='__PDF__':'''
if old not in s: raise SystemExit('quick doc handler missing')
s=s.replace(old,new,1)
p.write_text(s)
