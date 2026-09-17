from self_improvement_service import SelfImprovementService


class Store:
    def __init__(self): self.row=None
    def create(self,u,i): self.row=[1,i,'requested',None,None,None,None]; return 1
    def update(self,i,**kw):
        fields={'state':2,'branch':3,'pr_number':4,'test_summary':5,'deploy_sha':6}
        for k,v in kw.items(): self.row[fields[k]]=v
    def latest_pending(self,u): return tuple(self.row)

class Coder:
    def prepare_patch(self,instruction,branch): return 'patch'
class Git:
    def create_improvement_branch(self,i): return f'nami/improve-{i}'
    def apply_patch(self,b,p): pass
    def open_pr(self,b,i): return 99
    def merge_pr(self,p): return 'abc123'
class Gate:
    def run(self): return True,'OK existing estimate\nOK image/pdf'


def test_prepare_then_explicit_approval():
    store=Store(); svc=SelfImprovementService('captain',store,Coder(),Git(),Gate())
    result=svc.prepare('captain','見積を改善して')
    assert result['state']=='pr_open'
    assert result['pr_number']==99
    merged=svc.approve_and_merge('captain','反映して')
    assert merged['sha']=='abc123'
