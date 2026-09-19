from pathlib import Path

p=Path('app.py')
s=p.read_text()

# This migration is intentionally idempotent. Current app.py may already use the
# newer line_estimate_intent router, so an already-migrated/newer implementation
# is a successful no-op rather than a CI failure.
if 'from nami_agent import plan_with_ai' not in s:
    if 'from line_estimate_intent import should_batch_estimate' in s:
        p.write_text(s)
        raise SystemExit(0)
    anchor='from estimate_document import make_estimate_document, make_estimate_image'
    if anchor not in s:
        raise AssertionError('estimate integration anchor missing')
    s=s.replace(anchor, anchor+'\nfrom nami_agent import plan_with_ai', 1)

old="""        batch_answer=None
        if is_batch_estimate_command(text):
            items=recent_estimate_batch(cid)
"""
new="""        recent_media=recent_estimate_batch(cid)
        plan=plan_with_ai(ai,text,uid,cid,bool(recent_media))
        semantic_batch=(plan.get('tool')=='estimate_batch' and plan.get('batch'))
        batch_answer=None
        if semantic_batch or is_batch_estimate_command(text):
            items=recent_media
"""
if old in s:
    s=s.replace(old,new,1)

old="""        batch_marker=batch_artifact_marker(text) if isinstance(batch_answer,list) else None
"""
new="""        batch_marker=None
        if isinstance(batch_answer,list):
            outs=set(plan.get('outputs') or [])
            if 'image' in outs and 'pdf' in outs: batch_marker='__ESTIMATE_BOTH__'
            elif 'pdf' in outs: batch_marker='__ESTIMATE_PDF__'
            elif 'image' in outs: batch_marker='__ESTIMATE_IMAGE__'
            else: batch_marker=batch_artifact_marker(text)
"""
if old in s:
    s=s.replace(old,new,1)

p.write_text(s)
