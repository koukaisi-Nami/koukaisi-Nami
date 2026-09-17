from pathlib import Path

p=Path('app.py')
s=p.read_text()
needle='''def improvement_plan(text,uid,cid):\n'''
insert=r'''def semantic_intent_route(text,uid,cid):
    """Use the upper AI only for ambiguous change requests, never normal chat."""
    t=(text or "").strip()
    if not can_self_improve(uid): return "chat"
    if improvement_intent(t): return "self_improve"
    # Cheap gate: ordinary chat never pays reviewer latency/cost.
    if not re.search(r"(改善|変えて|変更|直し|直せ|使いにく|使いやす|こうして|ようにして|設定|ルール|覚えて|記憶|今後|これから)",t,re.I):
        return "chat"
    prompt="""あなたは航海士ナミの意図分類器。船長の発言を1語だけで分類する。
self_improve: ナミ自身の機能・挙動・コード・ツール能力を新設/変更/修正する要求。
memory: 呼び名、好み、個人設定、会話/グループ/会社ルールなど、既存機能で記憶すれば実現できる要求。
ask: memoryかself_improveか本当に判別不能。
chat: その他。
重要: 「Xと送ったらYと返すようにして」「これ使いにくいからいい感じに直して」はself_improve。
「俺のこと船長って呼んで」「このグループではキャプテンと呼んで」はmemory。
出力は self_improve / memory / ask / chat のどれか1語のみ。"""
    try:
        payload={"model":MODEL,"instructions":prompt,"input":[{"role":"user","content":[{"type":"input_text","text":t[:1500]}]}],"max_output_tokens":20}
        r=HTTP.post(OA,headers={"Authorization":f"Bearer {OPENAI_KEY}","Content-Type":"application/json"},json=payload,timeout=30)
        if not r.ok: return "chat"
        d=r.json(); raw=(d.get("output_text") or "").strip().lower()
        if not raw:
            vals=[]
            for item in d.get("output",[]):
                if item.get("type")=="message":
                    for z in item.get("content",[]):
                        if z.get("type") in ("output_text","text") and z.get("text"): vals.append(z["text"])
            raw=" ".join(vals).strip().lower()
        for v in ("self_improve","memory","ask","chat"):
            if raw==v or raw.startswith(v): return v
    except Exception as x:
        print("semantic_intent_route",repr(x),flush=True)
    return "chat"

'''
if 'def semantic_intent_route(' not in s:
    if needle not in s: raise SystemExit('improvement_plan anchor missing')
    s=s.replace(needle,insert+needle,1)
old='''        owner_self_improve = improvement_intent(text) and can_self_improve(uid)\n        if not owner_self_improve:\n            learn_important(text,uid,cid)\n'''
new='''        semantic_route = semantic_intent_route(text,uid,cid) if can_self_improve(uid) else "chat"\n        owner_self_improve = semantic_route == "self_improve"\n        ambiguous_change = semantic_route == "ask"\n        if not owner_self_improve and semantic_route in ("memory","chat"):\n            learn_important(text,uid,cid)\n'''
if old not in s: raise SystemExit('webhook routing anchor missing')
s=s.replace(old,new,1)
old2='''        if batch_answer:\n            ans=batch_answer\n'''
new2='''        if ambiguous_change:\n            ans="これは会話の設定として覚える？それともナミ自身の機能として改善する？🧭"\n        elif batch_answer:\n            ans=batch_answer\n'''
if old2 not in s: raise SystemExit('answer chain anchor missing')
s=s.replace(old2,new2,1)
p.write_text(s)
print('patched semantic intent router')
