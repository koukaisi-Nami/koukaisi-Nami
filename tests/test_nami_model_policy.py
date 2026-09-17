import unittest
from nami_model_policy import ModelTier, policy_for, should_escalate


class ModelPolicyTests(unittest.TestCase):
    def test_chat_stays_fast(self):
        p=policy_for('chat')
        self.assertEqual(p.tier, ModelTier.FAST)
        self.assertFalse(p.reviewer)

    def test_self_improvement_uses_strong_reviewer(self):
        p=policy_for('self_improvement')
        self.assertEqual(p.tier, ModelTier.STRONG)
        self.assertTrue(p.reviewer)

    def test_uncertain_work_escalates(self):
        self.assertTrue(should_escalate(uncertainty=.8))
        self.assertTrue(should_escalate(uncertainty=.1, correction_requested=True))
        self.assertFalse(should_escalate(uncertainty=.1))

    def test_document_is_bounded(self):
        p=policy_for('document', large_document=True)
        self.assertLessEqual(p.max_context_items, 18)
        self.assertLessEqual(p.max_output_tokens, 5000)


if __name__ == '__main__':
    unittest.main()
