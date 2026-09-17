#!/usr/bin/env python3
"""Post-deploy guard for Nami.
Checks production health after main changes. On repeated failure, reverts the just-merged
commit (never rewrites history), pushes the revert, and reports outcome to captain via LINE.
Secrets are read only from GitHub Actions secrets/environment.
"""
import json, os, subprocess, sys, time, urllib.request

HEALTH_URL=os.environ.get('NAMI_HEALTH_URL','https://koukaisi-nami.onrender.com/').rstrip('/')+'/'
LINE_TOKEN=os.environ.get('LINE_CHANNEL_ACCESS_TOKEN','')
OWNER=os.environ.get('NAMI_OWNER_LINE_USER_ID','')
SHA=os.environ.get('GITHUB_SHA','')

def health():
    try:
        with urllib.request.urlopen(HEALTH_URL, timeout=15) as r:
            body=r.read(4096).decode('utf-8','replace')
            return 200 <= r.status < 300 and ('航海士ナミ' in body or '航海中' in body), f'HTTP {r.status}'
    except Exception as e:return False,repr(e)

def push_line(text):
    if not LINE_TOKEN or not OWNER:
        print('LINE notify skipped: secret/owner unavailable'); return False
    data=json.dumps({'to':OWNER,'messages':[{'type':'text','text':text[:4900]}],ensure_ascii=False).encode()
    req=urllib.request.Request('https://api.line.me/v2/bot/message/push',data=data,headers={'Authorization':'Bearer '+LINE_TOKEN,'Content-Type':'application/json'})
    try:
        with urllib.request.urlopen(req,timeout=15) as r:
            print('LINE notify',r.status); return 200 <= r.status < 300
    except Exception as e:
        print('LINE notify failed',repr(e)); return False

def main():
    # Render may still be rolling over after GitHub main changes; bounded wait only in CI.
    last='not checked'
    for attempt in range(1,7):
        ok,last=health(); print('health',attempt,ok,last)
        if ok:
            push_line('本番反映とヘルスチェック成功🧭\nナミは正常稼働中。\ncommit: '+SHA[:7])
            return 0
        time.sleep(15)
    # Fail closed: revert exactly the current main commit; do not touch DB or memories.
    print('health failed repeatedly; reverting',SHA)
    subprocess.run(['git','config','user.name','nami-safety-bot'],check=True)
    subprocess.run(['git','config','user.email','nami-safety-bot@users.noreply.github.com'],check=True)
    subprocess.run(['git','revert','--no-edit',SHA],check=True)
    subprocess.run(['git','push','origin','HEAD:main'],check=True)
    push_line('⚠️ 本番ヘルスチェックに失敗したため、自動で直前変更をロールバックしました。\n既存の記憶DBは変更していません。\n原因: '+last[:500])
    return 1

if __name__=='__main__':sys.exit(main())
