import pytest
from improvement_intent import parse_intent


def test_parse_global_improvement():
    out=parse_intent('{"kind":"global_improvement","instruction":"見積を直す","scope":"global","reason":"能力変更"}')
    assert out['kind']=='global_improvement'
    assert out['scope']=='global'


def test_reject_unknown_kind():
    with pytest.raises(ValueError):
        parse_intent('{"kind":"whatever"}')
