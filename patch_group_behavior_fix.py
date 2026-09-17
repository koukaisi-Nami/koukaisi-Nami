from pathlib import Path
p=Path('app.py');s=p.read_text()
old='''        if grouped(e) and not called(m):
            proactive=manager_review(text,uid,cid)
            if proactive:
                save_msg("assistant:manager:"+eid,cid,"bot","航海士ナミ","assistant",proactive)
                reply(e.get("replyToken"),proactive)
            continue
'''
new='''        # Group safety: Nami is silent unless explicitly called/mentioned.
        # Do not run manager_review, reminders, tasks, learning commands or AI replies
        # on ordinary member chatter. This keeps group behavior predictable.
        if grouped(e) and not called(m):
            continue
'''
assert old in s
s=s.replace(old,new,1)
# In groups, an uploaded image/PDF is stored for later use but never produces an unsolicited reply.
# The existing media branch already has this behavior; keep it as an invariant.
p.write_text(s)
