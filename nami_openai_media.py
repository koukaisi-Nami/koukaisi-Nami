"""Frontier media adapters for Nami.

Provider calls are isolated here so app.py stays small. Each call is bounded and
returns bytes/text only; LINE delivery remains in the runtime layer.
"""
from __future__ import annotations

import base64
import io
import os
import re

from nami_frontier import current_stack


IMAGE_ENDPOINT = "https://api.openai.com/v1/images/generations"
TRANSCRIBE_ENDPOINT = "https://api.openai.com/v1/audio/transcriptions"
SPEECH_ENDPOINT = "https://api.openai.com/v1/audio/speech"


def wants_image_generation(text: str) -> bool:
    t = (text or "").strip()
    if not t:
        return False
    create = re.search(r"(画像|イラスト|バナー|ロゴ|サムネ|ビジュアル).{0,18}(作って|生成|描いて|デザイン|つくって)", t, re.I)
    create = create or re.search(r"(作って|生成して|描いて).{0,18}(画像|イラスト|バナー|ロゴ|サムネ)", t, re.I)
    # Do not hijack existing estimate/document artifact requests.
    business_artifact = re.search(r"(見積|初期費用|請求書|契約書).{0,20}(画像|PDF)", t, re.I)
    return bool(create and not business_artifact)


def image_prompt(text: str) -> str:
    t = re.sub(r"^(ナミ|なみ|nami)[、,\s]*", "", (text or "").strip(), flags=re.I)
    return t[:6000]


def generate_image(prompt: str, api_key: str, http, *, size: str = "1024x1024") -> bytes:
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY missing")
    stack = current_stack(api_key, http)
    payload = {
        "model": stack.image,
        "prompt": (prompt or "")[:6000],
        "size": size,
        "output_format": "png",
    }
    r = http.post(
        IMAGE_ENDPOINT,
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
        json=payload,
        timeout=110,
    )
    if not r.ok:
        raise RuntimeError(f"image generation failed {r.status_code}: {r.text[:500]}")
    data = r.json().get("data") or []
    if not data:
        raise RuntimeError("image generation returned no data")
    item = data[0]
    b64 = item.get("b64_json")
    if b64:
        raw = base64.b64decode(b64)
        if raw:
            return raw
    url = item.get("url")
    if url:
        rr = http.get(url, timeout=30)
        if rr.ok and rr.content:
            return rr.content
    raise RuntimeError("image generation returned no image bytes")


def transcribe(audio: bytes, filename: str, api_key: str, http) -> str:
    if not audio or not api_key:
        raise RuntimeError("audio/api key missing")
    stack = current_stack(api_key, http)
    files = {"file": (filename or "audio.m4a", io.BytesIO(audio))}
    data = {"model": stack.transcribe}
    r = http.post(TRANSCRIBE_ENDPOINT, headers={"Authorization": f"Bearer {api_key}"}, files=files, data=data, timeout=110)
    if not r.ok:
        raise RuntimeError(f"transcription failed {r.status_code}: {r.text[:500]}")
    payload = r.json()
    return str(payload.get("text") or "").strip()


def synthesize_speech(text: str, api_key: str, http, *, voice: str | None = None) -> bytes:
    if not text or not api_key:
        raise RuntimeError("text/api key missing")
    stack = current_stack(api_key, http)
    payload = {
        "model": stack.tts,
        "voice": voice or os.getenv("NAMI_TTS_VOICE", "alloy"),
        "input": text[:4000],
        "response_format": "mp3",
    }
    r = http.post(SPEECH_ENDPOINT, headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}, json=payload, timeout=90)
    if not r.ok or not r.content:
        raise RuntimeError(f"speech generation failed {r.status_code}: {r.text[:500]}")
    return r.content
