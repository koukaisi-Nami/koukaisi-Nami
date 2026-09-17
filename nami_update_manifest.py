"""Small, auditable manifest for Nami's automatic update loop.

The manifest contains metadata only. It never downloads or executes an update.
A separate CI job can compare these entries with approved upstream sources.
"""
from dataclasses import dataclass


@dataclass(frozen=True)
class ManagedComponent:
    name: str
    kind: str
    current: str
    update_channel: str = "stable"
    auto_test: bool = True
    auto_merge: bool = False


MANAGED_COMPONENTS = (
    ManagedComponent("python-dependencies", "dependency-set", "pinned"),
    ManagedComponent("ai-model", "model", "configured-by-env"),
    ManagedComponent("github-actions", "workflow-dependencies", "pinned"),
)


def auto_merge_allowed(component: ManagedComponent) -> bool:
    """Defense-in-depth: Nami's update system never auto-merges."""
    return False
