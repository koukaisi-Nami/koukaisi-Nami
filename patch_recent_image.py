from pathlib import Path
p=Path('app.py')
s=p.read_text()
old='''    if kind=="estimate" and not wants_image and not wants_pdf:\n        if qid:\n            blob,mime=content(qid)\n            if blob:\n                if blob[:5]==b"%PDF-":mime="application/pdf"\n                prompt=("この募集図面から、お客様へそのままLINE転送できる初期費用の概算を作成してください。短く見やすく丁寧にしてください。Markdown表、見出し記号、計算過程、内部事情、前回回答への言及は禁止です。\\n"\n                        "【初期費用の概算】、物件名・号室、確定できる費用を項目：金額円で1行ずつ、現時点の合計、金額不明だけ【別途確認】、短い注意書きの順にしてください。\\n"\n                        "図面から読めない金額は絶対に推測せず合計に含めないでください。日割り等は入居日不明なら別途確認にしてください。保存済みの会社ルールがある場合は優先してください。")\n                return analyze(blob,mime,uid,cid,question=prompt)\n        return None\n'''
new='''    if kind=="estimate" and not wants_image and not wants_pdf:\n        prompt=("募集図面の読取結果から、お客様へそのままLINE転送できる初期費用の概算を作成してください。短く見やすく丁寧にしてください。Markdown表、計算過程、内部事情、前回回答への言及は禁止です。\\n"\n                "【初期費用の概算】、物件名・号室、確定できる費用を項目：金額円で1行ずつ、現時点の合計、金額不明だけ【別途確認】、短い注意書きの順にしてください。\\n"\n                "読めない金額は絶対に推測せず合計に含めないでください。日割り等は入居日不明なら別途確認にしてください。保存済みの会社ルールがある場合は優先してください。")\n        if qid:\n            blob,mime=content(qid)\n            if blob:\n                if blob[:5]==b"%PDF-":mime="application/pdf"\n                return analyze(blob,mime,uid,cid,question=prompt)\n        # LINEでは画像を送った直後に別メッセージで「見積もり教えて」と送る運用が多い。\n        # その場合も直前に保存済みの画像解析を使い、再添付を要求しない。\n        latest=image_analysis(cid) or ""\n        if latest:\n            return ask(prompt+"\\n\\n【直前の募集図面の読取結果】\\n"+latest,uid,cid)\n        return "募集図面を送ってから『ナミ、見積もり教えて』でOKだよ。画像にリプライしなくても大丈夫。"\n'''
if old not in s: raise SystemExit('estimate anchor missing')
s=s.replace(old,new,1)
# 「これだよ」「これね」なども直前画像参照として扱う
s=s.replace('re.search(r"(この|図面|画像|PDF|資料)",clean,re.I)', 're.search(r"(この|これ|それ|図面|画像|写真|PDF|資料)",clean,re.I)')
p.write_text(s)
