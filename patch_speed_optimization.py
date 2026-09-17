from pathlib import Path
p=Path('app.py'); s=p.read_text()

# 1) Keep less context in normal requests: DB retains full history/memory.
s=s.replace('CHAT_HISTORY_COUNT=10\nMEMORY_CONTEXT_COUNT=8\nSKILL_CONTEXT_COUNT=5','CHAT_HISTORY_COUNT=6\nMEMORY_CONTEXT_COUNT=5\nSKILL_CONTEXT_COUNT=4',1)

# 2) Reuse HTTP connections for LINE/OpenAI calls.
needle='OA="https://api.openai.com/v1/responses"\n'
if 'HTTP=requests.Session()' not in s:
    s=s.replace(needle,needle+'HTTP=requests.Session()\n',1)
# Only hot-path external calls; leave GitHub/self-improvement untouched.
s=s.replace('r=requests.post(OA,headers={"Authorization":f"Bearer {OPENAI_KEY}","Content-Type":"application/json"},\n                        json=payload,timeout=120)', 'r=HTTP.post(OA,headers={"Authorization":f"Bearer {OPENAI_KEY}","Content-Type":"application/json"},\n                        json=payload,timeout=90)',1)
s=s.replace('rr=requests.post(OA,headers={"Authorization":f"Bearer {OPENAI_KEY}","Content-Type":"application/json"},json=retry,timeout=150)', 'rr=HTTP.post(OA,headers={"Authorization":f"Bearer {OPENAI_KEY}","Content-Type":"application/json"},json=retry,timeout=120)',1)
s=s.replace('r=requests.post(OA,headers={"Authorization":f"Bearer {OPENAI_KEY}","Content-Type":"application/json"},json=payload,timeout=180)', 'r=HTTP.post(OA,headers={"Authorization":f"Bearer {OPENAI_KEY}","Content-Type":"application/json"},json=payload,timeout=150)',1)

# 3) Avoid expensive LINE profile GET for every event: 10-minute in-process cache.
old='''def name(e):\n    s=e.get("source",{}); uid=s.get("userId")\n    if not uid:return "ユーザー"\n    try:\n        h={"Authorization":f"Bearer {TOKEN}"}\n        if s.get("type")=="group":u=f"https://api.line.me/v2/bot/group/{s['groupId']}/member/{uid}"\n        elif s.get("type")=="room":u=f"https://api.line.me/v2/bot/room/{s['roomId']}/member/{uid}"\n        else:u=f"https://api.line.me/v2/bot/profile/{uid}"\n        r=requests.get(u,headers=h,timeout=10)\n        return r.json().get("displayName","ユーザー") if r.ok else "ユーザー"\n    except:return "ユーザー"'''
new='''PROFILE_CACHE={}\ndef name(e):\n    s=e.get("source",{}); uid=s.get("userId")\n    if not uid:return "ユーザー"\n    now=time.time(); cached=PROFILE_CACHE.get(uid)\n    if cached and now-cached[0] < 600:return cached[1]\n    try:\n        h={"Authorization":f"Bearer {TOKEN}"}\n        if s.get("type")=="group":u=f"https://api.line.me/v2/bot/group/{s['groupId']}/member/{uid}"\n        elif s.get("type")=="room":u=f"https://api.line.me/v2/bot/room/{s['roomId']}/member/{uid}"\n        else:u=f"https://api.line.me/v2/bot/profile/{uid}"\n        r=HTTP.get(u,headers=h,timeout=5)\n        result=r.json().get("displayName","ユーザー") if r.ok else "ユーザー"\n        PROFILE_CACHE[uid]=(now,result)\n        if len(PROFILE_CACHE)>500: PROFILE_CACHE.clear()\n        return result\n    except:return cached[1] if cached else "ユーザー"'''
if old not in s: raise SystemExit('name target missing')
s=s.replace(old,new,1)

# 4) Connection reuse for reply and media fetch.
s=s.replace('r=requests.post("https://api.line.me/v2/bot/message/reply",','r=HTTP.post("https://api.line.me/v2/bot/message/reply",',1)
s=s.replace('r=requests.get(f"https://api-data.line.me/v2/bot/message/{mid}/content",','r=HTTP.get(f"https://api-data.line.me/v2/bot/message/{mid}/content",',1)

# 5) Add lightweight latency logs so next optimization is evidence-based.
old_ai='''def ai(text,uid,cid,img=None,mime=None,extra=""):\n    parts=[{"type":"input_text","text":ctx(uid,cid,text,extra)+"\\n【今回】\\n"+text[:4000]}]'''
new_ai='''def ai(text,uid,cid,img=None,mime=None,extra=""):\n    started=time.perf_counter()\n    parts=[{"type":"input_text","text":ctx(uid,cid,text,extra)+"\\n【今回】\\n"+text[:4000]}]'''
if old_ai not in s: raise SystemExit('ai target missing')
s=s.replace(old_ai,new_ai,1)
s=s.replace('if d.get("output_text"):return d["output_text"].strip()','if d.get("output_text"):\n            print("LATENCY_AI_MS",round((time.perf_counter()-started)*1000),flush=True); return d["output_text"].strip()',1)
s=s.replace('if answer:return answer','if answer:\n            print("LATENCY_AI_MS",round((time.perf_counter()-started)*1000),flush=True); return answer',1)

p.write_text(s)
