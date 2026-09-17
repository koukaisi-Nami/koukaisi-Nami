from nami_evolution import Action, Risk, UpgradeCandidate, assess, validate_changed_paths
from nami_update_manifest import MANAGED_COMPONENTS, auto_merge_allowed


def test_secret_change_is_blocked():
    c = UpgradeCandidate("x", "1", "2", Risk.LOW, requires_secret_change=True)
    assert assess(c).actions == (Action.BLOCK,)


def test_permission_change_is_blocked():
    c = UpgradeCandidate("x", "1", "2", Risk.LOW, requires_permission_change=True)
    assert assess(c).actions == (Action.BLOCK,)


def test_schema_change_requires_owner():
    c = UpgradeCandidate("db", "1", "2", Risk.MEDIUM, requires_schema_change=True)
    assert assess(c).actions == (Action.AUTO_TEST, Action.CREATE_PR, Action.OWNER_APPROVAL)


def test_high_risk_requires_owner():
    c = UpgradeCandidate("model", "1", "2", Risk.HIGH)
    assert Action.OWNER_APPROVAL in assess(c).actions


def test_dangerous_paths_rejected():
    ok, errors = validate_changed_paths([".env", ".github/workflows/deploy.yml", "a/../b"])
    assert not ok
    assert len(errors) == 3


def test_normal_paths_allowed():
    ok, errors = validate_changed_paths(["nami_evolution.py", "tests/test_nami_evolution.py"])
    assert ok and errors == ()


def test_no_component_can_auto_merge():
    assert MANAGED_COMPONENTS
    assert all(not auto_merge_allowed(c) for c in MANAGED_COMPONENTS)
