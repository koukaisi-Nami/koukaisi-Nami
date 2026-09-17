from pathlib import Path
p=Path('app.py')
s=p.read_text()

s=s.replace('''def content(mid):
    r=requests.get(f"https://api-data.line.me/v2/bot/message/{mid}/content",
      headers={"Authorization":f"Bearer {TOKEN}"},timeout=40)
    return (r.content,r.headers.get("Content-Type","image/jpeg")) if r.ok else (None,None)
''','''def content(mid):
    r=requests.get(f"https://api-data.line.me/v2/bot/message/{mid}/content",
      headers={"Authorization":f"Bearer {TOKEN}"},timeout=40)
    return (r.content,r.headers.get("Content-Type","application/octet-stream")) if r.ok else (None,None)

def media_ai(blob,mime,uid,cid,question=""):
    q=(question or "").strip() or "この資料を詳細に読み取ってください。"
    if mime and "pdf" in mime.lower():
        parts=[{"type":"input_text","text":ctx(uid,cid,q)+"\\n【今回】\\n"+q[:3000]}, {"type":"input_file","filename":"document.pdf","file_data":"data:application/pdf;base64,"+base64.b64encode(blob).decode()}]
        payload={"model":MODEL,"instructions":SYSTEM,"input":[{"role":"user","content":parts}],"max_output_tokens":1200}
        try:
            r=requests.post(OA,headers={"Authorization":f"Bearer {OPENAI_KEY}","Content-Type":"application/json"},json=payload,timeout=180)
            if not r.ok: print("OPENAI_MEDIA",r.status_code,r.text[:2000],flush=True); return f"PDF解析エラー({r.status_code})"
            d=r.json(); out=d.get("output_text","")
            if not out:
                vals=[]
                for i in d.get("output",[]):
                    if i.get("type")=="message":
                        for z in i.get("content",[]):
                            if z.get("type")=="output_text": vals.append(z.get("text",""))
                out="\\n".join(vals)
            return out.strip() or "PDFを読み取れなかったよ。"
        except Exception as x: print("media_ai_pdf",repr(x),flush=True); return "PDF解析で接続エラー"
    return ai(q,uid,cid,img=blob,mime=mime)
''')

s=s.replace('''def analyze(img,mime,uid,cid):
    return ai("""画像を詳細に解析。賃貸募集図面なら物件名、号室、所在地、交通、間取り、面積、賃料、管理費、
敷礼、保証金、契約期間、保証会社、保険、鍵、その他初期/月額費用、入居日、設備、特約、AD等を抽出。
見積に使える情報を構造化。不明・未記載は要確認。推測禁止。""",uid,cid,img,mime)
''','''def analyze(img,mime,uid,cid,question=""):
    prompt="""資料を高精度で詳細に解析。小さい文字・表・注記も確認する。
賃貸募集図面なら物件名、号室、所在地、交通、間取り、面積、賃料、管理費、敷金、礼金、保証金、契約期間、保証会社、初回/月額保証料、火災保険、鍵交換、24時間サポート、クリーニング、その他初期/月額費用、入居日、設備、特約、AD等を抽出。
見積に使える金額を項目別に構造化し、必須/任意・税込/税別も分かる範囲で区別。数字は推測しない。不鮮明・未記載は必ず「要確認」。"""
    if question: prompt += "\\nユーザーの質問を最優先して答える: "+question[:1500]
    return media_ai(img,mime,uid,cid,prompt)
''')

s=s.replace('''        m=e.get("message",{}); typ=m.get("type")
        if typ not in ("text","image"):continue
''','''        m=e.get("message",{}); typ=m.get("type")
        if typ not in ("text","image","file"):continue
''')

s=s.replace('''        if typ=="image":
            rawimg,mime=content(mid)
            if not rawimg:continue
            a=analyze(rawimg,mime,uid,cid)
            save_image(cid,uid,mid,a)
            save_msg(eid,cid,uid,nm,"user","[画像解析]\\n"+a,"image",mid,qid)
            # Personal chat replies; group stores silently, preserving context.
            if not grouped(e):
                save_msg("assistant:"+eid,cid,"bot","航海士ナミ","assistant",a)
                reply(e.get("replyToken"),a)
            continue
''','''        if typ in ("image","file"):
            rawmedia,mime=content(mid)
            if not rawmedia:continue
            filename=(m.get("fileName") or "").lower()
            is_pdf=(typ=="file" and (filename.endswith(".pdf") or "pdf" in (mime or "").lower()))
            if typ=="file" and not is_pdf:
                reply(e.get("replyToken"),"今は画像とPDFを読めるよ🧭 このファイル形式はまだ未対応。")
                continue
            a=analyze(rawmedia,"application/pdf" if is_pdf else mime,uid,cid)
            save_image(cid,uid,mid,a)
            label="PDF解析" if is_pdf else "画像解析"
            save_msg(eid,cid,uid,nm,"user",f"[{label}]\\n"+a,"file" if is_pdf else "image",mid,qid)
            if not grouped(e):
                save_msg("assistant:"+eid,cid,"bot","航海士ナミ","assistant",a)
                reply(e.get("replyToken"),a)
            continue
''')

s=s.replace('''    payload={"model":MODEL,"instructions":SYSTEM,"input":[{"role":"user","content":parts}],"max_output_tokens":900,
             "tools":[{"type":"web_search"}],"tool_choice":"auto"}
''','''    needs_web=bool(re.search(r"(最新|今日|現在|ニュース|天気|相場|営業時間|公式|検索して|調べて|web|ネット)",text or "",re.I))
    payload={"model":MODEL,"instructions":SYSTEM,"input":[{"role":"user","content":parts}],"max_output_tokens":900}
    if needs_web:
        payload["tools"]=[{"type":"web_search"}]; payload["tool_choice"]="auto"
''')

p.write_text(s)
print('patched',len(s))
# workflow trigger
