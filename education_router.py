import re

# Rules that can safely become company skills without changing executable code.
EDUCATION_PATTERNS = re.compile(
    r"(今後|これから|次から|ルール|覚えて|教育|対応して|表記|呼び方|順番|言い方|必ず|しないで)", re.I
)
# Requests that clearly require executable/UI/integration changes must go through PR approval.
CODE_PATTERNS = re.compile(
    r"(コード|実装|機能|API|連携|GitHub|PR|デプロイ|Webhook|自動送信|画面|ボタン|PDF|画像生成|バグ|エラー|直して|改善して)", re.I
)


def classify_instruction(text):
    t=(text or '').strip()
    if not t:
        return 'chat'
    if CODE_PATTERNS.search(t):
        return 'code_change'
    if EDUCATION_PATTERNS.search(t):
        return 'education'
    return 'chat'


def approval_required(kind):
    return kind == 'code_change'


def education_confirmation(rule):
    return f"了解、船長。この内容は業務ルールとして覚えます。\n{rule.strip()}"


def code_change_confirmation():
    return "これはコード変更が必要です。改善案をPRにして、船長の『反映して』があるまで本番には入れません。"
