import unittest
from estimate_model import normalize_estimate, estimate_to_text

class EstimateModelTests(unittest.TestCase):
    def sample(self):
        return {'property':'ALTERNA銀座 904号室','move_in':'15日','items':[
            {'key':'current_rent','label':'当月前家賃','amount':142400,'breakdown':'日割り16日分'},
            {'key':'next_rent','label':'次月前家賃','amount':269000},
            {'key':'brokerage','label':'仲介手数料','original_amount':273900,'discount_amount':136950,'amount':136950,'breakdown':'半額'},
        ]}
    def test_total_uses_final_amount_only(self):
        d=normalize_estimate(self.sample())
        self.assertEqual(d['total'],548350)
    def test_proration_and_discount_are_preserved(self):
        t=estimate_to_text(self.sample())
        self.assertIn('日割り16日分',t)
        self.assertIn('仲介手数料：136,950円（半額）',t)
        self.assertIn('初期費用合計：548,350円',t)
    def test_unknown_never_drops_structure(self):
        d=normalize_estimate({'property':'X','items':[{'label':'鍵交換','amount':None}]})
        self.assertEqual(len(d['items']),1)
        self.assertFalse(d['total_complete'])
        self.assertIn('要確認',estimate_to_text(d))

if __name__=='__main__': unittest.main()
