"""Post-deploy verification contract for shared Nami releases."""


class DeploymentGuard:
    def __init__(self, health_check, regression_check):
        self.health_check=health_check
        self.regression_check=regression_check

    def verify(self):
        health=bool(self.health_check())
        regression_ok,summary=self.regression_check()
        return {
            'ok': health and regression_ok,
            'health': health,
            'regression': regression_ok,
            'summary': summary,
        }
