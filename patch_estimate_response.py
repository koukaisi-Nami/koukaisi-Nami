from pathlib import Path
p=Path('app.py')
s=p.read_text()

old='''        d=r.json()
        if d.get("output_text"):return d["output_text"].strip()
        out=[]
        for i in d.get("output",[]):
            if i.get("type")=="message":
                for z in i.get("content",[]):
                    if z.get("type")=="output_text":out.append(z.get("text",""))
        return "\\n".join(out).strip() or "回答を作れなかったよ。"
'''
new='''        d=r.json()
        if d.get("output_text"):return d["output_text"].strip()
        out=[]
        for i in d.get("output",[]):
            if i.get("type")=="message":
                for z in i.get("content",[]):
                    if z.get("type") in ("output_text","text") and z.get("text"):
                        out.append(z.get("text",""))
        answer="\\n".join(out).strip()
        if answer:return answer
        # Some models can finish with an incomplete response before emitting text.
        # Retry once without tools, with more output budget, preserving the image/question.
        status=d.get("status","")
        incomplete=d.get("incomplete_details") or {}
        print("OPENAI_EMPTY",{"status":status,"incomplete":incomplete,"types":[i.get("type") for i in d.get("output",[])]},flush=True)
        retry=dict(payload)
        retry.pop("tools",None); retry.pop("tool_choice",None)
        retry["max_output_tokens"]=1600 if img else 1200
        rr=requests.post(OA,headers={"Authorization":f"Bearer {OPENAI_KEY}","Content-Type":"application/json"},json=retry,timeout=150)
        if not rr.ok:
            print("OPENAI_RETRY",rr.status_code,rr.text[:2000],flush=True)
            return f"AIエラー({rr.status_code})"
        dd=rr.json()
        if dd.get("output_text"):return dd["output_text"].strip()
        vals=[]
        for i in dd.get("output",[]):
            if i.get("type")=="message":
                for z in i.get("content",[]):
                    if z.get("type") in ("output_text","text") and z.get("text"):
                        vals.append(z.get("text",""))
        return "\\n".join(vals).strip() or "資料は受け取れたけど回答生成に失敗したよ。もう一度同じ資料に返信してね。"
'''
if old not in s: raise SystemExit('ai target not found')
s=s.replace(old,new,1)

old2='''    if question: prompt += "\\nユーザーの質問を最優先して答える: "+question[:1500]
    return media_ai(img,mime,uid,cid,prompt)
'''
new2='''    if question:
        prompt += "\\nユーザーの質問を最優先して答える: "+question[:1500]
        if re.search(r"(見積|初期費用|いくら|費用|合計)",question,re.I):
            prompt += """\n【見積回答ルール】
読み取れた金額を使って、その場で初期費用の概算を計算する。
賃料・管理費・日割り賃料/管理費・前家賃・敷金・礼金・保証会社初回保証料・火災保険・鍵交換・仲介手数料・その他必須費用を項目別に表示し、最後に合計を出す。
仲介手数料など会社ルールが保存済みskillsにあればそれを優先する。図面にない金額は勝手に作らず「要確認」とし、確定項目だけの小計も出す。
入居日が不明なら日割りは「入居日要確認」とし、日割りを除いた確定/概算小計を出す。単に『作れません』で終わらず、読み取れた範囲で必ず見積表を返す。"""
    return media_ai(img,mime,uid,cid,prompt)
'''
if old2 not in s: raise SystemExit('analyze target not found')
s=s.replace(old2,new2,1)
p.write_text(s)
print('patched estimate response')
