"""Nami 3.0 capability router.

Small, dependency-free policy layer. It chooses a capability; it does not execute
external tools. Existing Nami handlers remain the source of truth until each
capability is migrated behind this interface.
"""
from dataclasses import dataclass
from enum import Enum


class Capability(str, Enum):
    CHAT = "chat"
    KNOWLEDGE = "knowledge"
    WEB = "web"
    VISION = "vision"
    DOCUMENT = "document"
    ESTIMATE = "estimate"
    IMAGE_GENERATION = "image_generation"
    SELF_IMPROVEMENT = "self_improvement"


@dataclass(frozen=True)
class Route:
    capability: Capability
    reason: str
    requires_confirmation: bool = False


def route(text="", *, has_image=False, has_pdf=False, owner=False):
    t = (text or "").strip().lower()
    if owner and any(x in t for x in ("コードを直", "改善して", "修正して", "実装して", "prを")):
        return Route(Capability.SELF_IMPROVEMENT, "owner-requested code change", True)
    if has_pdf or any(x in t for x in ("pdf", "請求書", "契約書", "書類")):
        return Route(Capability.DOCUMENT, "document task")
    if has_image or any(x in t for x in ("図面", "写真", "画像", "スクショ")):
        return Route(Capability.VISION, "visual task")
    if any(x in t for x in ("見積", "初期費用", "請求")):
        return Route(Capability.ESTIMATE, "structured business calculation")
    if any(x in t for x in ("画像作って", "画像生成", "バナー", "イラスト")):
        return Route(Capability.IMAGE_GENERATION, "image generation task")
    if any(x in t for x in ("検索", "調べて", "最新", "公式")):
        return Route(Capability.WEB, "fresh external information")
    if any(x in t for x in ("覚えて", "知識", "ルール", "教えて")):
        return Route(Capability.KNOWLEDGE, "knowledge or memory task")
    return Route(Capability.CHAT, "normal conversation")
