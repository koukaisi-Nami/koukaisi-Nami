import os, re, json, base64, hashlib, hmac, requests, psycopg, ast, time, threading
from io import BytesIO
from datetime import datetime, timedelta
from functools import wraps
from intent_router import should_create_reminder, reminder_has_enough_context, reminder_needs_timing, reminder_needs_timing
from flask import Flask, request, abort, Response, render_template_string, send_file
from estimate_document import make_estimate_document, make_estimate_image
from structured_estimate_runtime import generate_text as structured_estimate
from owner_guard import can_self_improve
from nami_supervisor import route_intent, line_scope, wants_company_memory, needs_supervisor_review, reviewer_instructions

app = Flask(__name__)
SECRET=os.getenv("LINE_CHANNEL_SECRET","")
TOKEN=os.getenv("LINE_CHANNEL_ACCESS_TOKEN","")
OPENAI_KEY=os.getenv("OPENAI_API_KEY","")
DB_URL=os.getenv("DATABASE_URL","")
MODEL=os.getenv("OPENAI_MODEL","gpt-5.6-luna")
OA="https://api.openai.com/v1/responses"
HTTP=requests.Session()

# LINE承認式の自己改善
GITHUB_TOKEN=os.getenv("GITHUB_TOKEN","")
GITHUB_REPO=os.getenv("GITHUB_REPO","")  # owner/repo
GITHUB_BRANCH=os.getenv("GITHUB_BRANCH","main")
GITHUB_APP_PATH=os.getenv("GITHUB_APP_PATH","app.py")
SELF_IMPROVE=os.getenv("SELF_IMPROVE","false").lower()=="true"
DASHBOARD_PASSWORD=os.getenv("NAMI_DASHBOARD_PASSWORD","")
CHAT_HISTORY_COUNT=6
MEMORY_CONTEXT_COUNT=5
SKILL_CONTEXT_COUNT=4

def db(): return psycopg.connect(DB_URL)

def init_db():
    if not DB_URL: return
    with db() as cn:
        with cn.cursor() as c:
            c.execute("""CREATE TABLE IF NOT EXISTS messages(
              id BIGSERIAL PRIMARY KEY,event_id TEXT UNIQUE,conversation_id TEXT NOT NULL,
              user_id TEXT,user_name TEXT,role TEXT NOT NULL,message_type TEXT DEFAULT 'text',
              content TEXT NOT NULL,line_message_id TEXT,quoted_message_id TEXT,
              created_at TIMESTAMPTZ DEFAULT NOW())""")
            # Safe migrations from older versions
            c.execute("ALTER TABLE messages ADD COLUMN IF NOT EXISTS event_id TEXT")
            c.execute("ALTER TABLE messages ADD COLUMN IF NOT EXISTS conversation_id TEXT")
            c.execute("ALTER TABLE messages ADD COLUMN IF NOT EXISTS user_id TEXT")
            c.execute("ALTER TABLE messages ADD COLUMN IF NOT EXISTS user_name TEXT")
            c.execute("ALTER TABLE messages ADD COLUMN IF NOT EXISTS role TEXT")
            c.execute("ALTER TABLE messages ADD COLUMN IF NOT EXISTS message_type TEXT DEFAULT 'text'")
            c.execute("ALTER TABLE messages ADD COLUMN IF NOT EXISTS line_message_id TEXT")
            c.execute("ALTER TABLE messages ADD COLUMN IF NOT EXISTS quoted_message_id TEXT")
            c.execute("""CREATE TABLE IF NOT EXISTS memories(
              id BIGSERIAL PRIMARY KEY,scope TEXT NOT NULL,scope_id TEXT NOT NULL,
              category TEXT DEFAULT 'general',subject TEXT DEFAULT '',content TEXT NOT NULL,
              created_by TEXT,created_at TIMESTAMPTZ DEFAULT NOW(),updated_at TIMESTAMPTZ DEFAULT NOW())""")
            # Older deployments used a smaller memories schema. Add columns before
            # creating indexes so a migration never stops the whole app startup.
            c.execute("ALTER TABLE memories ADD COLUMN IF NOT EXISTS scope TEXT DEFAULT 'user'")
            c.execute("ALTER TABLE memories ADD COLUMN IF NOT EXISTS scope_id TEXT DEFAULT ''")
            c.execute("ALTER TABLE memories ADD COLUMN IF NOT EXISTS category TEXT DEFAULT 'general'")
            c.execute("ALTER TABLE memories ADD COLUMN IF NOT EXISTS subject TEXT DEFAULT ''")
            c.execute("ALTER TABLE memories ADD COLUMN IF NOT EXISTS created_by TEXT")
            c.execute("ALTER TABLE memories ADD COLUMN IF NOT EXISTS updated_at TIMESTAMPTZ DEFAULT NOW()")
            c.execute("UPDATE memories SET scope='user' WHERE scope IS NULL")
            c.execute("UPDATE memories SET scope_id='' WHERE scope_id IS NULL")
            c.execute("""CREATE TABLE IF NOT EXISTS skills(
              id BIGSERIAL PRIMARY KEY,scope TEXT DEFAULT 'company',scope_id TEXT DEFAULT 'company',
              name TEXT NOT NULL,instructions TEXT NOT NULL,created_by TEXT,
              created_at TIMESTAMPTZ DEFAULT NOW(),updated_at TIMESTAMPTZ DEFAULT NOW())""")
            c.execute("ALTER TABLE skills ADD COLUMN IF NOT EXISTS scope TEXT DEFAULT 'company'")
            c.execute("ALTER TABLE skills ADD COLUMN IF NOT EXISTS scope_id TEXT DEFAULT 'company'")
            c.execute("ALTER TABLE skills ADD COLUMN IF NOT EXISTS created_by TEXT")
            c.execute("ALTER TABLE skills ADD COLUMN IF NOT EXISTS updated_at TIMESTAMPTZ DEFAULT NOW()")
            c.execute("""CREATE TABLE IF NOT EXISTS images(
              id BIGSERIAL PRIMARY KEY,conversation_id TEXT NOT NULL,user_id TEXT,
              line_message_id TEXT UNIQUE,analysis TEXT NOT NULL,created_at TIMESTAMPTZ DEFAULT NOW())""")
            c.execute("""CREATE TABLE IF NOT EXISTS improvement_requests(
              id BIGSERIAL PRIMARY KEY,conversation_id TEXT NOT NULL,user_id TEXT NOT NULL,
              request_text TEXT NOT NULL,status TEXT DEFAULT 'pending',
              plan TEXT DEFAULT '',created_at TIMESTAMPTZ DEFAULT NOW(),
              updated_at TIMESTAMPTZ DEFAULT NOW())""")
            c.execute("""CREATE TABLE IF NOT EXISTS manager_insights(
              id BIGSERIAL PRIMARY KEY,conversation_id TEXT NOT NULL,user_id TEXT,
              insight_type TEXT NOT NULL,severity INTEGER DEFAULT 1,
              summary TEXT NOT NULL,status TEXT DEFAULT 'open',
              created_at TIMESTAMPTZ DEFAULT NOW(),updated_at TIMESTAMPTZ DEFAULT NOW())""")
            c.execute("CREATE INDEX IF NOT EXISTS manager_insights_idx ON manager_insights(conversation_id,status,created_at DESC)")
            c.execute("ALTER TABLE improvement_requests ADD COLUMN IF NOT EXISTS pr_number INTEGER")
            c.execute("ALTER TABLE improvement_requests ADD COLUMN IF NOT EXISTS pr_url TEXT")
            # Indexes are deliberately last: the columns above now exist for both
            # fresh installs and upgrades from every earlier Nami version.
            c.execute("CREATE INDEX IF NOT EXISTS msg_conv ON messages(conversation_id,created_at DESC)")
            c.execute("CREATE INDEX IF NOT EXISTS msg_line_id ON messages(line_message_id)")
            c.execute("CREATE INDEX IF NOT EXISTS mem_scope ON memories(scope,scope_id,updated_at DESC)")
            c.execute("""CREATE TABLE IF NOT EXISTS cases(
              id BIGSERIAL PRIMARY KEY,client_name TEXT NOT NULL,assignee TEXT DEFAULT '',
              status TEXT DEFAULT 'ヒアリング中',budget TEXT DEFAULT '',area TEXT DEFAULT '',
              move_in TEXT DEFAULT '',notes TEXT DEFAULT '',next_action TEXT DEFAULT '',
              due_date DATE,created_at TIMESTAMPTZ DEFAULT NOW(),updated_at TIMESTAMPTZ DEFAULT NOW())""")
            c.execute("""CREATE TABLE IF NOT EXISTS tasks(
              id BIGSERIAL PRIMARY KEY,case_id BIGINT REFERENCES cases(id) ON DELETE CASCADE,
              title TEXT NOT NULL,status TEXT DEFAULT 'open',due_date DATE,
              created_at TIMESTAMPTZ DEFAULT NOW(),updated_at TIMESTAMPTZ DEFAULT NOW())""")
            # Preserve legacy task rows while making task actions available in LINE.
            c.execute("ALTER TABLE tasks ADD COLUMN IF NOT EXISTS conversation_id TEXT")
            c.execute("ALTER TABLE tasks ADD COLUMN IF NOT EXISTS user_id TEXT")
            c.execute("ALTER TABLE tasks ADD COLUMN IF NOT EXISTS due_date DATE")
            c.execute("ALTER TABLE tasks ADD COLUMN IF NOT EXISTS status TEXT DEFAULT 'open'")
            c.execute("ALTER TABLE tasks ADD COLUMN IF NOT EXISTS created_at TIMESTAMPTZ DEFAULT NOW()")
            c.execute("ALTER TABLE tasks ADD COLUMN IF NOT EXISTS updated_at TIMESTAMPTZ DEFAULT NOW()")
            c.execute("""CREATE TABLE IF NOT EXISTS manager_review_state(
              conversation_id TEXT PRIMARY KEY,last_checked_at TIMESTAMPTZ DEFAULT NOW())""")
            c.execute("CREATE INDEX IF NOT EXISTS cases_updated_idx ON cases(updated_at DESC)")
            c.execute("CREATE INDEX IF NOT EXISTS tasks_open_idx ON tasks(status,due_date)")
            c.execute("""CREATE TABLE IF NOT EXISTS reminders(
              id BIGSERIAL PRIMARY KEY,conversation_id TEXT NOT NULL,target_id TEXT NOT NULL,
              creator_user_id TEXT,assignee TEXT NOT NULL,steps JSONB NOT NULL DEFAULT '[]'::jsonb,
              current_index INTEGER DEFAULT 0,interval_minutes INTEGER DEFAULT 10,
              next_run_at TIMESTAMPTZ,status TEXT DEFAULT 'active',last_error TEXT DEFAULT '',
              created_at TIMESTAMPTZ DEFAULT NOW(),updated_at TIMESTAMPTZ DEFAULT NOW())""")
            c.execute("ALTER TABLE reminders ADD COLUMN IF NOT EXISTS explicit_opt_in BOOLEAN DEFAULT FALSE")
            # Kill every legacy reminder created before explicit opt-in existed.
            c.execute("UPDATE reminders SET status='cancelled',next_run_at=NULL,updated_at=NOW() WHERE status='active' AND COALESCE(explicit_opt_in,FALSE)=FALSE")
            c.execute("ALTER TABLE reminders ADD COLUMN IF NOT EXISTS explicit_opt_in BOOLEAN DEFAULT FALSE")
            # Kill every legacy reminder created before explicit opt-in existed.
            c.execute("UPDATE reminders SET status='cancelled',next_run_at=NULL,updated_at=NOW() WHERE status='active' AND COALESCE(explicit_opt_in,FALSE)=FALSE")
            c.execute("CREATE INDEX IF NOT EXISTS reminders_due_idx ON reminders(status,next_run_at)")
            c.execute("""CREATE TABLE IF NOT EXISTS line_members(
              conversation_id TEXT NOT NULL,user_id TEXT NOT NULL,display_name TEXT NOT NULL,
              updated_at TIMESTAMPTZ DEFAULT NOW(),PRIMARY KEY(conversation_id,user_id))""")
            c.execute("CREATE INDEX IF NOT EXISTS line_members_name_idx ON line_members(conversation_id,display_name)")
            c.execute("""CREATE TABLE IF NOT EXISTS estimate_batch_items(
              id BIGSERIAL PRIMARY KEY,conversation_id TEXT NOT NULL,user_id TEXT,
              line_message_id TEXT UNIQUE,analysis TEXT NOT NULL,created_at TIMESTAMPTZ DEFAULT NOW())""")
            c.execute("CREATE INDEX IF NOT EXISTS estimate_batch_conv ON estimate_batch_items(conversation_id,created_at DESC)")
        cn.commit()

