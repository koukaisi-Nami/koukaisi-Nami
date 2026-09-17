from line_improvement_bridge import LineImprovementBridge


class Service:
    def prepare(self,u,i): return {'state':'pr_open','pr_number':7,'tests':'OK'}
    def approve_and_merge(self,u,t): return {'pr_number':7,'sha':'abc'}


def classify(prompt):
    return '{"kind":"global_improvement","instruction":"見積改善","scope":"global","reason":"能力変更"}'


def test_non_owner_bypasses_code_change_path():
    bridge=LineImprovementBridge(classify,Service(),'captain')
    assert bridge.handle('crew','ナミを改善して') is None


def test_owner_can_prepare_but_not_auto_merge():
    bridge=LineImprovementBridge(classify,Service(),'captain')
    text=bridge.handle('captain','今後見積を改善して')
    assert 'PR #7' in text
    assert 'まだ反映してない' in text
