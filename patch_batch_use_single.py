from pathlib import Path
p=Path('app.py')
s=p.read_text()
# Extract the exact single-estimate prompt into one shared function.
needle='''def three_document_command(text,uid,cid,qid=None):\n'''
shared='''def single_estimate_prompt(user_instruction=""):\n    return ("募集図面の読取結果から、お客様へそのままLINE転送できる初期費用の概算を作成してください。短く見やすく丁寧にし、Markdown表、計算過程、内部事情、前回回答への言及は禁止です。\\n"\n            "表示項目と順番は必ず次で固定：当月前家賃、次月前家賃、敷金、礼金、初回保証料、仲介手数料、火災保険、24時間サポート、鍵交換、事務手数料、合計。該当しない又は金額不明の項目も省略せず『－』と表示してください。\\n"\n            "管理費・共益費は前家賃に含めます。当月前家賃は入居日の指定がない場合は必ず『－』。入居日の指定がある場合のみ賃料＋管理費・共益費を日割り計算してください。次月前家賃は賃料＋管理費・共益費で計算してください。\\n"\n            "仲介手数料は今回のユーザー発言で明示指定した場合だけ計上してください。今回指定がなければ図面・会社ルール・過去見積に金額があっても必ず『－』。自動計算しないでください。\\n"\n            "【保険判定・最優先】損保、損害保険、家財保険、家財、住宅保険、借家人賠償責任保険、少額短期保険、保険料、保険加入など住宅保険を火災保険として扱う。『損保 要2万円2年』なら火災保険：20,000円。保険加入記載のみで金額なし、又は保険記載自体なしなら必ず『火災保険（仮）：20,000円』と表示し合計へ加算。火災保険を－にしない。\\n"\n            "【保証料fallback】保証会社の初回保証料の金額・率が資料にない場合は、賃料＋管理費・共益費の50%を『初回保証料（仮）』として表示し合計に含める。\\n"\n            "【表記ゆれ】敷金/保証金/契約保証金/預り金、初回保証料/保証委託料/初回委託保証料/保証会社利用料、24時間サポート/安心サポート/緊急サポート/入居者サポート、鍵交換/鍵交換代/鍵設定費/シリンダー交換等は意味と文脈で分類。既存カテゴリ外の契約時費用も図面名のまま事務手数料の後に追加。保証金は敷金相当か独立費用か判定し二重計上しない。\\n"\n            "【合計】『－』以外に表示した全ての契約時金額（仮計上・次月前家賃・追加費用含む）を必ず合計し、回答前に再検算。\\n"\n            "出力は【初期費用概算】から始め、末尾は『※入居日・未確定項目により金額が変動します。』。余計な前置き、月額費用一覧、要確認一覧は書かない。\\n"\n            "【今回のユーザー指定】"+(user_instruction or "なし"))\n\ndef batch_estimates_using_single(groups,user_instruction,uid,cid):\n    \"\"\"Run the same single-property estimate prompt once per property.\"\"\"\n    answers=[]\n    for g in groups:\n        p=g['property']\n        analyses='\\n---\\n'.join(a.get('analysis','') for a in g['attachments'])\n        material=f"物件名：{p.get('name','')}\\n号室：{p.get('room','')}\\n住所：{p.get('address','')}\\n【募集図面の読取結果】\\n{analyses}"\n        answers.append(ai(single_estimate_prompt(user_instruction)+"\\n\\n"+material,uid,cid))\n    return answers\n\n'''
if needle not in s: raise SystemExit('three_document_command target missing')
s=s.replace(needle,shared+needle,1)
# Replace only the single-estimate local prompt with the shared exact rules.
start=s.index('        prompt=("募集図面の読取結果から、お客様へそのままLINE転送できる初期費用の概算を作成してください。',s.index('def three_document_command'))
end=s.index('        if qid:',start)
s=s[:start]+'        prompt=single_estimate_prompt(clean)\n'+s[end:]
# Batch: one AI call per property using the exact same shared prompt.
old='''                prompt,err=estimate_instruction(groups,ambiguous,text)\n                if err:batch_answer=err\n                elif prompt:\n                    batch_answer=ai(prompt,uid,cid)\n                    clear_estimate_batch(cid)'''
new='''                if ambiguous:\n                    batch_answer="資料の一部で物件を特定できませんでした。どの物件の資料か指定してください。"\n                else:\n                    batch_answer=batch_estimates_using_single(groups,text,uid,cid)\n                    clear_estimate_batch(cid)'''
if old not in s: raise SystemExit('batch target missing')
s=s.replace(old,new,1)
# Reply accepts list => one LINE bubble per property, max 5 per reply API call.
old='''def reply(tok,text):\n    chunks=[text[i:i+4900] for i in range(0,len(text),4900)][:5]'''
new='''def reply(tok,text):\n    if isinstance(text,(list,tuple)):\n        chunks=[str(x).strip()[:4900] for x in text if str(x).strip()][:5]\n    else:\n        chunks=[str(text)[i:i+4900] for i in range(0,len(str(text)),4900)][:5]'''
if old not in s: raise SystemExit('reply target missing')
s=s.replace(old,new,1)
# save_msg needs text, while reply can keep the list for separate LINE bubbles.
old='''        save_msg("assistant:"+eid,cid,"bot","航海士ナミ","assistant",ans)\n        reply(e.get("replyToken"),ans)'''
new='''        saved_ans="\\n\\n".join(ans) if isinstance(ans,(list,tuple)) else ans\n        save_msg("assistant:"+eid,cid,"bot","航海士ナミ","assistant",saved_ans)\n        reply(e.get("replyToken"),ans)'''
if old not in s: raise SystemExit('save/reply target missing')
s=s.replace(old,new,1)
p.write_text(s)
