"""Compact safety kernel for Nami self-improvement. Fail closed."""
from dataclasses import dataclass
import ast, json, re

ALLOWED_REVIEW_ACTIONS = {"answer", "memory", "self_improve", "ask_owner"}
ALLOWED_MEMORY_SCOPES = {"none", "user", "conversation", "company"}
MAX_REVIEW_BYTES = 24_000
MAX_RETRIES = 3

@dataclass(frozen=True)
class ReviewResult:
    action: str
    corrected_answer: str = ""
    memory_scope: str = "none"
    memory_text: str = ""
    improvement_request: str = ""
    reason: str = ""


def parse_review(raw):
    if not isinstance(raw, str) or not raw.strip():
        raise ValueError("empty reviewer output")
    if len(raw.encode("utf-8")) > MAX_REVIEW_BYTES:
        raise ValueError("reviewer output too large")
    text = re.sub(r"^```(?:json)?\s*", "", raw.strip(), flags=re.I)
    text = re.sub(r"\s*```$", "", text)
    try:
        obj = json.loads(text)
    except json.JSONDecodeError as exc:
        raise ValueError("invalid reviewer JSON") from exc
    if not isinstance(obj, dict):
        raise ValueError("reviewer result must be an object")
    action, scope = obj.get("action"), obj.get("memory_scope", "none")
    if action not in ALLOWED_REVIEW_ACTIONS:
        raise ValueError("invalid reviewer action")
    if scope not in ALLOWED_MEMORY_SCOPES:
        raise ValueError("invalid memory scope")
    if action == "memory" and scope == "none":
        raise ValueError("memory action requires a scope")
    if action == "self_improve" and not str(obj.get("improvement_request", "")).strip():
        raise ValueError("self_improve requires improvement_request")
    return ReviewResult(action, str(obj.get("corrected_answer", "")), scope,
                        str(obj.get("memory_text", "")),
                        str(obj.get("improvement_request", "")),
                        str(obj.get("reason", "")))


def validate_candidate(source, required_markers=()):
    errors = []
    try:
        ast.parse(source)
    except SyntaxError as exc:
        errors.append(f"syntax:{exc}")
    for marker in required_markers:
        if marker not in source:
            errors.append(f"missing:{marker}")
    if re.search(r"(?:sk-[A-Za-z0-9_-]{20,}|gh[pousr]_[A-Za-z0-9]{20,})", source):
        errors.append("possible-secret")
    return errors


def change_risk(request_text, changed_files):
    text = ((request_text or "") + " " + " ".join(changed_files or [])).lower()
    checks = {
        "memory-isolation": ("memory", "記憶", "group", "グループ"),
        "database-compatibility": ("db", "postgres", "migration", "保存"),
        "self-improvement-guard": ("github", "pr", "self", "改善", "コード"),
        "line-regression": ("line", "webhook", "reply", "返信"),
        "credential-safety": ("secret", "token", "key", "権限"),
    }
    return tuple(sorted(k for k, words in checks.items() if any(w in text for w in words)))
