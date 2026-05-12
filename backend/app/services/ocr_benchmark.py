from __future__ import annotations

import json
import os
from contextlib import contextmanager
from dataclasses import dataclass
from difflib import SequenceMatcher
from pathlib import Path

from app.core.config import get_settings
from app.integrations.ocr import get_ocr_provider
from app.processors.documents import extract_document
from app.services.analysis import significant_token_roots


@dataclass(frozen=True)
class OCRBenchmarkCase:
    benchmark_id: str
    scenario: str
    file_name: str
    expected_text: str
    expected_keywords: list[str]
    expected_format: str


def _round(value: float) -> float:
    return round(float(value), 4)


def _load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _token_roots(text: str) -> set[str]:
    roots = set(significant_token_roots(text))
    digits = {"".join(ch for ch in token if ch.isdigit()) for token in text.split() if any(ch.isdigit() for ch in token)}
    roots |= {digit for digit in digits if digit}
    return roots


def _keyword_covered(keyword: str, predicted_roots: set[str]) -> bool:
    expected_roots = _token_roots(keyword)
    return bool(expected_roots) and expected_roots.issubset(predicted_roots)


def evaluate_ocr_case(expected_text: str, predicted_text: str, *, expected_keywords: list[str]) -> dict[str, object]:
    expected_roots = _token_roots(expected_text)
    predicted_roots = _token_roots(predicted_text)
    overlap = expected_roots & predicted_roots

    precision = 0.0 if not predicted_roots else len(overlap) / len(predicted_roots)
    recall = 0.0 if not expected_roots else len(overlap) / len(expected_roots)
    f1 = 0.0 if precision == 0.0 or recall == 0.0 else 2 * precision * recall / (precision + recall)
    keyword_hits = sum(1 for keyword in expected_keywords if _keyword_covered(keyword, predicted_roots))
    keyword_coverage = 0.0 if not expected_keywords else keyword_hits / len(expected_keywords)

    return {
        "char_similarity": _round(SequenceMatcher(None, expected_text, predicted_text).ratio()),
        "token_precision": _round(precision),
        "token_recall": _round(recall),
        "token_f1": _round(f1),
        "keyword_hits": keyword_hits,
        "keyword_total": len(expected_keywords),
        "keyword_coverage": _round(keyword_coverage),
        "expected_token_total": len(expected_roots),
        "predicted_token_total": len(predicted_roots),
        "overlap_token_total": len(overlap),
    }


def _mean(values: list[float]) -> float:
    return _round(sum(values) / len(values)) if values else 0.0


@contextmanager
def temporary_ocr_runtime(provider: str = "tesseract", languages: str = "rus+eng"):
    previous_provider = os.environ.get("XAI_APP_OCR_PROVIDER")
    previous_languages = os.environ.get("XAI_APP_OCR_LANGUAGES")
    try:
        os.environ["XAI_APP_OCR_PROVIDER"] = provider
        os.environ["XAI_APP_OCR_LANGUAGES"] = languages
        get_settings.cache_clear()
        get_ocr_provider.cache_clear()
        yield
    finally:
        if previous_provider is None:
            os.environ.pop("XAI_APP_OCR_PROVIDER", None)
        else:
            os.environ["XAI_APP_OCR_PROVIDER"] = previous_provider

        if previous_languages is None:
            os.environ.pop("XAI_APP_OCR_LANGUAGES", None)
        else:
            os.environ["XAI_APP_OCR_LANGUAGES"] = previous_languages

        get_settings.cache_clear()
        get_ocr_provider.cache_clear()


def run_ocr_benchmark(manifest_path: Path) -> dict[str, object]:
    manifest = _load_json(manifest_path)
    base_dir = manifest_path.parent
    cases = [
        OCRBenchmarkCase(
            benchmark_id=item["benchmark_id"],
            scenario=item["scenario"],
            file_name=item["file_name"],
            expected_text=item["expected_text"],
            expected_keywords=item.get("expected_keywords", []),
            expected_format=item["expected_format"],
        )
        for item in manifest["cases"]
    ]

    with temporary_ocr_runtime(
        provider=manifest.get("ocr_provider", "tesseract"),
        languages=manifest.get("ocr_languages", "rus+eng"),
    ):
        provider_status = get_ocr_provider().describe()
        results: list[dict[str, object]] = []
        by_format: dict[str, list[dict[str, object]]] = {}
        for case in cases:
            file_path = base_dir / case.file_name
            extraction = extract_document(str(file_path))
            metrics = evaluate_ocr_case(
                case.expected_text,
                extraction.text,
                expected_keywords=case.expected_keywords,
            )
            case_report = {
                "benchmark_id": case.benchmark_id,
                "scenario": case.scenario,
                "file_name": case.file_name,
                "format": case.expected_format,
                "requires_review": extraction.requires_review,
                "page_count": extraction.page_count,
                "extracted_text_excerpt": extraction.text[:240],
                **metrics,
            }
            results.append(case_report)
            by_format.setdefault(case.expected_format, []).append(case_report)

    aggregate = {
        "case_total": len(results),
        "requires_review_rate": _round(sum(1 for item in results if item["requires_review"]) / len(results)) if results else 0.0,
        "char_similarity_mean": _mean([item["char_similarity"] for item in results]),
        "token_precision_mean": _mean([item["token_precision"] for item in results]),
        "token_recall_mean": _mean([item["token_recall"] for item in results]),
        "token_f1_mean": _mean([item["token_f1"] for item in results]),
        "keyword_coverage_mean": _mean([item["keyword_coverage"] for item in results]),
    }

    format_summary = {
        fmt: {
            "case_total": len(items),
            "char_similarity_mean": _mean([item["char_similarity"] for item in items]),
            "token_f1_mean": _mean([item["token_f1"] for item in items]),
            "keyword_coverage_mean": _mean([item["keyword_coverage"] for item in items]),
            "requires_review_rate": _round(sum(1 for item in items if item["requires_review"]) / len(items)),
        }
        for fmt, items in sorted(by_format.items())
    }

    return {
        "benchmark_name": manifest["benchmark_name"],
        "ocr_provider": provider_status,
        "aggregate": aggregate,
        "by_format": format_summary,
        "cases": results,
    }
