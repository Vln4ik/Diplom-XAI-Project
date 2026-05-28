from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any

from app.core.config import get_settings
from app.services.visual_signatures import load_first_visual_page


@dataclass(frozen=True)
class VisualQualityAssessment:
    available: bool
    provider: str
    page_number: int | None
    width: int | None
    height: int | None
    contrast_score: float
    sharpness_score: float
    dark_ratio: float
    bright_ratio: float
    quality_score: float
    issue_keys: tuple[str, ...]
    evidence: tuple[str, ...]
    confidence: float
    reason: str | None = None


class VisualQualityProvider(ABC):
    @property
    @abstractmethod
    def provider_name(self) -> str:
        raise NotImplementedError

    @property
    @abstractmethod
    def mode(self) -> str:
        raise NotImplementedError

    @abstractmethod
    def assess(self, path_value: str | None) -> VisualQualityAssessment:
        raise NotImplementedError

    def describe(self) -> dict[str, object]:
        return {
            "provider": self.provider_name,
            "mode": self.mode,
            "runtime_scope": "local_server",
            "sends_documents_to_external_services": False,
        }


class DisabledVisualQualityProvider(VisualQualityProvider):
    def __init__(self, reason: str = "visual quality provider is disabled") -> None:
        self.reason = reason

    @property
    def provider_name(self) -> str:
        return "disabled"

    @property
    def mode(self) -> str:
        return "disabled"

    def assess(self, path_value: str | None) -> VisualQualityAssessment:
        return _unavailable(self.reason, provider=self.provider_name)

    def describe(self) -> dict[str, object]:
        details = super().describe()
        details["available"] = False
        details["reason"] = self.reason
        return details


class LayoutBaselineVisualQualityProvider(VisualQualityProvider):
    @property
    def provider_name(self) -> str:
        return "layout-quality-baseline-v1"

    @property
    def mode(self) -> str:
        return "baseline"

    def assess(self, path_value: str | None) -> VisualQualityAssessment:
        if not path_value:
            return _unavailable("storage path is empty", provider=self.provider_name)

        path = Path(path_value)
        if not path.exists():
            return _unavailable("source file is not available in local storage", provider=self.provider_name)

        try:
            image, page_number = load_first_visual_page(path)
        except Exception as exc:
            return _unavailable(str(exc), provider=self.provider_name)

        if image is None:
            return _unavailable("unsupported visual source", provider=self.provider_name)

        return _assess_image(image, page_number=page_number, provider=self.provider_name)

    def describe(self) -> dict[str, object]:
        details = super().describe()
        details.update(
            {
                "available": True,
                "scope": "scan_quality_baseline",
                "supported_sources": ["png", "jpg", "jpeg", "tif", "tiff", "bmp", "pdf:first_page"],
                "returns": ["contrast_score", "sharpness_score", "blank_like", "low_resolution", "evidence"],
                "production_grade": False,
            }
        )
        return details


def assess_visual_quality(path_value: str | None) -> VisualQualityAssessment:
    return get_visual_quality_provider().assess(path_value)


@lru_cache(maxsize=1)
def get_visual_quality_provider() -> VisualQualityProvider:
    provider = get_settings().visual_quality_provider.lower().replace("-", "_")
    if provider in {"disabled", "off", "none"}:
        return DisabledVisualQualityProvider()
    if provider in {"layout", "layout_baseline", "layout_quality_baseline", "baseline"}:
        return LayoutBaselineVisualQualityProvider()
    return DisabledVisualQualityProvider(reason=f"unknown visual quality provider: {get_settings().visual_quality_provider}")


def describe_visual_quality_provider() -> dict[str, object]:
    details = get_visual_quality_provider().describe()
    details["configured_provider"] = get_settings().visual_quality_provider
    return details


def _unavailable(reason: str, *, provider: str = "layout-quality-baseline-v1") -> VisualQualityAssessment:
    return VisualQualityAssessment(
        available=False,
        provider=provider,
        page_number=None,
        width=None,
        height=None,
        contrast_score=0.0,
        sharpness_score=0.0,
        dark_ratio=0.0,
        bright_ratio=0.0,
        quality_score=0.0,
        issue_keys=(),
        evidence=(),
        confidence=0.0,
        reason=reason,
    )


def _assess_image(image: Any, *, page_number: int | None, provider: str) -> VisualQualityAssessment:
    from PIL import ImageFilter, ImageOps, ImageStat  # type: ignore

    prepared = image.convert("RGB")
    width, height = prepared.size
    thumbnail = prepared.copy()
    thumbnail.thumbnail((1200, 1200))

    grayscale = ImageOps.grayscale(thumbnail)
    stat = ImageStat.Stat(grayscale)
    contrast_score = _clamp((stat.stddev[0] if stat.stddev else 0.0) / 80.0, 0.0, 1.0)

    edges = grayscale.filter(ImageFilter.FIND_EDGES)
    edge_stat = ImageStat.Stat(edges)
    sharpness_score = _clamp((edge_stat.mean[0] if edge_stat.mean else 0.0) / 30.0, 0.0, 1.0)

    histogram = grayscale.histogram()
    total_pixels = max(1, sum(histogram))
    dark_ratio = sum(histogram[:50]) / total_pixels
    bright_ratio = sum(histogram[240:]) / total_pixels

    issue_keys: list[str] = []
    if min(width, height) < 800 or width * height < 1_000_000:
        issue_keys.append("low_resolution")
    if contrast_score < 0.16:
        issue_keys.append("low_contrast")
    if sharpness_score < 0.05 and dark_ratio >= 0.003:
        issue_keys.append("low_detail_or_blur")
    if dark_ratio < 0.003 and contrast_score < 0.08:
        issue_keys.append("blank_like")
    if dark_ratio > 0.65:
        issue_keys.append("too_dark")
    if bright_ratio > 0.985 and dark_ratio < 0.006:
        issue_keys.append("mostly_empty")

    resolution_score = _clamp(min(width, height) / 1200.0, 0.0, 1.0)
    density_score = _clamp(dark_ratio / 0.04, 0.0, 1.0)
    quality_score = _clamp(
        0.28 * resolution_score + 0.28 * contrast_score + 0.24 * sharpness_score + 0.20 * density_score,
        0.0,
        1.0,
    )
    confidence = _clamp(0.56 + len(issue_keys) * 0.08, 0.0, 0.9) if issue_keys else _clamp(0.45 + quality_score * 0.35, 0.0, 0.82)
    evidence = (
        f"page={page_number or 1}",
        f"size={width}x{height}",
        f"contrast_score={contrast_score:.3f}",
        f"sharpness_score={sharpness_score:.3f}",
        f"dark_ratio={dark_ratio:.4f}",
        f"bright_ratio={bright_ratio:.4f}",
        f"quality_score={quality_score:.3f}",
    )
    return VisualQualityAssessment(
        available=True,
        provider=provider,
        page_number=page_number,
        width=width,
        height=height,
        contrast_score=round(contrast_score, 4),
        sharpness_score=round(sharpness_score, 4),
        dark_ratio=round(dark_ratio, 5),
        bright_ratio=round(bright_ratio, 5),
        quality_score=round(quality_score, 4),
        issue_keys=tuple(issue_keys),
        evidence=evidence,
        confidence=round(confidence, 4),
        reason=None if issue_keys else "visual baseline did not find quality issues",
    )


def _clamp(value: float, minimum: float, maximum: float) -> float:
    return min(maximum, max(minimum, value))
