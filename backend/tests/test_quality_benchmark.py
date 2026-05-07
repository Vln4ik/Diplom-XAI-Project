from __future__ import annotations

from pathlib import Path

from app.services.quality_benchmark import (
    BenchmarkExpectedRequirement,
    BenchmarkPredictedRequirement,
    RequirementMatch,
    evaluate_evidence_linking,
    evaluate_requirement_extraction,
    precision_recall_f1,
    run_quality_benchmark,
    run_quality_benchmark_suite,
)


def test_precision_recall_f1_computes_expected_values():
    metrics = precision_recall_f1(true_positive=3, predicted_total=4, expected_total=5)

    assert metrics == {
        "precision": 0.75,
        "recall": 0.6,
        "f1": 0.6667,
    }


def test_evaluate_requirement_extraction_matches_by_similarity_and_category():
    expected = [
        BenchmarkExpectedRequirement(
            benchmark_id="req-license",
            title="Необходимо предоставить сведения о лицензии, аккредитации и кадровом составе.",
            category="Лицензия и аккредитация",
            expected_status="data_found",
            expected_evidence=["Лицензия размещена на сайте."],
        )
    ]
    predicted = [
        BenchmarkPredictedRequirement(
            requirement_id="pred-1",
            title="Необходимо предоставить сведения о лицензии, аккредитации и кадровом составе",
            category="Лицензия и аккредитация",
            status="data_found",
            confidence_score=0.63,
            evidence_descriptions=["Лицензия размещена на сайте."],
        )
    ]

    report = evaluate_requirement_extraction(expected, predicted)

    assert report["matched_total"] == 1
    assert report["precision"] == 1.0
    assert report["recall"] == 1.0
    assert report["f1"] == 1.0
    assert report["category_accuracy"] == 1.0
    assert report["status_accuracy"] == 1.0


def test_evaluate_evidence_linking_counts_grounded_pairs():
    expected = BenchmarkExpectedRequirement(
        benchmark_id="req-site",
        title="На официальном сайте требуется опубликовать локальные нормативные акты.",
        category="Официальный сайт",
        expected_status="data_found",
        expected_evidence=[
            "Опубликованы локальные нормативные акты.",
            "website_sections_published | 2026 | 12",
        ],
    )
    predicted = BenchmarkPredictedRequirement(
        requirement_id="pred-site",
        title="На официальном сайте требуется опубликовать локальные нормативные акты.",
        category="Официальный сайт",
        status="data_found",
        confidence_score=0.71,
        evidence_descriptions=[
            "Опубликованы локальные нормативные акты.",
            "Несвязанный фрагмент.",
        ],
    )

    report = evaluate_evidence_linking(
        matches=[RequirementMatch(expected=expected, predicted=predicted, similarity=0.95)]
    )

    assert report["matched_total"] == 1
    assert report["precision"] == 0.5
    assert report["recall"] == 0.5
    assert report["grounded_requirements_share"] == 1.0


def test_run_quality_benchmark_returns_formal_metrics():
    benchmark_path = Path(__file__).resolve().parents[2] / "samples" / "benchmarks" / "rosobrnadzor_quality_benchmark.json"

    report = run_quality_benchmark(benchmark_path)

    assert report["benchmark_name"] == "rosobrnadzor_demo_quality_benchmark"
    assert report["expected_requirements"] == 3
    assert report["predicted_requirements"] >= 3
    assert report["requirement_extraction"]["f1"] >= 0.9
    assert report["evidence_linking"]["matched_total"] >= 4
    assert report["evidence_linking"]["precision"] >= 0.4
    assert report["evidence_linking"]["f1"] >= 0.5
    assert report["evidence_linking"]["grounded_requirements_share"] >= 0.66


def test_run_quality_benchmark_suite_aggregates_multiple_scenarios():
    benchmark_dir = Path(__file__).resolve().parents[2] / "samples" / "benchmarks"
    report = run_quality_benchmark_suite(sorted(benchmark_dir.glob("*.json")))

    assert report["suite_size"] >= 3
    assert report["aggregate"]["requirement_extraction"]["f1"] >= 0.9
    assert report["aggregate"]["evidence_linking"]["recall"] >= 0.5
