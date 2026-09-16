import os, base64, hashlib, hmac, json, re, requests, psycopg
from flask import Flask, request, abort

app = Flask(__name__)

LINE_CHANNEL_SECRET = os.getenv("LINE_CHANNEL_SECRET", "")
LINE_CHANNEL_ACCESS_TOKEN = os.getenv("LINE_CHANNEL_ACCESS_TOKEN", "")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
DATABASE_URL = os.getenv("DATABASE_URL", "")
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-5.6-luna")
OPENAI_URL = "https://api.openai.com/v1/responses"

# ---------- Database ----------
def db():
    return psycopg.connect(DATABASE_URL)

def init_db():
    if not DATABASE_URL:
        print("DATABASE_URL missing", flush=True); return
    with db() as conn:
        with conn.cursor() as c:
            c.execute("""CREATE TABLE IF NOT EXISTS messages(
              id BIGSERIAL PRIMARY KEY, event_id TEXT UNIQUE,
              conversation_id TEXT NOT NULL, user_id TEXT, user_name TEXT,
              role TEXT NOT NULL, message_type TEXT DEFAULT 'text',
              content TEXT NOT NULL, created_at TIMESTAMPTZ DEFAULT NOW())""")
            c.execute("CREATE INDEX IF NOT EXISTS msg_conv_idx ON messages(conversation_id,created_at DESC)")
            c.execute("""CREATE TABLE IF NOT EXISTS memories(
              id BIGSERIAL PRIMARY KEY, scope TEXT NOT NULL, scope_id TEXT NOT NULL,
              category TEXT DEFAULT 'general', subject TEXT DEFAULT '',
              content TEXT NOT NULL, created_by TEXT,
              created_at TIMESTAMPTZ DEFAULT NOW(), updated_at TIMESTAMPTZ DEFAULT NOW())""")
            c.execute("CREATE INDEX IF NOT EXISTS mem_scope_idx ON memories(scope,scope_id,updated_at DESC)")
            c.execute("""CREATE TABLE IF NOT EXISTS skills(
              id BIGSERIAL PRIMARY KEY, scope TEXT NOT NULL DEFAULT 'company',
              scope_id TEXT NOT NULL DEFAULT 'company', name TEXT NOT NULL,
              instructions TEXT NOT NULL, created_by TEXT,
              created_at TIMESTAMPTZ DEFAULT NOW(), updated_at TIMESTAMPTZ DEFAULT NOW())""")
            c.execute("CREATE INDEX IF NOT EXISTS skill_idx ON skills(scope,scope_id,updated_at DESC)")
        conn.commit()

def save_message(event_id,cid,uid,name,role,content,mtype="text"):
    if not DATABASE_URL or not content: return
    try:
        with db() as conn:
            with conn.cursor() as c:
                c.execute("""INSERT INTO messages(event_id,conversation_id,user_id,user_name,role,message_type,content)
                  VALUES(%s,%s,%s,%s,%s,%s,%s) ON CONFLICT(event_id) DO NOTHING""",
                  (event_id,cid,uid,name,role,mtype,content))
            conn.commit()
    except Exception as e: print("save_message",repr(e),flush=True)

def recent(cid,n=60):
    if not DATABASE_URL: return []
    try:
        with db() as conn:
            with conn.cursor() as c:
                c.execute("""SELECT role,user_name,content FROM messages WHERE conversation_id=%s
                             ORDER BY created_at DESC LIMIT %s""",(cid,n))
                rows=c.fetchall()
        return list(reversed(rows))
    except Exception as e: print("recent",repr(e),flush=True); return []

def add_memory(scope,scope_id,category,subject,content,uid):
    if not DATABASE_URL or not scope_id or not content.strip(): return False
    try:
        with db() as conn:
            with conn.cursor() as c:
                c.execute("""INSERT INTO memories(scope,scope_id,category,subject,content,created_by)
                             VALUES(%s,%s,%s,%s,%s,%s)""",
                          (scope,scope_id,category,subject,content.strip(),uid))
            conn.commit()
        return True
    except Exception as e: print("memory",repr(e),flush=True); return False

def memories(uid,cid,n=100):
    if not DATABASE_URL:return []
    try:
        with db() as conn:
            with conn.cursor() as c:
                c.execute("""SELECT scope,category,subject,content FROM memories
                  WHERE (scope='user' AND scope_id=%s)
                     OR (scope='conversation' AND scope_id=%s)
                     OR (scope='company' AND scope_id='company')
                  ORDER BY updated_at DESC LIMIT %s""",(uid,cid,n))
                return c.fetchall()
    except Exception as e: print("memories",repr(e),flush=True); return []

