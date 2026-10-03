from structured_estimate_runtime import _enforce_user_move_in, _user_specified_move_in
from estimate_model import estimate_to_text


def test_drawing_move_in_cannot_create_proration_without_user_date():
    data={"property":"Test 101","move_in":"2026-08-10","items":[{"key":"current_rent","label":"当月前家賃","amount":2129,"status":"known"}]}
    fixed=_enforce_user_move_in(data,"この物件の初期費用を教えて")
    assert fixed["move_in"] == ""
    assert fixed["items"][0]["amount"] is None


def test_explicit_user_move_in_is_allowed():
    assert _user_specified_move_in("8月10日入居で見積もり")
    assert _user_specified_move_in("入居日は2026/10/1")
    assert not _user_specified_move_in("この物件の初期費用を教えて")


def test_line_amounts_use_consistent_divider():
    text=estimate_to_text({"property":"Test","items":[
        {"key":"deposit","label":"敷金","amount":0},
        {"key":"guarantee","label":"初回保証料","amount":35000},
        {"key":"brokerage","label":"仲介手数料","amount":73700},
    ]})
    rows=[line for line in text.splitlines() if "｜" in line]
    assert len(rows) == 4
    assert all(" ｜ " in line for line in rows)
