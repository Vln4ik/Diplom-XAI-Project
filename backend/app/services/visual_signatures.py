from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any

from app.core.config import get_settings


@dataclass(frozen=True)
class VisualMark:
    kind: str
    confidence: float
    bbox: tuple[float, float, float, float]
    evidence: str


@dataclass(frozen=True)
class VisualSignatureDetection:
    available: bool
    provider: str
    page_number: int | None
    signature_like: bool
    seal_like: bool
    confidence: float
    marks: tuple[VisualMark, ...]
    reason: str | None = None


class VisualSignatureProvider(ABC):
    @property
    @abstractmethod
    def provider_name(self) -> str:
        raise NotImplementedError

    @property
    @abstractmethod
    def mode(self) -> str:
        raise NotImplementedError

    @abstractmethod
    def detect(self, path_value: str | None) -> VisualSignatureDetection:
        raise NotImplementedError

    def describe(self) -> dict[str, object]:
        return {
            "provider": self.provider_name,
            "mode": self.mode,
            "runtime_scope": "local_server",
            "sends_documents_to_external_services": False,
        }


class DisabledVisualSignatureProvider(VisualSignatureProvider):
    def __init__(self, reason: str = "visual signature provider is disabled") -> None:
        self.reason = reason

    @property
    def provider_name(self) -> str:
        return "disabled"

    @property
    def mode(self) -> str:
        return "disabled"

    def detect(self, path_value: str | None) -> VisualSignatureDetection:
        return _unavailable(self.reason, provider=self.provider_name)

    def describe(self) -> dict[str, object]:
        details = super().describe()
        details["available"] = False
        details["reason"] = self.reason
        return details


class LayoutBaselineVisualSignatureProvider(VisualSignatureProvider):
    @property
    def provider_name(self) -> str:
        return "layout-baseline-v1"

    @property
    def mode(self) -> str:
        return "baseline"

    def detect(self, path_value: str | None) -> VisualSignatureDetection:
        if not path_value:
            return _unavailable("storage path is empty", provider=self.provider_name)

        path = Path(path_value)
        if not path.exists():
            return _unavailable("source file is not available in local storage", provider=self.provider_name)

        try:
            image, page_number = _load_first_visual_page(path)
        except Exception as exc:
            return _unavailable(str(exc), provider=self.provider_name)

        if image is None:
            return _unavailable("unsupported visual source", provider=self.provider_name)

        prepared = image.convert("RGB")
        prepared.thumbnail((1100, 1100))
        marks = _detect_marks(prepared)
        signature_like = any(mark.kind == "signature" for mark in marks)
        seal_like = any(mark.kind == "seal" for mark in marks)
        confidence = max((mark.confidence for mark in marks), default=0.0)
        reason = None if marks else "layout-aware baseline did not find signature-like or seal-like components"
        return VisualSignatureDetection(
            available=True,
            provider=self.provider_name,
            page_number=page_number,
            signature_like=signature_like,
            seal_like=seal_like,
            confidence=round(confidence, 4),
            marks=tuple(marks[:4]),
            reason=reason,
        )

    def describe(self) -> dict[str, object]:
        details = super().describe()
        details.update(
            {
                "available": True,
                "scope": "signature_like_and_seal_like_components",
                "supported_sources": ["png", "jpg", "jpeg", "tif", "tiff", "bmp", "pdf:first_page"],
                "returns": ["bbox", "confidence", "evidence"],
                "production_grade": False,
            }
        )
        return details


def detect_visual_signature_or_seal(path_value: str | None) -> VisualSignatureDetection:
    return get_visual_signature_provider().detect(path_value)


def load_first_visual_page(path: Path) -> tuple[Any | None, int | None]:
    return _load_first_visual_page(path)


