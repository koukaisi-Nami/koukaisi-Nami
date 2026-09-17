"""Stable capability contracts for Nami 3.0.

Adapters are intentionally tiny. Heavy knowledge, files and model payloads stay
outside the application process; this module only defines routing contracts.
"""
from dataclasses import dataclass
from typing import Any, Protocol

from nami_router import Capability


@dataclass(frozen=True)
class CapabilityRequest:
    capability: Capability
    text: str = ""
    payload: Any = None
    user_scope: str | None = None
    conversation_scope: str | None = None


@dataclass(frozen=True)
class CapabilityResult:
    ok: bool
    output: Any = None
    source: str = ""
    error: str = ""


class CapabilityAdapter(Protocol):
    capability: Capability

    def execute(self, request: CapabilityRequest) -> CapabilityResult: ...


class NullAdapter:
    """Safe placeholder used until a real provider is explicitly enabled."""

    def __init__(self, capability: Capability):
        self.capability = capability

    def execute(self, request: CapabilityRequest) -> CapabilityResult:
        if request.capability != self.capability:
            return CapabilityResult(False, error="capability mismatch")
        return CapabilityResult(False, error=f"adapter disabled: {self.capability.value}")


def default_adapters() -> dict[Capability, CapabilityAdapter]:
    return {cap: NullAdapter(cap) for cap in Capability}
