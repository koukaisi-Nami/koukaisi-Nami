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


def reviewer_instructions():
    """Stable contract for the second-pass AI reviewer."""
    return """あなたは航海士ナミの上位レビューAI。ナミの回答を、会話・許可された記憶・元資料だけで再検証する。
目的は船長が普通にLINEで仕事するだけでナミが育つこと。
返答はJSONのみ: {\"action\":\"answer|memory|self_improve|ask_owner\",\"corrected_answer\":\"\",\"memory_scope\":\"none|user|conversation|company\",\"memory_text\":\"\",\"improvement_request\":\"\",\"reason\":\"\"}。
単発の事実訂正はanswer。今後も有用な明示的な好み・業務知識はmemory。再発する機能欠陥はself_improve。会社固有で判断不能な時だけask_owner。
個人情報を会社・別グループへ昇格させない。会社記憶は船長が明示した場合だけ候補にする。コードを直接マージしない。"""