def add_estimate_batch_item(cid,uid,mid,analysis):
    try:
        with db() as cn:
            with cn.cursor() as c:c.execute("INSERT INTO estimate_batch_items(conversation_id,user_id,line_message_id,analysis) VALUES(%s,%s,%s,%s) ON CONFLICT(line_message_id) DO NOTHING",(cid,uid,mid,analysis))
            cn.commit()
    except Exception as x:print("estimate_batch_add",repr(x),flush=True)

def recent_estimate_batch(cid,minutes=15):
    try:
        with db() as cn:
            with cn.cursor() as c:
                c.execute("SELECT line_message_id,analysis FROM estimate_batch_items WHERE conversation_id=%s AND created_at>=NOW()-(%s * INTERVAL '1 minute') ORDER BY created_at",(cid,minutes))
                return [{"line_message_id":r[0],"analysis":r[1]} for r in c.fetchall()]
    except Exception as x:print("estimate_batch_recent",repr(x),flush=True);return []

def clear_estimate_batch(cid):
    try:
        with db() as cn:
            with cn.cursor() as c:c.execute("DELETE FROM estimate_batch_items WHERE conversation_id=%s",(cid,))
            cn.commit()
    except Exception as x:print("estimate_batch_clear",repr(x),flush=True)

def group_attachments(items):
    """Split saved analyses into individual properties, including several sheets inside one image."""
    if not items:return [],True
    source='\n\n'.join(f"【資料{i+1}】\n{x.get('analysis','')}" for i,x in enumerate(items))
    prompt="""募集図面の読取結果を物件単位に完全分離する。1枚の画像内に複数の募集図面がある場合も必ず全物件を分ける。別物件の金額を混ぜない。JSONのみで返す。形式: {\"properties\":[{\"name\":\"物件名\",\"room\":\"号室\",\"address\":\"住所\",\"analysis\":\"その物件だけの賃料・管理費・敷礼・保証料・保険・鍵・サポート・その他費用等\"}]}。物件名不明でも賃料や間取り等から別図面と判断できれば別要素にする。推測で金額を補わない。"""
    try:
        payload={"model":MODEL,"instructions":prompt,"input":[{"role":"user","content":[{"type":"input_text","text":source[:12000]}]}],"max_output_tokens":2200}
        r=HTTP.post(OA,headers={"Authorization":f"Bearer {OPENAI_KEY}","Content-Type":"application/json"},json=payload,timeout=120)
        if not r.ok:raise RuntimeError(f"split {r.status_code}")
        d=r.json(); raw=d.get("output_text","")
        if not raw:
            vals=[]
            for out in d.get("output",[]):
                if out.get("type")=="message":
                    for z in out.get("content",[]):
                        if z.get("type") in ("output_text","text") and z.get("text"):vals.append(z["text"])
            raw='\n'.join(vals)
        raw=re.sub(r"^```(?:json)?\s*|\s*```$","",raw.strip())
        props=json.loads(raw).get("properties",[])
        groups=[]
        for prop in props:
            analysis=(prop.get("analysis") or '').strip()
            if not analysis:continue
            groups.append({"property":{"name":prop.get("name",''),"room":prop.get("room",''),"address":prop.get("address",'')},"attachments":[{"analysis":analysis}]})
        return groups,(len(groups)==0)
    except Exception as x:
        print("group_attachments",repr(x),flush=True)
        # Safe fallback: treat each uploaded attachment independently rather than mixing them.
        groups=[]
        for i,item in enumerate(items,1):
            groups.append({"property":{"name":f"{i}件目","room":"","address":""},"attachments":[item]})
        return groups,False

def is_batch_estimate_command(text):
    t=text or ''
    batch_word=r"(?:まとめて|一括|全部|全て|すべて|全物件|複数|[0-9０-９一二三四五六七八九十]+\s*(?:件|物件)(?:分)?)"
    return bool(re.search(batch_word+r".*(?:見積|初期費用)|(?:見積|初期費用).*"+batch_word,t,re.I))

def batch_artifact_marker(text):
    t=text or ''
    wants_image=bool(re.search(r"(?:画像|写真|PNG|イメージ)",t,re.I))
    wants_pdf=bool(re.search(r"PDF",t,re.I))
    if wants_image and wants_pdf:return "__ESTIMATE_BOTH__"
    if wants_pdf:return "__ESTIMATE_PDF__"
    if wants_image:return "__ESTIMATE_IMAGE__"
    return None

def send_batch_estimate_artifacts(reply_token,target,estimates,base,marker):
    if not estimates:return
    first_messages=[]
    for i,estimate in enumerate(estimates):
        estimate_text=estimate.get('text','') if isinstance(estimate,dict) else str(estimate)
        estimate_data=estimate.get('data') if isinstance(estimate,dict) else estimate
        key=hashlib.sha256((str(time.time())+str(i)+estimate_text).encode()).hexdigest()[:24]
        ESTIMATE_CACHE[key]=(time.time(),estimate_data)
        image_url=f"{base}/estimate-file/{key}.png"
        pdf_url=f"{base}/estimate-file/{key}.pdf"
        msgs=[]
        if marker in ("__ESTIMATE_IMAGE__","__ESTIMATE_BOTH__"):
            msgs.append({"type":"image","originalContentUrl":image_url,"previewImageUrl":image_url})
        if marker in ("__ESTIMATE_PDF__","__ESTIMATE_BOTH__"):
            msgs.append({"type":"text","text":"見積もり概算書PDFはこちら\n"+pdf_url})
        if i==0:first_messages.extend(msgs)
        else:
            for msg in msgs:
                try:HTTP.post("https://api.line.me/v2/bot/message/push",headers={"Authorization":"Bearer "+TOKEN,"Content-Type":"application/json"},json={"to":target,"messages":[msg]},timeout=20)
                except Exception as x:print("batch_artifact_push",repr(x),flush=True)
    if first_messages:
        try:HTTP.post("https://api.line.me/v2/bot/message/reply",headers={"Authorization":"Bearer "+TOKEN,"Content-Type":"application/json"},json={"replyToken":reply_token,"messages":first_messages[:5]},timeout=20)
        except Exception as x:print("batch_artifact_reply",repr(x),flush=True)

def line_target(e):
    src=e.get("source",{})
    return src.get("groupId") or src.get("roomId") or src.get("userId")

def remember_line_member(cid,uid,display_name):
    if not DB_URL or not cid or not uid or not display_name:return
    try:
        with db() as cn:
            with cn.cursor() as c:
                c.execute("""INSERT INTO line_members(conversation_id,user_id,display_name) VALUES(%s,%s,%s) ON CONFLICT(conversation_id,user_id) DO UPDATE SET display_name=EXCLUDED.display_name,updated_at=NOW()""",(cid,uid,display_name))
            cn.commit()
    except Exception as x:print("remember_line_member",repr(x),flush=True)

def find_line_member(cid,name):
    if not DB_URL or not cid or not name:return None
    wanted=name.lstrip('@').strip()
    try:
        with db() as cn:
            with cn.cursor() as c:
                c.execute("SELECT user_id,display_name FROM line_members WHERE conversation_id=%s ORDER BY updated_at DESC",(cid,)); rows=c.fetchall()
        exact=[r for r in rows if r[1]==wanted]; partial=[r for r in rows if wanted.lower() in (r[1] or '').lower()]
        return (exact or partial or [None])[0]
    except Exception as x:print("find_line_member",repr(x),flush=True);return None

