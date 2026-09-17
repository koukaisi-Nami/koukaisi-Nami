import unittest
from estimate_model import normalize_estimate
from estimate_document import _detail, make_estimate_document, make_estimate_image

class EstimateRendererTests(unittest.TestCase):
    def test_structured_payload_keeps_proration_discount_and_total(self):
        d=normalize_estimate({'property':'ALTERNA銀座 904号室','move_in':'15日','items':[
            {'key':'current_rent','label':'当月前家賃','amount':142400,'breakdown':'日割り16日分'},
            {'key':'brokerage','label':'仲介手数料','original_amount':273900,'discount_amount':136950,'amount':136950,'breakdown':'半額'},
        ]})
        self.assertEqual(d['move_in'],'15日')
        self.assertEqual(d['items'][0]['breakdown'],'日割り16日分')
        self.assertEqual(d['items'][1]['discount_amount'],136950)
        self.assertEqual(d['total'],279350)
        self.assertEqual(_detail(d['items'][1]),'通常273,900円 → 割引136,950円')

    def test_unknown_has_no_noisy_detail(self):
        self.assertEqual(_detail({'amount':None,'breakdown':''}),'')

    def test_pdf_and_png_render(self):
        payload={'property':'物件A','items':[{'key':'next_rent','label':'次月前家賃','amount':100000,'breakdown':''}]}
        self.assertGreater(len(make_estimate_document(payload).getvalue()),1000)
        self.assertGreater(len(make_estimate_image(payload).getvalue()),1000)

if __name__=='__main__': unittest.main()
