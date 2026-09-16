import os, re, json, base64, hashlib, hmac, requests, psycopg, ast, time
from flask import Flask, request, abort

app = Flask(__name__)
SECRET=os.getenv("LINE_CHANNEL_SECRET","")
TOKEN=os.getenv("LINE_CHANNEL_ACCESS_TOKEN","")
OPENAI_KEY=os.getenv("OPENAI_API_KEY","")
DB_URL=os.getenv("DATABASE_URL","")
MODEL=os.getenv("OPENAI_MODEL","gpt-5.6-luna")
OA="https://api.openai.com/v1/responses"

# LINE承認式の自己改善
GITHUB_TOKEN=os.getenv("GITHUB_TOKEN","")
GITHUB_REPO=os.getenv("GITHUB_REPO","")  # owner/repo
GITHUB_BRANCH=os.getenv("GITHUB_BRANCH","main")
GITHUB_APP_PATH=os.getenv("GITHUB_APP_PATH","app.py")
SELF_IMPROVE=os.getenv("SELF_IMPROVE","false").lower()=="true"

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
            c.execute("ALTER TABLE messages ADD COLUMN IF NOT EXISTS line_message_id TEXT")
            c.execute("ALTER TABLE messages ADD COLUMN IF NOT EXISTS quoted_message_id TEXT")
            c.execute("CREATE INDEX IF NOT EXISTS msg_conv ON messages(conversation_id,created_at DESC)")
            c.execute("CREATE INDEX IF NOT EXISTS msg_line_id ON messages(line_message_id)")
            c.execute("""CREATE TABLE IF NOT EXISTS memories(
              id BIGSERIAL PRIMARY KEY,scope TEXT NOT NULL,scope_id TEXT NOT NULL,
              category TEXT DEFAULT 'general',subject TEXT DEFAULT '',content TEXT NOT NULL,
              created_by TEXT,created_at TIMESTAMPTZ DEFAULT NOW(),updated_at TIMESTAMPTZ DEFAULT NOW())""")
            c.execute("CREATE INDEX IF NOT EXISTS mem_scope ON memories(scope,scope_id,updated_at DESC)")
            c.execute("""CREATE TABLE IF NOT EXISTS skills(
              id BIGSERIAL PRIMARY KEY,scope TEXT DEFAULT 'company',scope_id TEXT DEFAULT 'company',
              name TEXT NOT NULL,instructions TEXT NOT NULL,created_by TEXT,
              created_at TIMESTAMPTZ DEFAULT NOW(),updated_at TIMESTAMPTZ DEFAULT NOW())""")
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
        cn.commit()

