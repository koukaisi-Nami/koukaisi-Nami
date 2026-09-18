import json
from structured_estimate_runtime import _extract

def test_extract_plain_json():
    assert _extract('{"property":"A","items":[]}')["property"]=="A"

def test_extract_fenced_json():
    raw='\`\`\`json\n{"property":"A","items":[]}\n\`\`\`'
    assert _extract(raw)["property"]=="A"

def test_extract_repairs_smart_quotes_and_trailing_comma():
    raw='説明\n{“property”:“A”,“items”:[],}\n以上'
    data=_extract(raw)
    assert data["property"]=="A"
    assert data["items"]==[]


def test_generate_retries_until_valid_json():
    from structured_estimate_runtime import generate
    replies=iter([
        'not json',
        '{"property":"A","items":[{"key":"next_rent","label":"次月前家賃","amount":147000,}],',
        '{"property":"A","items":[{"key":"next_rent","label":"次月前家賃","amount":147000}],"notes":[]}'
    ])
    calls=[]
    def fake_ai(req,uid,cid):
        calls.append(req)
        return next(replies)
    data=generate(fake_ai,'2026年9月15日入居','賃料141000円 管理費6000円','u','c','A')
    assert data["property"]=="A"
    assert len(calls)==3
    assert next(x for x in data["items"] if x["key"]=="next_rent")["amount"]==147000
