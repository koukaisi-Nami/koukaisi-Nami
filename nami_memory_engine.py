"""Nami 3.0 memory/retrieval policy.

Pure policy only: existing PostgreSQL storage remains the source of truth.
This module prevents cross-scope leakage and caps prompt context independently
from how much durable memory is stored.
"""
from dataclasses import dataclass
from typing import Iterable

MAX_CONTEXT_ITEMS = 8
MAX_CONTEXT_CHARS = 6000
ALLOWED_SCOPES = {"user", "conversation", "company"}


@dataclass(frozen=True)
class MemoryHit:
    scope: str
    scope_id: str
    content: str
    relevance: float = 0.0
    updated_at: float = 0.0


def allowed_scope_ids(uid: str, cid: str) -> tuple[tuple[str, str], ...]:
    if not uid or not cid:
        raise ValueError("uid and cid are required")
    return (("user", uid), ("conversation", cid), ("company", "company"))


def select_context(hits: Iterable[MemoryHit], uid: str, cid: str,
                   max_items: int = MAX_CONTEXT_ITEMS,
                   max_chars: int = MAX_CONTEXT_CHARS) -> tuple[MemoryHit, ...]:
    """Return only relevant, authorized memories within a hard prompt budget."""
    if max_items < 1 or max_chars < 1:
        return ()
    allowed = set(allowed_scope_ids(uid, cid))
    candidates = []
    for hit in hits:
        if hit.scope not in ALLOWED_SCOPES:
            continue
        if (hit.scope, hit.scope_id) not in allowed:
            continue
        text = (hit.content or "").strip()
        if not text:
            continue
        candidates.append(MemoryHit(hit.scope, hit.scope_id, text,
                                    float(hit.relevance), float(hit.updated_at)))
    candidates.sort(key=lambda h: (h.relevance, h.updated_at), reverse=True)
    selected, used = [], 0
    for hit in candidates:
        if len(selected) >= max_items:
            break
        remaining = max_chars - used
        if remaining <= 0:
            break
        text = hit.content[:remaining]
        if not text:
            break
        selected.append(MemoryHit(hit.scope, hit.scope_id, text,
                                  hit.relevance, hit.updated_at))
        used += len(text)
    return tuple(selected)


def render_context(hits: Iterable[MemoryHit]) -> str:
    return "\n".join(f"[{h.scope}] {h.content}" for h in hits)
