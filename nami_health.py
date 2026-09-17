"""Nami 3.0 deployment health policy.

Side-effect free: decides whether a deployment is healthy enough to keep.
Actual Render rollback/deploy actions remain in the privileged execution layer.
"""
from dataclasses import dataclass
from enum import Enum


class DeployAction(str, Enum):
    KEEP = "keep"
    ROLLBACK = "rollback"
    HOLD = "hold"


@dataclass(frozen=True)
class HealthSample:
    http_ok: bool
    webhook_ok: bool
    error_rate: float = 0.0
    p95_latency_ms: int = 0
    critical_regressions: int = 0


def decide(sample: HealthSample, baseline: HealthSample | None = None) -> DeployAction:
    if not sample.http_ok or not sample.webhook_ok:
        return DeployAction.ROLLBACK
    if sample.critical_regressions > 0:
        return DeployAction.ROLLBACK
    if not 0.0 <= sample.error_rate <= 1.0:
        return DeployAction.ROLLBACK
    if baseline:
        if sample.error_rate > max(0.05, baseline.error_rate * 2.0):
            return DeployAction.ROLLBACK
        if baseline.p95_latency_ms > 0 and sample.p95_latency_ms > baseline.p95_latency_ms * 2.5:
            return DeployAction.HOLD
    if sample.error_rate > 0.05:
        return DeployAction.HOLD
    return DeployAction.KEEP
