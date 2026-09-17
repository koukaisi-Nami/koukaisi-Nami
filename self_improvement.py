"""Safe self-improvement workflow for Nami.

Nami may prepare improvements from the owner's LINE instructions, but production
changes require explicit owner approval. Existing tools stay untouched until a
reviewed PR is merged and deployed.
"""
from dataclasses import dataclass
from enum import Enum
from typing import Callable, Optional


class ImprovementState(str, Enum):
    REQUESTED = "requested"
    PLANNED = "planned"
    PATCHED = "patched"
    TESTED = "tested"
    PR_OPEN = "pr_open"
    APPROVED = "approved"
    DEPLOYED = "deployed"
    FAILED = "failed"


@dataclass
class Improvement:
    instruction: str
    requested_by: str
    state: ImprovementState = ImprovementState.REQUESTED
    branch: str = ""
    pr_number: Optional[int] = None
    test_summary: str = ""
    deploy_sha: str = ""


class SelfImprovementGuard:
    """Permission/state guard shared by LINE and GitHub adapters."""

    APPROVAL_PHRASES = {"反映して", "本番反映", "マージして", "適用して"}

    def __init__(self, owner_user_id: str):
        if not owner_user_id:
            raise ValueError("owner_user_id is required")
        self.owner_user_id = owner_user_id

    def is_owner(self, user_id: str) -> bool:
        return bool(user_id) and user_id == self.owner_user_id

    def require_owner(self, user_id: str) -> None:
        if not self.is_owner(user_id):
            raise PermissionError("Only the owner can modify Nami globally")

    def request(self, user_id: str, instruction: str) -> Improvement:
        self.require_owner(user_id)
        instruction = (instruction or "").strip()
        if not instruction:
            raise ValueError("instruction is required")
        return Improvement(instruction=instruction, requested_by=user_id)

    def approve(self, improvement: Improvement, user_id: str, message: str) -> Improvement:
        self.require_owner(user_id)
        if improvement.state not in {ImprovementState.TESTED, ImprovementState.PR_OPEN}:
            raise RuntimeError("Improvement must pass tests before approval")
        normalized = (message or "").strip()
        if not any(p in normalized for p in self.APPROVAL_PHRASES):
            raise PermissionError("Explicit production approval is required")
        improvement.state = ImprovementState.APPROVED
        return improvement

    def can_merge(self, improvement: Improvement) -> bool:
        return improvement.state == ImprovementState.APPROVED and improvement.pr_number is not None


class RegressionGate:
    """All registered checks must pass before Nami may ask for production approval."""

    def __init__(self):
        self.checks: list[tuple[str, Callable[[], bool]]] = []

    def add(self, name: str, check: Callable[[], bool]):
        self.checks.append((name, check))

    def run(self) -> tuple[bool, str]:
        results=[]; ok=True
        for name, check in self.checks:
            try:
                passed=bool(check())
            except Exception as exc:
                passed=False
                results.append(f"NG {name}: {exc}")
            else:
                results.append(("OK " if passed else "NG ")+name)
            ok = ok and passed
        return ok, "\n".join(results)
