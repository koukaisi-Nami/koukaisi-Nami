from pathlib import Path

p = Path('app.py')
s = p.read_text(encoding='utf-8')

old_intent = '''def improvement_intent(text):
    return bool(re.search(r"(改善して|直して|機能追加|できるようにして|アップデートして|改修して)",text or ""))'''
new_intent = '''def improvement_intent(text):
    # Explicit owner development instructions must never fall through to memory/chat.
    return bool(re.search(
        r"(機能改善|改善して|直して|修正して|機能追加|できるようにして|アップデートして|改修して|"
        r"コード.{0,24}(?:変更|修正|直|書き換)|(?:実装|追加)して|PR.{0,24}(?:作|作成))",
        text or "", re.I))'''
if old_intent not in s:
    raise SystemExit('improvement_intent anchor not found')
s = s.replace(old_intent, new_intent, 1)

old_learn = '''        save_msg(eid,cid,uid,nm,"user",text,"text",mid,qid)
        learn_important(text,uid,cid)

        if grouped(e) and not called(m):'''
new_learn = '''        save_msg(eid,cid,uid,nm,"user",text,"text",mid,qid)
        # Owner self-improvement is classified before durable learning. This prevents
        # code/PR instructions from being accidentally stored as personal/group memory.
        owner_self_improve = improvement_intent(text) and can_self_improve(uid)
        if not owner_self_improve:
            learn_important(text,uid,cid)

        if grouped(e) and not called(m):'''
if old_learn not in s:
    raise SystemExit('webhook learning anchor not found')
s = s.replace(old_learn, new_learn, 1)

old_route = '''        elif improvement_intent(text) and can_self_improve(uid):
            plan=improvement_plan(text,uid,cid)'''
new_route = '''        elif owner_self_improve:
            plan=improvement_plan(text,uid,cid)'''
if old_route not in s:
    raise SystemExit('self-improvement route anchor not found')
s = s.replace(old_route, new_route, 1)

p.write_text(s, encoding='utf-8')
print('patched app.py: owner self-improvement now precedes memory learning')
