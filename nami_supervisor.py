"""Supervisor/reviewer layer for Nami.

Pure routing helpers live here so they can be regression-tested without touching
PostgreSQL. Persistence remains in app.py and existing memories are never reset.
"""
import re

SELF_IMPROVE_RE = re.compile(
    r"(改善して|直して|修正して|改修して|機能追加|できるようにして|アップデートして|"
    r"コード.{0,20}(?:直|変更|修正)|PR.{0,20}(?:作|作成)|実装して|仕様.{0,20}(?:変|変更))",
    re.I,
)
EXPLICIT_MEMORY_RE = re.compile(r"(覚えて|記憶して|保存して|今後はこれで|このやり方を覚えて)", re.I)
COMPANY_SCOPE_RE = re.compile(r"(全社共通|会社共通|会社全体|社内共通|全グループ共通|会社ルール|弊社ルール)", re.I)


def route_intent(text, is_owner=False):
    """Return self_improve before any memory interpretation for owner requests."""
    t = (text or "").strip()
    if is_owner and SELF_IMPROVE_RE.search(t):
        return "self_improve"
    if EXPLICIT_MEMORY_RE.search(t):
        return "memory"
    return "chat"


def line_scope(source):
    """Resolve LINE source without guessing a group id from message text."""
    source = source or {}
    typ = source.get("type")
    if typ == "group" and source.get("groupId"):
        return "conversation", "group:" + source["groupId"]
    if typ == "room" and source.get("roomId"):
        return "conversation", "room:" + source["roomId"]
    return "user", str(source.get("userId") or "unknown")


def wants_company_memory(text):
    return bool(COMPANY_SCOPE_RE.search(text or "") and EXPLICIT_MEMORY_RE.search(text or ""))


def needs_supervisor_review(text, answer=""):
    """Cheap trigger: ask the reviewer only when uncertainty/correction is visible."""
    blob = (text or "") + "\n" + (answer or "")
    return bool(re.search(r"(これ違|間違|合ってる|確認して|自信ない|不明|わからない|要確認|怪しい)", blob, re.I))
