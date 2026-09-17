import base64
import os
import unittest

import nami_frontier as nf
from nami_openai_media import wants_image_generation, generate_image


class FakeResponse:
    def __init__(self, payload=None, content=b"", ok=True, status=200):
        self._payload = payload or {}
        self.content = content
        self.ok = ok
        self.status_code = status
        self.text = ""
    def json(self):
        return self._payload


class FakeHTTP:
    def get(self, url, **kwargs):
        if url.endswith('/v1/models'):
            return FakeResponse({"data": [{"id":"gpt-image-2"}]})
        return FakeResponse(content=b"url-image")
    def post(self, url, **kwargs):
        return FakeResponse({"data": [{"b64_json": base64.b64encode(b"png-bytes").decode()}]})


class MediaTests(unittest.TestCase):
    def setUp(self):
        nf._CACHE["at"] = 0.0
        nf._CACHE["models"] = ()
        os.environ["NAMI_AUTO_MODEL_DISCOVERY"] = "false"

    def test_image_generation_intent(self):
        self.assertTrue(wants_image_generation("ナミ、船のロゴ画像を作って"))
        self.assertTrue(wants_image_generation("イラスト描いて"))
        self.assertFalse(wants_image_generation("この画像を読んで"))
        self.assertFalse(wants_image_generation("見積を画像で作って"))

    def test_image_generation_uses_frontier_model_and_returns_bytes(self):
        raw = generate_image("test", "key", FakeHTTP())
        self.assertEqual(raw, b"png-bytes")


if __name__ == '__main__':
    unittest.main()