def push_line_mention(target,prefix,user_id,display_name,suffix=''):
    if not TOKEN or not target:return False,"missing LINE token/target"
    mention='@'+display_name; text=(prefix or '')+mention+(suffix or ''); start=len(prefix or '')
    msg={"type":"text","text":text,"mention":{"mentionees":[{"index":start,"length":len(mention),"type":"user","userId":user_id}]}}
    try:
        r=HTTP.post("https://api.line.me/v2/bot/message/push",headers={"Authorization":"Bearer "+TOKEN,"Content-Type":"application/json"},json={"to":target,"messages":[msg]},timeout=15)
        return r.ok,("" if r.ok else f"LINE {r.status_code}: {r.text[:300]}")
    except Exception as x:return False,repr(x)

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
                c.execute("""INSERT INTO reminders(conversation_id,target_id,creator_user_id,assignee,steps,interval_minutes,next_run_at,explicit_opt_in)
                VALUES(%s,%s,%s,%s,%s::jsonb,%s,NOW()+(%s * INTERVAL '1 minute'),TRUE) RETURNING id""",
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
                          WHERE status='active' AND explicit_opt_in=TRUE AND next_run_at<=NOW() ORDER BY next_run_at LIMIT 20 FOR UPDATE SKIP LOCKED""")
                        due=c.fetchall()
                        for rid,target,assignee,steps,idx,mins in due:
                            c.execute("UPDATE reminders SET next_run_at=NOW()+(%s*INTERVAL '1 minute'),updated_at=NOW() WHERE id=%s",(mins,rid))
                    cn.commit()
                for rid,target,assignee,steps,idx,mins in due:
                    steps=steps if isinstance(steps,list) else json.loads(steps); task=steps[idx] if idx<len(steps) else "タスク"
                    member=find_line_member(target,assignee)
                    suffix=f"：{task}\n完了したら「{task}完了」と報告してください。"
                    if member:
                        ok,err=push_line_mention(target,"【タスクリマインド】\n",member[0],member[1],suffix)
                    else:
                        ok,err=push_line(target,f"【タスクリマインド】\n{assignee}{suffix}")
                    if not ok:
                        with db() as cn:
                            with cn.cursor() as c:c.execute("UPDATE reminders SET last_error=%s WHERE id=%s",(err,rid))
                            cn.commit()
        except Exception as x:print("reminder_loop",repr(x),flush=True)
        time.sleep(20)

def start_reminder_worker():
    if DB_URL and os.getenv("REMINDER_WORKER","true").lower()=="true":
        threading.Thread(target=reminder_loop,daemon=True,name="nami-reminders").start()

def save_msg(eid,cid,uid,name,role,content,mtype="text",mid=None,qid=None):
    if not DB_URL or not content:return
    try:
        with db() as cn:
            with cn.cursor() as c:
                c.execute("""INSERT INTO messages(event_id,conversation_id,user_id,user_name,role,
                message_type,content,line_message_id,quoted_message_id)
                VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s) ON CONFLICT DO NOTHING""",
                (eid,cid,uid,name,role,mtype,content,mid,qid))
            cn.commit()
    except Exception as x: print("save_msg",repr(x),flush=True)

def save_image(cid,uid,mid,analysis):
    try:
        with db() as cn:
            with cn.cursor() as c:
                c.execute("""INSERT INTO images(conversation_id,user_id,line_message_id,analysis)
                VALUES(%s,%s,%s,%s) ON CONFLICT(line_message_id) DO UPDATE SET analysis=EXCLUDED.analysis""",
                (cid,uid,mid,analysis))
            cn.commit()
    except Exception as x: print("save_image",repr(x),flush=True)

def image_analysis(cid,mid=None):
    if not DB_URL:return None
    try:
        with db() as cn:
            with cn.cursor() as c:
                if mid:
                    c.execute("SELECT analysis FROM images WHERE conversation_id=%s AND line_message_id=%s LIMIT 1",(cid,mid))
                else:
                    c.execute("SELECT analysis FROM images WHERE conversation_id=%s ORDER BY created_at DESC LIMIT 1",(cid,))
                r=c.fetchone()
                return r[0] if r else None
    except Exception as x: print("image_analysis",repr(x),flush=True); return None

def history(cid,n=CHAT_HISTORY_COUNT):
    try:
        with db() as cn:
            with cn.cursor() as c:
                c.execute("""SELECT role,user_name,content FROM messages WHERE conversation_id=%s
                ORDER BY created_at DESC LIMIT %s""",(cid,n)); rows=c.fetchall()
        return list(reversed(rows))
    except: return []

def add_memory(scope,sid,cat,subject,content,uid):
    content=(content or "").strip()
    if not content.strip():
        return
    if scope not in ("user","conversation","company"):
        return
    sid="company" if scope=="company" else str(sid)
    try:
        with db() as cn:
            with cn.cursor() as c:
                c.execute("""SELECT id FROM memories WHERE scope=%s AND scope_id=%s
                AND lower(content)=lower(%s) LIMIT 1""",(scope,sid,content))
                if not c.fetchone():
                    c.execute("""INSERT INTO memories(scope,scope_id,category,subject,content,created_by)
                    VALUES(%s,%s,%s,%s,%s,%s)""",(scope,sid,cat,(subject or "").strip(),content,uid))
            cn.commit()
    except Exception as x:
        print("add_memory",repr(x),flush=True)

def memory_terms(text):
    raw=(text or "").lower(); terms=[]
    for word in re.findall(r"[a-z0-9_-]{2,}|[ぁ-んァ-ヶ一-龠]{2,}",raw):
        if word not in ("これ","それ","あれ","こと","ため","ので","です","ます","ナミ"): terms.append(word[:40])
    for word in ("見積","請求","物件","賃貸","入居","申込","審査","契約","鍵","保証","家賃","タスク","顧客","追客","図面","写真","会社"):
        if word in raw: terms.append(word)
    return list(dict.fromkeys(terms))[:12]

def mems(uid,cid,query="",limit=MEMORY_CONTEXT_COUNT):
    """Keep all memories in PostgreSQL and select a relevant working set."""
    try:
        with db() as cn:
            with cn.cursor() as c:
                c.execute("""SELECT scope,category,subject,content FROM memories WHERE
                (scope='user' AND scope_id=%s) OR (scope='conversation' AND scope_id=%s)
                OR (scope='company' AND scope_id='company')
                ORDER BY updated_at DESC LIMIT 160""",(str(uid),str(cid)))
                rows=c.fetchall()
        terms=[str(x).lower() for x in memory_terms(query) if str(x).strip()]
        def score(row):
            scope,category,subject,content=row
            subject=str(subject or "")
            hay=" ".join(str(x or "") for x in (category,subject,content)).lower()
            hits=sum((8 if term in subject.lower() else 3) for term in terms if term in hay)
            return hits+{"conversation":2,"user":1,"company":0}.get(scope,0)
        ranked=sorted(rows,key=score,reverse=True)
        relevant=[r for r in ranked if score(r)>2]
        return (relevant+[r for r in ranked if r not in relevant])[:max(1,int(limit))]
    except Exception:
        return []

def add_skill(name,body,uid):
    try:
        with db() as cn:
            with cn.cursor() as c:
                c.execute("INSERT INTO skills(scope,scope_id,name,instructions,created_by) VALUES('company','company',%s,%s,%s)",
                          (name[:120],body.strip(),uid))
            cn.commit()
    except Exception as x: print("skill",repr(x),flush=True)

def skill_rows(query="",limit=SKILL_CONTEXT_COUNT):
    try:
        with db() as cn:
            with cn.cursor() as c:
                c.execute("SELECT name,instructions FROM skills WHERE scope='company' ORDER BY updated_at DESC LIMIT 80")
                rows=c.fetchall()
        terms=memory_terms(query)
        return sorted(rows,key=lambda row:sum(5 for term in terms if term in (row[0]+" "+row[1]).lower()),reverse=True)[:limit]
    except:return []


def add_improvement(cid,uid,request_text,plan):
    try:
        with db() as cn:
            with cn.cursor() as c:
                c.execute("""INSERT INTO improvement_requests(conversation_id,user_id,request_text,status,plan)
                VALUES(%s,%s,%s,'pending',%s) RETURNING id""",(cid,uid,request_text,plan))
                rid=c.fetchone()[0]
            cn.commit()
        return rid
    except Exception as x:
        print("improvement",repr(x),flush=True); return None

def latest_pending_improvement(cid,uid):
    try:
        with db() as cn:
            with cn.cursor() as c:
                c.execute("""SELECT id,request_text,plan FROM improvement_requests
                WHERE conversation_id=%s AND user_id=%s AND status='pending'
                ORDER BY created_at DESC LIMIT 1""",(cid,uid))
                return c.fetchone()
    except:return None

def set_improvement_status(rid,status):
    try:
        with db() as cn:
            with cn.cursor() as c:
                c.execute("""UPDATE improvement_requests SET status=%s,updated_at=NOW() WHERE id=%s""",(status,rid))
            cn.commit()
    except Exception as x: print("improvement_status",repr(x),flush=True)


CORE_GUARDS=[
 "CREATE TABLE IF NOT EXISTS messages","CREATE TABLE IF NOT EXISTS memories",
 "CREATE TABLE IF NOT EXISTS skills","CREATE TABLE IF NOT EXISTS images",
 "CREATE TABLE IF NOT EXISTS improvement_requests","CREATE TABLE IF NOT EXISTS manager_insights",
 "def called(","if grouped(e) and not called(m):","def learn_important(",
 "def manager_review(","web_search","quotedMessageId","def analyze(",
 "見積","請求書","不動産賃貸仲介営業マン","def improvement_intent(",
 '@app.post("/webhook")'
]

def github_ready():
    return SELF_IMPROVE and bool(GITHUB_TOKEN and GITHUB_REPO)

def gh_headers():
    return {"Authorization":f"Bearer {GITHUB_TOKEN}",
            "Accept":"application/vnd.github+json",
            "X-GitHub-Api-Version":"2022-11-28"}

def gh(method,path,**kwargs):
    r=requests.request(method,f"https://api.github.com/repos/{GITHUB_REPO}{path}",
                       headers=gh_headers(),timeout=45,**kwargs)
    if not r.ok:
        request_id=r.headers.get("x-github-request-id","")
        print("GITHUB_ERROR", {"method":method,"path":path,"status":r.status_code,
              "request_id":request_id,"body":r.text[:2000]}, flush=True)
    return r

def gh_fail(label,r):
    request_id=r.headers.get("x-github-request-id","")
    try:
        d=r.json(); detail=d.get("message") or r.text[:500]
    except Exception:
        detail=r.text[:500]
    raise RuntimeError(f"{label}: GitHub {r.status_code} {detail} request_id={request_id}")

def repo_file(path=GITHUB_APP_PATH,ref=None):
    r=gh("GET",f"/contents/{path}",params={"ref":ref or GITHUB_BRANCH})
    if not r.ok: gh_fail("GitHub read failed",r)
    d=r.json()
    return base64.b64decode(d["content"]).decode(),d["sha"]

def validate_candidate(src):
    errors=[]
    try: ast.parse(src)
    except SyntaxError as e: errors.append("Python syntax: "+str(e))
    for g in CORE_GUARDS:
        if g not in src: errors.append("必須機能欠落: "+g)
    if len(src)<15000: errors.append("コード量が異常に小さい")
    # no obvious embedded credentials
    if re.search(r'(sk-[A-Za-z0-9_-]{20,}|gh[pousr]_[A-Za-z0-9]{20,})',src):
        errors.append("秘密鍵らしき文字列を検出")
    return errors

def improvement_targets(req_text,src):
    """Select only the functions relevant to an approved self-improvement."""
    text=(req_text or "").lower()
    groups=[
      (("記憶","覚え","学習","メンバー","人","プロフィール"),
       ["add_memory","mems","ctx","learn_important","explicit_learning"]),
      (("返信","line","グループ","メンション","呼びかけ"),
       ["called","reply","webhook","manager_review"]),
      (("画像","図面","写真"),["content","image_analysis","analyze","webhook"]),
      (("見積","請求","物件","賃貸","審査","契約"),["ai","analyze","manager_review","webhook"]),
      (("自己改善","コード","github","pr"),
       ["improvement_intent","improvement_plan","codegen_improvement","create_pr","merge_pr"]),
      (("db","データベース","postgres","保存"),["init_db","save_msg","save_image","history"]),
    ]
    names=[]
    for words,funcs in groups:
        if any(w in text for w in words): names.extend(funcs)
    if not names: names=["ai","ctx","webhook"]
    tree=ast.parse(src); lines=src.splitlines(keepends=True); found={}
    for node in tree.body:
        if isinstance(node,(ast.FunctionDef,ast.AsyncFunctionDef)) and node.name in names:
            found[node.name]="".join(lines[node.lineno-1:node.end_lineno])
    ordered={name:found[name] for name in dict.fromkeys(names) if name in found}
    return dict(list(ordered.items())[:6])

def targeted_candidate(req_text,current):
    targets=improvement_targets(req_text,current)
    if not targets: raise RuntimeError("対象機能を特定できなかった")
    instruction="""本番稼働中のLINE Bot『航海士ナミ』を安全に部分改修する。
