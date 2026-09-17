import unittest

from nami_orchestrator import allowed_to_execute, build_plan
from nami_router import Capability


class OrchestratorTests(unittest.TestCase):
    def test_normal_chat_stays_light(self):
        p = build_plan("元気？")
        self.assertEqual(p.route.capability, Capability.CHAT)
        self.assertTrue(allowed_to_execute(p))

    def test_document_gets_cross_check(self):
        p = build_plan("このPDFを確認して", has_pdf=True)
        self.assertEqual(p.route.capability, Capability.DOCUMENT)
        self.assertLessEqual(len(p.steps), 6)
        self.assertIn(Capability.KNOWLEDGE, [s.capability for s in p.steps])

    def test_self_improvement_fails_closed(self):
        p = build_plan("コードを改善して", owner=True, changed_files=["app.py"])
        self.assertEqual(p.route.capability, Capability.SELF_IMPROVEMENT)
        self.assertFalse(allowed_to_execute(p))
        self.assertTrue(allowed_to_execute(p, owner_confirmed=True))
        self.assertIn("self-improvement-guard", p.risks)


if __name__ == "__main__":
    unittest.main()
