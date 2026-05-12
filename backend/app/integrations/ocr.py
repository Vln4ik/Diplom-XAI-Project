from __future__ import annotations

from dataclasses import dataclass
from difflib import SequenceMatcher
from functools import lru_cache
from pathlib import Path
from shutil import which
from typing import Any

from app.core.config import get_settings


class OCRError(RuntimeError):
    pass


@dataclass
class OCRResult:
    text: str
    provider: str
    metadata: dict[str, object]


@dataclass(frozen=True)
class OCRCandidate:
    text: str
    variant: str
    psm: int
    mean_confidence: float
    token_count: int
    score: float


class OCRProvider:
    def provider_name(self) -> str:
        raise NotImplementedError

    def mode(self) -> str:
        raise NotImplementedError

    def extract_text(self, path: Path) -> OCRResult:
        raise NotImplementedError

    def extract_image_object(self, image: Any, source_name: str) -> OCRResult:
        raise NotImplementedError

    def describe(self) -> dict[str, object]:
        return {
            "provider": self.provider_name(),
            "mode": self.mode(),
        }


class DisabledOCRProvider(OCRProvider):
    def __init__(self, reason: str | None = None) -> None:
        self.reason = reason

    def provider_name(self) -> str:
        return "disabled"

    def mode(self) -> str:
        return "disabled"

    def extract_text(self, path: Path) -> OCRResult:
        raise OCRError(f"OCR is disabled for file '{path.name}'")

    def extract_image_object(self, image: Any, source_name: str) -> OCRResult:
        raise OCRError(f"OCR is disabled for source '{source_name}'")

    def describe(self) -> dict[str, object]:
        details = super().describe()
        details["available"] = False
        if self.reason:
            details["error"] = self.reason
        return details


