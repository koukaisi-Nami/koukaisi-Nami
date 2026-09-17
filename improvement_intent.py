"""Structured intent contract for deciding whether a LINE instruction changes Nami itself.

The LLM may classify meaning, but deterministic permission gates in
self_improvement.py remain authoritative.
"""
import json

SCHEMA={
    "kind":"chat|memory|global_improvement|approve_improvement",
    "instruction":"",
    "scope":"conversation|user|company|global",
    "reason":""
}


def classifier_prompt(text: str) -> str:
    return f"""次のLINEメッセージの意図をJSONだけで分類する。
単なる会話、覚えてほしい情報、ナミ自身の能力/動作/コードを今後変える指示、本番反映の承認を区別する。
キーワード一致ではなく文脈と意味で判断する。
global_improvement は『今後こうして』『機能追加』『この動作を直して』等、全ナミの能力を変える要求。
approve_improvement は直前にテスト済みPRが提示されている場合の明示的な反映承認。
形式: {json.dumps(SCHEMA,ensure_ascii=False)}
メッセージ: {text}"""


def parse_intent(raw: str) -> dict:
    raw=(raw or '').strip().removeprefix('```json').removeprefix('```').removesuffix('```').strip()
    obj=json.loads(raw)
    kind=obj.get('kind')
    if kind not in {'chat','memory','global_improvement','approve_improvement'}:
        raise ValueError('invalid intent kind')
    return {"kind":kind,"instruction":str(obj.get('instruction') or ''),"scope":str(obj.get('scope') or 'conversation'),"reason":str(obj.get('reason') or '')}
