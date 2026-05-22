from __future__ import annotations

from pathlib import Path

from app.services.real_corpus import (
    load_benchmark_paths_from_real_corpus_manifest,
    load_real_corpus_case_paths,
    summarize_real_corpus_manifest,
    validate_real_corpus_case_manifest,
)


def test_load_real_corpus_case_paths_returns_all_pilot_cases():
    manifest_path = Path(__file__).resolve().parents[2] / "samples" / "real_corpus" / "manifests" / "pilot-redacted.json"

    case_paths = load_real_corpus_case_paths(manifest_path)

    assert len(case_paths) == 3
    assert case_paths[0].name == "case-manifest.json"


def test_validate_real_corpus_case_manifest_marks_alpha_case_ready():
    case_manifest_path = (
        Path(__file__).resolve().parents[2]
        / "samples"
        / "real_corpus"
        / "cases"
        / "college_alpha_full_package"
        / "case-manifest.json"
    )

    report = validate_real_corpus_case_manifest(case_manifest_path)

    assert report["case_id"] == "college_alpha_full_package"
    assert report["benchmark_ready"] is True
    assert report["document_total"] == 4
    assert report["issues"] == []


def test_summarize_real_corpus_manifest_returns_expected_counts():
    manifest_path = Path(__file__).resolve().parents[2] / "samples" / "real_corpus" / "manifests" / "pilot-redacted.json"

    report = summarize_real_corpus_manifest(manifest_path)

    assert report["case_total"] == 3
    assert report["benchmark_ready_case_total"] == 3
    assert report["issue_total"] == 0
    assert report["document_category_counts"]["normative"] == 3
    assert report["document_format_counts"]["json"] >= 3


def test_load_benchmark_paths_from_real_corpus_manifest_returns_case_annotations():
    manifest_path = Path(__file__).resolve().parents[2] / "samples" / "real_corpus" / "manifests" / "pilot-redacted.json"

    benchmark_paths = load_benchmark_paths_from_real_corpus_manifest(manifest_path)

    assert len(benchmark_paths) == 3
    assert benchmark_paths[0].name == "quality_benchmark.json"
