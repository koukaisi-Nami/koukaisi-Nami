"""Nami 3.0 lightweight orchestration kernel.

Keeps routing/policy separate from tool execution so capabilities can grow without
inflating app.py. It produces a bounded execution plan; adapters execute the plan.
"""
from dataclasses import dataclass, field
from typing import Mapping, Sequence

from nami_router import Capability, Route, route
from nami_safety import change_risk

MAX_STEPS = 6


@dataclass(frozen=True)
class ExecutionStep:
    capability: Capability
    purpose: str
    required: bool = True


@dataclass(frozen=True)
class Plan:
    route: Route
    steps: tuple[ExecutionStep, ...]
    risks: tuple[str, ...] = field(default_factory=tuple)
    needs_owner: bool = False


def build_plan(text: str = "", *, has_image=False, has_pdf=False,
               owner=False, changed_files: Sequence[str] = ()) -> Plan:
    """Build a bounded plan without executing tools or mutating state."""
    r = route(text, has_image=has_image, has_pdf=has_pdf, owner=owner)
    steps = [ExecutionStep(r.capability, r.reason)]

    # Compound tasks get a cheap verification stage rather than a second model call.
    if r.capability in {Capability.VISION, Capability.DOCUMENT, Capability.ESTIMATE}:
        steps.append(ExecutionStep(Capability.KNOWLEDGE, "cross-check against known rules"))

    risks = change_risk(text, changed_files)
    if r.capability == Capability.SELF_IMPROVEMENT:
        steps.append(ExecutionStep(Capability.SELF_IMPROVEMENT, "review, test and propose change"))
        risks = tuple(sorted(set(risks) | {"self-improvement-guard"}))

    steps = tuple(steps[:MAX_STEPS])
    return Plan(r, steps, risks, needs_owner=r.requires_confirmation)


def allowed_to_execute(plan: Plan, *, owner_confirmed=False) -> bool:
    """Fail closed for privileged plans; normal capability plans remain executable."""
    if plan.needs_owner and not owner_confirmed:
        return False
    return bool(plan.steps) and len(plan.steps) <= MAX_STEPS
