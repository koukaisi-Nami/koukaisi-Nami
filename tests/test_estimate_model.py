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
        self.assertIn('仲介手数料　136,950円（半額）',t)
        self.assertIn('合計　548,350円',t)
    def test_unknown_never_drops_structure(self):
        d=normalize_estimate({'property':'X','items':[{'label':'鍵交換','amount':None}]})
        self.assertEqual(len(d['items']),1)
        self.assertFalse(d['total_complete'])
        text=estimate_to_text(d)
        self.assertIn('鍵交換　－',text)
        self.assertNotIn('要確認',text)
        self.assertNotIn('※要確認項目は合計に含まれていません',text)

    def test_gran_paseo_customer_format_stays_clean(self):
        d={'property':'GRAN PASEO北新宿 107号室','items':[
            {'key':'current_rent','label':'当月前家賃','amount':None,'breakdown':'フリーレント2ヶ月。入居日不明'},
            {'key':'next_rent','label':'次月前家賃','amount':162000},
            {'key':'deposit','label':'敷金','amount':0},
            {'key':'key_money','label':'礼金','amount':0},
            {'key':'guarantee','label':'初回保証料','amount':81000},
            {'key':'brokerage','label':'仲介手数料','amount':165000},
            {'key':'insurance','label':'火災保険','amount':None},
            {'key':'support','label':'24時間サポート','amount':22000},
            {'key':'key_exchange','label':'鍵交換','amount':27500},
            {'key':'admin','label':'事務手数料','amount':None},
        ]}
        t=estimate_to_text(d)
        self.assertIn('当月前家賃　－',t)
        self.assertNotIn('フリーレント2ヶ月',t)
        self.assertIn('24時間サポート　22,000円',t)
        self.assertIn('鍵交換　27,500円',t)
        self.assertIn('火災保険：－',t)
        self.assertNotIn('要確認',t)

if __name__=='__main__': unittest.main()
