from intent_router import classify_message,should_create_reminder,reminder_has_enough_context

def test_question_never_becomes_reminder():
    t='ナミ、私のことは何と呼ぶ？'
    assert classify_message(t)=='question'
    assert not should_create_reminder(t)

def test_plain_task_is_not_auto_reminder():
    assert not should_create_reminder('赤崎、見積もりお願い')

def test_explicit_reminder_is_allowed():
    t='赤崎タスク 見積もり 精算書 税務。完了報告があるまで10分おきにリマインドして'
    assert should_create_reminder(t)
    assert reminder_has_enough_context(t)

def test_normal_chat_is_chat():
    assert classify_message('おはよう')=='chat'
