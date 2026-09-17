from pathlib import Path
p=Path('app.py'); s=p.read_text()
# DB draft table
anchor='''            c.execute("""CREATE TABLE IF NOT EXISTS manager_review_state(\n              conversation_id TEXT PRIMARY KEY,last_checked_at TIMESTAMPTZ DEFAULT NOW())""")'''
insert=anchor+'''\n            c.execute("""CREATE TABLE IF NOT EXISTS estimate_drafts(\n              conversation_id TEXT PRIMARY KEY,user_id TEXT,data JSONB NOT NULL DEFAULT '{}'::jsonb,\n              updated_at TIMESTAMPTZ DEFAULT NOW())""")'''
if anchor not in s: raise SystemExit('db anchor')
s=s.replace(anchor,insert,1)
# helpers before task_command
anchor='''def task_command(text,uid,cid):'''
helpers=r'''def _estimate_json_from_text(source,uid,cid):
    prompt="""次の募集図面解析/見積情報をJSONだけに変換。推測禁止、未記載はnull。金額は整数。
keys: property,room,rent,management,deposit,key_money,guarantee,brokerage,insurance,support24,key_exchange,office_fee,move_in_date
「保証会社初回保証料」はguarantee。管理費/共益費はmanagement。"""
    raw=ask(prompt+"\n\n"+(source or "")[:10000],uid,cid)
    try:
        raw=re.sub(r"^```(?:json)?\s*|\s*```$","",raw.strip())
        d=json.loads(raw); return d if isinstance(d,dict) else {}
    except Exception as x: print('estimate_json',repr(x),flush=True); return {}

def _estimate_draft_get(cid):
    if not DB_URL:return None
    try:
        with db() as cn:
            with cn.cursor() as c:
                c.execute("SELECT data FROM estimate_drafts WHERE conversation_id=%s AND updated_at>NOW()-INTERVAL '7 days'",(cid,)); r=c.fetchone()
                return r[0] if r else None
    except Exception as x: print('estimate_get',repr(x),flush=True); return None

def _estimate_draft_save(cid,uid,d):
    if not DB_URL:return
    try:
        with db() as cn:
            with cn.cursor() as c:
                c.execute("""INSERT INTO estimate_drafts(conversation_id,user_id,data) VALUES(%s,%s,%s::jsonb)
                ON CONFLICT(conversation_id) DO UPDATE SET user_id=EXCLUDED.user_id,data=EXCLUDED.data,updated_at=NOW()""",(cid,uid,json.dumps(d,ensure_ascii=False)))
            cn.commit()
    except Exception as x: print('estimate_save',repr(x),flush=True)

def _money_from(s):
    if not s:return None
    m=re.search(r"([0-9][0-9,]*(?:\.[0-9]+)?)\s*万",s)
    if m:return int(float(m.group(1).replace(',',''))*10000)
    m=re.search(r"([0-9][0-9,]*)\s*円?",s)
    return int(m.group(1).replace(',','')) if m else None

def _estimate_apply(text,d):
    d=dict(d or {}); t=text or ''
    # explicit brokerage instructions override everything
    if re.search(r"仲介手数料.{0,8}(なし|無料|0円)",t): d['brokerage']=0
    else:
        m=re.search(r"仲介手数料.{0,8}([0-9.]+)\s*(?:か|ヶ|ケ)?月",t)
        if m and d.get('rent') is not None:d['brokerage']=round(int(d['rent'])*float(m.group(1))*1.1)
        else:
            m=re.search(r"仲介手数料.{0,8}([0-9][0-9,]*(?:\.[0-9]+)?\s*万|[0-9][0-9,]*\s*円)",t)
            if m:d['brokerage']=_money_from(m.group(1))
    for key,label in [('insurance','火災保険'),('support24','24時間(?:安心)?サポート'),('key_exchange','鍵交換(?:代|費用)?'),('office_fee','事務手数料')]:
        m=re.search(label+r".{0,8}([0-9][0-9,]*(?:\.[0-9]+)?\s*万|[0-9][0-9,]*\s*円)",t)
        if m:d[key]=_money_from(m.group(1))
    m=re.search(r"(?:入居日?|入居)\s*[：:]?\s*(?:(\d{4})[/-])?(\d{1,2})[/-](\d{1,2})",t)
    if m:d['move_in_date']=f"{m.group(1)+'-' if m.group(1) else ''}{int(m.group(2)):02d}-{int(m.group(3)):02d}"
    return d

def _estimate_current_rent(d):
    ds=d.get('move_in_date'); base=(d.get('rent') or 0)+(d.get('management') or 0)
    if not ds or not base:return None
    try:
        import calendar
        parts=[int(x) for x in ds.split('-')]
        if len(parts)==3:y,m,day=parts
        else:y,m,day=datetime.now().year,parts[0],parts[1]
        days=calendar.monthrange(y,m)[1]
        return round(base*(days-day+1)/days)
    except:return None

def _estimate_render(d):
    def f(v):return '－' if v is None else f"{int(v):,}円"
    current=_estimate_current_rent(d); next_rent=((d.get('rent') or 0)+(d.get('management') or 0)) if d.get('rent') is not None else None
    vals=[('当月前家賃',current),('次月前家賃',next_rent),('敷金',d.get('deposit')),('礼金',d.get('key_money')),('初回保証料',d.get('guarantee')),('仲介手数料',d.get('brokerage')),('火災保険',d.get('insurance')),('24時間サポート',d.get('support24')),('鍵交換',d.get('key_exchange')),('事務手数料',d.get('office_fee'))]
    total=sum(v for _,v in vals if isinstance(v,(int,float)))
    prop=' '.join(str(x) for x in [d.get('property'),d.get('room')] if x)
    lines=['【初期費用概算】']+([prop] if prop else [])+['']+[f'{k}：{f(v)}' for k,v in vals]+['',f'合計：{total:,}円','', '※入居日・未確定項目により金額が変動します。']
    return '\n'.join(lines),vals,total

def _estimate_image_bytes(d):
    # Deterministic SVG: exact structured amounts, no generative image model.
    text,vals,total=_estimate_render(d); prop=' '.join(str(x) for x in [d.get('property'),d.get('room')] if x)
    esc=lambda x:(str(x).replace('&','&amp;').replace('<','&lt;').replace('>','&gt;'))
    rows=[]; y=300
    for k,v in vals:
        val='－' if v is None else f'{int(v):,}円'
        rows.append(f'<text x="100" y="{y}" class="k">{esc(k)}</text><text x="980" y="{y}" text-anchor="end" class="v">{esc(val)}</text><line x1="90" y1="{y+28}" x2="990" y2="{y+28}" class="line"/>'); y+=82
    svg=f'''<svg xmlns="http://www.w3.org/2000/svg" width="1080" height="1350"><rect width="1080" height="1350" fill="white"/><rect width="1080" height="18" fill="#102c4c"/><style>text{{font-family:-apple-system,BlinkMacSystemFont,"Noto Sans JP","Hiragino Sans",sans-serif;fill:#17263a}}.title{{font-size:54px;font-weight:700}}.sub{{font-size:25px;fill:#637083}}.k,.v{{font-size:30px}}.v{{font-weight:600}}.line{{stroke:#dce2e8;stroke-width:2}}.total{{font-size:43px;font-weight:800}}</style><text x="540" y="100" text-anchor="middle" class="title">見積もり概算書</text><text x="540" y="140" text-anchor="middle" class="sub">ESTIMATE</text><text x="90" y="210" class="k">{esc(prop)}</text>{''.join(rows)}<rect x="70" y="{y-20}" width="940" height="110" rx="8" fill="#f2f5f8"/><text x="100" y="{y+50}" class="total">合計（税込）</text><text x="980" y="{y+50}" text-anchor="end" class="total">{total:,}円</text><text x="90" y="{y+145}" class="sub">※入居日・未確定項目により金額が変動します。</text><text x="90" y="{y+205}" class="sub">Steer Ship株式会社</text></svg>'''
    try:
        import cairosvg
        return cairosvg.svg2png(bytestring=svg.encode(),output_width=1080,output_height=1350)
    except Exception as x: print('estimate_image',repr(x),flush=True); return None

def _estimate_image_reply(tok,d):
    png=_estimate_image_bytes(d)
    if not png:return False
    # LINE image messages require an HTTPS URL. Publish a short-lived in-memory image endpoint.
    key=hashlib.sha256(png+str(time.time()).encode()).hexdigest()[:32]
    ESTIMATE_IMAGES[key]=(png,time.time()+600)
    base=(os.getenv('PUBLIC_BASE_URL') or 'https://koukaisi-nami.onrender.com').rstrip('/')
    url=f'{base}/nami/estimate-image/{key}.png'
    try:
        r=requests.post('https://api.line.me/v2/bot/message/reply',headers={'Authorization':f'Bearer {TOKEN}','Content-Type':'application/json'},json={'replyToken':tok,'messages':[{'type':'image','originalContentUrl':url,'previewImageUrl':url}]},timeout=30)
        if not r.ok:print('LINE image reply',r.status_code,r.text[:1000],flush=True)
        return r.ok
    except Exception as x:print('LINE image reply',repr(x),flush=True);return False

ESTIMATE_IMAGES={}

@app.get('/nami/estimate-image/<key>.png')
def estimate_image_file(key):
    item=ESTIMATE_IMAGES.get(key)
    if not item or item[1]<time.time():abort(404)
    return Response(item[0],mimetype='image/png',headers={'Cache-Control':'public, max-age=600'})

def estimate_followup_command(text,uid,cid):
    if not re.search(r'(仲介手数料|火災保険|24時間(?:安心)?サポート|鍵交換|事務手数料|入居日?)',text or ''):return None
    d=_estimate_draft_get(cid)
    if not d:return None
    d=_estimate_apply(text,d);_estimate_draft_save(cid,uid,d)
    return _estimate_render(d)[0]

'''+anchor
if anchor not in s: raise SystemExit('task anchor')
s=s.replace(anchor,helpers,1)
# replace estimate text prompt branch to save structured draft and render fixed format
start='''    if kind=="estimate" and not wants_image and not wants_pdf:\n'''
end='''    media_summary=""\n'''
a=s.index(start); b=s.index(end,a)
new=r'''    if kind=="estimate" and not wants_image and not wants_pdf:
        source=''
        if qid:
            blob,mime=content(qid)
            if blob:
                if blob[:5]==b'%PDF-':mime='application/pdf'
                source=analyze(blob,mime,uid,cid,question='物件名、号室、賃料、管理費/共益費、敷金、礼金、初回保証料、仲介手数料、火災保険、24時間サポート、鍵交換、事務手数料を正確に抽出。推測禁止。')
        if not source:source=image_analysis(cid) or ''
        if not source:return "募集図面を送ってから『ナミ、見積もり教えて』でOKだよ。"
        d=_estimate_json_from_text(source,uid,cid); d=_estimate_apply(clean,d); _estimate_draft_save(cid,uid,d)
        return _estimate_render(d)[0]
'''
s=s[:a]+new+s[b:]
# image command should build draft marker instead of summary marker
old='''        return ("__ESTIMATE_IMAGE__",media_summary)'''
new='''        d=_estimate_json_from_text(media_summary,uid,cid); d=_estimate_apply(clean,d); _estimate_draft_save(cid,uid,d)\n        return ("__ESTIMATE_IMAGE__",d)'''
if old not in s: raise SystemExit('image marker')
s=s.replace(old,new,1)
# webhook followup and actual image reply
old='''        quick_task=task_command(text,uid,cid)\n        quick_doc=three_document_command(text,uid,cid,qid)'''
new='''        quick_task=task_command(text,uid,cid)\n        quick_followup=estimate_followup_command(text,uid,cid)\n        quick_doc=None if quick_followup else three_document_command(text,uid,cid,qid)'''
if old not in s: raise SystemExit('webhook command anchor')
s=s.replace(old,new,1)
old='''        if quick_task:\n            ans=quick_task\n        elif quick_doc:\n            if isinstance(quick_doc,tuple) and quick_doc[0]=='__ESTIMATE_IMAGE__':\n                ans='見積もり画像用の内容を作成したよ🧭\\n'+quick_doc[1]+'\\n※画像は固定テンプレート描画で金額を変えずに生成する仕様です。' '''
new='''        image_replied=False\n        if quick_task:\n            ans=quick_task\n        elif quick_followup:\n            ans=quick_followup\n        elif quick_doc:\n            if isinstance(quick_doc,tuple) and quick_doc[0]=='__ESTIMATE_IMAGE__':\n                image_replied=_estimate_image_reply(e.get("replyToken"),quick_doc[1])\n                ans='見積もり画像を作成しました。' if image_replied else _estimate_render(quick_doc[1])[0]'''
if old not in s: raise SystemExit('webhook image anchor')
s=s.replace(old,new,1)
old='''        save_msg("assistant:"+eid,cid,"bot","航海士ナミ","assistant",ans)\n        reply(e.get("replyToken"),ans)'''
new='''        save_msg("assistant:"+eid,cid,"bot","航海士ナミ","assistant",ans)\n        if not image_replied: reply(e.get("replyToken"),ans)'''
if old not in s: raise SystemExit('final reply anchor')
s=s.replace(old,new,1)
p.write_text(s)