def forget(uid,cid,keyword):
    if not DATABASE_URL:return 0
    with db() as conn:
        with conn.cursor() as c:
            c.execute("""DELETE FROM memories WHERE
              ((scope='user' AND scope_id=%s) OR (scope='conversation' AND scope_id=%s))
              AND (content ILIKE %s OR subject ILIKE %s)""",
              (uid,cid,f"%{keyword}%",f"%{keyword}%"))
            n=c.rowcount
        conn.commit()
    return n

def add_skill(name,instructions,uid,scope="company",scope_id="company"):
    if not DATABASE_URL or not instructions.strip():return False
    try:
        with db() as conn:
            with conn.cursor() as c:
                c.execute("""INSERT INTO skills(scope,scope_id,name,instructions,created_by)
                             VALUES(%s,%s,%s,%s,%s)""",(scope,scope_id,name[:120],instructions.strip(),uid))
            conn.commit()
        return True
    except Exception as e: print("skill",repr(e),flush=True); return False

def skills(cid,n=80):
    if not DATABASE_URL:return []
    try:
        with db() as conn:
            with conn.cursor() as c:
                c.execute("""SELECT name,instructions FROM skills
                  WHERE (scope='company' AND scope_id='company')
                     OR (scope='conversation' AND scope_id=%s)
                  ORDER BY updated_at DESC LIMIT %s""",(cid,n))
                return c.fetchall()
    except Exception as e: print("skills",repr(e),flush=True); return []

# ---------- LINE ----------
def verify(body,sig):
    digest=hmac.new(LINE_CHANNEL_SECRET.encode(),body,hashlib.sha256).digest()
    return hmac.compare_digest(base64.b64encode(digest).decode(),sig or "")

def ids(event):
    s=event.get("source",{})
    uid=s.get("userId","unknown")
    if s.get("type")=="group": cid="group:"+s.get("groupId","unknown")
    elif s.get("type")=="room": cid="room:"+s.get("roomId","unknown")
    else: cid="user:"+uid
    return cid,uid

def is_group(event): return event.get("source",{}).get("type") in ("group","room")

def profile_name(event):
    s=event.get("source",{}); uid=s.get("userId")
    if not uid:return "ユーザー"
    try:
        h={"Authorization":f"Bearer {LINE_CHANNEL_ACCESS_TOKEN}"}
        if s.get("type")=="group":
            u=f"https://api.line.me/v2/bot/group/{s['groupId']}/member/{uid}"
        elif s.get("type")=="room":
            u=f"https://api.line.me/v2/bot/room/{s['roomId']}/member/{uid}"
        else:u=f"https://api.line.me/v2/bot/profile/{uid}"
        r=requests.get(u,headers=h,timeout=10)
        if r.ok:return r.json().get("displayName","ユーザー")
    except Exception as e:print("profile",repr(e),flush=True)
    return "ユーザー"

def called(msg):
    text=msg.get("text","")
    if re.search(r"(ナミ|なみ|nami)",text,re.I):return True
    for m in msg.get("mention",{}).get("mentionees",[]):
        if m.get("isSelf") is True:return True
    return False

def reply(token,text):
    if not token:return
    text=(text or "うまく回答を作れなかった！").strip()
    # LINE text limit safety; split into <= 4900 chars, max 5
    chunks=[text[i:i+4900] for i in range(0,len(text),4900)][:5] or ["回答なし"]
    payload={"replyToken":token,"messages":[{"type":"text","text":x} for x in chunks]}
    try:
        r=requests.post("https://api.line.me/v2/bot/message/reply",
          headers={"Authorization":f"Bearer {LINE_CHANNEL_ACCESS_TOKEN}","Content-Type":"application/json"},
          json=payload,timeout=30)
        print("LINE",r.status_code,r.text,flush=True)
    except Exception as e:print("reply",repr(e),flush=True)

def get_content(mid):
    r=requests.get(f"https://api-data.line.me/v2/bot/message/{mid}/content",
      headers={"Authorization":f"Bearer {LINE_CHANNEL_ACCESS_TOKEN}"},timeout=40)
    if r.ok:return r.content,r.headers.get("Content-Type","image/jpeg")
    print("content",r.status_code,r.text,flush=True); return None,None

