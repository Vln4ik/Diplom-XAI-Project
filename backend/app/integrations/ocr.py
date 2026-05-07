from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from app.core.config import get_settings


class OCRError(RuntimeError):
    pass


@dataclass
class OCRResult:
    text: str
    provider: str
    metadata: dict[str, object]


class OCRProvider:
    def provider_name(self) -> str:
        raise NotImplementedError

    def mode(self) -> str:
        raise NotImplementedError

    def extract_text(self, path: Path) -> OCRResult:
        raise NotImplementedError

    def describe(self) -> dict[str, object]:
        return {
            "provider": self.provider_name(),
            "mode": self.mode(),
        }


class DisabledOCRProvider(OCRProvider):
    def provider_name(self) -> str:
        return "disabled"

    def mode(self) -> str:
        return "disabled"

    def extract_text(self, path: Path) -> OCRResult:
        raise OCRError(f"OCR is disabled for file '{path.name}'")


class TesseractOCRProvider(OCRProvider):
    def __init__(self) -> None:
        self.settings = get_settings()
        try:
            import pytesseract  # type: ignore
            from PIL import Image  # type: ignore
        except Exception as exc:  # pragma: no cover - optional dependency path
            raise OCRError("Tesseract OCR dependencies are not installed") from exc
        self._pytesseract = pytesseract
        self._image_module = Image
        if self.settings.tesseract_cmd:
            self._pytesseract.pytesseract.tesseract_cmd = self.settings.tesseract_cmd

    def provider_name(self) -> str:
        return "tesseract"

    def mode(self) -> str:
        return "model"

    def extract_text(self, path: Path) -> OCRResult:
        image = self._image_module.open(path)
        text = self._pytesseract.image_to_string(image, lang=self.settings.ocr_languages).strip()
        if not text:
            raise OCRError(f"OCR produced empty text for '{path.name}'")
        return OCRResult(
            text=text,
            provider=self.provider_name(),
            metadata={"languages": self.settings.ocr_languages},
        )


@lru_cache(maxsize=1)
def get_ocr_provider() -> OCRProvider:
    provider = get_settings().ocr_provider.lower()
    if provider == "tesseract":
        try:
            return TesseractOCRProvider()
        except OCRError:
            return DisabledOCRProvider()
    return DisabledOCRProvider()


def describe_ocr_provider() -> dict[str, object]:
    provider = get_ocr_provider()
    details = provider.describe()
    details["configured_provider"] = get_settings().ocr_provider
    details["languages"] = get_settings().ocr_languages
    return details
