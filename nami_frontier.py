"""Nami frontier runtime policy.

Keeps model selection centralized, capacity-aware and forward-compatible.
The module has no DB side effects and can safely fall back to known-good models.
"""
from __future__ import annotations

from dataclasses import dataclass
import os
import re
import threading
import time
from typing import Iterable

# Current stable OpenAI frontier stack (verified against official model docs).
DEFAULT_FAST = "gpt-5.6-luna"
DEFAULT_BALANCED = "gpt-5.6-terra"
DEFAULT_STRONG = "gpt-5.6"  # alias for the current GPT-5.6 Sol line
DEFAULT_IMAGE = "gpt-image-2"
DEFAULT_REALTIME = "gpt-realtime-2.1"
DEFAULT_TRANSCRIBE = "gpt-transcribe"
DEFAULT_TTS = "gpt-4o-mini-tts"
DEFAULT_EMBEDDING = "text-embedding-3-large"

_MODEL_RE = re.compile(r"^gpt-(\d+)\.(\d+)-(sol|terra|luna)$", re.I)
_IMAGE_RE = re.compile(r"^gpt-image-(\d+)(?:\.(\d+))?$", re.I)
_REALTIME_RE = re.compile(r"^gpt-realtime-(\d+)(?:\.(\d+))?$", re.I)
_CACHE_LOCK = threading.Lock()
_CACHE = {"at": 0.0, "models": ()}
_DISCOVERY_TTL = int(os.getenv("NAMI_MODEL_DISCOVERY_TTL", "21600"))


@dataclass(frozen=True)
class FrontierStack:
    fast: str = DEFAULT_FAST
    balanced: str = DEFAULT_BALANCED
    strong: str = DEFAULT_STRONG
    image: str = DEFAULT_IMAGE
    realtime: str = DEFAULT_REALTIME
    transcribe: str = DEFAULT_TRANSCRIBE
    tts: str = DEFAULT_TTS
    embedding: str = DEFAULT_EMBEDDING


def _version_tuple(model_id: str):
    m = _MODEL_RE.match(model_id or "")
    if not m:
        return None
    return int(m.group(1)), int(m.group(2)), m.group(3).lower()


def _latest_lane(model_ids: Iterable[str], lane: str, fallback: str) -> str:
    rows = []
    for model_id in model_ids or ():
        parsed = _version_tuple(model_id)
        if parsed and parsed[2] == lane:
            rows.append((parsed[0], parsed[1], model_id))
    if not rows:
        return fallback
    rows.sort(reverse=True)
    return rows[0][2]


def _latest_specialized(model_ids: Iterable[str], pattern, fallback: str) -> str:
    rows = []
    for model_id in model_ids or ():
        m = pattern.match(model_id or "")
        if m:
            rows.append((int(m.group(1)), int(m.group(2) or 0), model_id))
    if not rows:
        return fallback
    rows.sort(reverse=True)
    return rows[0][2]


def _fetch_model_ids(api_key: str, http) -> tuple[str, ...]:
    if not api_key or http is None:
        return ()
    now = time.time()
    with _CACHE_LOCK:
        if now - float(_CACHE.get("at", 0.0)) < _DISCOVERY_TTL:
            return tuple(_CACHE.get("models") or ())
    try:
        response = http.get(
            "https://api.openai.com/v1/models",
            headers={"Authorization": f"Bearer {api_key}"},
            timeout=15,
        )
        if not response.ok:
            return ()
        payload = response.json()
        ids = tuple(sorted({str(x.get("id", "")) for x in payload.get("data", []) if x.get("id")}))
        with _CACHE_LOCK:
            _CACHE["at"] = now
            _CACHE["models"] = ids
        return ids
    except Exception:
        return ()


def current_stack(api_key: str = "", http=None) -> FrontierStack:
    """Return current compatible frontier models.

    Newer compatible Sol/Terra/Luna, GPT-Image and GPT-Realtime versions visible
    to the account are selected automatically. Unknown naming schemes are ignored,
    so an unrelated new product can never silently replace production.
    """
    fast = os.getenv("NAMI_FAST_MODEL", DEFAULT_FAST)
    balanced = os.getenv("NAMI_BALANCED_MODEL", DEFAULT_BALANCED)
    strong = os.getenv("NAMI_STRONG_MODEL", DEFAULT_STRONG)
    image = os.getenv("NAMI_IMAGE_MODEL", DEFAULT_IMAGE)
    realtime = os.getenv("NAMI_REALTIME_MODEL", DEFAULT_REALTIME)
    transcribe = os.getenv("NAMI_TRANSCRIBE_MODEL", DEFAULT_TRANSCRIBE)
    tts = os.getenv("NAMI_TTS_MODEL", DEFAULT_TTS)
    embedding = os.getenv("NAMI_EMBEDDING_MODEL", DEFAULT_EMBEDDING)

    discover = os.getenv("NAMI_AUTO_MODEL_DISCOVERY", "true").lower() == "true"
    if discover:
        ids = _fetch_model_ids(api_key, http)
        if ids:
            fast = _latest_lane(ids, "luna", fast)
            balanced = _latest_lane(ids, "terra", balanced)
            sol = _latest_lane(ids, "sol", "")
            if sol:
                strong = sol
            image = _latest_specialized(ids, _IMAGE_RE, image)
            realtime = _latest_specialized(ids, _REALTIME_RE, realtime)
    return FrontierStack(fast, balanced, strong, image, realtime, transcribe, tts, embedding)


def task_for_text(text: str = "") -> str:
    t = (text or "").lower()
    if re.search(r"(コード|実装|自己改善|github|\bpr\b|デバッグ|バグ|セキュリティ)", t, re.I):
        return "self_improvement"
    if re.search(r"(契約|重説|法令|税務|訴訟|個人情報|審査|重要|最終確認|合ってる|違くない)", t, re.I):
        return "high_risk"
    if re.search(r"(pdf|書類|請求書|契約書|図面|画像|写真|見積|初期費用|検索|調べて|最新|公式)", t, re.I):
        return "balanced"
    return "chat"


def model_for_task(task: str, api_key: str = "", http=None) -> str:
    stack = current_stack(api_key, http)
    task = (task or "chat").lower()
    if task in {"self_improvement", "code_review", "high_risk", "supervisor"}:
        return stack.strong
    if task in {"balanced", "document", "vision", "estimate", "knowledge", "web", "manager"}:
        return stack.balanced
    return stack.fast


def reasoning_for_task(task: str) -> str:
    task = (task or "chat").lower()
    if task in {"self_improvement", "code_review", "high_risk", "supervisor"}:
        return "high"
    if task in {"document", "vision", "estimate", "knowledge", "web", "manager", "balanced"}:
        return "medium"
    return "low"


def frontier_snapshot(api_key: str = "", http=None) -> dict:
    s = current_stack(api_key, http)
    return {
        "fast": s.fast,
        "balanced": s.balanced,
        "strong": s.strong,
        "image": s.image,
        "realtime": s.realtime,
        "transcribe": s.transcribe,
        "tts": s.tts,
        "embedding": s.embedding,
        "auto_discovery": os.getenv("NAMI_AUTO_MODEL_DISCOVERY", "true").lower() == "true",
    }
