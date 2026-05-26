from __future__ import annotations

from pathlib import Path

from app.services.quality_benchmark import (
    BenchmarkExpectedSection,
    BenchmarkExpectedRequirement,
    BenchmarkPredictedRequirement,
    BenchmarkPredictedSection,
    RequirementMatch,
    evaluate_applicability,
    evaluate_evidence_linking,
    evaluate_requirement_extraction,
    evaluate_report_sections,
    load_benchmark_paths_from_manifest,
    precision_recall_f1,
    resolve_benchmark_runtime_overrides,
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
            expected_applicability="applicable",
            expected_evidence=["Лицензия размещена на сайте."],
        )
    ]
    predicted = [
        BenchmarkPredictedRequirement(
            requirement_id="pred-1",
            title="Необходимо предоставить сведения о лицензии, аккредитации и кадровом составе",
            category="Лицензия и аккредитация",
            applicability_status="applicable",
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
        expected_applicability="applicable",
        expected_evidence=[
            "Опубликованы локальные нормативные акты.",
            "website_sections_published | 2026 | 12",
        ],
    )
    predicted = BenchmarkPredictedRequirement(
        requirement_id="pred-site",
        title="На официальном сайте требуется опубликовать локальные нормативные акты.",
        category="Официальный сайт",
        applicability_status="applicable",
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
    assert report["matched_predicted_total"] == 1
    assert report["precision"] == 0.5
    assert report["recall"] == 0.5
    assert report["grounded_requirements_share"] == 1.0


def test_evaluate_evidence_linking_allows_merged_ocr_evidence_to_cover_multiple_expected_snippets():
    expected = BenchmarkExpectedRequirement(
        benchmark_id="req-ocr-site",
        title="На официальном сайте должны быть размещены локальные акты и образовательные программы.",
        category="Официальный сайт",
        expected_status="data_found",
        expected_applicability="applicable",
        expected_evidence=[
            "На сайте размещены локальные нормативные акты.",
            "Программы обучения опубликованы.",
        ],
    )
    predicted = BenchmarkPredictedRequirement(
        requirement_id="pred-ocr-site",
        title="На официальном сайте должны быть размещены локальные акты и образовательные программы.",
        category="Официальный сайт",
        applicability_status="applicable",
        status="data_found",
        confidence_score=0.74,
        evidence_descriptions=[
            "На сайте размещены локальные нормативные акты. Программы обучения опубликованы. 2026",
        ],
    )

    report = evaluate_evidence_linking(
        matches=[RequirementMatch(expected=expected, predicted=predicted, similarity=0.95)]
    )

    assert report["matched_total"] == 2
    assert report["matched_predicted_total"] == 1
    assert report["precision"] == 1.0
    assert report["recall"] == 1.0
    assert report["f1"] == 1.0
    assert len(report["per_requirement"][0]["matches"]) == 2


def test_evaluate_applicability_reports_accuracy():
    expected = BenchmarkExpectedRequirement(
        benchmark_id="req-mixed",
        title="Учреждение обязано вести журнал контроля температуры серверной комнаты.",
        category="Общие сведения об организации",
        expected_status="needs_clarification",
        expected_applicability="needs_clarification",
        expected_evidence=[],
    )
    predicted = BenchmarkPredictedRequirement(
        requirement_id="pred-mixed",
        title="Учреждение обязано вести журнал контроля температуры серверной комнаты.",
        category="Общие сведения об организации",
        applicability_status="needs_clarification",
        status="needs_clarification",
        confidence_score=0.2,
        evidence_descriptions=[],
    )

    report = evaluate_applicability([RequirementMatch(expected=expected, predicted=predicted, similarity=0.95)])

    assert report["accuracy"] == 1.0
    assert report["mismatches"] == []


def test_evaluate_report_sections_tracks_requirement_coverage():
    expected_sections = [
        BenchmarkExpectedSection(
            title="Перечень применимых требований",
            expected_requirement_ids=["req_programs", "req_license_staff"],
            min_source_requirements=2,
            require_non_empty_content=True,
            content_markers=["Всего требований", "Применимых"],
            min_content_markers=2,
            quality_pass_threshold=0.75,
        )
    ]
    predicted_sections = [
        BenchmarkPredictedSection(
            title="Перечень применимых требований",
            content=(
                "Всего требований: 2. Применимых: 2. "
                "Организация должна разместить сведения о реализуемых образовательных программах. "
                "Необходимо предоставить сведения о лицензии, аккредитации и кадровом составе."
            ),
            source_requirement_ids=["pred-programs", "pred-license"],
        )
    ]
    matches = [
        RequirementMatch(
            expected=BenchmarkExpectedRequirement(
                benchmark_id="req_programs",
                title="Организация должна разместить сведения о реализуемых образовательных программах.",
                category="Образовательные программы",
                expected_status="data_found",
                expected_applicability="applicable",
                expected_evidence=[],
            ),
            predicted=BenchmarkPredictedRequirement(
                requirement_id="pred-programs",
                title="Организация должна разместить сведения о реализуемых образовательных программах.",
                category="Образовательные программы",
                applicability_status="applicable",
                status="data_found",
                confidence_score=0.7,
                evidence_descriptions=[],
            ),
            similarity=0.98,
        ),
        RequirementMatch(
            expected=BenchmarkExpectedRequirement(
                benchmark_id="req_license_staff",
                title="Необходимо предоставить сведения о лицензии, аккредитации и кадровом составе.",
                category="Лицензия и аккредитация",
                expected_status="data_found",
                expected_applicability="applicable",
                expected_evidence=[],
            ),
            predicted=BenchmarkPredictedRequirement(
                requirement_id="pred-license",
                title="Необходимо предоставить сведения о лицензии, аккредитации и кадровом составе.",
                category="Лицензия и аккредитация",
                applicability_status="applicable",
                status="data_found",
                confidence_score=0.8,
                evidence_descriptions=[],
            ),
            similarity=0.98,
        ),
    ]

    report = evaluate_report_sections(expected_sections, predicted_sections, matches)

    assert report["presence_rate"] == 1.0
    assert report["non_empty_content_share"] == 1.0
    assert report["source_requirement_coverage"] == 1.0
    assert report["min_source_requirement_pass_share"] == 1.0
    assert report["requirement_content_coverage_mean"] == 1.0
    assert report["content_marker_coverage_mean"] == 1.0
    assert report["min_content_marker_pass_share"] == 1.0
    assert report["quality_score_mean"] == 1.0
    assert report["quality_pass_share"] == 1.0


def test_evaluate_report_sections_penalizes_missing_content_markers():
    expected_sections = [
        BenchmarkExpectedSection(
            title="Заключение",
            expected_requirement_ids=[],
            min_source_requirements=1,
            require_non_empty_content=True,
            content_markers=["Итоговая готовность отчета", "Открытых рисков"],
            min_content_markers=2,
            quality_pass_threshold=0.75,
        )
    ]
    predicted_sections = [
        BenchmarkPredictedSection(
            title="Заключение",
            content="Краткое итоговое заключение без явных метрик.",
            source_requirement_ids=["pred-programs"],
        )
    ]

    report = evaluate_report_sections(expected_sections, predicted_sections, matches=[])

    assert report["content_marker_coverage_mean"] == 0.0
    assert report["min_content_marker_pass_share"] == 0.0
    assert report["quality_score_mean"] == 0.3333
    assert report["quality_pass_share"] == 0.0


def test_run_quality_benchmark_returns_formal_metrics():
    benchmark_path = Path(__file__).resolve().parents[2] / "samples" / "benchmarks" / "rosobrnadzor_quality_benchmark.json"

    report = run_quality_benchmark(benchmark_path)

    assert report["benchmark_name"] == "rosobrnadzor_demo_quality_benchmark"
    assert report["expected_requirements"] == 3
    assert report["predicted_requirements"] >= 3
    assert report["requirement_extraction"]["f1"] >= 0.9
    assert report["applicability"]["accuracy"] >= 0.9
    assert report["evidence_linking"]["matched_total"] >= 4
    assert report["evidence_linking"]["precision"] >= 0.4
    assert report["evidence_linking"]["f1"] >= 0.5
    assert report["evidence_linking"]["grounded_requirements_share"] >= 0.66
    assert report["report_sections"]["presence_rate"] >= 0.5
    assert report["report_sections"]["quality_score_mean"] >= 0.7
    assert report["report_sections"]["quality_pass_share"] >= 0.5


def test_run_quality_benchmark_suite_aggregates_multiple_scenarios():
    benchmark_dir = Path(__file__).resolve().parents[2] / "samples" / "benchmarks"
    report = run_quality_benchmark_suite(sorted(benchmark_dir.glob("*.json")))

    assert report["suite_size"] >= 3
    assert report["aggregate"]["requirement_extraction"]["f1"] >= 0.9
    assert report["aggregate"]["applicability"]["accuracy_mean"] >= 0.75
    assert report["aggregate"]["evidence_linking"]["recall"] >= 0.5
    assert report["aggregate"]["report_sections"]["presence_rate_mean"] >= 0.5
    assert report["aggregate"]["report_sections"]["quality_score_mean"] >= 0.7


def test_load_benchmark_paths_from_manifest_resolves_relative_entries():
    manifest_path = Path(__file__).resolve().parents[2] / "samples" / "benchmark_suites" / "extended.json"

    benchmark_paths = load_benchmark_paths_from_manifest(manifest_path)

    assert len(benchmark_paths) == 7
    assert benchmark_paths[0].name == "rosobrnadzor_quality_benchmark.json"
    assert benchmark_paths[-1].name == "rosobrnadzor_quality_ocr_augmented_mixed_layout.json"


def test_resolve_benchmark_runtime_overrides_supports_runtime_block():
    provider, languages = resolve_benchmark_runtime_overrides(
        {
            "name": "ocr-aware-benchmark",
            "runtime": {
                "ocr_provider": "tesseract",
                "ocr_languages": "rus+eng",
            },
        }
    )

    assert provider == "tesseract"
    assert languages == "rus+eng"