class TesseractOCRProvider(OCRProvider):
    _PSM_CANDIDATES = (3, 4, 11)

    def __init__(self) -> None:
        self.settings = get_settings()
        try:
            import pytesseract  # type: ignore
            from PIL import Image, ImageOps  # type: ignore
        except Exception as exc:  # pragma: no cover - optional dependency path
            raise OCRError("Tesseract OCR dependencies are not installed") from exc
        self._pytesseract = pytesseract
        self._image_module = Image
        self._image_ops = ImageOps
        self._tesseract_cmd = self.settings.tesseract_cmd or which("tesseract")
        if not self._tesseract_cmd:
            raise OCRError("Tesseract binary is not available in PATH")
        self._pytesseract.pytesseract.tesseract_cmd = self._tesseract_cmd

    def provider_name(self) -> str:
        return "tesseract"

    def mode(self) -> str:
        return "model"

    def extract_text(self, path: Path) -> OCRResult:
        with self._image_module.open(path) as image:
            return self.extract_image_object(image, source_name=path.name)

    def extract_image_object(self, image: Any, source_name: str) -> OCRResult:
        candidates = self._collect_candidates(image)
        if not candidates:
            raise OCRError(f"OCR produced empty text for '{source_name}'")
        best = max(candidates, key=lambda candidate: candidate.score)
        table_rows = self._extract_layout_table_rows(image)
        merged_text = self._merge_table_rows(best.text, table_rows)
        return OCRResult(
            text=merged_text,
            provider=self.provider_name(),
            metadata={
                "languages": self.settings.ocr_languages,
                "tesseract_cmd": self._tesseract_cmd,
                "variant": best.variant,
                "psm": best.psm,
                "mean_confidence": round(best.mean_confidence, 2),
                "token_count": best.token_count,
                "tested_candidates": len(candidates),
                "table_rows_recovered": len(table_rows),
            },
        )

    def describe(self) -> dict[str, object]:
        details = super().describe()
        details["available"] = True
        details["tesseract_cmd"] = self._tesseract_cmd
        details["psm_candidates"] = list(self._PSM_CANDIDATES)
        details["variants"] = ["original", "threshold"]
        return details

    def _collect_candidates(self, image: Any) -> list[OCRCandidate]:
        candidates: list[OCRCandidate] = []
        for variant_name, prepared in self._iter_image_variants(image):
            for psm in self._PSM_CANDIDATES:
                candidate = self._run_candidate(prepared, variant_name=variant_name, psm=psm)
                if candidate is not None:
                    candidates.append(candidate)
        return candidates

    def _iter_image_variants(self, image: Any) -> list[tuple[str, Any]]:
        grayscale = self._image_ops.autocontrast(image.convert("L"))
        threshold = grayscale.point(lambda value: 255 if value > 180 else 0, mode="1").convert("L")
        return [
            ("original", image),
            ("threshold", threshold),
        ]

    def _run_candidate(self, image: Any, *, variant_name: str, psm: int) -> OCRCandidate | None:
        config = f"--oem 3 --psm {psm}"
        text = self._normalize_text(
            self._pytesseract.image_to_string(
                image,
                lang=self.settings.ocr_languages,
                config=config,
            )
        )
        if not text:
            return None

        data = self._pytesseract.image_to_data(
            image,
            lang=self.settings.ocr_languages,
            config=config,
            output_type=self._pytesseract.Output.DICT,
        )
        confidences = [
            float(value)
            for value in data.get("conf", [])
            if str(value).strip() and str(value) != "-1"
        ]
        tokens = [str(value).strip() for value in data.get("text", []) if str(value).strip()]
        lines = [line for line in text.splitlines() if line.strip()]
        line_token_counts = [len(line.split()) for line in lines]
        mean_confidence = sum(confidences) / len(confidences) if confidences else 0.0
        token_count = len(tokens)
        mean_tokens_per_line = sum(line_token_counts) / len(line_token_counts) if line_token_counts else 0.0
        single_token_line_ratio = (
            sum(1 for count in line_token_counts if count <= 1) / len(line_token_counts)
            if line_token_counts
            else 1.0
        )
        structure_bonus = min(mean_tokens_per_line, 6.0) * 1.5
        fragmentation_penalty = single_token_line_ratio * 4.0
        score = (
            mean_confidence
            + min(token_count, 30) / 100
            + structure_bonus
            - fragmentation_penalty
        )
        return OCRCandidate(
            text=text,
            variant=variant_name,
            psm=psm,
            mean_confidence=mean_confidence,
            token_count=token_count,
            score=score,
        )

    @staticmethod
    def _normalize_text(text: str) -> str:
        lines = [line.strip() for line in text.splitlines() if line.strip()]
        return "\n".join(lines).strip()

    def _extract_layout_table_rows(self, image: Any) -> list[str]:
        try:
            import numpy as np  # type: ignore
        except Exception:
            return []

        grayscale = image.convert("L")
        array = np.array(grayscale)
        dark_mask = array < 180
        row_counts = dark_mask.sum(axis=1)
        col_counts = dark_mask.sum(axis=0)

        horizontal_lines = self._cluster_positions(
            [index for index, count in enumerate(row_counts) if count > grayscale.width * 0.45]
        )
        vertical_lines = self._cluster_positions(
            [index for index, count in enumerate(col_counts) if count > grayscale.height * 0.18]
        )

        if len(horizontal_lines) < 3 or len(vertical_lines) < 4:
            return []

        left = max(vertical_lines[0][0] - 10, 0)
        right = min(vertical_lines[-1][1] + 10, grayscale.width)
        if right - left < 300:
            return []

        column_bounds = [
            (max(vertical_lines[index][0] + 8, 0), min(vertical_lines[index + 1][1] - 8, grayscale.width))
            for index in range(min(3, len(vertical_lines) - 1))
        ]

        rows: list[str] = []
        for index in range(len(horizontal_lines) - 1):
            top = horizontal_lines[index][1] + 5
            bottom = horizontal_lines[index + 1][0] - 5
            if bottom - top < 40:
                continue

            row_text = self._ocr_table_row(
                grayscale=grayscale,
                row_bounds=(top, bottom),
                column_bounds=column_bounds,
            )
            if row_text:
                rows.append(row_text)

        return rows

    @staticmethod
    def _cluster_positions(values: list[int], gap: int = 2) -> list[tuple[int, int]]:
        if not values:
            return []
        clusters: list[tuple[int, int]] = []
        start = previous = values[0]
        for value in values[1:]:
            if value <= previous + gap:
                previous = value
                continue
            clusters.append((start, previous))
            start = previous = value
        clusters.append((start, previous))
        return clusters

    def _ocr_table_row(
        self,
        *,
        grayscale: Any,
        row_bounds: tuple[int, int],
        column_bounds: list[tuple[int, int]],
    ) -> str:
        top, bottom = row_bounds
        row_crop = grayscale.crop((column_bounds[0][0], top, column_bounds[-1][1], bottom))
        threshold_row = self._image_ops.autocontrast(row_crop).point(lambda value: 255 if value > 180 else 0, mode="1").convert("L")

        cell_texts: list[str] = []
        for index, (left, right) in enumerate(column_bounds):
            cell_crop = threshold_row.crop((left - column_bounds[0][0], 0, right - column_bounds[0][0], bottom - top))
            if index == 0:
                text = self._extract_cell_text(cell_crop, lang=self.settings.ocr_languages, psms=(7, 11))
            elif index == 1:
                text = self._extract_cell_text(cell_crop, lang="eng", psms=(8, 7, 11))
            else:
                text = self._extract_cell_text(cell_crop, lang="eng", psms=(7, 11, 8))
            cell_texts.append(text)

        non_empty = [text for text in cell_texts if text]
        if len(non_empty) < 2:
            return ""
        return " ".join(non_empty).strip()

    def _extract_cell_text(self, cell_crop: Any, *, lang: str, psms: tuple[int, ...]) -> str:
        best_text = ""
        best_score = -1.0
        for psm in psms:
            config = f"--oem 3 --psm {psm}"
            text = self._normalize_text(
                self._pytesseract.image_to_string(cell_crop, lang=lang, config=config)
            ).replace("\n", " ")
            if not text:
                continue
            data = self._pytesseract.image_to_data(
                cell_crop,
                lang=lang,
                config=config,
                output_type=self._pytesseract.Output.DICT,
            )
            confidences = [
                float(value)
                for value in data.get("conf", [])
                if str(value).strip() and str(value) != "-1"
            ]
            tokens = [str(value).strip() for value in data.get("text", []) if str(value).strip()]
            mean_confidence = sum(confidences) / len(confidences) if confidences else 0.0
            score = mean_confidence + len(tokens) / 10
            if score > best_score:
                best_score = score
                best_text = text
        return best_text

    def _merge_table_rows(self, base_text: str, table_rows: list[str]) -> str:
        if not table_rows:
            return base_text
        merged_lines = [line.strip() for line in base_text.splitlines() if line.strip()]
        merged_lower = "\n".join(merged_lines).lower()
        existing_roots = self._text_roots("\n".join(merged_lines))
        for row in table_rows:
            normalized_row = " ".join(part.strip() for part in row.split() if part.strip())
            if not normalized_row:
                continue
            if normalized_row.lower() in merged_lower:
                continue
            row_roots = self._text_roots(normalized_row)
            line_similarities = [
                (self._line_similarity(normalized_row, line), index, line)
                for index, line in enumerate(merged_lines)
            ]
            similarity, similar_index, similar_line = max(line_similarities, default=(0.0, -1, ""))
            if similarity >= 0.72:
                similar_roots = self._text_roots(similar_line)
                if len(row_roots) > len(similar_roots) and row_roots.issuperset(similar_roots):
                    merged_lines[similar_index] = normalized_row
                    merged_lower = "\n".join(line.lower() for line in merged_lines)
                    existing_roots = self._text_roots("\n".join(merged_lines))
                continue
            if len(row_roots) < 2:
                continue
            new_roots = row_roots - existing_roots
            novelty_ratio = len(new_roots) / max(len(row_roots), 1)
            should_append = len(new_roots) >= 2 and novelty_ratio >= 0.5
            if not should_append and self._looks_cross_column_record(normalized_row) and similarity < 0.55:
                should_append = True
            if not should_append:
                continue
            merged_lines.append(normalized_row)
            merged_lower += "\n" + normalized_row.lower()
            existing_roots |= row_roots
        return "\n".join(merged_lines).strip()

    @staticmethod
    def _text_roots(text: str) -> set[str]:
        from app.services.analysis import significant_token_roots

        roots = set(significant_token_roots(text))
        roots |= {
            "".join(char for char in token if char.isdigit())
            for token in text.split()
            if any(char.isdigit() for char in token)
        }
        return {root for root in roots if root}

    @staticmethod
    def _looks_cross_column_record(text: str) -> bool:
        tokens = [token for token in text.split() if token.strip()]
        has_cyrillic = any("а" <= char.lower() <= "я" or char.lower() == "ё" for char in text)
        has_latin = any("a" <= char.lower() <= "z" for char in text)
        has_digits = any(char.isdigit() for char in text)
        has_meaningful_lower_latin_token = any(
            sum(1 for char in token if "a" <= char <= "z") >= 3
            for token in tokens
        )
        return len(tokens) >= 3 and has_cyrillic and (has_digits or has_meaningful_lower_latin_token or has_latin and has_digits)

    @classmethod
    def _line_similarity(cls, left: str, right: str) -> float:
        left_roots = cls._text_roots(left)
        right_roots = cls._text_roots(right)
        root_overlap = len(left_roots & right_roots) / max(len(left_roots | right_roots), 1)
        sequence_ratio = SequenceMatcher(None, left.lower(), right.lower()).ratio()
        return max(root_overlap, sequence_ratio)


@lru_cache(maxsize=1)
def get_ocr_provider() -> OCRProvider:
    provider = get_settings().ocr_provider.lower()
    if provider == "tesseract":
        try:
            return TesseractOCRProvider()
        except OCRError as exc:
            return DisabledOCRProvider(reason=str(exc))
    return DisabledOCRProvider(reason="OCR provider is disabled by configuration")


def describe_ocr_provider() -> dict[str, object]:
    provider = get_ocr_provider()
    details = provider.describe()
    details["configured_provider"] = get_settings().ocr_provider
    details["languages"] = get_settings().ocr_languages
    return details
