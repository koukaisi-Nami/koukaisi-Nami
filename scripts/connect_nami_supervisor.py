from pathlib import Path

p=Path('app.py')
s=p.read_text()

imp='from owner_guard import can_self_improve\n'
newimp=imp+'from nami_supervisor import route_intent, line_scope, wants_company_memory, needs_supervisor_review, reviewer_instructions\n'
if newimp not in s:
    assert imp in s
    s=s.replace(imp,newimp,1)

# Fix explicit group-memory routing without deleting or migrating existing memories.
s=s.replace('def explicit_learning(text,uid):','def explicit_learning(text,uid,cid=None,source_type="user"):',1)
old_group='add_memory("conversation",cid if \'cid\' in locals() else "", "group_context","グループルール",group.group(1).strip(),uid)'
new_group='''if source_type not in ("group","room") or not cid:\n            return "どのグループの記憶にするか、そのグループで送ってね🧭"\n        add_memory("conversation",cid, "group_context","グループルール",group.group(1).strip(),uid)'''
if old_group in s:
    s=s.replace(old_group,new_group,1)

# Company-wide memory writes are owner-only.
marker='if company_scope:\n        payload='
if marker in s and 'if company_scope:\n        if not can_self_improve(uid):' not in s:
    s=s.replace(marker,'if company_scope:\n        if not can_self_improve(uid):\n            return "会社共通ルールの変更は船長だけができるよ🧭"\n        payload=',1)
marker2='if company_scope and company_fact:\n        add_memory("company"'
if marker2 in s:
    s=s.replace(marker2,'if company_scope and company_fact:\n        if not can_self_improve(uid): return None\n        add_memory("company"',1)

# The current runtime already routes self-improvement before explicit_learning.
# Keep that ordering, but pass real LINE source context into memory handling.
old='taught=explicit_learning(text,uid)'
new='''source_type=(e.get("source") or {}).get("type","user")\n            taught=explicit_learning(text,uid,cid,source_type)'''
if old in s:
    s=s.replace(old,new,1)

# Fail closed if expected safety wiring was not achieved.
assert 'from nami_supervisor import' in s
assert 'def explicit_learning(text,uid,cid=None,source_type="user"):' in s
assert 'taught=explicit_learning(text,uid,cid,source_type)' in s
assert 'add_memory("conversation",cid, "group_context","グループルール"' in s

p.write_text(s)