渡された関数だけを変更対象にし、それ以外の機能・記憶・DBデータは絶対に削除しない。
秘密情報をコードへ埋め込まない。DB変更は後方互換のALTER/CREATE IF NOT EXISTSを使う。
出力はJSONのみ。形式は {"replacements":[{"function":"関数名","new":"その関数を丸ごと置換するPythonコード"}],"summary":"短い説明"}。
変更不要な関数はreplacementsに含めない。functionは渡された関数名だけに限る。
"""
    selected="\n\n".join(f"【{name}】\n{body}" for name,body in targets.items())
    payload={"model":MODEL,"instructions":instruction,
      "input":[{"role":"user","content":[{"type":"input_text","text":
        "【改修要求】\n"+req_text+"\n\n【変更可能な関数だけ】\n"+selected}]}]}
    r=requests.post(OA,headers={"Authorization":f"Bearer {OPENAI_KEY}","Content-Type":"application/json"},
                    json=payload,timeout=180)
    if not r.ok: raise RuntimeError(f"AI codegen failed {r.status_code}")
    d=r.json(); out=d.get("output_text","")
    if not out:
        xs=[]
        for item in d.get("output",[]):
            if item.get("type")=="message":
                for z in item.get("content",[]):
                    if z.get("type")=="output_text": xs.append(z.get("text",""))
        out="\n".join(xs)
    out=re.sub(r"^```(?:json)?\s*|\s*```$","",out.strip())
    try: data=json.loads(out)
    except json.JSONDecodeError as x: raise RuntimeError("部分改修のJSONが不正: "+str(x))
    replacements=data.get("replacements",[])
    if not replacements: raise RuntimeError("変更内容が返されなかった")
    candidate=current
    for item in replacements:
        name=item.get("function",""); new=item.get("new","").strip()
        old=targets.get(name)
        if not old or not new.startswith("def "+name+"("):
            raise RuntimeError("許可外の関数変更を検出")
        if candidate.count(old)!=1:
            raise RuntimeError("変更元関数を安全に特定できなかった")
        candidate=candidate.replace(old,new+"\n",1)
    return candidate

def codegen_improvement(req_text,uid,cid):
    current,_=repo_file()
    return targeted_candidate(req_text,current)

def create_pr(req_text):
    candidate=codegen_improvement(req_text,"system","system")
    errors=validate_candidate(candidate)
    if errors:return None,"安全チェック停止:\n- "+"\n- ".join(errors[:15])
    current,base_sha=repo_file()
    ref=gh("GET",f"/git/ref/heads/{GITHUB_BRANCH}")
    if not ref.ok: gh_fail("base branch read failed",ref)
    branch=f"nami/improve-{int(time.time())}"
    r=gh("POST","/git/refs",json={"ref":f"refs/heads/{branch}","sha":ref.json()["object"]["sha"]})
    if not r.ok: gh_fail("branch create failed",r)
    r=gh("PUT",f"/contents/{GITHUB_APP_PATH}",json={
      "message":"Nami approved improvement candidate",
      "content":base64.b64encode(candidate.encode()).decode(),
      "sha":base_sha,"branch":branch})
    if not r.ok: gh_fail("candidate commit failed",r)
    r=gh("POST","/pulls",json={"title":"航海士ナミ 自己改善",
      "head":branch,"base":GITHUB_BRANCH,
      "body":"LINEから作成した改善候補。必須機能ガード済み。船長のLINE承認後のみマージ。"})
    if not r.ok: gh_fail("PR create failed",r)
    d=r.json()
    return (d["number"],d["html_url"]),None

def attach_pr(rid,num,url):
    with db() as cn:
        with cn.cursor() as c:
            c.execute("""UPDATE improvement_requests SET pr_number=%s,pr_url=%s,
            status='awaiting_approval',updated_at=NOW() WHERE id=%s""",(num,url,rid))
        cn.commit()

def latest_awaiting(cid,uid):
    try:
        with db() as cn:
            with cn.cursor() as c:
                c.execute("""SELECT id,request_text,pr_number,pr_url FROM improvement_requests
                WHERE conversation_id=%s AND user_id=%s AND status='awaiting_approval'
                ORDER BY created_at DESC LIMIT 1""",(cid,uid))
                return c.fetchone()
    except:return None

def merge_pr(num):
    # Re-read candidate and run guards again immediately before merge.
    pr=gh("GET",f"/pulls/{num}")
    if not pr.ok:
        print("GITHUB_MERGE_READ_ERROR",pr.status_code,pr.text[:2000],flush=True)
        return False,f"PRを取得できなかった (GitHub {pr.status_code})"
    head=pr.json()["head"]["ref"]
    candidate,_=repo_file(GITHUB_APP_PATH,head)
    errors=validate_candidate(candidate)
    if errors:return False,"反映直前チェックで停止:\n- "+"\n- ".join(errors[:15])
    r=gh("PUT",f"/pulls/{num}/merge",json={"merge_method":"squash",
      "commit_title":f"航海士ナミ 自己改善 #{num}"})
    if not r.ok:
        print("GITHUB_MERGE_ERROR",r.status_code,r.text[:2000],flush=True)
        return False,f"GitHubマージに失敗 (GitHub {r.status_code})。現行本番は維持したよ。"
    return True,"反映したよ🧭 RenderのAuto-DeployがONなら自動デプロイが始まる。"


def improvement_intent(text):
    return bool(re.search(r"(改善して|直して|機能追加|できるようにして|アップデートして|改修して)",text or ""))

def improvement_plan(text,uid,cid):
    prompt="""これは航海士ナミ自身への機能改善要求です。
要求を、既存機能を壊さない前提で短い実装計画にしてください。
必ず「維持する機能」「追加/修正内容」「テスト項目」「必要な追加設定」を含める。
本番コードを勝手に変更したとは言わない。承認後に開発変更へ進む前提で書く。
要求: """+text
    return ai(prompt,uid,cid)

def ids(e):
    s=e.get("source",{}); uid=s.get("userId","unknown")
    if s.get("type")=="group":cid="group:"+s.get("groupId","unknown")
    elif s.get("type")=="room":cid="room:"+s.get("roomId","unknown")
    else:cid="user:"+uid
    return cid,uid

def grouped(e):return e.get("source",{}).get("type") in ("group","room")

PROFILE_CACHE={}
def name(e):
    s=e.get("source",{}); uid=s.get("userId")
    if not uid:return "ユーザー"
    now=time.time(); cached=PROFILE_CACHE.get(uid)
    if cached and now-cached[0] < 600:return cached[1]
    try:
        h={"Authorization":f"Bearer {TOKEN}"}
        if s.get("type")=="group":u=f"https://api.line.me/v2/bot/group/{s['groupId']}/member/{uid}"
        elif s.get("type")=="room":u=f"https://api.line.me/v2/bot/room/{s['roomId']}/member/{uid}"
        else:u=f"https://api.line.me/v2/bot/profile/{uid}"
        r=HTTP.get(u,headers=h,timeout=5)
        result=r.json().get("displayName","ユーザー") if r.ok else "ユーザー"
        PROFILE_CACHE[uid]=(now,result)
        if len(PROFILE_CACHE)>500: PROFILE_CACHE.clear()
        return result
    except:return cached[1] if cached else "ユーザー"

def called(m):
    if re.search(r"(ナミ|なみ|nami)",m.get("text",""),re.I):return True
    return any(x.get("isSelf") is True for x in m.get("mention",{}).get("mentionees",[]))

def reply(tok,text):
    if isinstance(text,(list,tuple)):
        chunks=[str(x).strip()[:4900] for x in text if str(x).strip()][:5]
    else:
        chunks=[str(text)[i:i+4900] for i in range(0,len(str(text)),4900)][:5]
    try:
        r=HTTP.post("https://api.line.me/v2/bot/message/reply",
          headers={"Authorization":f"Bearer {TOKEN}","Content-Type":"application/json"},
          json={"replyToken":tok,"messages":[{"type":"text","text":x} for x in chunks]},timeout=30)
        if not r.ok:
            print("LINE reply",r.status_code,r.text[:1000],flush=True)
        return r.ok
    except Exception as x:
        print("LINE reply",repr(x),flush=True)
        return False

def content(mid):
    r=HTTP.get(f"https://api-data.line.me/v2/bot/message/{mid}/content",
      headers={"Authorization":f"Bearer {TOKEN}"},timeout=40)
    return (r.content,r.headers.get("Content-Type","application/octet-stream")) if r.ok else (None,None)

def media_ai(blob,mime,uid,cid,question=""):
    q=(question or "").strip() or "この資料を詳細に読み取ってください。"
    if mime and "pdf" in mime.lower():
        parts=[{"type":"input_text","text":ctx(uid,cid,q)+"\n【今回】\n"+q[:3000]}, {"type":"input_file","filename":"document.pdf","file_data":"data:application/pdf;base64,"+base64.b64encode(blob).decode()}]
        payload={"model":MODEL,"instructions":SYSTEM,"input":[{"role":"user","content":parts}],"max_output_tokens":1200}
        try:
            r=HTTP.post(OA,headers={"Authorization":f"Bearer {OPENAI_KEY}","Content-Type":"application/json"},json=payload,timeout=150)
            if not r.ok: print("OPENAI_MEDIA",r.status_code,r.text[:2000],flush=True); return f"PDF解析エラー({r.status_code})"
            d=r.json(); out=d.get("output_text","")
            if not out:
                vals=[]
                for i in d.get("output",[]):
                    if i.get("type")=="message":
                        for z in i.get("content",[]):
                            if z.get("type")=="output_text": vals.append(z.get("text",""))
                out="\n".join(vals)
            return out.strip() or "PDFを読み取れなかったよ。"
        except Exception as x: print("media_ai_pdf",repr(x),flush=True); return "PDF解析で接続エラー"
    return ai(q,uid,cid,img=blob,mime=mime)

SYSTEM="""あなたは航海士ナミ。優秀な日本の不動産賃貸仲介営業マン兼営業事務。
ヒアリング、物件提案、図面読解、初期費用見積、申込、審査、保証会社、必要書類、重説・契約・鍵渡し、
顧客フォロー、営業LINE、請求書整理に強い。
グループごとの履歴、発言者ごとの記憶、会社から教わった業務ルールを混同せず利用する。
最新情報・天気・ニュース・会社・店舗・相場・現在の制度など現在性が必要ならweb_searchを使う。
図面の不鮮明/未記載項目や金額を推測しない。必ず「要確認」。
見積は賃料、管理費、日割り、前家賃、敷金、礼金、保証料、保険、鍵、仲介手数料、その他を分離し、
初回/月額、税込/税別、必須/任意を混同しない。会社独自ルールは保存済みskillsを優先。
引用された画像や直近画像の解析が文脈にあれば「この画像」として利用する。
ユーザーが普通の会話で明確に自己情報・顧客条件・会社知識を述べた場合も文脈として活用する。
法令・審査・税務等の重要事項は不確かな断定をしない。LINE向けに簡潔、成果物は整理して答える。

