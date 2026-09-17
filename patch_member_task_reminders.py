from pathlib import Path
p=Path('app.py'); s=p.read_text()
s=s.replace('import os, re, json, base64, hashlib, hmac, requests, psycopg, ast, time','import os, re, json, base64, hashlib, hmac, requests, psycopg, ast, time, threading')
s=s.replace('from datetime import datetime','from datetime import datetime, timedelta')
needle='''            c.execute("CREATE INDEX IF NOT EXISTS tasks_open_idx ON tasks(status,due_date)")'''
insert='''            c.execute("CREATE INDEX IF NOT EXISTS tasks_open_idx ON tasks(status,due_date)")
            c.execute("""CREATE TABLE IF NOT EXISTS reminders(
              id BIGSERIAL PRIMARY KEY,conversation_id TEXT NOT NULL,target_id TEXT NOT NULL,
              creator_user_id TEXT,assignee TEXT NOT NULL,steps JSONB NOT NULL DEFAULT '[]'::jsonb,
              current_index INTEGER DEFAULT 0,interval_minutes INTEGER DEFAULT 10,
              next_run_at TIMESTAMPTZ,status TEXT DEFAULT 'active',last_error TEXT DEFAULT '',
              created_at TIMESTAMPTZ DEFAULT NOW(),updated_at TIMESTAMPTZ DEFAULT NOW())""")
            c.execute("CREATE INDEX IF NOT EXISTS reminders_due_idx ON reminders(status,next_run_at)")'''
