import os
import unittest
from unittest.mock import patch

from owner_guard import can_self_improve, owner_lock_configured


class OwnerGuardTests(unittest.TestCase):
    def test_fails_closed_without_owner(self):
        with patch.dict(os.environ, {}, clear=True):
            self.assertFalse(owner_lock_configured())
            self.assertFalse(can_self_improve("U123"))

    def test_only_configured_owner_is_allowed(self):
        with patch.dict(os.environ, {"NAMI_OWNER_LINE_USER_ID": "UOWNER"}, clear=True):
            self.assertTrue(owner_lock_configured())
            self.assertTrue(can_self_improve("UOWNER"))
            self.assertFalse(can_self_improve("UOTHER"))

    def test_multiple_owner_env_is_supported(self):
        with patch.dict(os.environ, {"NAMI_OWNER_LINE_USER_IDS": "U1,U2"}, clear=True):
            self.assertTrue(can_self_improve("U1"))
            self.assertTrue(can_self_improve("U2"))
            self.assertFalse(can_self_improve("U3"))


if __name__ == "__main__":
    unittest.main()
