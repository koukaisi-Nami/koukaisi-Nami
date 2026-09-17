"""Owner-only authorization for Nami self-improvement.

Keep feature availability global across every LINE conversation while restricting
code-changing actions to explicitly configured owner LINE user IDs.
"""
import os


def _owner_ids():
    raw = os.getenv("NAMI_OWNER_LINE_USER_IDS", "") or os.getenv("NAMI_OWNER_LINE_USER_ID", "")
    return {value.strip() for value in raw.split(",") if value.strip()}


def owner_lock_configured():
    return bool(_owner_ids())


def can_self_improve(user_id):
    """Fail closed: nobody can change code until an owner ID is configured."""
    return bool(user_id) and user_id in _owner_ids()
