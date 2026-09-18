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
