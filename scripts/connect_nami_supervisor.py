from pathlib import Path

p=Path('app.py')
s=p.read_text()

imp='from owner_guard import can_self_improve\n'
newimp=imp+'from nami_supervisor import route_intent, line_scope, wants_company_memory, needs_supervisor_review, reviewer_instructions\n'
if newimp not in s:
    assert imp in s
    s=s.replace(imp,newimp,1)

# Fix the explicit group-memory bug without deleting or migrating any memories.
s=s.replace('def explicit_learning(text,uid):','def explicit_learning(text,uid,cid=None,source_type="user"):',1)
s=s.replace("add_memory(\"conversation\",cid if 'cid' in locals() else \"\", \"group_context\",\"グループルール\",group.group(1).strip(),uid)","\n        if source_type not in (\"group\",\"room\") or not cid:\n            return \"どのグループの記憶にするか、そのグループで送ってね🧭\"\n        add_memory(\"conversation\",cid, \"group_context\",\"グループルール\",group.group(1).strip(),uid)",1)

# Company memory is owner-only even if technical text contains company keywords.
s=s.replace('if company_scope:\n        payload=', 'if company_scope:\n        if not can_self_improve(uid):\n            return \"会社共通ルールの変更は船長だけができるよ🧭\"\n        payload=',1)

# Existing learn_important company writes are also owner-only.
s=s.replace('if company_scope and company_fact:\n        add_memory("company"', 'if company_scope and company_fact:\n        if not can_self_improve(uid): return None\n        add_memory("company"',1)

# Route owner self-improvement before memory interpretation at the existing call site.
old='learned=explicit_learning(text,uid)'
new='''source_type=(e.get("source") or {}).get("type","user")\n        if route_intent(text,is_owner=can_self_improve(uid))=="self_improve":\n            learned=None\n        else:\n            learned=explicit_learning(text,uid,cid,source_type)'''
assert old in s, 'explicit_learning call site changed'
s=s.replace(old,new,1)

p.write_text(s)
