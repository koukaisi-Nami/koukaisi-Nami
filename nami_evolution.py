"""Nami 3.0 safe auto-evolution policy.

This module is intentionally side-effect free. It decides whether a proposed
upgrade may proceed; execution (PRs/deploys) remains outside this policy layer.
"""
from dataclasses import dataclass, field
from enum import Enum
from typing import Iterable


class Risk(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class Action(str, Enum):
    AUTO_TEST = "auto_test"
    CREATE_PR = "create_pr"
    OWNER_APPROVAL = "owner_approval"
    BLOCK = "block"


@dataclass(frozen=True)
class UpgradeCandidate:
    component: str
    current_version: str
    target_version: str
    risk: Risk
    reason: str = ""
    changed_files: tuple[str, ...] = ()
    requires_schema_change: bool = False
    requires_secret_change: bool = False
    requires_permission_change: bool = False


@dataclass(frozen=True)
class EvolutionDecision:
    actions: tuple[Action, ...]
    reasons: tuple[str, ...] = ()
    max_attempts: int = 3


def assess(candidate: UpgradeCandidate) -> EvolutionDecision:
    reasons: list[str] = []
    if candidate.requires_secret_change:
        return EvolutionDecision((Action.BLOCK,), ("secret changes are never auto-applied",))
    if candidate.requires_permission_change:
        return EvolutionDecision((Action.BLOCK,), ("permission changes require explicit owner workflow",))
    if candidate.requires_schema_change:
        return EvolutionDecision((Action.AUTO_TEST, Action.CREATE_PR, Action.OWNER_APPROVAL), ("database/schema changes require owner approval",))
    if candidate.risk is Risk.CRITICAL:
        return EvolutionDecision((Action.BLOCK,), ("critical-risk upgrade",))
    if candidate.risk is Risk.HIGH:
        return EvolutionDecision((Action.AUTO_TEST, Action.CREATE_PR, Action.OWNER_APPROVAL), ("high-risk upgrade",))
    if candidate.risk is Risk.MEDIUM:
        return EvolutionDecision((Action.AUTO_TEST, Action.CREATE_PR), ("medium-risk upgrade",))
    return EvolutionDecision((Action.AUTO_TEST, Action.CREATE_PR), ("low-risk upgrade",))


def validate_changed_paths(paths: Iterable[str]) -> tuple[bool, tuple[str, ...]]:
    """Reject dangerous paths before an upgrade can reach a PR."""
    blocked_prefixes = (".github/workflows/",)
    blocked_names = {".env", ".env.production", "id_rsa", "credentials.json"}
    normalized = tuple(p.replace("\\", "/").lstrip("/") for p in paths)
    errors: list[str] = []
    for path in normalized:
        if path in blocked_names:
            errors.append(f"secret-like path: {path}")
        if path.startswith(blocked_prefixes):
            errors.append(f"workflow change requires dedicated review: {path}")
        if ".." in path.split("/"):
            errors.append(f"path traversal: {path}")
    return not errors, tuple(errors)
