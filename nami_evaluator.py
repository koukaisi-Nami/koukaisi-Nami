"""Nami 3.0 evaluator policy for multi-agent review.

Reviewers are advisory. Any malformed/high-risk result fails closed and no
reviewer can merge or deploy code.
"""
from dataclasses import dataclass
from enum import Enum
from typing import Iterable


class Verdict(str, Enum):
    APPROVE = "approve"
    FIX = "fix"
    REJECT = "reject"


@dataclass(frozen=True)
class Review:
    verdict: Verdict
    reason: str = ""
    confidence: float = 0.0


@dataclass(frozen=True)
class Evaluation:
    verdict: Verdict
    reasons: tuple[str, ...]
    requires_owner: bool = False


def evaluate(reviews: Iterable[Review], *, high_risk: bool = False) -> Evaluation:
    rows = tuple(reviews)
    if not rows:
        return Evaluation(Verdict.REJECT, ("no reviewer result",), high_risk)
    reasons = tuple(r.reason for r in rows if r.reason)
    if any(r.verdict is Verdict.REJECT for r in rows):
        return Evaluation(Verdict.REJECT, reasons or ("review rejected",), high_risk)
    if any(r.verdict is Verdict.FIX for r in rows):
        return Evaluation(Verdict.FIX, reasons or ("review requires changes",), high_risk)
    if not all(r.verdict is Verdict.APPROVE and 0.0 <= r.confidence <= 1.0 for r in rows):
        return Evaluation(Verdict.REJECT, ("invalid reviewer result",), high_risk)
    return Evaluation(Verdict.APPROVE, reasons, high_risk)


def parse_review(data) -> Review:
    if not isinstance(data, dict):
        raise ValueError("review must be an object")
    raw = data.get("verdict")
    try:
        verdict = Verdict(raw)
    except Exception as exc:
        raise ValueError("invalid verdict") from exc
    confidence = float(data.get("confidence", 0.0))
    if not 0.0 <= confidence <= 1.0:
        raise ValueError("invalid confidence")
    return Review(verdict, str(data.get("reason", ""))[:2000], confidence)
