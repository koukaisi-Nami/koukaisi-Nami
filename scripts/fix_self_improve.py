from pathlib import Path
import ast

p=Path('app.py')
s=p.read_text()
old='''def gh(method,path,**kwargs):\n    return requests.request(method,f"https://api.github.com/repos/{GITHUB_REPO}{path}",\n                            headers=gh_headers(),timeout=45,**kwargs)\n'''
new='''def gh(method,path,**kwargs):\n    r=requests.request(method,f"https://api.github.com/repos/{GITHUB_REPO}{path}",\n                       headers=gh_headers(),timeout=45,**kwargs)\n    if not r.ok:\n        request_id=r.headers.get("x-github-request-id","")\n        print("GITHUB_ERROR", {"method":method,"path":path,"status":r.status_code,\n              "request_id":request_id,"body":r.text[:2000]}, flush=True)\n    return r\n\ndef gh_fail(label,r):\n    request_id=r.headers.get("x-github-request-id","")\n    try:\n        d=r.json(); detail=d.get("message") or r.text[:500]\n    except Exception:\n        detail=r.text[:500]\n    raise RuntimeError(f"{label}: GitHub {r.status_code} {detail} request_id={request_id}")\n'''
if old not in s: raise SystemExit('gh target not found')
s=s.replace(old,new,1)
repls={
'if not r.ok: raise RuntimeError(f"GitHub read failed {r.status_code}")':'if not r.ok: gh_fail("GitHub read failed",r)',
'if not ref.ok: raise RuntimeError("base branch read failed")':'if not ref.ok: gh_fail("base branch read failed",ref)',
'if not r.ok: raise RuntimeError("branch create failed")':'if not r.ok: gh_fail("branch create failed",r)',
'if not r.ok: raise RuntimeError("candidate commit failed")':'if not r.ok: gh_fail("candidate commit failed",r)',
'if not r.ok: raise RuntimeError("PR create failed")':'if not r.ok: gh_fail("PR create failed",r)',
'if not pr.ok:return False,"PRを取得できなかった"':'if not pr.ok:\n        print("GITHUB_MERGE_READ_ERROR",pr.status_code,pr.text[:2000],flush=True)\n        return False,f"PRを取得できなかった (GitHub {pr.status_code})"',
'if not r.ok:return False,"GitHubマージに失敗。現行本番は維持したよ。"':'if not r.ok:\n        print("GITHUB_MERGE_ERROR",r.status_code,r.text[:2000],flush=True)\n        return False,f"GitHubマージに失敗 (GitHub {r.status_code})。現行本番は維持したよ。"'
}
for a,b in repls.items():
    if a not in s: raise SystemExit('target not found: '+a[:60])
    s=s.replace(a,b,1)
ast.parse(s)
p.write_text(s)
print('self-improvement GitHub diagnostics patched; syntax OK')
