from pathlib import Path
import re

p=Path('app.py')
s=p.read_text()

imp='from owner_guard import can_self_improve\n'
anchor='from structured_estimate_runtime import generate_text as structured_estimate\n'
if imp not in s:
    if anchor not in s:
        raise SystemExit('structured_estimate import anchor missing')
    s=s.replace(anchor,anchor+imp,1)

# Gate merge approval. Accept either quote style and treat an already guarded
# current runtime as success; this migration must be idempotent.
if 'elif awaiting and can_self_improve(uid) and re.search(' not in s:
    pattern=r"elif awaiting and re\.search\((r?[\"'].*?[\"']),text\.strip\(\),re\.I\):"
    m=re.search(pattern,s)
    if not m:
        raise SystemExit('merge approval anchor missing')
    old=m.group(0)
    new=old.replace('elif awaiting and re.search(', 'elif awaiting and can_self_improve(uid) and re.search(',1)
    s=s.replace(old,new,1)

# Improvement creation is safe in either supported architecture:
# 1) direct intent route explicitly guarded by can_self_improve(uid), or
# 2) semantic route where owner_self_improve can only become true after the
#    owner check at route creation.
legacy_old='elif improvement_intent(text):\n            plan=improvement_plan(text,uid,cid)'
legacy_new='elif improvement_intent(text) and can_self_improve(uid):\n            plan=improvement_plan(text,uid,cid)'
supervisor_new='elif routed_intent=="self_improve" and can_self_improve(uid):\n            plan=improvement_plan(text,uid,cid)'
semantic_guard="semantic_route=semantic_intent_route(text,uid,cid) if can_self_improve(uid) else 'chat'"
semantic_branch='elif owner_self_improve:'
if legacy_old in s:
    s=s.replace(legacy_old,legacy_new,1)
elif legacy_new in s or supervisor_new in s:
    pass
elif semantic_guard in s and semantic_branch in s:
    pass
else:
    raise SystemExit('improvement creation anchor missing')

p.write_text(s)
print('owner guard integrated')
