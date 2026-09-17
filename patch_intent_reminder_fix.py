from pathlib import Path
p=Path('app.py');s=p.read_text()
if 'from intent_router import should_create_reminder, reminder_has_enough_context' not in s:
    s=s.replace('from functools import wraps\n','from functools import wraps\nfrom intent_router import should_create_reminder, reminder_has_enough_context\n',1)
old='''        reminder_done=complete_member_reminder(cid,text)
        member_task=parse_member_task(text)
        reminder_created=None
        if member_task:
            assignee,steps,interval=member_task
            reminder_created=create_member_reminder(cid,line_target(e),uid,assignee,steps,interval)'''
new='''        reminder_done=complete_member_reminder(cid,text)
        member_task=parse_member_task(text) if should_create_reminder(text) else None
        reminder_created=None
        if member_task and reminder_has_enough_context(text):
            assignee,steps,interval=member_task
            reminder_created=create_member_reminder(cid,line_target(e),uid,assignee,steps,interval)'''
assert old in s
s=s.replace(old,new,1)
p.write_text(s)
