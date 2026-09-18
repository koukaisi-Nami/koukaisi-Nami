from pathlib import Path
p=Path('app.py'); s=p.read_text()

# This integration is already present in production app.py.
# Keep this CI helper idempotent: verify the required anchors instead of
# trying to re-apply an obsolete source patch.
required = [
    'from structured_estimate_runtime import generate_text as structured_estimate',
    'ESTIMATE_CACHE[key]=(time.time(),estimate_data)',
    'return (marker,estimate_data,estimate_text)',
]
missing=[anchor for anchor in required if anchor not in s]
if missing:
    raise AssertionError('structured estimate integration missing: '+', '.join(missing))
print('structured estimate integration already connected')
