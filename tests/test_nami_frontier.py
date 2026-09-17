import os
import unittest

import nami_frontier as nf


class FakeResponse:
    ok = True
    def json(self):
        return {"data": [
            {"id": "gpt-5.6-luna"},
            {"id": "gpt-5.6-terra"},
            {"id": "gpt-5.6-sol"},
            {"id": "gpt-5.7-luna"},
            {"id": "gpt-5.7-terra"},
            {"id": "gpt-5.7-sol"},
            {"id": "weird-new-model"},
        ]}


class FakeHTTP:
    def get(self, *args, **kwargs):
        return FakeResponse()


class FrontierTests(unittest.TestCase):
    def setUp(self):
        nf._CACHE["at"] = 0.0
        nf._CACHE["models"] = ()
        for name in (
            "NAMI_FAST_MODEL", "NAMI_BALANCED_MODEL", "NAMI_STRONG_MODEL",
            "NAMI_IMAGE_MODEL", "NAMI_REALTIME_MODEL", "NAMI_TRANSCRIBE_MODEL",
        ):
            os.environ.pop(name, None)
        os.environ["NAMI_AUTO_MODEL_DISCOVERY"] = "true"

    def test_verified_defaults(self):
        os.environ["NAMI_AUTO_MODEL_DISCOVERY"] = "false"
        s = nf.current_stack()
        self.assertEqual(s.fast, "gpt-5.6-luna")
        self.assertEqual(s.balanced, "gpt-5.6-terra")
        self.assertEqual(s.strong, "gpt-5.6")
        self.assertEqual(s.image, "gpt-image-2")
        self.assertEqual(s.realtime, "gpt-realtime-2.1")
        self.assertEqual(s.transcribe, "gpt-transcribe")

    def test_auto_discovery_moves_only_compatible_lanes(self):
        s = nf.current_stack("key", FakeHTTP())
        self.assertEqual(s.fast, "gpt-5.7-luna")
        self.assertEqual(s.balanced, "gpt-5.7-terra")
        self.assertEqual(s.strong, "gpt-5.7-sol")

    def test_unknown_names_never_override(self):
        self.assertIsNone(nf._version_tuple("weird-new-model"))

    def test_task_routing(self):
        os.environ["NAMI_AUTO_MODEL_DISCOVERY"] = "false"
        self.assertEqual(nf.model_for_task("chat"), "gpt-5.6-luna")
        self.assertEqual(nf.model_for_task("document"), "gpt-5.6-terra")
        self.assertEqual(nf.model_for_task("self_improvement"), "gpt-5.6")

    def test_text_risk_router(self):
        self.assertEqual(nf.task_for_text("おはよう"), "chat")
        self.assertEqual(nf.task_for_text("このPDF見て"), "balanced")
        self.assertEqual(nf.task_for_text("このコードを直して"), "self_improvement")
        self.assertEqual(nf.task_for_text("この契約内容合ってる？"), "high_risk")

    def test_reasoning_tiers(self):
        self.assertEqual(nf.reasoning_for_task("chat"), "low")
        self.assertEqual(nf.reasoning_for_task("document"), "medium")
        self.assertEqual(nf.reasoning_for_task("code_review"), "high")


if __name__ == "__main__":
    unittest.main()