@lru_cache(maxsize=1)
def get_visual_signature_provider() -> VisualSignatureProvider:
    provider = get_settings().visual_signature_provider.lower().replace("-", "_")
    if provider in {"disabled", "off", "none"}:
        return DisabledVisualSignatureProvider()
    if provider in {"layout", "layout_baseline", "layout_baseline_v1", "baseline"}:
        return LayoutBaselineVisualSignatureProvider()
    return DisabledVisualSignatureProvider(reason=f"unknown visual signature provider: {get_settings().visual_signature_provider}")


def describe_visual_signature_provider() -> dict[str, object]:
    details = get_visual_signature_provider().describe()
    details["configured_provider"] = get_settings().visual_signature_provider
    return details


def _unavailable(reason: str, *, provider: str = "layout-baseline-v1") -> VisualSignatureDetection:
    return VisualSignatureDetection(
        available=False,
        provider=provider,
        page_number=None,
        signature_like=False,
        seal_like=False,
        confidence=0.0,
        marks=(),
        reason=reason,
    )


def _load_first_visual_page(path: Path) -> tuple[Any | None, int | None]:
    suffix = path.suffix.lower()
    if suffix in {".png", ".jpg", ".jpeg", ".tif", ".tiff", ".bmp"}:
        from PIL import Image  # type: ignore

        return Image.open(path), 1

    if suffix == ".pdf":
        try:
            import pypdfium2 as pdfium  # type: ignore
        except Exception as exc:
            raise RuntimeError("PDF rendering dependency pypdfium2 is unavailable") from exc

        pdf = None
        page = None
        try:
            pdf = pdfium.PdfDocument(str(path))
            if len(pdf) == 0:
                return None, None
            page = pdf[0]
            return page.render(scale=2.0).to_pil(), 1
        finally:
            if page is not None and hasattr(page, "close"):
                page.close()
            if pdf is not None and hasattr(pdf, "close"):
                pdf.close()

    return None, None


def _detect_marks(image: Any) -> list[VisualMark]:
    width, height = image.size
    pixels = image.load()
    bottom_start = int(height * 0.42)

    dark_mask = bytearray(width * height)
    color_mask = bytearray(width * height)
    for y in range(bottom_start, height):
        for x in range(width):
            red, green, blue = pixels[x, y]
            index = y * width + x
            if red < 95 and green < 95 and blue < 95:
                dark_mask[index] = 1
            if _is_stamp_color(red, green, blue):
                color_mask[index] = 1

    marks: list[VisualMark] = []
    for component in _connected_components(dark_mask, width, height, min_pixels=26):
        mark = _signature_mark_from_component(component, width, height)
        if mark is not None:
            marks.append(mark)
    for component in _connected_components(color_mask, width, height, min_pixels=42):
        mark = _seal_mark_from_component(component, width, height)
        if mark is not None:
            marks.append(mark)

    marks.sort(key=lambda item: item.confidence, reverse=True)
    return marks


def _is_stamp_color(red: int, green: int, blue: int) -> bool:
    red_stamp = red > 135 and green < 130 and blue < 135
    blue_stamp = blue > 130 and red < 130 and green < 170
    green_stamp = green > 110 and red < 110 and blue < 150
    return red_stamp or blue_stamp or green_stamp


def _connected_components(mask: bytearray, width: int, height: int, *, min_pixels: int) -> list[dict[str, int | float]]:
    visited = bytearray(width * height)
    components: list[dict[str, int | float]] = []
    for index, value in enumerate(mask):
        if not value or visited[index]:
            continue
        queue = [index]
        visited[index] = 1
        min_x = max_x = index % width
        min_y = max_y = index // width
        pixels = 0
        while queue:
            current = queue.pop()
            pixels += 1
            x = current % width
            y = current // width
            min_x = min(min_x, x)
            max_x = max(max_x, x)
            min_y = min(min_y, y)
            max_y = max(max_y, y)
            for neighbor in _neighbors(current, x, y, width, height):
                if mask[neighbor] and not visited[neighbor]:
                    visited[neighbor] = 1
                    queue.append(neighbor)
        if pixels < min_pixels:
            continue
        box_width = max_x - min_x + 1
        box_height = max_y - min_y + 1
        components.append(
            {
                "min_x": min_x,
                "min_y": min_y,
                "max_x": max_x,
                "max_y": max_y,
                "width": box_width,
                "height": box_height,
                "pixels": pixels,
                "density": pixels / max(1, box_width * box_height),
            }
        )
    return components


