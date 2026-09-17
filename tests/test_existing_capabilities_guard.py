"""Fail the shared-brain PR if core existing Nami capability modules disappear."""
from pathlib import Path


def test_existing_capability_files_are_preserved():
    required=[
        'app.py',
        'estimate_model.py',
        'estimate_document.py',
        'structured_estimate_runtime.py',
    ]
    missing=[p for p in required if not Path(p).exists()]
    assert not missing, f"Existing Nami capabilities removed: {missing}"
