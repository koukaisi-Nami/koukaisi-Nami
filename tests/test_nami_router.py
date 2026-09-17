import unittest
from nami_router import Capability, route


class NamiRouterTests(unittest.TestCase):
    def test_owner_code_change_requires_confirmation(self):
        r = route("コードを直して", owner=True)
        self.assertEqual(r.capability, Capability.SELF_IMPROVEMENT)
        self.assertTrue(r.requires_confirmation)

    def test_pdf_routes_to_document(self):
        self.assertEqual(route("このPDFを読んで").capability, Capability.DOCUMENT)

    def test_image_routes_to_vision(self):
        self.assertEqual(route("この図面を読んで").capability, Capability.VISION)

    def test_estimate_routes_to_structured_engine(self):
        self.assertEqual(route("初期費用を出して").capability, Capability.ESTIMATE)

    def test_fresh_info_routes_to_web(self):
        self.assertEqual(route("最新情報を調べて").capability, Capability.WEB)

    def test_default_is_chat(self):
        self.assertEqual(route("おはよう").capability, Capability.CHAT)


if __name__ == "__main__":
    unittest.main()
