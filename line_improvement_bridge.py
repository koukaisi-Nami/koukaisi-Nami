"""Thin LINE-facing bridge for Nami self-improvement.

No webhook code is changed here. app.py can opt into this bridge after existing
capability regression tests are green.
"""
from improvement_intent import classifier_prompt, parse_intent


class LineImprovementBridge:
    def __init__(self, classify_ai, service, owner_user_id):
        self.classify_ai=classify_ai
        self.service=service
        self.owner_user_id=owner_user_id

    def handle(self, user_id: str, text: str):
        # Non-owners never enter the global code-change path.
        if user_id != self.owner_user_id:
            return None
        intent=parse_intent(self.classify_ai(classifier_prompt(text)))
        if intent['kind']=='global_improvement':
            result=self.service.prepare(user_id,intent['instruction'] or text)
            if result['state']=='failed':
                return '改善案は作ったけど既存機能テストで止めたよ。\n'+result.get('tests','')
            return f"改善案を作ってテストしたよ。PR #{result['pr_number']}。本番にはまだ反映してない。反映するなら『反映して』と送って。"
        if intent['kind']=='approve_improvement':
            result=self.service.approve_and_merge(user_id,text)
            return f"承認を受けてPR #{result['pr_number']}をmainへ反映したよ。デプロイ確認が終わるまでは本番成功扱いにしない。"
        return None