# ---------- Teach / remember ----------
def teaching(text):
    t=re.sub(r"^(ナミ|なみ|nami)[、,\s]*","",text.strip(),flags=re.I)
    patterns=[
      r"(.{1,40}?)(?:の作り方|のやり方|のルール)(?:は|を)?[：:、,\s]*(.+)",
      r"(?:学習して|今後はこれで|このやり方を覚えて)[：:、,\s]*(.+)"
    ]
    m=re.search(patterns[0],t,re.S)
    if m and len(m.group(2).strip())>=4:return m.group(1)+"の作り方",m.group(2).strip()
    m=re.search(patterns[1],t,re.S)
    if m and len(m.group(1).strip())>=4:return "業務ルール",m.group(1).strip()
    return None,None

def remember_cmd(text):
    t=re.sub(r"^(ナミ|なみ|nami)[、,\s]*","",text.strip(),flags=re.I)
    for p in [r"(.+?)って覚えて(?:おいて)?[！!。.]?$",r"(.+?)を覚えて(?:おいて)?[！!。.]?$",
              r"覚えて(?:おいて)?[：:]\s*(.+)$"]:
        m=re.search(p,t,re.S)
        if m:return m.group(1).strip()
    return None

def forget_cmd(text):
    t=re.sub(r"^(ナミ|なみ|nami)[、,\s]*","",text.strip(),flags=re.I)
    for p in [r"(.+?)を忘れて",r"(.+?)って忘れて",r"忘れて[：:]\s*(.+)"]:
        m=re.search(p,t,re.S)
        if m:return m.group(1).strip()
    return None

# ---------- AI ----------
SYSTEM="""あなたはLINE上のAI「航海士ナミ」。Steer Shipの優秀な不動産賃貸仲介営業マン兼営業事務として振る舞う。
日本の賃貸仲介実務に強く、ヒアリング、物件提案、募集図面読解、初期費用、申込、入居審査、保証会社、必要書類、
重説・契約・鍵渡し・入居までの一般的な流れ、顧客フォロー、営業文面、請求・見積の整理を支援する。
法令・税務・審査基準・物件募集状況など変動する事項は断定せず、必要ならWeb検索で最新情報を確認する。

絶対ルール:
- 会話履歴・ユーザー記憶・会社知識・業務スキルを区別して利用する。別人や別グループを混同しない。
- グループでは全メッセージが履歴として保存される前提だが、ナミ自身は呼ばれた時だけ回答する。
- 保存された会社独自ルールは一般論より優先。ただし違法・危険・明らかな誤りはその旨を示す。
- 最新の天気、ニュース、会社、店舗、相場、物件など現在性が必要ならweb_searchを使う。
- 図面・写真は丁寧に読む。読めない文字や記載のない金額を捏造しない。「要確認」と明記する。
- 見積は賃料、管理費、敷金、礼金、前家賃、日割り、保証料、保険、鍵交換、仲介手数料、その他を分ける。
- 月額/初回、税込/税別、必須/任意を混同しない。根拠がない金額は計算しない。
- 請求書は宛名、発行者、発行日、請求項目、数量、単価、税、合計、期日、振込先等を保存ルールに従い整理。不明は要確認。
- 顧客条件（予算、エリア、駅距離、間取り、入居日、ペット、法人/個人、審査事情等）を会話文脈から正確に扱う。
- 宅建業法など法的な重要事項は一般的説明と個別判断を分け、必要に応じ専門家/管理会社等への確認を促す。
- 簡潔なLINE口調。業務成果物は見やすく整理する。
"""

def context(uid,cid):
    h="\n".join(f"{'ナミ' if r=='assistant' else (n or 'ユーザー')}: {x}" for r,n,x in recent(cid))
    m="\n".join(f"- [{s}/{cat}/{sub}] {x}" for s,cat,sub,x in memories(uid,cid))
    sk="\n".join(f"- 【{n}】{x}" for n,x in skills(cid))
    return f"【このトークの履歴】\n{h or 'なし'}\n\n【参照可能な長期記憶】\n{m or 'なし'}\n\n【会社から教わった業務ルール】\n{sk or 'なし'}"

