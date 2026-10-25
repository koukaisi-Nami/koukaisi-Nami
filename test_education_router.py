from education_router import classify_instruction, approval_required


def test_business_rule_is_education():
    assert classify_instruction('今後、仲介手数料は指定がなければ－にして') == 'education'


def test_code_change_requires_approval():
    kind=classify_instruction('LINEからPDFを自動送信する機能を実装して')
    assert kind == 'code_change'
    assert approval_required(kind)


def test_bug_fix_is_code_change():
    assert classify_instruction('このエラー直して') == 'code_change'


def test_normal_chat_is_not_saved_as_rule():
    assert classify_instruction('今日の予定教えて') == 'chat'