def _neighbors(index: int, x: int, y: int, width: int, height: int) -> tuple[int, ...]:
    values: list[int] = []
    if x > 0:
        values.append(index - 1)
    if x < width - 1:
        values.append(index + 1)
    if y > 0:
        values.append(index - width)
    if y < height - 1:
        values.append(index + width)
    return tuple(values)


def _signature_mark_from_component(component: dict[str, int | float], width: int, height: int) -> VisualMark | None:
    box_width = int(component["width"])
    box_height = int(component["height"])
    pixels = int(component["pixels"])
    density = float(component["density"])
    aspect_ratio = box_width / max(1, box_height)
    center_y = (int(component["min_y"]) + int(component["max_y"])) / 2

    if center_y < height * 0.42:
        return None
    if box_width < width * 0.08 or box_height < 4 or box_height > height * 0.18:
        return None
    if aspect_ratio < 1.8 or not (0.01 <= density <= 0.55):
        return None

    width_score = min(1.0, box_width / max(1, width * 0.24))
    aspect_score = min(1.0, aspect_ratio / 5.0)
    density_score = 1.0 - min(1.0, abs(density - 0.16) / 0.26)
    pixel_score = min(1.0, pixels / 550)
    confidence = 0.28 + width_score * 0.24 + aspect_score * 0.2 + density_score * 0.18 + pixel_score * 0.1
    return VisualMark(
        kind="signature",
        confidence=round(min(confidence, 0.92), 4),
        bbox=_normalized_bbox(component, width, height),
        evidence=(
            f"wide dark component in lower page area: width={box_width}, height={box_height}, "
            f"aspect={aspect_ratio:.2f}, density={density:.3f}"
        ),
    )


def _seal_mark_from_component(component: dict[str, int | float], width: int, height: int) -> VisualMark | None:
    box_width = int(component["width"])
    box_height = int(component["height"])
    pixels = int(component["pixels"])
    density = float(component["density"])
    aspect_ratio = box_width / max(1, box_height)
    center_y = (int(component["min_y"]) + int(component["max_y"])) / 2

    if center_y < height * 0.35:
        return None
    if box_width < width * 0.035 or box_height < height * 0.025:
        return None
    if not (0.45 <= aspect_ratio <= 1.85) or not (0.015 <= density <= 0.65):
        return None

    size_score = min(1.0, min(box_width, box_height) / max(1, width * 0.08))
    aspect_score = 1.0 - min(1.0, abs(aspect_ratio - 1.0) / 0.85)
    density_score = 1.0 - min(1.0, abs(density - 0.2) / 0.32)
    pixel_score = min(1.0, pixels / 700)
    confidence = 0.3 + size_score * 0.24 + aspect_score * 0.2 + density_score * 0.16 + pixel_score * 0.1
    return VisualMark(
        kind="seal",
        confidence=round(min(confidence, 0.94), 4),
        bbox=_normalized_bbox(component, width, height),
        evidence=(
            f"colored stamp-like component: width={box_width}, height={box_height}, "
            f"aspect={aspect_ratio:.2f}, density={density:.3f}"
        ),
    )


def _normalized_bbox(component: dict[str, int | float], width: int, height: int) -> tuple[float, float, float, float]:
    return (
        round(float(component["min_x"]) / width, 4),
        round(float(component["min_y"]) / height, 4),
        round(float(component["max_x"]) / width, 4),
        round(float(component["max_y"]) / height, 4),
    )