def openai_response(text,uid,cid,image=None,mime=None):
    if not OPENAI_API_KEY:return "OPENAI_API_KEYが設定されていません。"
    content=[{"type":"input_text","text":context(uid,cid)+"\n\n【今回の依頼】\n"+text}]
    if image:
        b64=base64.b64encode(image).decode()
        content.append({"type":"input_image","image_url":f"data:{mime or 'image/jpeg'};base64,{b64}","detail":"high"})
    payload={
      "model":OPENAI_MODEL,
      "instructions":SYSTEM,
      "input":[{"role":"user","content":content}],
      "tools":[{"type":"web_search"}],
      "tool_choice":"auto"
    }
    try:
        r=requests.post(OPENAI_URL,headers={"Authorization":f"Bearer {OPENAI_API_KEY}",
          "Content-Type":"application/json"},json=payload,timeout=120)
        if not r.ok:
            print("OPENAI",r.status_code,r.text,flush=True)
            return f"AI側でエラーが出たよ（{r.status_code}）。Renderのログを確認してね。"
        d=r.json()
        if d.get("output_text"):return d["output_text"].strip()
        out=[]
        for item in d.get("output",[]):
            if item.get("type")=="message":
                for z in item.get("content",[]):
                    if z.get("type")=="output_text" and z.get("text"):out.append(z["text"])
        return "\n".join(out).strip() or "回答を作れなかったよ。"
    except Exception as e:
        print("openai",repr(e),flush=True); return "AIへの接続でエラーが出たよ。"

def analyze_image(image,mime,uid,cid):
    prompt="""この画像を不動産賃貸営業の視点で読み取ってください。
募集図面なら、物件名/号室/所在地/交通/間取り/面積/賃料/管理費/敷金/礼金/保証金/契約期間/
保証会社/火災保険/鍵交換/その他初期費用/月額費用/入居可能日/設備/特約/広告料など、読める項目を抽出。
見積作成に必要な情報を整理し、不鮮明・記載なしは「要確認」。数字を推測しない。
会社の保存済み見積ルールがある場合のみ、それを適用して見積案も作る。"""
    return openai_response(prompt,uid,cid,image,mime)

# ---------- Webhook ----------
@app.get("/")
def health(): return "航海士ナミ OK",200

@app.post("/webhook")
def webhook():
    raw=request.get_data()
    if not verify(raw,request.headers.get("X-Line-Signature","")): abort(400)
    data=request.get_json(silent=True) or {}
    for e in data.get("events",[]):
        if e.get("type")!="message":continue
        msg=e.get("message",{}); typ=msg.get("type")
        if typ not in ("text","image"):continue
        cid,uid=ids(e); name=profile_name(e)
        event_id=e.get("webhookEventId") or msg.get("id")
        token=e.get("replyToken")

        if typ=="text":
            text=msg.get("text","")
            # Always store group and 1:1 text before deciding whether to speak.
            save_message(event_id,cid,uid,name,"user",text,"text")

            # In groups: silence unless called/mentioned. Still remembered in that group's history.
            if is_group(e) and not called(msg):continue

            skname,inst=teaching(text)
            if skname and inst:
                add_skill(skname,inst,uid)
                ans=f"学習したよ🧭\n【{skname}】\n{inst}\n今後の業務でこのルールを参照するね。"
            else:
                f=forget_cmd(text)
                if f:
                    n=forget(uid,cid,f); ans=f"「{f}」に関する記憶を{n}件削除したよ。"
                else:
                    mem=remember_cmd(text)
                    if mem:
                        # Explicit remember defaults to user memory. Company procedures should use learning command.
                        add_memory("user",uid,"general","",mem,uid)
                        ans=f"覚えたよ🧭\n「{mem}」"
                    else:
                        ans=openai_response(text,uid,cid)
            save_message("assistant:"+str(event_id),cid,"bot","航海士ナミ","assistant",ans)
            reply(token,ans)

        elif typ=="image":
            # Image is saved as a durable textual analysis; LINE content itself can expire.
            image,mime=get_content(msg.get("id"))
            if not image:continue
            summary=analyze_image(image,mime,uid,cid)
            save_message(event_id,cid,uid,name,"user","[画像]\n"+summary,"image")
            # 1:1 replies immediately. In groups, image alone cannot reliably contain a bot mention,
            # so store silently; user can follow with "ナミ、この図面見積もり作って".
            if not is_group(e):
                save_message("assistant:"+str(event_id),cid,"bot","航海士ナミ","assistant",summary)
                reply(token,summary)
    return "OK",200

try:init_db()
except Exception as e:print("init",repr(e),flush=True)

if __name__=="__main__":
    app.run(host="0.0.0.0",port=int(os.getenv("PORT","10000")))
