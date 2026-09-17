import unittest
from nami_context_budget import ContextBudget, compact_items, capacity_state


class ContextBudgetTests(unittest.TestCase):
    def test_context_never_exceeds_budget(self):
        budget=ContextBudget(max_items=3,max_chars=20,per_item_chars=10)
        selected=compact_items(['abcdefghijk','1234567890','XYZXYZXYZ','tail'],budget)
        self.assertLessEqual(len(selected),3)
        self.assertLessEqual(sum(map(len,selected)),20)

    def test_source_is_not_mutated(self):
        source=['a'*50,'b'*50]
        compact_items(source,ContextBudget(max_items=1,max_chars=5,per_item_chars=5))
        self.assertEqual(source,['a'*50,'b'*50])

    def test_capacity_reports_truncation(self):
        state=capacity_state(['a'*20,'b'*20],ContextBudget(max_items=1,max_chars=10,per_item_chars=10))
        self.assertTrue(state['truncated'])
        self.assertEqual(state['selected_count'],1)


if __name__ == '__main__':
    unittest.main()
