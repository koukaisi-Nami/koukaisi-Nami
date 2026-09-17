from pathlib import Path

p=Path('app.py')
s=p.read_text()
old='''def codegen_improvement(req_text,uid,cid):
    current,_=repo_file()
    return targeted_candidate(req_text,current)

def create_pr(req_text):
    candidate=codegen_improvement(req_text,"system","system")
    errors=validate_candidate(candidate)
    if errors:return None,"安全チェック停止:\\n- "+"\\n- ".join(errors[:15])
    current,base_sha=repo_file()
'''
new='''def codegen_improvement(req_text,uid,cid):
    current,_=repo_file()
    return targeted_candidate(req_text,current)

def supervisor_review(req_text,current,candidate,attempt):
    """Review only the proposed code change. Never merge or mutate memory here."""
    targets=improvement_targets(req_text,candidate)
    selected="\\n\\n".join(f"【{name}】\\n{body}" for name,body in targets.items())
    instruction="""あなたは航海士ナミの上位コードレビューAI。要求と候補コードを厳格に照合する。
既存機能・個人/グループ/会社記憶の分離・owner guard・承認前マージ禁止を壊さないこと。
秘密情報を要求/出力しない。問題がなければapprove。問題があればfixと具体的な修正指示を返す。
JSONのみ: {"action":"approve|fix","feedback":"具体的な理由と修正指示"}。"""
    text=f"【要求】\\n{req_text}\\n【レビュー試行】{attempt}/3\\n【候補コード（関連関数のみ）】\\n{selected}"
    payload={"model":MODEL,"instructions":instruction,"input":[{"role":"user","content":[{"type":"input_text","text":text}]}],"max_output_tokens":900}
    r=requests.post(OA,headers={"Authorization":f"Bearer {OPENAI_KEY}","Content-Type":"application/json"},json=payload,timeout=120)
    if not r.ok: raise RuntimeError(f"supervisor review failed {r.status_code}")
    d=r.json(); out=d.get("output_text","")
    if not out:
        xs=[]
        for item in d.get("output",[]):
            if item.get("type")=="message":
                for z in item.get("content",[]):
                    if z.get("type")=="output_text": xs.append(z.get("text",""))
        out="\\n".join(xs)
    out=re.sub(r"^```(?:json)?\\s*|\\s*```$","",out.strip())
    try:data=json.loads(out)
    except Exception as x: raise RuntimeError("上位AIレビューJSONが不正: "+str(x))
    action=str(data.get("action","")).lower()
    if action not in ("approve","fix"): raise RuntimeError("上位AIレビュー判定が不正")
    return action,str(data.get("feedback","")).strip()[:4000]

def reviewed_candidate(req_text):
    """Generate, validate and supervisor-review a candidate, bounded to three attempts."""
    current,_=repo_file()
    candidate=targeted_candidate(req_text,current)
    audit=[]
    for attempt in range(1,4):
        errors=validate_candidate(candidate)
        if errors:
            audit.append(f"attempt {attempt}: guard failed: "+"; ".join(errors[:5]))
            if attempt>=3:return None,audit,"安全チェックが3回以内に解消しなかった"
            candidate=targeted_candidate(req_text+"\\n【前回の安全チェックエラー】\\n"+"\\n".join(errors[:10]),current)
            continue
        action,feedback=supervisor_review(req_text,current,candidate,attempt)
        audit.append(f"attempt {attempt}: supervisor {action}: {feedback[:500]}")
        if action=="approve":return candidate,audit,None
        if attempt>=3:return None,audit,"上位AIレビューが3回以内に承認しなかった"
        candidate=targeted_candidate(req_text+"\\n【上位AIレビュー修正指示】\\n"+feedback,current)
    return None,audit,"レビュー上限に到達"

def create_pr(req_text):
    candidate,audit,review_error=reviewed_candidate(req_text)
    if review_error:return None,review_error+"\\n"+"\\n".join(audit[-3:])
    errors=validate_candidate(candidate)
    if errors:return None,"安全チェック停止:\\n- "+"\\n- ".join(errors[:15])
    current,base_sha=repo_file()
'''
if old not in s:
    raise SystemExit('target block not found')
s=s.replace(old,new,1)
old_body='''      "body":"LINEから作成した改善候補。必須機能ガード済み。船長のLINE承認後のみマージ。"})'''
new_body='''      "body":"LINEから作成した改善候補。上位AIレビュー（最大3回）と必須機能ガード済み。船長のLINE承認後のみマージ。\\n\\nレビュー監査:\\n"+"\\n".join(audit[-3:])[:4000]})'''
if old_body not in s:
    raise SystemExit('PR body target not found')
s=s.replace(old_body,new_body,1)
p.write_text(s)
print('supervisor review loop wired')
