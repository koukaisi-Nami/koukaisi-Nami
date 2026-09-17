from pathlib import Path
p=Path('app.py'); s=p.read_text()
anchor='''def task_command(text,uid,cid):\n'''
if anchor not in s: raise SystemExit('task anchor missing')
insert=r'''
def three_document_command(text,uid,cid,qid=None):
    """Handle Steer Ship standard AD / brokerage / estimate commands from LINE."""
    clean=re.sub(r"^(ナミ|なみ|nami)[、,\s]*","",(text or "").strip(),flags=re.I)
    kind=None
    if re.search(r"(AD請求|AD作|広告料.*請求|業務委託料.*請求)",clean,re.I): kind="ad"
    elif re.search(r"(中手|仲介手数料精算)",clean,re.I): kind="brokerage"
    elif re.search(r"(見積|初期費用|入居計算)",clean,re.I): kind="estimate"
    if not kind:return None

    # A plain estimate question against quoted media should be answered immediately from the source.
    if kind=="estimate" and not re.search(r"(PDF|作って|作成|発行|書類)",clean,re.I):
        if qid:
            blob,mime=content(qid)
            if blob:
                if blob[:5]==b"%PDF-": mime="application/pdf"
                return analyze(blob,mime,uid,cid,question=text)
        return None

    # Pull facts from quoted image/PDF once; do not invent missing amounts.
    media_summary=""
    if qid:
        blob,mime=content(qid)
        if blob:
            if blob[:5]==b"%PDF-": mime="application/pdf"
            media_summary=analyze(blob,mime,uid,cid,question=(
                "帳票作成用に、物件名、号室、賃料、管理費、敷金、礼金、保証料、保険、鍵交換、"
                "クリーニング、24時間サポート、その他必須費用、AD記載を簡潔に抽出して。推測禁止。"))
    elif re.search(r"(この|図面|画像|PDF|資料)",clean,re.I):
        media_summary=image_analysis(cid) or ""

    def grab(pattern):
        m=re.search(pattern,clean,re.I); return m.group(1).strip() if m else ""
    client=grab(r"(?:宛名|宛先)[：:\s]*([^、,\n]+)")
    deadline=grab(r"(?:期限|支払期限)[：:\s]*([^、,\n]+)")
    prop=grab(r"(?:物件名)[：:\s]*([^、,\n]+)")
    room=grab(r"(?:号室)[：:\s]*([^、,\n]+)")
    amount=grab(r"(?:金額)[：:\s]*([0-9,]+)円?")
    ad=grab(r"AD\s*([0-9.]+)")
    broker=grab(r"(?:中手|仲介手数料)\s*([0-9.]+)\s*(?:ヶ月|か月|月)?")

    # Ask only for fields that cannot safely be inferred. Media facts are shown so the user can answer once.
    if kind=="ad":
        missing=[]
        if not client:missing.append("宛名")
        if not deadline:missing.append("支払期限")
        if not amount and not ad:missing.append("AD金額またはAD率（例：AD100）")
        if not prop and not media_summary:missing.append("物件名・号室")
        if missing:
            return "AD請求書を作るよ🧭\n不足："+"、".join(missing)+(f"\n\n図面から読めた内容：\n{media_summary[:1800]}" if media_summary else "")
        desc=f"物件：{prop or '図面参照'} {room}".strip()
        if ad and not amount: desc+=f" / AD{ad}（基準額は図面・会社ルールから確定できる場合のみ計算）"
        data={"client":client,"title":"AD請求書","amount":("¥"+amount if amount else "要確認"),"description":desc,"notes":f"支払期限：{deadline}\n{media_summary[:1200]}"}
        return ("__PDF__", "AD請求書", data)

    if kind=="brokerage":
        missing=[]
        if not deadline:missing.append("支払期限")
        if not amount and not broker:missing.append("仲介手数料金額または月数（例：中手0.5ヶ月）")
        if not prop and not media_summary:missing.append("物件名・号室")
        if missing:
            return "中手を作るよ🧭\n不足："+"、".join(missing)+(f"\n\n図面から読めた内容：\n{media_summary[:1800]}" if media_summary else "")
        data={"client":client,"title":"仲介手数料精算書","amount":("¥"+amount if amount else f"{broker}ヶ月（要金額確定）"),"description":f"物件：{prop or '図面参照'} {room}".strip(),"notes":f"支払期限：{deadline}\n{media_summary[:1200]}"}
        return ("__PDF__", "仲介手数料精算書", data)

    # Estimate PDF: use the media analysis as source and never silently fabricate missing fields.
    if not media_summary:
        return "見積書を作る資料がまだないよ。募集図面の画像/PDFにリプライして『ナミ、見積もりPDF作って』と送って。"
    data={"client":client,"title":"入居初期費用見積書","amount":"図面記載額から算出","description":media_summary[:1800],"notes":"不明項目は要確認。日割りは入居日確定後に計算。"}
    return ("__PDF__", "見積り書", data)

'''
s=s.replace(anchor,insert+anchor,1)

old='''        quick_task=task_command(text,uid,cid)\n        awaiting=latest_awaiting(cid,uid)\n        if quick_task:\n            ans=quick_task\n'''
new='''        quick_task=task_command(text,uid,cid)\n        quick_doc=three_document_command(text,uid,cid,qid)\n        awaiting=latest_awaiting(cid,uid)\n        if quick_task:\n            ans=quick_task\n        elif quick_doc:\n            if isinstance(quick_doc,tuple) and quick_doc[0]=="__PDF__":\n                _,pdf_kind,pdf_data=quick_doc\n                # LINE reply API cannot attach raw PDF. Generate via existing PDF route semantics and\n                # give a clear confirmation; dashboard remains the download surface until a public file URL is configured.\n                make_pdf(pdf_kind,pdf_data)\n                ans=f"{pdf_kind}の内容を作成したよ🧭\\n"+pdf_data.get("description","")+"\\n金額："+pdf_data.get("amount","-")+"\\n"+pdf_data.get("notes","")\n            else:\n                ans=quick_doc\n'''
if old not in s: raise SystemExit('webhook anchor missing')
s=s.replace(old,new,1)
p.write_text(s)
print('three documents patched')
