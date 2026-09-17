from pathlib import Path
p=Path('app.py'); s=p.read_text()
s=s.replace('from intent_router import should_create_reminder, reminder_has_enough_context','from intent_router import should_create_reminder, reminder_has_enough_context, reminder_needs_timing',1)
needle='''            c.execute("CREATE INDEX IF NOT EXISTS reminders_due_idx ON reminders(status,next_run_at)")'''
replacement='''            c.execute("ALTER TABLE reminders ADD COLUMN IF NOT EXISTS explicit_opt_in BOOLEAN DEFAULT FALSE")
            # Kill every legacy reminder created before explicit opt-in existed.
            c.execute("UPDATE reminders SET status='cancelled',next_run_at=NULL,updated_at=NOW() WHERE status='active' AND COALESCE(explicit_opt_in,FALSE)=FALSE")
            c.execute("CREATE INDEX IF NOT EXISTS reminders_due_idx ON reminders(status,next_run_at)")'''
assert needle in s; s=s.replace(needle,replacement,1)
s=s.replace('''INSERT INTO reminders(conversation_id,target_id,creator_user_id,assignee,steps,interval_minutes,next_run_at)
                VALUES(%s,%s,%s,%s,%s::jsonb,%s,NOW()+(%s * INTERVAL '1 minute')) RETURNING id''','''INSERT INTO reminders(conversation_id,target_id,creator_user_id,assignee,steps,interval_minutes,next_run_at,explicit_opt_in)
                VALUES(%s,%s,%s,%s,%s::jsonb,%s,NOW()+(%s * INTERVAL '1 minute'),TRUE) RETURNING id''',1)
s=s.replace("WHERE status='active' AND next_run_at<=NOW() ORDER BY next_run_at LIMIT 20 FOR UPDATE SKIP LOCKED","WHERE status='active' AND explicit_opt_in=TRUE AND next_run_at<=NOW() ORDER BY next_run_at LIMIT 20 FOR UPDATE SKIP LOCKED",1)
s=s.replace('''        reminder_done=complete_member_reminder(cid,text)
        member_task=parse_member_task(text) if should_create_reminder(text) else None
        reminder_created=None
        if member_task and reminder_has_enough_context(text):''','''        reminder_done=complete_member_reminder(cid,text)
        reminder_timing_missing=reminder_needs_timing(text)
        member_task=parse_member_task(text) if reminder_has_enough_context(text) else None
        reminder_created=None
        if member_task:''',1)
s=s.replace('''        if reminder_done:
            ans=reminder_done
        elif reminder_created:''','''        if reminder_done:
            ans=reminder_done
        elif reminder_timing_missing:
            ans="リマインドする間隔を指定してね。例：『10分おきにリマインドして』"
        elif reminder_created:''',1)
p.write_text(s)
