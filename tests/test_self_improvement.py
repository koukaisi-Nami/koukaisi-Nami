import pytest
from self_improvement import ImprovementState, RegressionGate, SelfImprovementGuard


def test_non_owner_cannot_request_global_change():
    guard=SelfImprovementGuard("captain")
    with pytest.raises(PermissionError):
        guard.request("crew", "見積を変えて")


def test_owner_cannot_approve_before_tests():
    guard=SelfImprovementGuard("captain")
    item=guard.request("captain", "見積を変えて")
    with pytest.raises(RuntimeError):
        guard.approve(item,"captain","反映して")


def test_explicit_approval_required_after_tests():
    guard=SelfImprovementGuard("captain")
    item=guard.request("captain", "見積を変えて")
    item.state=ImprovementState.TESTED
    with pytest.raises(PermissionError):
        guard.approve(item,"captain","いいね")
    guard.approve(item,"captain","反映して")
    assert item.state == ImprovementState.APPROVED


def test_merge_requires_pr_and_approval():
    guard=SelfImprovementGuard("captain")
    item=guard.request("captain", "改善")
    item.state=ImprovementState.TESTED
    item.pr_number=50
    assert not guard.can_merge(item)
    guard.approve(item,"captain","マージして")
    assert guard.can_merge(item)


def test_regression_gate_fails_closed():
    gate=RegressionGate()
    gate.add("existing estimate", lambda: True)
    gate.add("existing image", lambda: False)
    ok,summary=gate.run()
    assert not ok
    assert "OK existing estimate" in summary
    assert "NG existing image" in summary
