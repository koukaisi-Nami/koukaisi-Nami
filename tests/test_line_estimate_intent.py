from line_estimate_intent import (
    is_contextual_estimate_request, should_batch_estimate,
    requested_count, needs_count_warning,
)

def test_five_files_natural_command():
    assert should_batch_estimate("ここから続くPDFファイル5件分見積もり出して",5)

def test_followup_without_repeating_estimate_word():
    assert should_batch_estimate("これ全部お願い",5)
    assert should_batch_estimate("さっきのやつ出して",5)
    assert should_batch_estimate("これら見て",3)

def test_no_material_never_hijacks_chat():
    assert not should_batch_estimate("これ全部お願い",0)
    assert not should_batch_estimate("お願い",0)

def test_single_material_can_be_contextual():
    assert should_batch_estimate("この資料お願い",1)

def test_count_detection():
    assert requested_count("5件分お願い")==5
    assert requested_count("５物件見積もり")==5
    assert requested_count("五件見積もり")==5
    assert requested_count("全部お願い") is None

def test_count_mismatch_is_detectable():
    assert needs_count_warning("5件見積もり",4)
    assert not needs_count_warning("5件見積もり",5)


def test_plain_media_upload_requires_no_estimate_action():
    # Media uploads are handled before text intent routing; without an explicit
    # follow-up text there is no estimate command to execute.
    assert not should_batch_estimate("",1)
    assert should_batch_estimate("ナミ、見積もりちょうだい",1)
