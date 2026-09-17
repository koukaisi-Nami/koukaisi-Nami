from pathlib import Path
p=Path('app.py')
s=p.read_text()

a=s.index('def ai('); b=s.index('\ndef analyze(',a); seg=s[a:b]
start=seg.index('        out=[]\n'); end=seg.index('\n    except Exception as x:print("ai"',start)
replacement='''        out=[]
        for i in d.get("output",[]):
            if i.get("type")=="message":
                for z in i.get("content",[]):
                    if z.get("type") in ("output_text","text") and z.get("text"): out.append(z.get("text",""))
        answer="\\n".join(out).strip()
        if answer:return answer
        print("OPENAI_EMPTY",{"status":d.get("status","") ,"incomplete":d.get("incomplete_details") or {}},flush=True)
        retry=dict(payload); retry.pop("tools",None); retry.pop("tool_choice",None)
        retry["max_output_tokens"]=1600 if img else 1200
        rr=requests.post(OA,headers={"Authorization":f"Bearer {OPENAI_KEY}","Content-Type":"application/json"},json=retry,timeout=150)
        if not rr.ok:
            print("OPENAI_RETRY",rr.status_code,rr.text[:2000],flush=True); return f"AIエラー({rr.status_code})"
        dd=rr.json()
        if dd.get("output_text"):return dd["output_text"].strip()
        vals=[]
        for i in dd.get("output",[]):
            if i.get("type")=="message":
                for z in i.get("content",[]):
                    if z.get("type") in ("output_text","text") and z.get("text"): vals.append(z.get("text",""))
        return "\\n".join(vals).strip() or "資料は受け取れたけど回答生成に失敗したよ。もう一度同じ資料に返信してね。"'''
seg=seg[:start]+replacement+seg[end:]; s=s[:a]+seg+s[b:]

a=s.index('def analyze('); b=s.index('\ndef learn_important(',a); seg=s[a:b]
start=seg.index('    if question:')
endline='    return media_ai(img,mime,uid,cid,prompt)'
end=seg.index(endline,start)+len(endline)
replacement2='''    if question:
        prompt += "\\nユーザーの質問を最優先して答える: "+question[:1500]
        if re.search(r"(見積|初期費用|いくら|費用|合計)",question,re.I):
            prompt += """\n【見積回答ルール】
読み取れた金額を使って、その場で初期費用の概算を計算する。
賃料・管理費・日割り賃料/管理費・前家賃・敷金・礼金・保証会社初回保証料・火災保険・鍵交換・仲介手数料・その他必須費用を項目別に表示し、最後に合計を出す。
会社ルールが保存済みskillsにあれば優先。図面にない金額は作らず「要確認」とし、確定項目だけの小計も出す。
入居日不明なら日割りは「入居日要確認」とし、日割りを除く小計を出す。単に『作れません』で終わらず、読み取れた範囲で必ず見積を返す。"""
    return media_ai(img,mime,uid,cid,prompt)'''
seg=seg[:start]+replacement2+seg[end:]; s=s[:a]+seg+s[b:]
p.write_text(s)
print('patched estimate response')
