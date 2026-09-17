import json
import unittest
from nami_safety import parse_review, validate_candidate, change_risk

class SafetyTests(unittest.TestCase):
    def test_valid_review_and_fenced_json(self):
        raw='```json\n'+json.dumps({'action':'self_improve','memory_scope':'none','improvement_request':'add test'})+'\n```'
        self.assertEqual(parse_review(raw).action, 'self_improve')

    def test_malformed_is_never_approval(self):
        for raw in ('', '{"action":"approve"}', '{bad', '{"action":"memory","memory_scope":"none"}'):
            with self.assertRaises(ValueError): parse_review(raw)

    def test_candidate_safety(self):
        self.assertEqual(validate_candidate('x=1', ('def webhook(',)), ['missing:def webhook('])
        self.assertIn('possible-secret', validate_candidate('x="sk-abcdefghijklmnopqrstuvwxyz123456"'))

    def test_risk_detection(self):
        risks=change_risk('グループ記憶を改善して', ['app.py'])
        self.assertIn('memory-isolation', risks)
        self.assertIn('self-improvement-guard', change_risk('コード改善', ['nami_supervisor.py']))

if __name__ == '__main__':
    unittest.main()
