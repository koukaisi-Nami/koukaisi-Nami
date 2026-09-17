from pathlib import Path
import ast

p = Path("app.py")
s = p.read_text(encoding="utf-8")
old = '''        if not r.ok:\n            print("OPENAI",r.status_code,r.text,flush=True)\n            if r.status_code==429:\n                return f"AIが混み合ってるよ🧭 上限回復まで{format_retry(r.text)}。少し時間をあけてもう一度送って。"\n            return f"AIエラー({r.status_code})"'''
new = '''        if not r.ok:\n            # Keep enough diagnostics in Render logs to tell temporary rate limits\n            # from exhausted API quota without exposing the API key.\n            request_id = r.headers.get("x-request-id") or r.headers.get("request-id") or ""\n            rate_headers = {\n                k: r.headers.get(k, "") for k in (\n                    "x-ratelimit-limit-requests",\n                    "x-ratelimit-remaining-requests",\n                    "x-ratelimit-reset-requests",\n                    "x-ratelimit-limit-tokens",\n                    "x-ratelimit-remaining-tokens",\n                    "x-ratelimit-reset-tokens",\n                    "retry-after",\n                )\n            }\n            try:\n                err = r.json().get("error", {})\n                error_type = err.get("type", "")\n                error_code = err.get("code", "")\n            except Exception:\n                error_type = ""\n                error_code = ""\n            print("OPENAI_ERROR", {\n                "status": r.status_code,\n                "request_id": request_id,\n                "error_type": error_type,\n                "error_code": error_code,\n                "rate_limit": rate_headers,\n                "body": r.text[:2000],\n            }, flush=True)\n            if r.status_code==429:\n                kind = error_code or error_type\n                if kind == "insufficient_quota":\n                    return "OpenAI APIの利用枠不足だよ🧭 時間待ちでは直らない可能性が高いので、APIのBilling / Usageを確認して。"\n                return f"AIが混み合ってるよ🧭 上限回復まで{format_retry(r.text)}。少し時間をあけてもう一度送って。"\n            return f"AIエラー({r.status_code})"'''
if s.count(old) != 1:
    raise SystemExit(f"target block count={s.count(old)}; refusing unsafe patch")
s = s.replace(old, new, 1)
ast.parse(s)
required = ["def ai(", "def manager_review(", "@app.post(\"/webhook\")", "def create_pr("]
missing = [x for x in required if x not in s]
if missing:
    raise SystemExit(f"required guards missing: {missing}")
p.write_text(s, encoding="utf-8")
print("patched app.py safely")
