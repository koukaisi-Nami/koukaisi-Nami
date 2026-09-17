from pathlib import Path
p=Path('app.py'); s=p.read_text()
anchor='''def task_command(text,uid,cid):\n'''
if anchor not in s: raise SystemExit('task anchor missing')
insert=r'''
def three_document_command(text,uid,cid,qid=None):
    """Steer Ship: AD / brokerage / customer-ready estimate commands."""
    clean=re.sub(r"^(ナミ|なみ|nami)[、,\s]*","",(text or "").strip(),flags=re.I)
    kind="ad" if re.search(r"(AD請求|AD作|広告料.*請求|業務委託料.*請求)",clean,re.I) else ("brokerage" if re.search(r"(中手|仲介手数料精算)",clean,re.I) else ("estimate" if re.search(r"(見積|初期費用|入居計算)",clean,re.I) else None))
    if not kind:return None
    wants_image=kind=="estimate" and bool(re.search(r"(画像|イメージ|一枚|1枚|写真にして)",clean,re.I))
    wants_pdf=bool(re.search(r"(PDF|pdf|書類|発行)",clean))
    if kind=="estimate" and not wants_image and not wants_pdf:
        if qid:
            blob,mime=content(qid)
            if blob:
                if blob[:5]==b"%PDF-":mime="application/pdf"
                prompt='''この募集図面から、お客様へそのままLINE転送できる初期費用の概算を作成してください。短く見やすく丁寧にしてください。Markdown表、###、計算過程、内部事情、前回回答への言及は禁止です。\n「【初期費用の概算】」→物件名・号室→確定できる費用を「項目：○円」で1行ずつ→「現時点の合計：○円」→金額不明だけ「【別途確認】」→短い注意書き、の順にしてください。\n図面から読めない金額は絶対に推測せず合計に含めないでください。日割り等は入居日不明なら別途確認にしてください。保存済みの会社ルールがある場合は優先してください。'''
                return analyze(blob,mime,uid,cid,question=prompt)
        return None
    media_summary=""
    if qid:
        blob,mime=content(qid)
        if blob:
            if blob[:5]==b"%PDF-":mime="application/pdf"
            media_summary=analyze(blob,mime,uid,cid,question="物件名、号室、賃料、管理費/共益費、敷金、礼金、保証料、仲介手数料、保険、鍵交換、クリーニング、24時間サポート、その他必須費用を帳票用に抽出。各金額と条件を明記。推測禁止。")
    elif re.search(r"(この|図面|画像|PDF|資料)",clean,re.I):media_summary=image_analysis(cid) or ""
    if kind=="estimate" and wants_image:
        if not media_summary:return "見積もり画像を作る募集図面がないよ。図面の画像/PDFにリプライして『ナミ、見積もり画像作って』と送って。"
        # Marker consumed by webhook. Rendering must use deterministic template, not generative AI, so numbers cannot mutate.
        return ("__ESTIMATE_IMAGE__",media_summary)
    if kind=="estimate":
        if not media_summary:return "見積書を作る募集図面がないよ。図面にリプライして送って。"
        return ("__PDF__","見積り書",{"title":"見積もり概算書","description":media_summary,"notes":"本書は概算の見積もりです。詳細は別途ご案内いたします。"})
    def grab(pat):
        m=re.search(pat,clean,re.I);return m.group(1).strip() if m else ""
    client=grab(r"(?:宛名|宛先)[：:\s]*([^、,\n]+)");deadline=grab(r"(?:期限|支払期限)[：:\s]*([^、,\n]+)");amount=grab(r"(?:金額)[：:\s]*([0-9,]+)円?");ad=grab(r"AD\s*([0-9.]+)");broker=grab(r"(?:中手|仲介手数料)\s*([0-9.]+)")
    if kind=="ad":
        missing=[]
        if not client:missing.append("宛名")
        if not deadline:missing.append("支払期限")
        if not amount and not ad:missing.append("AD金額またはAD率")
        if missing:return "AD請求書を作るよ🧭\n不足："+"、".join(missing)
        return ("__PDF__","AD請求書",{"client":client,"title":"AD請求書","amount":("¥"+amount if amount else "要確認"),"description":media_summary or "図面参照","notes":"支払期限："+deadline})
    missing=[]
    if not deadline:missing.append("支払期限")
    if not amount and not broker:missing.append("仲介手数料金額または月数")
    if missing:return "中手を作るよ🧭\n不足："+"、".join(missing)
    return ("__PDF__","仲介手数料精算書",{"client":client,"title":"仲介手数料精算書","amount":("¥"+amount if amount else broker+"ヶ月（要金額確定）"),"description":media_summary or "図面参照","notes":"支払期限："+deadline})

'''
s=s.replace(anchor,insert+anchor,1)
old='''        quick_task=task_command(text,uid,cid)\n        awaiting=latest_awaiting(cid,uid)\n        if quick_task:\n            ans=quick_task\n'''
new='''        quick_task=task_command(text,uid,cid)\n        quick_doc=three_document_command(text,uid,cid,qid)\n        awaiting=latest_awaiting(cid,uid)\n        if quick_task:\n            ans=quick_task\n        elif quick_doc:\n            if isinstance(quick_doc,tuple) and quick_doc[0]=="__ESTIMATE_IMAGE__":\n                ans="見積もり画像用の内容を作成したよ🧭\\n"+quick_doc[1]+"\\n※画像は固定テンプレート描画で金額を変えずに生成する仕様です。"\n            elif isinstance(quick_doc,tuple) and quick_doc[0]=="__PDF__":\n                _,pdf_kind,pdf_data=quick_doc;make_pdf(pdf_kind,pdf_data)\n                ans=pdf_kind+"の内容を作成したよ🧭\\n"+pdf_data.get("description","")\n            else:ans=quick_doc\n'''
if old not in s:raise SystemExit('webhook anchor missing')
s=s.replace(old,new,1);p.write_text(s);print('three documents patched')
# customer-ready-estimate-v2
