from pathlib import Path
p=Path('app.py');s=p.read_text()
s=s.replace('from intent_router import classify_message, should_create_reminder, reminder_has_enough_context, reminder_needs_timing','from intent_router import classify_message, should_create_reminder, reminder_has_enough_context, reminder_needs_timing\nfrom multi_property_estimate import group_attachments, estimate_instruction',1)
needle='''            c.execute("CREATE INDEX IF NOT EXISTS reminders_due_idx ON reminders(status,next_run_at)")'''
repl=needle+'''\n            c.execute("""CREATE TABLE IF NOT EXISTS estimate_batch_items(\n              id BIGSERIAL PRIMARY KEY,conversation_id TEXT NOT NULL,user_id TEXT,\n              line_message_id TEXT UNIQUE,analysis TEXT NOT NULL,created_at TIMESTAMPTZ DEFAULT NOW())""")\n            c.execute("CREATE INDEX IF NOT EXISTS estimate_batch_conv ON estimate_batch_items(conversation_id,created_at DESC)")'''
assert needle in s;s=s.replace(needle,repl,1)
marker='''def line_target(e):'''
helpers='''def add_estimate_batch_item(cid,uid,mid,analysis):\n    try:\n        with db() as cn:\n            with cn.cursor() as c:c.execute("INSERT INTO estimate_batch_items(conversation_id,user_id,line_message_id,analysis) VALUES(%s,%s,%s,%s) ON CONFLICT(line_message_id) DO NOTHING",(cid,uid,mid,analysis))\n            cn.commit()\n    except Exception as x:print("estimate_batch_add",repr(x),flush=True)\n\ndef recent_estimate_batch(cid,minutes=15):\n    try:\n        with db() as cn:\n            with cn.cursor() as c:\n                c.execute("SELECT line_message_id,analysis FROM estimate_batch_items WHERE conversation_id=%s AND created_at>=NOW()-(%s * INTERVAL '1 minute') ORDER BY created_at",(cid,minutes))\n                return [{"line_message_id":r[0],"analysis":r[1]} for r in c.fetchall()]\n    except Exception as x:print("estimate_batch_recent",repr(x),flush=True);return []\n\ndef clear_estimate_batch(cid):\n    try:\n        with db() as cn:\n            with cn.cursor() as c:c.execute("DELETE FROM estimate_batch_items WHERE conversation_id=%s",(cid,))\n            cn.commit()\n    except Exception as x:print("estimate_batch_clear",repr(x),flush=True)\n\ndef is_batch_estimate_command(text):\n    return bool(re.search(r"(まとめて|一括|全部|複数).*(見積|初期費用)|(見積|初期費用).*(まとめて|一括|全部|複数)",(text or ''),re.I))\n\n'''+marker
assert marker in s;s=s.replace(marker,helpers,1)
old='''            save_image(cid,uid,mid,a)\n            label="PDF解析" if is_pdf else "画像解析"'''
new='''            save_image(cid,uid,mid,a)\n            add_estimate_batch_item(cid,uid,mid,a)\n            label="PDF解析" if is_pdf else "画像解析"'''
assert old in s;s=s.replace(old,new,1)
old2='''        reminder_done=complete_member_reminder(cid,text)\n        reminder_timing_missing=reminder_needs_timing(text)'''
new2='''        batch_answer=None\n        if is_batch_estimate_command(text):\n            items=recent_estimate_batch(cid)\n            if not items:\n                batch_answer="直近15分の見積資料が見つからないよ。PDFや画像をまとめて送ってから『ナミ、まとめて見積もり』と送ってね。"\n            else:\n                groups,ambiguous=group_attachments(items)\n                prompt,err=estimate_instruction(groups,ambiguous,text)\n                if err:batch_answer=err\n                elif prompt:\n                    batch_answer=ai(prompt,uid,cid)\n                    clear_estimate_batch(cid)\n        reminder_done=complete_member_reminder(cid,text)\n        reminder_timing_missing=reminder_needs_timing(text)'''
assert old2 in s;s=s.replace(old2,new2,1)
old3='''        if reminder_done:\n            ans=reminder_done'''
new3='''        if batch_answer:\n            ans=batch_answer\n        elif reminder_done:\n            ans=reminder_done'''
assert old3 in s;s=s.replace(old3,new3,1)
p.write_text(s)
