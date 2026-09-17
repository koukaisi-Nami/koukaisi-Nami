#!/usr/bin/env python3
import json, os, subprocess, sys, time, urllib.request

HEALTH_URL = os.environ.get("NAMI_HEALTH_URL", "https://koukaisi-nami.onrender.com/").rstrip("/") + "/"
LINE_TOKEN = os.environ.get("LINE_CHANNEL_ACCESS_TOKEN", "")
OWNER = os.environ.get("NAMI_OWNER_LINE_USER_ID", "")
SHA = os.environ.get("GITHUB_SHA", "")

def health():
    try:
        with urllib.request.urlopen(HEALTH_URL, timeout=15) as response:
            body = response.read(4096).decode("utf-8", "replace")
            return 200 <= response.status < 300 and ("航海士ナミ" in body or "航海中" in body), f"HTTP {response.status}"
    except Exception as exc:
        return False, repr(exc)

def push_line(text):
    if not LINE_TOKEN or not OWNER:
        print("LINE notify skipped: secret/owner unavailable")
        return False
    payload = json.dumps({"to": OWNER, "messages": [{"type": "text", "text": text[:4900]}]}, ensure_ascii=False).encode("utf-8")
    request = urllib.request.Request("https://api.line.me/v2/bot/message/push", data=payload, headers={"Authorization": "Bearer " + LINE_TOKEN, "Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(request, timeout=15) as response:
            return 200 <= response.status < 300
    except Exception as exc:
        print("LINE notify failed", repr(exc))
        return False

def main():
    if not SHA:
        print("GITHUB_SHA missing; refusing rollback")
        return 2
    last = "not checked"
    for attempt in range(1, 7):
        ok, last = health()
        print("health", attempt, ok, last)
        if ok:
            push_line("本番反映とヘルスチェック成功🧭\nナミは正常稼働中。\ncommit: " + SHA[:7])
            return 0
        if attempt < 6:
            time.sleep(15)
    subprocess.run(["git", "config", "user.name", "nami-safety-bot"], check=True)
    subprocess.run(["git", "config", "user.email", "nami-safety-bot@users.noreply.github.com"], check=True)
    subprocess.run(["git", "revert", "--no-edit", SHA], check=True)
    subprocess.run(["git", "push", "origin", "HEAD:main"], check=True)
    push_line("⚠️ 本番ヘルスチェックに失敗したため、自動で直前変更をロールバックしました。\n既存の記憶DBは変更していません。\n原因: " + last[:500])
    return 1

if __name__ == "__main__":
    sys.exit(main())
