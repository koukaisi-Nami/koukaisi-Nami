"""Bounded context helpers.

Long-term data remains in storage; only a compact, relevant working set is sent
to models. This keeps memory growth independent from prompt growth.
"""
from dataclasses import dataclass


@dataclass(frozen=True)
class ContextBudget:
    max_items: int = 12
    max_chars: int = 12000
    per_item_chars: int = 1800


def compact_items(items, budget=ContextBudget()):
    """Return a deterministic bounded working set without mutating source data."""
    out=[]
    used=0
    for item in items or ():
        text=str(item or "").strip()
        if not text:
            continue
        text=text[:budget.per_item_chars]
        remaining=budget.max_chars-used
        if remaining <= 0 or len(out) >= budget.max_items:
            break
        if len(text) > remaining:
            text=text[:remaining]
        out.append(text)
        used += len(text)
    return tuple(out)


def capacity_state(items, budget=ContextBudget()):
    compact=compact_items(items,budget)
    original_count=len(items or ())
    return {
        "selected_count": len(compact),
        "original_count": original_count,
        "truncated": len(compact) < original_count or sum(len(str(x or "")) for x in (items or ())) > budget.max_chars,
        "chars": sum(len(x) for x in compact),
    }
