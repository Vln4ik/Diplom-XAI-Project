from __future__ import annotations

from pathlib import Path

from app.services.ocr_benchmark import evaluate_ocr_case, run_ocr_benchmark


def test_evaluate_ocr_case_scores_overlap_and_keywords():
    report = evaluate_ocr_case(
        "Лицензия и локальные акты размещены на сайте. Teachers total 48.",
        "Лицензия и акты размещены на сайте. Teachers total 48.",
        expected_keywords=["лицензия", "локальные акты", "48"],
    )

    assert report["char_similarity"] >= 0.8
    assert report["token_recall"] >= 0.75
    assert report["token_precision"] >= 0.75
    assert report["token_f1"] >= 0.75
    assert report["keyword_hits"] >= 2
    assert report["keyword_coverage"] >= 0.66


def test_run_ocr_benchmark_on_committed_corpus():
    manifest_path = (
        Path(__file__).resolve().parents[2] / "samples" / "ocr_benchmarks" / "ocr_benchmark_manifest.json"
    )

    report = run_ocr_benchmark(manifest_path)

    assert report["benchmark_name"] == "ocr_demo_benchmark"
    assert report["ocr_provider"]["provider"] == "tesseract"
    assert report["aggregate"]["case_total"] >= 5
    assert report["aggregate"]["char_similarity_mean"] >= 0.65
    assert report["aggregate"]["token_recall_mean"] >= 0.8
    assert report["aggregate"]["token_f1_mean"] >= 0.7
    assert report["aggregate"]["keyword_coverage_mean"] >= 0.8
    assert report["aggregate"]["requires_review_rate"] == 0.0

    cases = {case["benchmark_id"]: case for case in report["cases"]}
    assert cases["ocr-table-image"]["token_f1"] >= 0.9
    assert cases["ocr-mixed-layout-pdf"]["keyword_coverage"] >= 0.8
