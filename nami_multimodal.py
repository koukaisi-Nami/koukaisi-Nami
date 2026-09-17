"""Multimodal execution policy for Nami 3.0.

Separates source analysis from generated artifacts and keeps expensive media
work bounded. Actual provider calls remain in adapters/runtime handlers.
"""
from dataclasses import dataclass
from enum import Enum


class MediaTask(str, Enum):
    ANALYZE_IMAGE = "analyze_image"
    ANALYZE_PDF = "analyze_pdf"
    GENERATE_IMAGE = "generate_image"
    GENERATE_PDF = "generate_pdf"


@dataclass(frozen=True)
class MediaPlan:
    task: MediaTask
    max_files: int
    max_pages: int
    requires_source_trace: bool
    generated_artifact: bool


def plan_media(*, has_image=False, has_pdf=False, wants_image=False, wants_pdf=False):
    if wants_image and not has_image and not has_pdf:
        return MediaPlan(MediaTask.GENERATE_IMAGE, 0, 0, False, True)
    if wants_pdf and not has_pdf and not has_image:
        return MediaPlan(MediaTask.GENERATE_PDF, 0, 0, False, True)
    if has_pdf:
        return MediaPlan(MediaTask.ANALYZE_PDF, 6, 40, True, False)
    if has_image:
        return MediaPlan(MediaTask.ANALYZE_IMAGE, 12, 0, True, False)
    if wants_image:
        return MediaPlan(MediaTask.GENERATE_IMAGE, 0, 0, False, True)
    if wants_pdf:
        return MediaPlan(MediaTask.GENERATE_PDF, 0, 0, False, True)
    raise ValueError("no media task")


def source_and_generated_must_not_mix(source_kind, output_kind):
    """True when generated media must be labeled separately from source evidence."""
    return bool(source_kind and output_kind and source_kind != output_kind)
