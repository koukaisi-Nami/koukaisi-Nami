from pathlib import Path

p=Path('app.py')
s=p.read_text()
old='from estimate_document import make_estimate_document, make_estimate_image\n'
new=old+'from nami_agent import plan_with_ai\n'
assert old in s and 'from nami_agent import plan_with_ai' not in s
s=s.replace(old,new,1)

old="""        batch_answer=None
        if is_batch_estimate_command(text):
            items=recent_estimate_batch(cid)
"""
new="""        # General semantic planner: understand intent first, then reuse the proven tools below.
        # Legacy detectors remain as a fallback while the migration is rolled out.
        recent_media=recent_estimate_batch(cid)
        plan=plan_with_ai(ai,text,uid,cid,bool(recent_media))
        semantic_batch=(plan.get('tool')=='estimate_batch' and plan.get('batch'))
        batch_answer=None
        if semantic_batch or is_batch_estimate_command(text):
            items=recent_media
"""
assert old in s
s=s.replace(old,new,1)

old="""        batch_marker=batch_artifact_marker(text) if isinstance(batch_answer,list) else None
"""
new="""        # Prefer the planner's requested output format; keep the old marker parser as fallback.
        batch_marker=None
        if isinstance(batch_answer,list):
            outs=set(plan.get('outputs') or [])
            if 'image' in outs and 'pdf' in outs: batch_marker='__ESTIMATE_BOTH__'
            elif 'pdf' in outs: batch_marker='__ESTIMATE_PDF__'
            elif 'image' in outs: batch_marker='__ESTIMATE_IMAGE__'
            else: batch_marker=batch_artifact_marker(text)
"""
assert old in s
s=s.replace(old,new,1)
p.write_text(s)
