from pathlib import Path

p=Path('app.py')
s=p.read_text()

imp='from owner_guard import can_self_improve\n'
anchor='from structured_estimate_runtime import generate_text as structured_estimate\n'
if imp not in s:
    if anchor not in s: raise SystemExit('structured_estimate import anchor missing')
    s=s.replace(anchor,anchor+imp,1)

# Gate merge approval first. This is deliberately narrow so existing behavior stays intact.
old='elif awaiting and re.search(r"^(ナミ[、, ]*)?(反映して|承認|OK|おけ|やって)$",text.strip(),re.I):'
new='elif awaiting and can_self_improve(uid) and re.search(r"^(ナミ[、, ]*)?(反映して|承認|OK|おけ|やって)$",text.strip(),re.I):'
if old in s:
    s=s.replace(old,new,1)
elif new not in s:
    raise SystemExit('merge approval anchor missing')

# Gate improvement creation. Support both the legacy direct intent route and the
# supervisor route. Both remain fail-closed behind can_self_improve(uid).
legacy_old='elif improvement_intent(text):\n            plan=improvement_plan(text,uid,cid)'
legacy_new='elif improvement_intent(text) and can_self_improve(uid):\n            plan=improvement_plan(text,uid,cid)'
supervisor_new='elif routed_intent=="self_improve" and can_self_improve(uid):\n            plan=improvement_plan(text,uid,cid)'
if legacy_old in s:
    s=s.replace(legacy_old,legacy_new,1)
elif legacy_new not in s and supervisor_new not in s:
    raise SystemExit('improvement creation anchor missing')

p.write_text(s)
print('owner guard integrated')
