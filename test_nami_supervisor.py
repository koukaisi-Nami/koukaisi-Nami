from nami_supervisor import route_intent, line_scope, wants_company_memory, needs_supervisor_review, reviewer_instructions


def test_owner_fix_is_self_improvement_even_with_memory_words():
    text = "個人・グループ・全社の記憶を消さずに、この機能を直してPRを作って"
    assert route_intent(text, is_owner=True) == "self_improve"


def test_personal_preference_is_memory():
    assert route_intent("俺のこと船長って呼んで、覚えて", is_owner=True) == "memory"


def test_personal_line_never_becomes_group_scope():
    assert line_scope({"type": "user", "userId": "U1"}) == ("user", "U1")


def test_group_uses_real_group_id():
    assert line_scope({"type": "group", "groupId": "G1", "userId": "U1"}) == ("conversation", "group:G1")


def test_room_uses_real_room_id():
    assert line_scope({"type": "room", "roomId": "R1", "userId": "U1"}) == ("conversation", "room:R1")


def test_company_requires_explicit_memory_action():
    assert wants_company_memory("会社共通ルールとしてこれを覚えて")
    assert not wants_company_memory("個人・グループ・会社共通の記憶を分離するコードを直して")


def test_correction_triggers_reviewer():
    assert needs_supervisor_review("ナミ、これ違くない？")
    assert needs_supervisor_review("これ合ってる？")
    assert not needs_supervisor_review("今日の予定教えて")


def test_reviewer_contract_keeps_merge_and_company_memory_safe():
    contract = reviewer_instructions()
    assert "コードを直接マージしない" in contract
    assert "会社記憶" in contract
