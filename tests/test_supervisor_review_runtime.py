from pathlib import Path

APP=Path('app.py').read_text()
PATCH=Path('scripts/implement_supervisor_review_loop.py').read_text()

def test_runtime_has_real_supervisor_call():
    assert 'def supervisor_review(' in APP
    assert 'requests.post(OA' in APP[APP.index('def supervisor_review('):APP.index('def reviewed_candidate(')]

def test_review_loop_is_bounded_to_three():
    block=APP[APP.index('def reviewed_candidate('):APP.index('def create_pr(')]
    assert 'range(1,4)' in block
    assert 'attempt>=3' in block

def test_create_pr_requires_reviewed_candidate():
    block=APP[APP.index('def create_pr('):APP.index('def attach_pr(')]
    assert 'reviewed_candidate(req_text)' in block
    assert 'if review_error:return None' in block

def test_no_auto_merge_in_review_loop():
    block=APP[APP.index('def supervisor_review('):APP.index('def attach_pr(')]
    assert '/merge' not in block

def test_patch_never_destroys_memories():
    upper=PATCH.upper()
    for bad in ('DROP TABLE','DELETE FROM MEMORIES','TRUNCATE','UPDATE MEMORIES'):
        assert bad not in upper