def save_msg(eid,cid,uid,name,role,content,mtype="text",mid=None,qid=None):
    if not DB_URL or not content:return
    try:
        with db() as cn:
            with cn.cursor() as c:
                c.execute("""INSERT INTO messages(event_id,conversation_id,user_id,user_name,role,
                message_type,content,line_message_id,quoted_message_id)
                VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s) ON CONFLICT(event_id) DO NOTHING""",
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

def history(cid,n=70):
    try:
        with db() as cn:
            with cn.cursor() as c:
                c.execute("""SELECT role,user_name,content FROM messages WHERE conversation_id=%s
                ORDER BY created_at DESC LIMIT %s""",(cid,n)); rows=c.fetchall()
        return list(reversed(rows))
    except: return []

def add_memory(scope,sid,cat,subject,content,uid):
    if not content.strip():return
    try:
        with db() as cn:
            with cn.cursor() as c:
                # avoid exact duplicates
                c.execute("""SELECT id FROM memories WHERE scope=%s AND scope_id=%s
                AND lower(content)=lower(%s) LIMIT 1""",(scope,sid,content.strip()))
                if not c.fetchone():
                    c.execute("""INSERT INTO memories(scope,scope_id,category,subject,content,created_by)
                    VALUES(%s,%s,%s,%s,%s,%s)""",(scope,sid,cat,subject,content.strip(),uid))
            cn.commit()
    except Exception as x: print("add_memory",repr(x),flush=True)

def mems(uid,cid):
    try:
        with db() as cn:
            with cn.cursor() as c:
                c.execute("""SELECT scope,category,subject,content FROM memories WHERE
                (scope='user' AND scope_id=%s) OR (scope='conversation' AND scope_id=%s)
                OR (scope='company' AND scope_id='company')
                ORDER BY updated_at DESC LIMIT 120""",(uid,cid)); return c.fetchall()
    except:return []

def add_skill(name,body,uid):
    try:
        with db() as cn:
            with cn.cursor() as c:
                c.execute("INSERT INTO skills(scope,scope_id,name,instructions,created_by) VALUES('company','company',%s,%s,%s)",
                          (name[:120],body.strip(),uid))
            cn.commit()
    except Exception as x: print("skill",repr(x),flush=True)

def skill_rows():
    try:
        with db() as cn:
            with cn.cursor() as c:
                c.execute("SELECT name,instructions FROM skills WHERE scope='company' ORDER BY updated_at DESC LIMIT 100")
                return c.fetchall()
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
    return requests.request(method,f"https://api.github.com/repos/{GITHUB_REPO}{path}",
                            headers=gh_headers(),timeout=45,**kwargs)

def repo_file(path=GITHUB_APP_PATH,ref=None):
    r=gh("GET",f"/contents/{path}",params={"ref":ref or GITHUB_BRANCH})
    if not r.ok: raise RuntimeError(f"GitHub read failed {r.status_code}")
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

def codegen_improvement(req_text,uid,cid):
    current,_=repo_file()
    instruction="""本番稼働中のLINE Bot『航海士ナミ』を改修する。
要求を実装した完全なapp.pyだけを返す。markdown禁止。
既存機能は絶対に削除しない。DBは後方互換のALTER/CREATE IF NOT EXISTSを使う。
秘密情報をコードに埋め込まない。自己改善・営業部長モードも維持する。
"""
    payload={"model":MODEL,"instructions":instruction,
      "input":[{"role":"user","content":[{"type":"input_text","text":
        "【改修要求】\n"+req_text+"\n\n【現在のapp.py】\n"+current}]}]}
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
    out=re.sub(r"^```(?:python)?\s*|\s*```$","",out.strip())
    return out

def create_pr(req_text):
    candidate=codegen_improvement(req_text,"system","system")
    errors=validate_candidate(candidate)
    if errors:return None,"安全チェック停止:\n- "+"\n- ".join(errors[:15])
    current,base_sha=repo_file()
    ref=gh("GET",f"/git/ref/heads/{GITHUB_BRANCH}")
    if not ref.ok: raise RuntimeError("base branch read failed")
    branch=f"nami/improve-{int(time.time())}"
    r=gh("POST","/git/refs",json={"ref":f"refs/heads/{branch}","sha":ref.json()["object"]["sha"]})
    if not r.ok: raise RuntimeError("branch create failed")
    r=gh("PUT",f"/contents/{GITHUB_APP_PATH}",json={
      "message":"Nami approved improvement candidate",
      "content":base64.b64encode(candidate.encode()).decode(),
      "sha":base_sha,"branch":branch})
    if not r.ok: raise RuntimeError("candidate commit failed")
    r=gh("POST","/pulls",json={"title":"航海士ナミ 自己改善",
      "head":branch,"base":GITHUB_BRANCH,
      "body":"LINEから作成した改善候補。必須機能ガード済み。船長のLINE承認後のみマージ。"})
    if not r.ok: raise RuntimeError("PR create failed")
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
    if not pr.ok:return False,"PRを取得できなかった"
    head=pr.json()["head"]["ref"]
    candidate,_=repo_file(GITHUB_APP_PATH,head)
    errors=validate_candidate(candidate)
    if errors:return False,"反映直前チェックで停止:\n- "+"\n- ".join(errors[:15])
    r=gh("PUT",f"/pulls/{num}/merge",json={"merge_method":"squash",
      "commit_title":f"航海士ナミ 自己改善 #{num}"})
    if not r.ok:return False,"GitHubマージに失敗。現行本番は維持したよ。"
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

def name(e):
    s=e.get("source",{}); uid=s.get("userId")
    if not uid:return "ユーザー"
    try:
        h={"Authorization":f"Bearer {TOKEN}"}
        if s.get("type")=="group":u=f"https://api.line.me/v2/bot/group/{s['groupId']}/member/{uid}"
        elif s.get("type")=="room":u=f"https://api.line.me/v2/bot/room/{s['roomId']}/member/{uid}"
        else:u=f"https://api.line.me/v2/bot/profile/{uid}"
        r=requests.get(u,headers=h,timeout=10)
        return r.json().get("displayName","ユーザー") if r.ok else "ユーザー"
    except:return "ユーザー"

def called(m):
    if re.search(r"(ナミ|なみ|nami)",m.get("text",""),re.I):return True
    return any(x.get("isSelf") is True for x in m.get("mention",{}).get("mentionees",[]))

def reply(tok,text):
    chunks=[text[i:i+4900] for i in range(0,len(text),4900)][:5]
    requests.post("https://api.line.me/v2/bot/message/reply",
      headers={"Authorization":f"Bearer {TOKEN}","Content-Type":"application/json"},
      json={"replyToken":tok,"messages":[{"type":"text","text":x} for x in chunks]},timeout=30)

def content(mid):
    r=requests.get(f"https://api-data.line.me/v2/bot/message/{mid}/content",
      headers={"Authorization":f"Bearer {TOKEN}"},timeout=40)
    return (r.content,r.headers.get("Content-Type","image/jpeg")) if r.ok else (None,None)

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

def ctx(uid,cid,extra=""):
    h="\n".join(f"{'ナミ' if r=='assistant' else (n or 'ユーザー')}: {x}" for r,n,x in history(cid))
    m="\n".join(f"- [{s}/{cat}/{sub}] {x}" for s,cat,sub,x in mems(uid,cid))
    sk="\n".join(f"- 【{n}】{x}" for n,x in skill_rows())
    return f"【トーク履歴】\n{h or 'なし'}\n【長期記憶】\n{m or 'なし'}\n【会社ルール】\n{sk or 'なし'}\n{extra}"

def ai(text,uid,cid,img=None,mime=None,extra=""):
    parts=[{"type":"input_text","text":ctx(uid,cid,extra)+"\n【今回】\n"+text}]
    if img:
        parts.append({"type":"input_image","image_url":f"data:{mime or 'image/jpeg'};base64,{base64.b64encode(img).decode()}","detail":"high"})
    payload={"model":MODEL,"instructions":SYSTEM,"input":[{"role":"user","content":parts}],
             "tools":[{"type":"web_search"}],"tool_choice":"auto"}
    try:
        r=requests.post(OA,headers={"Authorization":f"Bearer {OPENAI_KEY}","Content-Type":"application/json"},
                        json=payload,timeout=120)
        if not r.ok:
            print("OPENAI",r.status_code,r.text,flush=True); return f"AIエラー({r.status_code})"
        d=r.json()
        if d.get("output_text"):return d["output_text"].strip()
        out=[]
        for i in d.get("output",[]):
            if i.get("type")=="message":
                for z in i.get("content",[]):
                    if z.get("type")=="output_text":out.append(z.get("text",""))
        return "\n".join(out).strip() or "回答を作れなかったよ。"
    except Exception as x:print("ai",repr(x),flush=True);return "AI接続エラー"

def analyze(img,mime,uid,cid):
    return ai("""画像を詳細に解析。賃貸募集図面なら物件名、号室、所在地、交通、間取り、面積、賃料、管理費、
敷礼、保証金、契約期間、保証会社、保険、鍵、その他初期/月額費用、入居日、設備、特約、AD等を抽出。
見積に使える情報を構造化。不明・未記載は要確認。推測禁止。""",uid,cid,img,mime)

def learn_important(text,uid,cid):
    # Conservative automatic memory: clear self/customer/company facts only.
    t=text.strip()
    if len(t)<2 or len(t)>500:return
    personal=re.search(r"(俺|私|僕|自分|わたし).{0,20}(好き|嫌い|希望|住んで|会社|仕事|誕生日|名前)",t)
    customer=re.search(r"(.+?さん).{0,30}(家賃|予算|入居|ペット|犬|猫|間取り|エリア|駅|審査|法人|個人)",t)
    company=re.search(r"(弊社|うちの会社|Steer Ship).{0,80}(手数料|ルール|料金|見積|請求|フロー)",t,re.I)
    if personal:add_memory("user",uid,"profile","本人情報",t,uid)
    elif customer:add_memory("conversation",cid,"customer",customer.group(1),t,uid)
    elif company:add_memory("company","company","company_knowledge","会社情報",t,uid)


def save_manager_insight(cid,uid,itype,severity,summary):
    try:
        with db() as cn:
            with cn.cursor() as c:
                c.execute("""INSERT INTO manager_insights(conversation_id,user_id,insight_type,severity,summary)
                VALUES(%s,%s,%s,%s,%s)""",(cid,uid,itype,int(severity),summary[:2000]))
            cn.commit()
    except Exception as x: print("manager_insight",repr(x),flush=True)

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


def explicit_learning(text,uid):
    t=re.sub(r"^(ナミ|なみ|nami)[、,\s]*","",text.strip(),flags=re.I)
    m=re.search(r"(.{1,50}?)(?:の作り方|のやり方|のルール)[：:、,\s]*(.+)",t,re.S)
    if m:
        add_skill(m.group(1)+"の作り方",m.group(2),uid);return f"学習したよ🧭\n【{m.group(1)}の作り方】\n{m.group(2)}"
    m=re.search(r"(?:学習して|今後はこれで|このやり方を覚えて)[：:、,\s]*(.+)",t,re.S)
    if m:
        add_skill("業務ルール",m.group(1),uid);return "業務ルールとして学習したよ🧭"
    m=re.search(r"(.+?)って覚えて(?:おいて)?[！!。.]?$",t,re.S)
    if m:
        add_memory("user",uid,"general","",m.group(1),uid);return f"覚えたよ🧭\n「{m.group(1)}」"
    return None

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
        if typ not in ("text","image"):continue
        cid,uid=ids(e); nm=name(e); eid=e.get("webhookEventId") or m.get("id"); mid=m.get("id")
        qid=m.get("quotedMessageId")

        if typ=="image":
            rawimg,mime=content(mid)
            if not rawimg:continue
            a=analyze(rawimg,mime,uid,cid)
            save_image(cid,uid,mid,a)
            save_msg(eid,cid,uid,nm,"user","[画像解析]\n"+a,"image",mid,qid)
            # Personal chat replies; group stores silently, preserving context.
            if not grouped(e):
                save_msg("assistant:"+eid,cid,"bot","航海士ナミ","assistant",a)
                reply(e.get("replyToken"),a)
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

        awaiting=latest_awaiting(cid,uid)
        if awaiting and re.search(r"^(ナミ[、, ]*)?(反映して|承認|OK|おけ|やって)$",text.strip(),re.I):
            try:
                ok,msg=merge_pr(awaiting[2])
                if ok:set_improvement_status(awaiting[0],"merged")
                ans=msg
            except Exception as x:
                print("merge_pr",repr(x),flush=True)
                ans="反映処理でエラー。既存本番は変更していないよ。"
        elif improvement_intent(text):
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
            taught=explicit_learning(text,uid)
            if taught: ans=taught
            else:
                # If LINE quotedMessageId points to an analyzed image, use it; otherwise attach latest image analysis
                quoted=image_analysis(cid,qid) if qid else None
                latest=image_analysis(cid) if re.search(r"(この|図面|画像|写真|見積)",text) else None
                chosen=quoted or latest
                extra=f"\n【参照画像の解析】\n{chosen}" if chosen else ""
                ans=ai(text,uid,cid,extra=extra)

        save_msg("assistant:"+eid,cid,"bot","航海士ナミ","assistant",ans)
        reply(e.get("replyToken"),ans)
    return "OK",200

try:init_db()
except Exception as x:print("init_db",repr(x),flush=True)

if __name__=="__main__":
    app.run(host="0.0.0.0",port=int(os.getenv("PORT","10000")))
