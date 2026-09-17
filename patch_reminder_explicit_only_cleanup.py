from pathlib import Path
p=Path('app.py')
s=p.read_text()

s=s.replace('from intent_router import should_create_reminder, reminder_has_enough_context',
            'from intent_router import should_create_reminder, reminder_has_enough_context, reminder_needs_timing')

old='''            c.execute("CREATE INDEX IF NOT EXISTS reminders_due_idx ON reminders(status,next_run_at)")'''
new='''            c.execute("ALTER TABLE reminders ADD COLUMN IF NOT EXISTS explicit_opt_in BOOLEAN DEFAULT FALSE")
            # Legacy reminders were created by the old automatic detector. Disable them once.
            c.execute("UPDATE reminders SET status='cancelled',next_run_at=NULL,updated_at=NOW() WHERE status='active' AND explicit_opt_in=FALSE")
            c.execute("CREATE INDEX IF NOT EXISTS reminders_due_idx ON reminders(status,next_run_at)")'''
assert old in s
s=s.replace(old,new,1)

old='''                c.execute("""INSERT INTO reminders(conversation_id,target_id,creator_user_id,assignee,steps,interval_minutes,next_run_at)
                VALUES(%s,%s,%s,%s,%s::jsonb,%s,NOW()+(%s * INTERVAL '1 minute')) RETURNING id""",
                (cid,target,uid,assignee,json.dumps(steps,ensure_ascii=False),interval,interval)); rid=c.fetchone()[0]'''
new='''                c.execute("""INSERT INTO reminders(conversation_id,target_id,creator_user_id,assignee,steps,interval_minutes,next_run_at,explicit_opt_in)
                VALUES(%s,%s,%s,%s,%s::jsonb,%s,NOW()+(%s * INTERVAL '1 minute'),TRUE) RETURNING id""",
                (cid,target,uid,assignee,json.dumps(steps,ensure_ascii=False),interval,interval)); rid=c.fetchone()[0]'''
assert old in s
s=s.replace(old,new,1)

s=s.replace("WHERE status='active' AND next_run_at<=NOW() ORDER BY next_run_at LIMIT 20 FOR UPDATE SKIP LOCKED",
            "WHERE status='active' AND explicit_opt_in=TRUE AND next_run_at<=NOW() ORDER BY next_run_at LIMIT 20 FOR UPDATE SKIP LOCKED")

old='''        member_task=parse_member_task(text) if should_create_reminder(text) else None
        reminder_created=None
        if member_task and reminder_has_enough_context(text):
            assignee,steps,interval=member_task
            reminder_created=create_member_reminder(cid,line_target(e),uid,assignee,steps,interval)
        quick_task=task_command(text,uid,cid)'''
new='''        member_task=parse_member_task(text) if (should_create_reminder(text) and reminder_has_enough_context(text)) else None
        reminder_created=None
        reminder_timing_missing=reminder_needs_timing(text)
        if member_task:
            assignee,steps,interval=member_task
            reminder_created=create_member_reminder(cid,line_target(e),uid,assignee,steps,interval)
        quick_task=task_command(text,uid,cid)'''
assert old in s
s=s.replace(old,new,1)

old='''        if reminder_done:
            ans=reminder_done
        elif reminder_created:'''
new='''        if reminder_done:
            ans=reminder_done
        elif reminder_timing_missing:
            ans="リマインドする時間か間隔を指定してね。例：『10分おきにリマインドして』『明日10時に通知して』"
        elif reminder_created:'''
assert old in s
s=s.replace(old,new,1)

p.write_text(s)