【営業部長モード】
普段の会話から、顧客条件の聞き漏れ、追客漏れ、見積の不足、申込/審査/契約の次アクション、
失注リスク、管理会社確認事項、営業文面の改善余地、社内ルールとの不整合を発見する。
ただし雑談や軽微なことには割り込まない。自発発言は「今すぐ対応価値が高い」場合だけ。
指摘は責めずに、事実→理由→具体的な次アクションの順で短く伝える。
過去の成約/失注/顧客反応から再利用できる知見は業務学習候補として扱う。
新機能が有効そうなら提案はできるが、本番コードの変更は必ず承認フローを通す。"""

def ctx(uid,cid,query="",extra=""):
    # The complete record stays in PostgreSQL; only relevant context enters this request.
    h="\n".join(f"{'ナミ' if r=='assistant' else (n or 'ユーザー')}: {x[:700]}" for r,n,x in history(cid))
    m="\n".join(f"- [{s}/{cat}/{sub}] {x[:700]}" for s,cat,sub,x in mems(uid,cid,query))
    sk="\n".join(f"- 【{n}】{x[:900]}" for n,x in skill_rows(query))
    return f"【トーク履歴】\n{h or 'なし'}\n【長期記憶】\n{m or 'なし'}\n【会社ルール】\n{sk or 'なし'}\n{extra}"

def format_retry(text):
    m=re.search(r"try again in\s+([0-9]+)m(?:([0-9.]+)s)?",text or "",re.I)
    if m:return f"約{m.group(1)}分"
    m=re.search(r"try again in\s+([0-9.]+)s",text or "",re.I)
    return f"約{max(1,round(float(m.group(1))))}秒" if m else "少し"

def ai(text,uid,cid,img=None,mime=None,extra=""):
    started=time.perf_counter()

    def finish(value):
        value=str(value or "").strip()
        return value if value.endswith("⚓️") else value+"⚓️"

    parts=[{"type":"input_text","text":ctx(uid,cid,text,extra)+"\n【今回】\n"+text[:4000]}]
    if img:
        parts.append({"type":"input_image","image_url":f"data:{mime or 'image/jpeg'};base64,{base64.b64encode(img).decode()}","detail":"high"})
    needs_web=bool(re.search(r"(最新|今日|現在|ニュース|天気|相場|営業時間|公式|検索して|調べて|web|ネット)",text or "",re.I))
    payload={"model":MODEL,"instructions":SYSTEM,"input":[{"role":"user","content":parts}],"max_output_tokens":900}
    if needs_web:
        payload["tools"]=[{"type":"web_search"}]
        payload["tool_choice"]="auto"
    try:
        r=HTTP.post(OA,headers={"Authorization":f"Bearer {OPENAI_KEY}","Content-Type":"application/json"},json=payload,timeout=90)
        if not r.ok:
            print("OPENAI",r.status_code,r.text,flush=True)
            if r.status_code==429:
                return finish(f"AIが混み合ってるよ🧭 上限回復まで{format_retry(r.text)}。少し時間をあけてもう一度送って。")
            return finish(f"AIエラー({r.status_code})")
        d=r.json()
        if d.get("output_text"):
            print("LATENCY_AI_MS",round((time.perf_counter()-started)*1000),flush=True)
            return finish(d["output_text"])
        out=[]
        for i in d.get("output",[]):
            if i.get("type")=="message":
                for z in i.get("content",[]):
                    if z.get("type") in ("output_text","text") and z.get("text"):
                        out.append(z.get("text",""))
        answer="\n".join(out).strip()
        if answer:
            print("LATENCY_AI_MS",round((time.perf_counter()-started)*1000),flush=True)
            return finish(answer)
        print("OPENAI_EMPTY",{"status":d.get("status",""),"incomplete":d.get("incomplete_details") or {}},flush=True)
        retry=dict(payload)
        retry.pop("tools",None)
        retry.pop("tool_choice",None)
        retry["max_output_tokens"]=1600 if img else 1200
        rr=HTTP.post(OA,headers={"Authorization":f"Bearer {OPENAI_KEY}","Content-Type":"application/json"},json=retry,timeout=120)
        if not rr.ok:
            print("OPENAI_RETRY",rr.status_code,rr.text[:2000],flush=True)
            return finish(f"AIエラー({rr.status_code})")
        dd=rr.json()
        if dd.get("output_text"):
            return finish(dd["output_text"])
        vals=[]
        for i in dd.get("output",[]):
            if i.get("type")=="message":
                for z in i.get("content",[]):
                    if z.get("type") in ("output_text","text") and z.get("text"):
                        vals.append(z.get("text",""))
        return finish("\n".join(vals).strip() or "資料は受け取れたけど回答生成に失敗したよ。もう一度同じ資料に返信してね。")
    except Exception as x:
        print("ai",repr(x),flush=True)
        return finish("AI接続エラー")

def analyze(img,mime,uid,cid,question=""):
    prompt="""資料を高精度で詳細に解析。小さい文字・表・注記も確認する。画像内に複数の募集図面・複数物件が写っている場合は、1件だけ選ばず全物件をそれぞれ独立して読み取り、物件ごとに明確に分ける。別物件の金額・条件を絶対に混ぜない。
賃貸募集図面なら各物件について物件名、号室、所在地、交通、間取り、面積、賃料、管理費、敷金、礼金、保証金、契約期間、保証会社、初回/月額保証料、火災保険、損保、損害保険、家財保険、住宅保険、借家人賠償責任保険、少額短期保険、保険料、鍵交換、24時間/安心/緊急サポート、クリーニング、その他初期/月額費用、入居日、設備、特約、AD等を抽出。保険は名称が火災保険でなくても住宅・家財・借家人賠償に関する記載と金額を必ず拾う。
見積に使える金額を項目別に構造化し、必須/任意・税込/税別も分かる範囲で区別。数字は推測しない。不鮮明・未記載は必ず「要確認」。"""
    if question:
        prompt += "\nユーザーの質問を最優先して答える: "+question[:1500]
        if re.search(r"(見積|初期費用|いくら|費用|合計)",question,re.I):
            prompt += """
【顧客向け見積回答ルール・最優先】
見積・初期費用の質問では物件詳細解析やMarkdown表を返さず、必ず次の形式だけで返す。
【初期費用概算】
物件名 号室

当月前家賃：金額または－
次月前家賃：金額または－
敷金：金額または－
礼金：金額または－
初回保証料：金額または－
仲介手数料：金額または－
火災保険：金額または－
24時間サポート：金額または－
鍵交換：金額または－
事務手数料：金額または－

合計：確定金額の合計

※入居日・未確定項目により金額が変動します。
Markdown表、詳細解析、計算過程、仲介手数料内訳は禁止。管理費・共益費は前家賃に含める。入居日指定なしなら当月前家賃は必ず－。不明項目は要確認ではなく－。
仲介手数料は今回のユーザー発言で明示指定した場合だけ計上。図面・会社ルール・過去見積に記載があっても今回指定がなければ必ず－。自動で1ヶ月＋税等にしない。表記は必ず「初回保証料」。"""
    return media_ai(img,mime,uid,cid,prompt)

def learn_important(text,uid,cid):
    # Save only durable, clearly attributable facts. Company-wide memories require
    # an explicit sharing scope so personal or project information is never promoted.
    t=(text or "").strip()
    if len(t)<2 or len(t)>500:
        return None

    company_scope=re.search(r"(全社|全社共通|会社全体|社内共通|全グループ|会社ルール|弊社ルール)",t,re.I)
    company_fact=re.search(r"(ルール|規定|方針|標準|手数料|料金|請求|見積|フロー|営業時間|禁止|必須)",t,re.I)
    if company_scope and company_fact:
        if not can_self_improve(uid): return None
        add_memory("company","company","company_rule","会社共通ルール",t,uid)
        return "会社共通ルールとして記憶しました。"
    if company_fact and re.search(r"(弊社|うちの会社|会社|社内|業務)",t,re.I):
        return "これは全社共通ルールとして保存してよい？"

    personal=re.search(r"(?:俺|私|僕|自分|わたし)(?:のこと)?(?:は|を|って|なら)?[^。！？\n]{0,80}(?:呼んで|呼び|好き|嫌い|希望|住んで|会社|仕事|誕生日|名前|好み|苦手|覚えて)",t,re.I)
    personal=personal or re.search(r"(?:俺|私|僕|自分|わたし)の?名前は|(?:俺|私|僕|自分|わたし)を.{0,20}呼んで",t,re.I)
    if personal:
        add_memory("user",uid,"profile","本人の好み・属性",t,uid)
        return None

    group_scope=re.search(r"(このグループ|この会話|この案件|この顧客|このお客|このスレッド)",t,re.I)
    customer=re.search(r"(.{1,50}?さん).{0,50}(家賃|予算|入居|ペット|犬|猫|間取り|エリア|駅|審査|法人|個人|希望|物件|案件)",t,re.I)
    if group_scope or customer:
        subject=customer.group(1).strip() if customer else "グループ情報"
        add_memory("conversation",cid,"customer" if customer else "group_context",subject,t,uid)
        return None
    return None


def save_manager_insight(cid,uid,itype,severity,summary):
    try:
        with db() as cn:
            with cn.cursor() as c:
                c.execute("""INSERT INTO manager_insights(conversation_id,user_id,insight_type,severity,summary)
                VALUES(%s,%s,%s,%s,%s)""",(cid,uid,itype,int(severity),summary[:2000]))
            cn.commit()
    except Exception as x: print("manager_insight",repr(x),flush=True)

def manager_review_allowed(cid):
    """Avoid a second AI request for every uncalled group message."""
    try:
        with db() as cn:
            with cn.cursor() as c:
                c.execute("SELECT last_checked_at < NOW() - INTERVAL '20 minutes' FROM manager_review_state WHERE conversation_id=%s",(cid,))
                row=c.fetchone()
                if row and not row[0]: return False
                c.execute("""INSERT INTO manager_review_state(conversation_id,last_checked_at) VALUES(%s,NOW())
                ON CONFLICT(conversation_id) DO UPDATE SET last_checked_at=EXCLUDED.last_checked_at""",(cid,))
            cn.commit()
        return True
    except Exception as x:
        print("manager_review_allowed",repr(x),flush=True); return False

def manager_review(text,uid,cid):
    """Return a proactive message only for high-value intervention; otherwise None."""
    if not OPENAI_KEY or len((text or "").strip()) < 4:
        return None
    # Cheap prefilter: only operational/sales-looking messages.
    trigger = re.search(
        r"(申込|審査|契約|内見|見積|請求|管理会社|保証会社|入居|退去|物件|家賃|敷金|礼金|"
        r"仲介|鍵|保険|追客|連絡|顧客|お客様|さん|空室|キャンセル|重説|必要書類|法人契約)",
        text, re.I)
    if not trigger:
        return None
    if not manager_review_allowed(cid):
        return None

    prompt = """あなたは不動産賃貸仲介会社の営業部長。
直近トーク履歴・会社ルール・今回の発言を見て、今この瞬間に自発的に割り込む価値があるか判定する。
雑談、単なる報告、軽微な改善には絶対に割り込まない。
以下のどれかで、放置すると営業損失・顧客トラブル・法務/契約事故・重大な確認漏れにつながる可能性が高い時だけ通知する:
- 顧客条件の重大な聞き漏れ
- 追客/期限/次アクションの明確な漏れ
- 見積/請求の重大な不足や矛盾
- 申込/審査/契約/重説/鍵渡しの重大な確認不足
- 保存済み会社ルールとの明確な不整合

