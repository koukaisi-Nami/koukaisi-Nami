"""Orchestrates Nami's improvement lifecycle without coupling it to LINE/app.py.

Concrete GitHub/code-generation adapters are injected. This keeps the existing
production webhook and business tools unchanged until the integration PR is
explicitly approved.
"""
from self_improvement import ImprovementState, SelfImprovementGuard


class SelfImprovementService:
    def __init__(self, owner_user_id, store, coder, git, regression):
        self.guard=SelfImprovementGuard(owner_user_id)
        self.store=store
        self.coder=coder
        self.git=git
        self.regression=regression

    def prepare(self, user_id: str, instruction: str):
        item=self.guard.request(user_id,instruction)
        db_id=self.store.create(user_id,instruction)
        try:
            branch=self.git.create_improvement_branch(db_id)
            self.store.update(db_id,state=ImprovementState.PLANNED.value,branch=branch)
            patch=self.coder.prepare_patch(instruction,branch=branch)
            self.git.apply_patch(branch,patch)
            self.store.update(db_id,state=ImprovementState.PATCHED.value)
            ok,summary=self.regression.run()
            self.store.update(db_id,state=(ImprovementState.TESTED if ok else ImprovementState.FAILED).value,test_summary=summary)
            if not ok:
                return {"id":db_id,"state":"failed","tests":summary}
            pr=self.git.open_pr(branch,instruction)
            self.store.update(db_id,state=ImprovementState.PR_OPEN.value,pr_number=pr)
            return {"id":db_id,"state":"pr_open","branch":branch,"pr_number":pr,"tests":summary}
        except Exception as exc:
            self.store.update(db_id,state=ImprovementState.FAILED.value,test_summary=str(exc))
            raise

    def approve_and_merge(self, user_id: str, approval_message: str):
        row=self.store.latest_pending(user_id)
        if not row:
            raise RuntimeError("No pending improvement")
        db_id,instruction,state,branch,pr_number,test_summary,deploy_sha=row
        if state != ImprovementState.PR_OPEN.value:
            raise RuntimeError("Pending improvement is not ready to merge")
        item=self.guard.request(user_id,instruction)
        item.state=ImprovementState.PR_OPEN
        item.branch=branch or ''
        item.pr_number=pr_number
        self.guard.approve(item,user_id,approval_message)
        if not self.guard.can_merge(item):
            raise RuntimeError("Merge guard rejected improvement")
        sha=self.git.merge_pr(pr_number)
        self.store.update(db_id,state=ImprovementState.APPROVED.value,deploy_sha=sha)
        return {"id":db_id,"state":"approved","sha":sha,"pr_number":pr_number}
