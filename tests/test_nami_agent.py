import unittest
from nami_agent import normalize_plan, plan_with_ai

class PlannerTests(unittest.TestCase):
    def test_normalize_outputs(self):
        p=normalize_plan({'tool':'estimate_batch','outputs':['image','pdf','image'],'batch':True},'x')
        self.assertEqual(p['outputs'],['image','pdf'])
        self.assertTrue(p['batch'])
    def test_unknown_tool_falls_back_chat(self):
        self.assertEqual(normalize_plan({'tool':'destroy_everything'},'hello')['tool'],'chat')
    def test_natural_language_json(self):
        def fake(prompt,uid,cid):
            return '```json\n{"tool":"estimate_batch","outputs":["image"],"batch":true,"needs_recent_media":true,"instruction":"3件を画像見積","confidence":0.98}\n```'
        p=plan_with_ai(fake,'この3件、全部画像で出して','u','c',True)
        self.assertEqual(p['tool'],'estimate_batch')
        self.assertEqual(p['outputs'],['image'])
        self.assertTrue(p['needs_recent_media'])
    def test_bad_ai_is_safe_chat(self):
        p=plan_with_ai(lambda *a:'not json','雑談しよ','u','c')
        self.assertEqual(p['tool'],'chat')
        self.assertEqual(p['confidence'],0.0)

if __name__=='__main__': unittest.main()
