from intent_router import should_create_reminder, reminder_has_enough_context, reminder_needs_timing


def test_normal_messages_never_schedule():
    for text in ['ナミ、テスト','ナミ、これの見積もり教えて','赤崎、見積もりお願い','タスク管理して']:
        assert not should_create_reminder(text)


def test_explicit_with_timing_schedules():
    t='赤崎の見積もりを10分おきにリマインドして'
    assert should_create_reminder(t)
    assert reminder_has_enough_context(t)


def test_explicit_without_timing_asks_instead_of_defaulting():
    t='赤崎の見積もりをリマインドして'
    assert should_create_reminder(t)
    assert reminder_needs_timing(t)
    assert not reminder_has_enough_context(t)
