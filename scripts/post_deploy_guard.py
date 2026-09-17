#!/usr/bin/env python3
"""Post-deploy guard for Nami.
Verify production after a main change. If the deployed app stays unhealthy, revert only
that change with a normal Git revert commit. Never touch the memory database.
"""
import json
import os
import subprocess
import sys
import time
import urllib.request

HEALTH_URL = os.environ.get("NAMI_HEALTH_URL", "https://koukaisi-nami.onrender.com/").rstrip("/") + "/"
LINE_TOKEN = os.environ.get("LINE_CHANNEL_ACCESS_TOKEN", "")
OWNER = os.environ.get("NAMI_OWNER_LINE_USER_ID", "")
SHA = os.environ.get("GITHUB_SHA", "")


def health():
    try:
        with urllib.request.urlopen(HEALTH_URL, timeout=15) as response:
            body = response.read(4096).decode("utf-8", "replace")
            healthy = 200 <= response.status < 300 and ("航海士ナミ" in body or "航海中" in body)
            return healthy, f"HTTP {response.status}"
    except Exception as exc:
        return False, repr(exc)


def push_line(text):
    if not LINE_TOKEN or not OWNER:
        print("LINE notify skipped: secret/owner unavailable")
        return False
    payload = json.dumps(
        {"to": OWNER, "messages": [{"type": "text", "text": text[:4900]}]},
        ensure_ascii=False,
    ).encode("utf-8")
    request = urllib.request.Request(
        "https://api.line.me/v2/bot/message/push",
        data=payload,
        headers={"Authorization": "Bearer " + LINE_TOKEN, "Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(request, timeout=15) as response:
            print("LINE notify", response.status)
            return 200 <= response.status < 300
    except Exception as exc:
        print("LINE notify failed", repr(exc))
        return False


def main():
    if not SHA:
        print("GITHUB_SHA missing; refusing rollback")
        return 2

    # Render can still be deploying immediately after the main push.
    # Six bounded checks keep this outside the normal LINE request path.
    last = "not checked"
    for attempt in range(1, 7):
        ok, last = health()
        print("health", attempt, ok, last)
        if ok:
            push_line("本番反映とヘルスチェック成功🧭\nナミは正常稼働中。\ncommit: " + SHA[:7])
            return 0
        if attempt < 6:
            time.sleep(15)

    print("health failed repeatedly; reverting", SHA)
    subprocess.run(["git", "config", "user.name", "nami-safety-bot"], check=True)
    subprocess.run(["git", "config", "user.email", "nami-safety-bot@users.noreply.github.com"], check=True)
    subprocess.run(["git", "revert", "--no-edit", SHA], check=True)
    subprocess.run(["git", "push", "origin", "HEAD:main"], check=True)
    push_line(
        "⚠️ 本番ヘルスチェックに失敗したため、自動で直前変更をロールバックしました。\n"
        "既存の記憶DBは変更していません。\n原因: " + last[:500]
    )
    return 1


if __name__ == "__main__":
    sys.exit(main())