assert needle in s;s=s.replace(needle,insert,1)
anchor='''def save_msg(eid,cid,uid,name,role,content,mtype="text",mid=None,qid=None):'''
helpers=r'''def line_target(e):
    src=e.get("source",{})
    return src.get("groupId") or src.get("roomId") or src.get("userId")

def push_line(target,text):
    if not TOKEN or not target:return False,"missing LINE token/target"
    try:
        r=requests.post("https://api.line.me/v2/bot/message/push",headers={"Authorization":"Bearer "+TOKEN,"Content-Type":"application/json"},json={"to":target,"messages":[{"type":"text","text":text[:4900]}]},timeout=15)
        return r.ok,("" if r.ok else f"LINE {r.status_code}: {r.text[:300]}")
    except Exception as x:return False,repr(x)

def parse_member_task(text):
    t=(text or "").strip()
    if not t or re.search(r"(ナミ|nami|なみ).*(お願い|やって|作って|確認)",t,re.I):return None
    interval=10
    mi=re.search(r"(\d+)\s*分おき",t)
    if mi: interval=max(1,int(mi.group(1)))
    m=re.search(r"(?:^|[\s、,])([^\s、,]{1,12})(?:タスク|[、,:：]\s*)(.+)",t)
    if not m:
        m=re.search(r"^([^\s、,]{1,12})[、,\s]+(.+?(?:お願い|やって|確認して|対応して|作って))$",t)
    if not m:return None
    assignee=m.group(1).lstrip("@").strip(); body=m.group(2).strip()
    body=re.sub(r"\d+\s*分おき.*$","",body).strip()
    body=re.sub(r"(?:お願い|やって|確認して|対応して|作って)[！!。]*$","",body).strip()
    steps=[x.strip(" ・→>、,") for x in re.split(r"\s*(?:→|>|、|,|\n)\s*|\s{2,}",body) if x.strip(" ・→>、,")]
    if len(steps)==1 and " " in body:
        cand=[x for x in body.split() if x]
        if 1 < len(cand) <= 8:steps=cand
    if not assignee or not steps:return None
    return assignee,steps,interval

def create_member_reminder(cid,target,uid,assignee,steps,interval):
    if not DB_URL or not target:return None
    try:
        with db() as cn:
            with cn.cursor() as c:
                c.execute("""INSERT INTO reminders(conversation_id,target_id,creator_user_id,assignee,steps,interval_minutes,next_run_at)
                VALUES(%s,%s,%s,%s,%s::jsonb,%s,NOW()+(%s * INTERVAL '1 minute')) RETURNING id""",
                (cid,target,uid,assignee,json.dumps(steps,ensure_ascii=False),interval,interval)); rid=c.fetchone()[0]
            cn.commit();return rid
    except Exception as x:print("create_member_reminder",repr(x),flush=True);return None

def complete_member_reminder(cid,text):
    if not DB_URL:return None
    if not re.search(r"(完了|終わった|できた|対応済み|済み)",text or ""):return None
    try:
        with db() as cn:
            with cn.cursor() as c:
                c.execute("""SELECT id,assignee,steps,current_index FROM reminders
                  WHERE conversation_id=%s AND status='active' ORDER BY created_at DESC LIMIT 1 FOR UPDATE""",(cid,)); r=c.fetchone()
                if not r:return None
                rid,assignee,steps,idx=r; steps=steps if isinstance(steps,list) else json.loads(steps)
                current=steps[idx] if idx<len(steps) else "タスク"
                # If the completion message names a different step, don't advance accidentally.
                named=[x for x in steps if x in text]
                if named and current not in text:return None
                if idx+1 < len(steps):
                    nxt=steps[idx+1]
                    c.execute("UPDATE reminders SET current_index=%s,next_run_at=NOW()+(interval_minutes*INTERVAL '1 minute'),updated_at=NOW() WHERE id=%s",(idx+1,rid))
                    msg=f"{current}の完了を確認。次は {assignee}：{nxt} です。完了報告までリマインドします。"
                else:
                    c.execute("UPDATE reminders SET status='completed',next_run_at=NULL,updated_at=NOW() WHERE id=%s",(rid,))
                    msg=f"{assignee}のタスク、すべて完了を確認しました。リマインドを停止します。"
            cn.commit();return msg
    except Exception as x:print("complete_member_reminder",repr(x),flush=True);return None

def reminder_loop():
    while True:
        try:
            if DB_URL:
                due=[]
                with db() as cn:
                    with cn.cursor() as c:
                        c.execute("""SELECT id,target_id,assignee,steps,current_index,interval_minutes FROM reminders
                          WHERE status='active' AND next_run_at<=NOW() ORDER BY next_run_at LIMIT 20 FOR UPDATE SKIP LOCKED""")
                        due=c.fetchall()
                        for rid,target,assignee,steps,idx,mins in due:
                            c.execute("UPDATE reminders SET next_run_at=NOW()+(%s*INTERVAL '1 minute'),updated_at=NOW() WHERE id=%s",(mins,rid))
                    cn.commit()
                for rid,target,assignee,steps,idx,mins in due:
                    steps=steps if isinstance(steps,list) else json.loads(steps); task=steps[idx] if idx<len(steps) else "タスク"
                    ok,err=push_line(target,f"【タスクリマインド】\n{assignee}：{task}\n完了したら「{task}完了」と報告してください。")
                    if not ok:
                        with db() as cn:
                            with cn.cursor() as c:c.execute("UPDATE reminders SET last_error=%s WHERE id=%s",(err,rid))
                            cn.commit()
        except Exception as x:print("reminder_loop",repr(x),flush=True)
        time.sleep(20)

def start_reminder_worker():
    if DB_URL and os.getenv("REMINDER_WORKER","true").lower()=="true":
        threading.Thread(target=reminder_loop,daemon=True,name="nami-reminders").start()

'''
assert anchor in s;s=s.replace(anchor,helpers+anchor,1)
needle2='''        quick_task=task_command(text,uid,cid)
        quick_doc=three_document_command(text,uid,cid,qid)'''
replace2='''        reminder_done=complete_member_reminder(cid,text)
        member_task=parse_member_task(text)
        reminder_created=None
        if member_task:
            assignee,steps,interval=member_task
            reminder_created=create_member_reminder(cid,line_target(e),uid,assignee,steps,interval)
        quick_task=task_command(text,uid,cid)
        quick_doc=three_document_command(text,uid,cid,qid)'''
assert needle2 in s;s=s.replace(needle2,replace2,1)
needle3='''        if quick_task:
            ans=quick_task
        elif quick_doc:'''
replace3='''        if reminder_done:
            ans=reminder_done
        elif reminder_created:
            assignee,steps,interval=member_task
            ans=f"{assignee}のタスクを登録しました。まず「{steps[0]}」を{interval}分おきに、完了報告があるまでリマインドします。"
        elif quick_task:
            ans=quick_task
        elif quick_doc:'''
assert needle3 in s;s=s.replace(needle3,replace3,1)
s=s.replace('''try:init_db()
except Exception as x:print("init_db",repr(x),flush=True)''','''try:
    init_db()
    start_reminder_worker()
except Exception as x:print("init_db",repr(x),flush=True)''')
p.write_text(s)