返答はJSONのみ:
{"speak":true/false,"type":"followup|estimate|contract|customer|rule|other","severity":1-5,"message":"..."}
speak=trueはseverity 4以上だけ。messageは事実→理由→具体的な次アクションを120文字程度で。
"""
    try:
        payload={"model":MODEL,"instructions":prompt,
                 "input":[{"role":"user","content":[{"type":"input_text",
                 "text":ctx(uid,cid)+"\n【今回の発言】\n"+text}]}]}
        r=requests.post(OA,headers={"Authorization":f"Bearer {OPENAI_KEY}","Content-Type":"application/json"},
                        json=payload,timeout=60)
        if not r.ok:return None
        d=r.json(); raw=d.get("output_text","")
        if not raw:
            vals=[]
            for i in d.get("output",[]):
                if i.get("type")=="message":
                    for z in i.get("content",[]):
                        if z.get("type")=="output_text": vals.append(z.get("text",""))
            raw="\n".join(vals)
        raw=re.sub(r"^```(?:json)?\s*|\s*```$","",raw.strip())
        obj=json.loads(raw)
        if obj.get("speak") and int(obj.get("severity",0))>=4 and obj.get("message"):
            save_manager_insight(cid,uid,obj.get("type","other"),obj.get("severity",4),obj["message"])
            return "🧭 部長ナミから1点\n"+obj["message"]
    except Exception as x:
        print("manager_review",repr(x),flush=True)
    return None


def explicit_learning(text,uid,cid=None,source_type="user"):
    t=re.sub(r"^(ナミ|なみ|nami)[、,\s]*","",(text or "").strip(),flags=re.I)
    if not t:
        return None

    company_scope=re.search(r"(全社|全社共通|会社全体|社内共通|全グループ|会社ルール|弊社ルール)",t,re.I)
    if company_scope:
        if not can_self_improve(uid):
            return "会社共通ルールの変更は船長だけができるよ🧭"
        payload=re.sub(r"(全社共通|全社|会社全体|社内共通|全グループ|会社ルール|弊社ルール)[、,:：\s]*","",t,flags=re.I).strip()
        if payload:
            add_memory("company","company","company_rule","会社共通ルール",payload,uid)
            return "会社共通ルールとして覚えたよ🧭"

    group=re.search(r"(?:このグループ|この会話|この案件|このスレッド)(?:では|のルールは)?[：:、,\s]*(.+)",t,re.S|re.I)
    if group:
        if source_type not in ("group","room") or not cid:
            return "どのグループの記憶にするか、そのグループで送ってね🧭"
        add_memory("conversation",cid, "group_context","グループルール",group.group(1).strip(),uid)
        return "このグループの記憶として覚えたよ🧭"

    m=re.search(r"(.{1,50}?)(?:の作り方|のやり方|のルール)[：:、,\s]*(.+)",t,re.S)
    if m:
        add_skill(m.group(1)+"の作り方",m.group(2),uid)
        return f"学習したよ🧭\n【{m.group(1)}の作り方】\n{m.group(2)}"
    m=re.search(r"(?:学習して|今後はこれで|このやり方を覚えて)[：:、,\s]*(.+)",t,re.S)
    if m:
        add_skill("業務ルール",m.group(1),uid)
        return "業務ルールとして学習したよ🧭"
    m=re.search(r"(.+?)って覚えて(?:おいて)?[！!。.]?$",t,re.S)
    if m:
        fact=m.group(1).strip()
        if re.search(r"(会社|社内|全社|全グループ|弊社)",fact,re.I):
            return "これは全社共通ルールとして保存してよい？"
        add_memory("user",uid,"general","本人から明示された記憶",fact,uid)
        return f"覚えたよ🧭\n「{fact}」"
    return None


def single_estimate_prompt(user_instruction=""):
    return ("募集図面の読取結果から、お客様へそのままLINE転送できる初期費用の概算を作成してください。短く見やすく丁寧にし、Markdown表、計算過程、内部事情、前回回答への言及は禁止です。\n"
            "表示項目と順番は必ず次で固定：当月前家賃、次月前家賃、敷金、礼金、初回保証料、仲介手数料、火災保険、24時間サポート、鍵交換、事務手数料、合計。該当しない又は金額不明の項目も省略せず『－』と表示してください。\n"
            "管理費・共益費は前家賃に含めます。当月前家賃は入居日の指定がない場合は必ず『－』。入居日の指定がある場合のみ賃料＋管理費・共益費を日割り計算してください。次月前家賃は賃料＋管理費・共益費で計算してください。\n"
            "仲介手数料は今回のユーザー発言で明示指定した場合だけ計上してください。今回指定がなければ図面・会社ルール・過去見積に金額があっても必ず『－』。自動計算しないでください。\n"
            "【保険判定・最優先】損保、損害保険、家財保険、家財、住宅保険、借家人賠償責任保険、少額短期保険、保険料、保険加入など住宅保険を火災保険として扱う。『損保 要2万円2年』なら火災保険：20,000円。保険加入記載のみで金額なし、又は保険記載自体なしなら必ず『火災保険（仮）：20,000円』と表示し合計へ加算。火災保険を－にしない。\n"
            "【保証料fallback】保証会社の初回保証料の金額・率が資料にない場合は、賃料＋管理費・共益費の50%を『初回保証料（仮）』として表示し合計に含める。\n"
            "【表記ゆれ】敷金/保証金/契約保証金/預り金、初回保証料/保証委託料/初回委託保証料/保証会社利用料、24時間サポート/安心サポート/緊急サポート/入居者サポート、鍵交換/鍵交換代/鍵設定費/シリンダー交換等は意味と文脈で分類。既存カテゴリ外の契約時費用も図面名のまま事務手数料の後に追加。保証金は敷金相当か独立費用か判定し二重計上しない。\n"
            "【合計】『－』以外に表示した全ての契約時金額（仮計上・次月前家賃・追加費用含む）を必ず合計し、回答前に再検算。\n"
            "出力は【初期費用概算】から始め、末尾は『※入居日・未確定項目により金額が変動します。』。余計な前置き、月額費用一覧、要確認一覧は書かない。\n"
            "【今回のユーザー指定】"+(user_instruction or "なし"))

def batch_estimates_using_single(groups,user_instruction,uid,cid):
    """Generate each property independently with the exact single-property flow."""
    answers=[]
    total=len(groups)
    for index,g in enumerate(groups,1):
        p=g['property']
        analyses='\n---\n'.join(a.get('analysis','') for a in g['attachments'])
        material=f"物件名：{p.get('name','')}\n号室：{p.get('room','')}\n住所：{p.get('address','')}\n【募集図面の読取結果】\n{analyses}"
        instruction=(user_instruction or '')+f"\nこれは全{total}件中{index}件目。ほかの物件と混ぜず、この1物件だけを単独見積もりとして計算・出力すること。"
        label=p.get('name') or p.get('address') or f'{index}件目'
        room=p.get('room') or ''
        prop_name=label+((' '+room) if room else '')
        data,estimate=structured_estimate(ai,instruction,material,uid,cid,prop_name)
        header=f"【{index}/{total} {prop_name}】"
        answers.append({'data':data,'text':header+"\n"+estimate})
    return answers

def three_document_command(text,uid,cid,qid=None):
    """Steer Ship: AD / brokerage / customer-ready estimate commands."""
    clean=re.sub(r"^(ナミ|なみ|nami)[、,\s]*","",(text or "").strip(),flags=re.I)
    kind="ad" if re.search(r"(AD請求|AD作|広告料.*請求|業務委託料.*請求)",clean,re.I) else ("brokerage" if re.search(r"(中手|仲介手数料精算)",clean,re.I) else ("estimate" if re.search(r"(見積|初期費用|入居計算)",clean,re.I) else None))
    if not kind:return None
    wants_image=kind=="estimate" and bool(re.search(r"(画像|イメージ|jpg|jpeg|png|一枚|1枚|写真にして)",clean,re.I))
    wants_pdf=kind=="estimate" and bool(re.search(r"(PDF|pdf)",clean,re.I)) or (kind!="estimate" and bool(re.search(r"(PDF|pdf|書類|発行)",clean,re.I)))
    if kind=="estimate" and not wants_image and not wants_pdf:
        prompt=single_estimate_prompt(clean)
        if qid:
            blob,mime=content(qid)
            if blob:
                if blob[:5]==b"%PDF-":mime="application/pdf"
                return analyze(blob,mime,uid,cid,question=prompt)
        latest=image_analysis(cid) or ""
        if latest:
            return ask(prompt+"\n\n【直前の募集図面の読取結果】\n"+latest,uid,cid)
        return "募集図面を送ってから『ナミ、見積もり教えて』でOKだよ。画像にリプライしなくても大丈夫。"
    media_summary=""
    if qid:
        blob,mime=content(qid)
        if blob:
            if blob[:5]==b"%PDF-":mime="application/pdf"
            media_summary=analyze(blob,mime,uid,cid,question="物件名、号室、賃料、管理費/共益費、敷金、礼金、保証料、仲介手数料、保険、鍵交換、クリーニング、24時間サポート、その他必須費用を帳票用に抽出。各金額と条件を明記。推測禁止。")
    elif re.search(r"(この|これ|それ|図面|画像|写真|PDF|資料)",clean,re.I):media_summary=image_analysis(cid) or ""
    if kind=="estimate" and (wants_image or wants_pdf):
        if not media_summary:return "見積書を作る募集図面がないよ。図面の画像/PDFにリプライして送って。"
        estimate_data,estimate_text=structured_estimate(ai,clean,media_summary,uid,cid)
        marker="__ESTIMATE_BOTH__" if (wants_image and wants_pdf) else ("__ESTIMATE_IMAGE__" if wants_image else "__ESTIMATE_PDF__")
        return (marker,estimate_data,estimate_text)
    def grab(pat):
        m=re.search(pat,clean,re.I);return m.group(1).strip() if m else ""
    client=grab(r"(?:宛名|宛先)[：:\s]*([^、,\n]+)");deadline=grab(r"(?:期限|支払期限)[：:\s]*([^、,\n]+)");amount=grab(r"(?:金額)[：:\s]*([0-9,]+)円?");ad=grab(r"AD\s*([0-9.]+)");broker=grab(r"(?:中手|仲介手数料)\s*([0-9.]+)")
    if kind=="ad":
        missing=[]
        if not client:missing.append("宛名")
        if not deadline:missing.append("支払期限")
        if not amount and not ad:missing.append("AD金額またはAD率")
        if missing:return "AD請求書を作るよ🧭\n不足："+"、".join(missing)
        return ("__PDF__","AD請求書",{"client":client,"title":"AD請求書","amount":("¥"+amount if amount else "要確認"),"description":media_summary or "図面参照","notes":"支払期限："+deadline})
    missing=[]
    if not deadline:missing.append("支払期限")
    if not amount and not broker:missing.append("仲介手数料金額または月数")
    if missing:return "中手を作るよ🧭\n不足："+"、".join(missing)
    return ("__PDF__","仲介手数料精算書",{"client":client,"title":"仲介手数料精算書","amount":("¥"+amount if amount else broker+"ヶ月（要金額確定）"),"description":media_summary or "図面参照","notes":"支払期限："+deadline})

def task_command(text,uid,cid):
    """Task commands stay fast because they do not invoke the AI."""
    clean=re.sub(r"^(ナミ|なみ|nami)[、,\s]*","",(text or "").strip(),flags=re.I)
    add=re.match(r"(?:タスク(?:を)?追加|タスク追加|やること追加)[：:\s]+(.+)",clean,re.S)
    if add:
        title=add.group(1).strip()[:500]
        if not title:return "タスクの内容を送って。例：ナミ タスク追加：田町の管理会社へ空室確認"
        try:
            with db() as cn:
                with cn.cursor() as c:
                    c.execute("INSERT INTO tasks(title,conversation_id,user_id) VALUES(%s,%s,%s) RETURNING id",(title,cid,uid)); tid=c.fetchone()[0]
                cn.commit()
            return f"タスクを登録したよ🧭 #{tid} {title}"
        except Exception as x:
            print("task_add",repr(x),flush=True); return "タスク登録でエラーが出た。"
    if re.search(r"^(?:タスク一覧|未完了タスク|やること一覧)$",clean):
        try:
            with db() as cn:
                with cn.cursor() as c:
                    c.execute("""SELECT id,title,due_date FROM tasks WHERE conversation_id=%s AND status='open'
                    ORDER BY due_date NULLS LAST,created_at DESC LIMIT 30""",(cid,)); rows=c.fetchall()
            return "未完了タスクはないよ🧭" if not rows else "未完了タスク🧭\n"+"\n".join(f"#{i} {t}"+(f"（{d}）" if d else "") for i,t,d in rows)
        except Exception as x:
            print("task_list",repr(x),flush=True); return "タスク取得でエラーが出た。"
    done=re.match(r"(?:タスク(?:を)?完了|完了タスク)[：\s#]*([0-9]+)",clean)
    if done:
        try:
            with db() as cn:
                with cn.cursor() as c:
                    c.execute("""UPDATE tasks SET status='done',updated_at=NOW() WHERE id=%s AND conversation_id=%s
                    AND status='open' RETURNING title""",(int(done.group(1)),cid)); row=c.fetchone()
                cn.commit()
            return f"完了にしたよ🧭 #{done.group(1)} {row[0]}" if row else "その未完了タスクは見つからなかった。"
        except Exception as x:
            print("task_done",repr(x),flush=True); return "タスク更新でエラーが出た。"
    return None

def dashboard_auth(view):
    @wraps(view)
    def wrapped(*args,**kwargs):
        if not DASHBOARD_PASSWORD:
            return "NAMI_DASHBOARD_PASSWORD をRenderのEnvironmentへ設定するとWeb司令室が開く。",503
        auth=request.authorization
        valid=auth and auth.username=="nami" and hmac.compare_digest(auth.password or "",DASHBOARD_PASSWORD)
        if not valid:
            return Response("認証が必要です",401,{"WWW-Authenticate":'Basic realm="Nami Command"'})
        return view(*args,**kwargs)
    return wrapped

def dashboard_rows(sql,params=()):
    try:
        with db() as cn:
            with cn.cursor() as c:
                c.execute(sql,params); return c.fetchall()
    except Exception as x:
        print("dashboard",repr(x),flush=True); return []

def make_pdf(kind,data):
    from reportlab.pdfgen import canvas
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.units import mm
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.cidfonts import UnicodeCIDFont
    pdfmetrics.registerFont(UnicodeCIDFont("HeiseiKakuGo-W5"))
    out=BytesIO(); page=canvas.Canvas(out,pagesize=A4); width,height=A4
    page.setTitle(f"航海士ナミ {kind}")
    page.setFont("HeiseiKakuGo-W5",20); page.drawString(20*mm,height-25*mm,kind)
    page.setFont("HeiseiKakuGo-W5",10); page.drawRightString(width-20*mm,height-25*mm,datetime.now().strftime("発行日 %Y/%m/%d"))
    y=height-45*mm
    for label,key in [("宛名","client"),("件名","title"),("金額","amount"),("内容","description"),("備考","notes")]:
        value=(data.get(key) or "-").replace("\n"," ")
        page.setFont("HeiseiKakuGo-W5",10); page.drawString(20*mm,y,label)
        page.setFont("HeiseiKakuGo-W5",12 if key=="amount" else 10); page.drawString(50*mm,y,value[:65])
        page.line(20*mm,y-4*mm,width-20*mm,y-4*mm); y-=14*mm
    page.setFont("HeiseiKakuGo-W5",9); page.drawString(20*mm,18*mm,"Steer Ship株式会社 / 航海士ナミ")
    page.showPage(); page.save(); out.seek(0); return out

def yen(value):
    try: return int(float(re.sub(r"[^0-9.]","",value or "0")))
    except: return 0

def quick_estimate(form):
    rent=yen(form.get("rent")); management=yen(form.get("management"))
    deposit=rent*float(form.get("deposit_months") or 0)
    key_money=rent*float(form.get("key_months") or 0)
    broker=(rent+management)*float(form.get("broker_months") or 1.1)
    guarantee=yen(form.get("guarantee")); insurance=yen(form.get("insurance")); key=yen(form.get("key_exchange")); other=yen(form.get("other"))
    lines=[("賃料",rent),("管理費",management),("敷金",deposit),("礼金",key_money),("仲介手数料",broker),("保証会社",guarantee),("火災保険",insurance),("鍵交換",key),("その他",other)]
    total=sum(v for _,v in lines)
    detail=" / ".join(f"{n} ¥{int(v):,}" for n,v in lines if v)
    return {"client":form.get("client",""),"title":form.get("title","初期費用見積"),"amount":f"¥{int(total):,}","description":detail,"notes":form.get("notes","")}

COMMAND_HTML="""<!doctype html><html lang='ja'><meta charset='utf-8'><title>航海士ナミ 司令室</title>
<style>body{margin:0;background:#07131f;color:#e8f0f7;font-family:-apple-system,BlinkMacSystemFont,'Hiragino Sans',sans-serif}main{max-width:1200px;margin:auto;padding:32px}h1{margin:0;color:#74d3ff}.sub{color:#9ab0c2}section{background:#102535;border:1px solid #21435a;border-radius:14px;padding:20px;margin-top:18px}h2{margin-top:0;color:#b6e8ff}table{width:100%;border-collapse:collapse}td,th{padding:9px;border-bottom:1px solid #23465e;text-align:left;font-size:14px}input,textarea,select{background:#071924;color:#fff;border:1px solid #37627a;border-radius:7px;padding:9px;width:100%;box-sizing:border-box}textarea{min-height:60px}.grid{display:grid;grid-template-columns:repeat(3,1fr);gap:10px}.wide{grid-column:span 3}button{background:#14a4e8;border:0;color:#fff;padding:10px 15px;border-radius:8px;font-weight:700;cursor:pointer}.stat{display:flex;gap:12px}.stat div{background:#0c1d2a;padding:12px;border-radius:10px;min-width:110px}</style>
<main><h1>航海士ナミ 司令室</h1><p class='sub'>LINEは現場、ここは案件・記憶・見積・請求の管理場所。</p>
<section><div class='stat'><div>案件 <b>{{ cases|length }}</b></div><div>未完了タスク <b>{{ tasks|length }}</b></div><div>部長ナミ注意 <b>{{ insights|length }}</b></div></div></section>
<section><h2>新規案件</h2><form method='post' class='grid'><input name='client_name' placeholder='顧客名' required><input name='assignee' placeholder='担当者'><select name='status'><option>ヒアリング中</option><option>物件提案中</option><option>申込中</option><option>審査中</option><option>契約中</option><option>成約</option></select><input name='budget' placeholder='予算'><input name='area' placeholder='希望エリア'><input name='move_in' placeholder='入居希望'><input class='wide' name='next_action' placeholder='次アクション'><textarea class='wide' name='notes' placeholder='条件・注意点'></textarea><button>案件を保存</button></form></section>
<section><h2>案件一覧</h2><table><tr><th>顧客</th><th>担当</th><th>状況</th><th>希望</th><th>次アクション</th></tr>{% for x in cases %}<tr><td>{{x[1]}}</td><td>{{x[2]}}</td><td>{{x[3]}}</td><td>{{x[4]}} / {{x[5]}}</td><td>{{x[8]}}</td></tr>{% else %}<tr><td colspan='5'>まだ案件がない</td></tr>{% endfor %}</table></section>
<section><h2>初期費用見積 - かんたん作成</h2><p class='sub'>月数と金額を入れるだけ。合計と内訳を自動計算してPDFにする。</p><form action='/nami/pdf' method='post' class='grid'><input type='hidden' name='kind' value='初期費用見積書'><input name='client' placeholder='宛名' required><input name='title' placeholder='物件名・号室' required><input name='rent' placeholder='賃料（円）' required><input name='management' placeholder='管理費（円）'><input name='deposit_months' value='0' placeholder='敷金（月数）'><input name='key_months' value='0' placeholder='礼金（月数）'><input name='broker_months' value='1.1' placeholder='仲介料（月数・税込）'><input name='guarantee' placeholder='保証会社（円）'><input name='insurance' placeholder='火災保険（円）'><input name='key_exchange' placeholder='鍵交換（円）'><input name='other' placeholder='その他（円）'><textarea class='wide' name='notes' placeholder='備考・特約'></textarea><button>自動計算して見積PDFを作成</button></form><hr><h2>請求書PDF</h2><form action='/nami/pdf' method='post' class='grid'><input type='hidden' name='kind' value='請求書'><input name='client' placeholder='宛名' required><input name='title' placeholder='件名' required><input name='amount' placeholder='金額（税込）' required><input class='wide' name='description' placeholder='内容'><textarea class='wide' name='notes' placeholder='備考'></textarea><button>請求書PDFを作成</button></form></section>
<section><h2>部長ナミの注意</h2><table>{% for x in insights %}<tr><td>{{x[4]}}</td><td>{{x[5]}}</td></tr>{% else %}<tr><td>今は重大な注意なし</td></tr>{% endfor %}</table></section></main></html>"""

@app.route("/nami",methods=["GET","POST"])
@dashboard_auth
def command_center():
    if request.method=="POST":
        values=(request.form.get("client_name",""),request.form.get("assignee",""),request.form.get("status","ヒアリング中"),request.form.get("budget",""),request.form.get("area",""),request.form.get("move_in",""),request.form.get("notes",""),request.form.get("next_action",""))
        if values[0]:
            with db() as cn:
                with cn.cursor() as c:
                    c.execute("""INSERT INTO cases(client_name,assignee,status,budget,area,move_in,notes,next_action)
                    VALUES(%s,%s,%s,%s,%s,%s,%s,%s)""",values)
                cn.commit()
    cases=dashboard_rows("SELECT id,client_name,assignee,status,budget,area,move_in,notes,next_action FROM cases ORDER BY updated_at DESC LIMIT 100")
    tasks=dashboard_rows("SELECT id,title,due_date FROM tasks WHERE status='open' ORDER BY due_date NULLS LAST LIMIT 100")
    insights=dashboard_rows("SELECT id,conversation_id,insight_type,severity,summary,created_at FROM manager_insights WHERE status='open' ORDER BY created_at DESC LIMIT 30")
    return render_template_string(COMMAND_HTML,cases=cases,tasks=tasks,insights=insights)

@app.post("/nami/pdf")
@dashboard_auth
def command_pdf():
    kind=request.form.get("kind","見積書")
    data=quick_estimate(request.form) if kind=="初期費用見積書" else request.form
    out=make_pdf(kind,data)
    stamp=datetime.now().strftime("%Y%m%d-%H%M")
    return send_file(out,as_attachment=True,download_name=f"{kind}-{stamp}.pdf",mimetype="application/pdf")

ESTIMATE_CACHE={}

@app.get("/estimate-file/<key>.<ext>")
def estimate_file_download(key,ext):
    row=ESTIMATE_CACHE.get(key)
    if not row:return "not found",404
    created,estimate=row
    if time.time()-created>600:
        ESTIMATE_CACHE.pop(key,None); return "expired",404
    if ext=="pdf": return send_file(make_estimate_document(estimate),mimetype="application/pdf",as_attachment=True,download_name="見積もり概算書.pdf")
    if ext=="png": return send_file(make_estimate_image(estimate),mimetype="image/png")
    return "not found",404

def reply_estimate_artifact(tok,base,key,marker):
    image_url=f"{base}/estimate-file/{key}.png"
    pdf_url=f"{base}/estimate-file/{key}.pdf"
    msgs=[]
    # Any explicit artifact request gets the finished estimate image directly in LINE.
    if marker in ("__ESTIMATE_IMAGE__","__ESTIMATE_PDF__","__ESTIMATE_BOTH__"):
        msgs.append({"type":"image","originalContentUrl":image_url,"previewImageUrl":image_url})
    if marker in ("__ESTIMATE_PDF__","__ESTIMATE_BOTH__"):
        # LINE Messaging API has no outbound arbitrary-PDF file message type.
        msgs.append({"type":"text","text":"見積もり概算書PDFはこちら\n"+pdf_url})
    try:
        sender=globals().get("HTTP",requests)
        r=sender.post("https://api.line.me/v2/bot/message/reply",headers={"Authorization":f"Bearer {TOKEN}","Content-Type":"application/json"},json={"replyToken":tok,"messages":msgs[:5]},timeout=20)
        if not r.ok: print("LINE estimate artifact",r.status_code,r.text[:1000],flush=True)
        return r.ok
    except Exception as x: print("reply_estimate_artifact",repr(x),flush=True); return False

@app.get("/")
def health():return "航海士ナミ FINAL 部長モード OK",200

@app.post("/webhook")
def webhook():
    raw=request.get_data()
    expected=base64.b64encode(hmac.new(SECRET.encode(),raw,hashlib.sha256).digest()).decode()
    if not hmac.compare_digest(expected,request.headers.get("X-Line-Signature","")):abort(400)
    for e in (request.get_json(silent=True) or {}).get("events",[]):
        if e.get("type")!="message":continue
        m=e.get("message",{}); typ=m.get("type")
        if typ not in ("text","image","file"):continue
        cid,uid=ids(e); nm=name(e); eid=e.get("webhookEventId") or m.get("id"); mid=m.get("id")
        remember_line_member(cid,uid,nm)
        qid=m.get("quotedMessageId")

        if typ in ("image","file"):
            rawmedia,mime=content(mid)
            if not rawmedia:continue
            filename=(m.get("fileName") or "").lower()
            is_pdf=(typ=="file" and (filename.endswith(".pdf") or "pdf" in (mime or "").lower()))
            if typ=="file" and not is_pdf:
                reply(e.get("replyToken"),"今は画像とPDFを読めるよ🧭 このファイル形式はまだ未対応。")
                continue
            a=analyze(rawmedia,"application/pdf" if is_pdf else mime,uid,cid)
            save_image(cid,uid,mid,a)
            add_estimate_batch_item(cid,uid,mid,a)
            label="PDF解析" if is_pdf else "画像解析"
            save_msg(eid,cid,uid,nm,"user",f"[{label}]\n"+a,"file" if is_pdf else "image",mid,qid)
            if not grouped(e):
                # Keep the detailed extraction internally for the estimate tool.
                # Do not dump raw listing analysis into LINE; the next estimate
                # instruction renders the canonical concise estimate instead.
                received="資料を読み取ったよ🧭 見積もり条件を送ってね。"
                save_msg("assistant:"+eid,cid,"bot","航海士ナミ","assistant",received)
                reply(e.get("replyToken"),received)
            continue

        text=m.get("text","")
        save_msg(eid,cid,uid,nm,"user",text,"text",mid,qid)
        learn_important(text,uid,cid)

        if grouped(e) and not called(m):
            proactive=manager_review(text,uid,cid)
            if proactive:
                save_msg("assistant:manager:"+eid,cid,"bot","航海士ナミ","assistant",proactive)
                reply(e.get("replyToken"),proactive)
            continue

        batch_answer=None
        if is_batch_estimate_command(text):
            items=recent_estimate_batch(cid)
            if not items:
                batch_answer="直近15分の見積資料が見つからないよ。PDFや画像をまとめて送ってから『ナミ、まとめて見積もり』と送ってね。"
            else:
                groups,ambiguous=group_attachments(items)
                if ambiguous:
                    batch_answer="資料の一部で物件を特定できませんでした。どの物件の資料か指定してください。"
                else:
                    batch_answer=batch_estimates_using_single(groups,text,uid,cid)
                    clear_estimate_batch(cid)
        reminder_done=complete_member_reminder(cid,text)
        reminder_timing_missing=reminder_needs_timing(text)
        member_task=parse_member_task(text) if reminder_has_enough_context(text) else None
        reminder_created=None
        if member_task:
            assignee,steps,interval=member_task
            reminder_created=create_member_reminder(cid,line_target(e),uid,assignee,steps,interval)
        quick_task=task_command(text,uid,cid)
        # Estimate requests must bypass the legacy document command entirely.
        # The legacy estimate path can call obsolete helpers before the canonical
        # structured estimate route gets a chance to run.
        estimate_intent=bool(re.search(r"(見積|初期費用)",text,re.I) or (re.search(r"仲介.{0,8}(?:半額|無料|割引)",text,re.I) and re.search(r"(画像|PNG|PDF|作って|出して)",text,re.I)))
        quick_doc=None if estimate_intent else three_document_command(text,uid,cid,qid)
        # Estimate is a tool, never a free-form chat answer. Force it after legacy parsing so
        # an older document route cannot preempt the canonical estimate engine.
        estimate_intent=bool(re.search(r"(見積|初期費用)",text,re.I) or (re.search(r"仲介.{0,8}(?:半額|無料|割引)",text,re.I) and re.search(r"(画像|PNG|PDF|作って|出して)",text,re.I)))
        if estimate_intent:
            latest_material=image_analysis(cid,qid) if qid else image_analysis(cid)
            if latest_material:
                try:
                    estimate_data,estimate_text=structured_estimate(ai,text,latest_material,uid,cid)
                    wants_image=bool(re.search(r"(画像|PNG|写真)",text,re.I))
                    wants_pdf=bool(re.search(r"PDF",text,re.I))
                    marker="__ESTIMATE_BOTH__" if wants_image and wants_pdf else ("__ESTIMATE_PDF__" if wants_pdf else ("__ESTIMATE_IMAGE__" if wants_image else None))
                    quick_doc=(marker,estimate_data,estimate_text) if marker else estimate_text
                except Exception as x:
                    print("structured_estimate_forced",repr(x),flush=True)
                    quick_doc="見積データの生成でエラーが出た。通常チャットでは代替せず停止したよ。"
            else:
                quick_doc="見積書を作る募集図面・PDF・文面が見つからないよ。資料を送ってから見積を指示してね。"
        awaiting=latest_awaiting(cid,uid)
        if batch_answer:
            ans=batch_answer
        elif reminder_done:
            ans=reminder_done
        elif reminder_timing_missing:
            ans="リマインドする間隔を指定してね。例：『10分おきにリマインドして』"
        elif reminder_created:
            assignee,steps,interval=member_task
            ans=f"{assignee}のタスクを登録しました。まず「{steps[0]}」を{interval}分おきに、完了報告があるまでリマインドします。"
        elif quick_task:
            ans=quick_task
        elif quick_doc:
            if isinstance(quick_doc,tuple) and quick_doc[0] in ('__ESTIMATE_IMAGE__','__ESTIMATE_PDF__','__ESTIMATE_BOTH__'):
                estimate_data=quick_doc[1]
                estimate_text=quick_doc[2]
                key=hashlib.sha256((eid+str(time.time())).encode()).hexdigest()[:24]
                ESTIMATE_CACHE[key]=(time.time(),estimate_data)
                base=os.getenv("PUBLIC_BASE_URL","https://koukaisi-nami.onrender.com").rstrip('/')
                save_msg("assistant:"+eid,cid,"bot","航海士ナミ","assistant",estimate_text)
                reply_estimate_artifact(e.get("replyToken"),base,key,quick_doc[0])
                continue
            elif isinstance(quick_doc,tuple) and quick_doc[0]=='__PDF__':
                _,pdf_kind,pdf_data=quick_doc;make_pdf(pdf_kind,pdf_data)
                ans=pdf_kind+'の内容を作成したよ🧭\n'+pdf_data.get('description','')
            else:ans=quick_doc
        elif awaiting and can_self_improve(uid) and re.search(r"^(ナミ[、, ]*)?(反映して|承認|OK|おけ|やって)$",text.strip(),re.I):
            try:
                ok,msg=merge_pr(awaiting[2])
                if ok:set_improvement_status(awaiting[0],"merged")
                ans=msg
            except Exception as x:
                print("merge_pr",repr(x),flush=True)
                ans="反映処理でエラー。既存本番は変更していないよ。"
        elif improvement_intent(text) and can_self_improve(uid):
            plan=improvement_plan(text,uid,cid)
            rid=add_improvement(cid,uid,text,plan)
            if github_ready():
                try:
                    pr,err=create_pr(text)
                    if pr:
                        attach_pr(rid,pr[0],pr[1])
                        ans=(f"改善候補を作ったよ🧭 ID:{rid}\n\n{plan}\n\n"
                             f"PR #{pr[0]} 作成済み。必須機能ガードを通過。"
                             "内容を反映するなら「反映して」と言ってね。")
                    else: ans="改善要求は保存したけど、"+err
                except Exception as x:
                    print("create_pr",repr(x),flush=True)
                    ans="改善要求は保存したけどPR作成で停止。既存本番は変更していないよ。"
            else:
                ans=(f"改善要求を保存したよ🧭 ID:{rid}\n\n{plan}\n\n"
                     "GitHub自己改善は未接続。RenderにGITHUB_TOKEN / GITHUB_REPO / SELF_IMPROVE=trueを設定すると有効になる。")
        else:
            source_type=(e.get("source") or {}).get("type","user")
            taught=explicit_learning(text,uid,cid,source_type)
            if taught: ans=taught
            else:
                # Reply to an image/PDF: fetch the original quoted media and answer from the actual bytes.
                # This avoids relying only on an older saved summary when the user asks a new question.
                quoted_saved=image_analysis(cid,qid) if qid else None
                quoted_blob=quoted_mime=None
                if qid:
                    quoted_blob,quoted_mime=content(qid)
                if quoted_blob:
                    # LINE may return application/octet-stream for files, so detect PDF by signature too.
                    is_quoted_pdf=(quoted_blob[:5]==b"%PDF-") or (quoted_mime and "pdf" in quoted_mime.lower())
                    media_mime="application/pdf" if is_quoted_pdf else quoted_mime
                    ans=analyze(quoted_blob,media_mime,uid,cid,question=text)
                else:
                    latest=image_analysis(cid) if re.search(r"(この|図面|画像|写真|PDF|資料|見積)",text,re.I) else None
                    chosen=quoted_saved or latest
                    extra=f"\n【参照資料の解析】\n{chosen}" if chosen else ""
                    ans=ai(text,uid,cid,extra=extra)

        batch_marker=batch_artifact_marker(text) if isinstance(batch_answer,list) else None
        if batch_marker and isinstance(batch_answer,list):
            base=os.getenv("PUBLIC_BASE_URL","https://koukaisi-nami.onrender.com").rstrip('/')
            saved_ans="\n\n".join((x.get('text','') if isinstance(x,dict) else str(x)) for x in batch_answer)
            save_msg("assistant:"+eid,cid,"bot","航海士ナミ","assistant",saved_ans)
            send_batch_estimate_artifacts(e.get("replyToken"),line_target(e),batch_answer,base,batch_marker)
            continue
        saved_ans="\n\n".join((x.get('text','') if isinstance(x,dict) else str(x)) for x in ans) if isinstance(ans,(list,tuple)) else ans
        save_msg("assistant:"+eid,cid,"bot","航海士ナミ","assistant",saved_ans)
        if isinstance(ans,list):
            target=line_target(e)
            if ans:
                reply(e.get("replyToken"),ans[0].get('text','') if isinstance(ans[0],dict) else ans[0])
                for item in ans[1:]:push_line(target,item.get('text','') if isinstance(item,dict) else item)
        else:
            reply(e.get("replyToken"),ans)
    return "OK",200

try:
    init_db()
    start_reminder_worker()
except Exception as x:print("init_db",repr(x),flush=True)

if __name__=="__main__":
    app.run(host="0.0.0.0",port=int(os.getenv("PORT","10000")))
