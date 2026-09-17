import unittest
from estimate_document import _document_data

class EstimateRendererTests(unittest.TestCase):
    def test_structured_payload_keeps_proration_discount_and_total(self):
        d=_document_data({'property':'ALTERNA銀座 904号室','move_in':'15日','items':[
            {'label':'当月前家賃','amount':142400,'breakdown':'日割り16日分'},
            {'label':'仲介手数料','original_amount':273900,'discount_amount':136950,'amount':136950,'breakdown':'半額'},
        ]})
        self.assertEqual(d['move_in'],'15日')
        self.assertEqual(d['items'][0]['breakdown'],'日割り16日分')
        self.assertEqual(d['items'][1]['discount_amount'],136950)
        self.assertEqual(d['total'],279350)

    def test_legacy_text_still_supported(self):
        d=_document_data('【初期費用概算】\n物件A\n家賃：100,000円\n合計：100,000円')
        self.assertEqual(d['property'],'物件A')
        self.assertEqual(d['total'],100000)

if __name__=='__main__': unittest.main()
