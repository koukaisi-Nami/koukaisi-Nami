from deployment_guard import DeploymentGuard


def test_deploy_success_requires_health_and_regression():
    guard=DeploymentGuard(lambda: True,lambda:(True,'OK'))
    assert guard.verify()['ok'] is True


def test_unhealthy_deploy_is_not_success():
    guard=DeploymentGuard(lambda: False,lambda:(True,'OK'))
    assert guard.verify()['ok'] is False
