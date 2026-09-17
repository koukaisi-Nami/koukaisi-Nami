"""Capacity-aware, provider-neutral model policy for Nami 3.0.

The policy decides how much reasoning/context a capability may consume. Model
names stay in environment/configuration; this module only selects a tier.
"""
from dataclasses import dataclass
from enum import Enum


class ModelTier(str, Enum):
    FAST = "fast"
    BALANCED = "balanced"
    STRONG = "strong"


@dataclass(frozen=True)
class ModelPolicy:
    tier: ModelTier
    max_context_items: int
    max_output_tokens: int
    timeout_seconds: int
    reviewer: bool = False


FAST_CAPABILITIES = {"chat", "memory", "reminder"}
STRONG_CAPABILITIES = {"self_improvement", "code_review"}


def policy_for(capability: str, *, uncertainty: float = 0.0, high_risk: bool = False,
               large_document: bool = False) -> ModelPolicy:
    cap = (capability or "chat").strip().lower()
    uncertainty = max(0.0, min(1.0, float(uncertainty or 0.0)))

    if high_risk or cap in STRONG_CAPABILITIES:
        return ModelPolicy(ModelTier.STRONG, 18, 5000, 90, reviewer=True)
    if large_document or cap in {"document", "vision", "estimate", "knowledge", "web"} or uncertainty >= 0.45:
        return ModelPolicy(ModelTier.BALANCED, 12, 3200, 60, reviewer=uncertainty >= 0.7)
    if cap in FAST_CAPABILITIES:
        return ModelPolicy(ModelTier.FAST, 6, 1400, 30, reviewer=False)
    return ModelPolicy(ModelTier.BALANCED, 10, 2400, 45, reviewer=False)


def should_escalate(*, uncertainty: float, correction_requested: bool = False,
                    high_risk: bool = False) -> bool:
    return bool(high_risk or correction_requested or float(uncertainty or 0.0) >= 0.7)
