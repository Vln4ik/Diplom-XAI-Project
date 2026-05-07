from __future__ import annotations

import json
import os
import tempfile
from dataclasses import dataclass
from pathlib import Path

from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient

from app.core.config import get_settings
from app.db.session import get_engine, get_session_factory
from app.services.analysis import requirement_similarity, significant_token_roots
from app.services.auth import create_user


@dataclass(frozen=True)
class BenchmarkExpectedRequirement:
    benchmark_id: str
    title: str
    category: str
    expected_status: str
    expected_evidence: list[str]


@dataclass(frozen=True)
class BenchmarkPredictedRequirement:
    requirement_id: str
    title: str
    category: str
    status: str
    confidence_score: float
    evidence_descriptions: list[str]


@dataclass(frozen=True)
class RequirementMatch:
    expected: BenchmarkExpectedRequirement
    predicted: BenchmarkPredictedRequirement
    similarity: float


def _load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _round(value: float) -> float:
    return round(float(value), 4)


def precision_recall_f1(*, true_positive: int, predicted_total: int, expected_total: int) -> dict[str, float]:
    precision = 0.0 if predicted_total == 0 else true_positive / predicted_total
    recall = 0.0 if expected_total == 0 else true_positive / expected_total
    f1 = 0.0 if precision == 0.0 or recall == 0.0 else 2 * precision * recall / (precision + recall)
    return {
        "precision": _round(precision),
        "recall": _round(recall),
        "f1": _round(f1),
    }


def _mean(values: list[float]) -> float:
    return _round(sum(values) / len(values)) if values else 0.0


def evidence_similarity(expected_snippet: str, predicted_snippet: str) -> float:
    base_similarity = requirement_similarity(expected_snippet, predicted_snippet)
    expected_roots = {token for token in significant_token_roots(expected_snippet) if not token.isdigit()}
    predicted_roots = {token for token in significant_token_roots(predicted_snippet) if not token.isdigit()}
    shared_roots = expected_roots & predicted_roots

    if "|" in expected_snippet or "|" in predicted_snippet:
        if not shared_roots:
            return 0.0
        if expected_snippet.split("|", 1)[0].strip() == predicted_snippet.split("|", 1)[0].strip():
            return 1.0
        return _round(min(0.99, base_similarity + 0.12))

    if not shared_roots and base_similarity < 0.75:
        return 0.0
    return base_similarity


def match_requirements(
    expected: list[BenchmarkExpectedRequirement],
    predicted: list[BenchmarkPredictedRequirement],
    *,
    min_similarity: float = 0.42,
) -> list[RequirementMatch]:
    candidates: list[tuple[float, int, int]] = []
    for expected_index, expected_item in enumerate(expected):
        for predicted_index, predicted_item in enumerate(predicted):
            similarity = requirement_similarity(expected_item.title, predicted_item.title)
            if expected_item.category == predicted_item.category:
                similarity += 0.1
            if similarity < min_similarity:
                continue
            candidates.append((min(similarity, 0.99), expected_index, predicted_index))

    candidates.sort(reverse=True)
    matched_expected: set[int] = set()
    matched_predicted: set[int] = set()
    matches: list[RequirementMatch] = []
    for similarity, expected_index, predicted_index in candidates:
        if expected_index in matched_expected or predicted_index in matched_predicted:
            continue
        matched_expected.add(expected_index)
        matched_predicted.add(predicted_index)
        matches.append(
            RequirementMatch(
                expected=expected[expected_index],
                predicted=predicted[predicted_index],
                similarity=_round(similarity),
            )
        )
    return matches


def evaluate_requirement_extraction(
    expected: list[BenchmarkExpectedRequirement],
    predicted: list[BenchmarkPredictedRequirement],
) -> dict[str, object]:
    matches = match_requirements(expected, predicted)
    metrics = precision_recall_f1(
        true_positive=len(matches),
        predicted_total=len(predicted),
        expected_total=len(expected),
    )
    category_accuracy = (
        sum(1 for match in matches if match.expected.category == match.predicted.category) / len(matches)
        if matches
        else 0.0
    )
    status_accuracy = (
        sum(1 for match in matches if match.expected.expected_status == match.predicted.status) / len(matches)
        if matches
        else 0.0
    )
    average_similarity = sum(match.similarity for match in matches) / len(matches) if matches else 0.0
    return {
        "expected_total": len(expected),
        "predicted_total": len(predicted),
        "matched_total": len(matches),
        **metrics,
        "category_accuracy": _round(category_accuracy),
        "status_accuracy": _round(status_accuracy),
        "average_match_similarity": _round(average_similarity),
        "unmatched_expected_ids": [item.benchmark_id for item in expected if item.benchmark_id not in {match.expected.benchmark_id for match in matches}],
        "unexpected_predicted_titles": [item.title for item in predicted if item.requirement_id not in {match.predicted.requirement_id for match in matches}],
        "matches": [
            {
                "expected_id": match.expected.benchmark_id,
                "expected_title": match.expected.title,
                "predicted_title": match.predicted.title,
                "similarity": match.similarity,
                "category_match": match.expected.category == match.predicted.category,
                "status_match": match.expected.expected_status == match.predicted.status,
            }
            for match in matches
        ],
    }


def evaluate_evidence_linking(
    matches: list[RequirementMatch],
    *,
    min_similarity: float = 0.34,
) -> dict[str, object]:
    true_positive = 0
    expected_total = 0
    predicted_total = 0
    grounded_requirements = 0
    per_requirement: list[dict[str, object]] = []

    for match in matches:
        expected_items = match.expected.expected_evidence
        predicted_items = match.predicted.evidence_descriptions
        expected_total += len(expected_items)
        predicted_total += len(predicted_items)

        candidate_pairs: list[tuple[float, int, int]] = []
        for expected_index, expected_snippet in enumerate(expected_items):
            for predicted_index, predicted_snippet in enumerate(predicted_items):
                similarity = evidence_similarity(expected_snippet, predicted_snippet)
                if similarity < min_similarity:
                    continue
                candidate_pairs.append((similarity, expected_index, predicted_index))
        candidate_pairs.sort(reverse=True)

        matched_expected: set[int] = set()
        matched_predicted: set[int] = set()
        local_matches: list[dict[str, object]] = []
        for similarity, expected_index, predicted_index in candidate_pairs:
            if expected_index in matched_expected or predicted_index in matched_predicted:
                continue
            matched_expected.add(expected_index)
            matched_predicted.add(predicted_index)
            local_matches.append(
                {
                    "expected_snippet": expected_items[expected_index],
                    "predicted_snippet": predicted_items[predicted_index],
                    "similarity": _round(similarity),
                }
            )

        true_positive += len(local_matches)
        if local_matches:
            grounded_requirements += 1

        per_requirement.append(
            {
                "expected_id": match.expected.benchmark_id,
                "expected_total": len(expected_items),
                "predicted_total": len(predicted_items),
                "matched_total": len(local_matches),
                "recall": _round(0.0 if not expected_items else len(local_matches) / len(expected_items)),
                "precision": _round(0.0 if not predicted_items else len(local_matches) / len(predicted_items)),
                "matches": local_matches,
            }
        )

    metrics = precision_recall_f1(
        true_positive=true_positive,
        predicted_total=predicted_total,
        expected_total=expected_total,
    )
    return {
        "expected_total": expected_total,
        "predicted_total": predicted_total,
        "matched_total": true_positive,
        **metrics,
        "grounded_requirements_share": _round(0.0 if not matches else grounded_requirements / len(matches)),
        "per_requirement": per_requirement,
    }


def _build_alembic_config(backend_root: Path) -> Config:
    config = Config(str(backend_root / "alembic.ini"))
    config.set_main_option("script_location", str(backend_root / "alembic"))
    return config


def _auth_headers(test_client: TestClient, email: str, password: str) -> dict[str, str]:
    response = test_client.post("/api/auth/login", json={"email": email, "password": password})
    response.raise_for_status()
    access_token = response.json()["access_token"]
    return {"Authorization": f"Bearer {access_token}"}


def _predicted_requirements_from_api(test_client: TestClient, headers: dict[str, str], organization_id: str) -> list[BenchmarkPredictedRequirement]:
    requirements = test_client.get(f"/api/organizations/{organization_id}/requirements", headers=headers)
    requirements.raise_for_status()
    predicted: list[BenchmarkPredictedRequirement] = []
    for item in requirements.json():
        explanation = test_client.get(f"/api/requirements/{item['id']}/explanation", headers=headers)
        explanation.raise_for_status()
        evidence_descriptions = [evidence.get("description", "") for evidence in explanation.json().get("evidence_json", [])]
        predicted.append(
            BenchmarkPredictedRequirement(
                requirement_id=item["id"],
                title=item["title"],
                category=item["category"],
                status=item["status"],
                confidence_score=float(item["confidence_score"]),
                evidence_descriptions=evidence_descriptions,
            )
        )
    return predicted


def run_quality_benchmark(benchmark_path: Path) -> dict[str, object]:
    from app.main import app
    from app.workers.celery_app import celery_app

    benchmark = _load_json(benchmark_path)
    project_root = benchmark_path.resolve().parents[2]
    backend_root = project_root / "backend"
    document_root = project_root / "samples" / "documents"

    expected_requirements = [
        BenchmarkExpectedRequirement(
            benchmark_id=item["id"],
            title=item["title"],
            category=item["category"],
            expected_status=item["expected_status"],
            expected_evidence=item["expected_evidence"],
        )
        for item in benchmark["expected_requirements"]
    ]

    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)
        temp_database = temp_path / "benchmark.db"
        temp_storage = temp_path / "storage"
        predicted_requirements: list[BenchmarkPredictedRequirement] = []

        previous_env = {
            "XAI_APP_DATABASE_URL": str(get_settings().database_url),
            "XAI_APP_STORAGE_PATH": str(get_settings().storage_path),
            "XAI_APP_SECRET_KEY": get_settings().secret_key,
            "XAI_APP_CELERY_TASK_ALWAYS_EAGER": str(get_settings().celery_task_always_eager),
        }
        previous_celery_eager = celery_app.conf.task_always_eager

        try:
            os.environ["XAI_APP_DATABASE_URL"] = f"sqlite:///{temp_database}"
            os.environ["XAI_APP_STORAGE_PATH"] = str(temp_storage)
            os.environ["XAI_APP_SECRET_KEY"] = "benchmark-secret-key-with-enough-length-123"
            os.environ["XAI_APP_CELERY_TASK_ALWAYS_EAGER"] = "1"

            get_settings.cache_clear()
            get_engine.cache_clear()
            get_session_factory.cache_clear()
            celery_app.conf.task_always_eager = True
            command.upgrade(_build_alembic_config(backend_root), "head")

            session_factory = get_session_factory()
            with session_factory() as session:
                create_user(session, full_name="Benchmark Admin", email="benchmark@example.com", password="ChangeMe123!")

            with TestClient(app) as test_client:
                headers = _auth_headers(test_client, "benchmark@example.com", "ChangeMe123!")
                organization = test_client.post(
                    "/api/organizations",
                    headers=headers,
                    json={"name": "Benchmark College", "organization_type": "educational"},
                )
                organization.raise_for_status()
                organization_id = organization.json()["id"]

                document_ids: list[str] = []
                for document in benchmark["documents"]:
                    file_path = document_root / document["filename"]
                    upload = test_client.post(
                        f"/api/organizations/{organization_id}/documents",
                        headers=headers,
                        data={"category": document["category"]},
                        files={"files": (document["filename"], file_path.read_bytes(), "application/octet-stream")},
                    )
                    upload.raise_for_status()
                    document_id = upload.json()[0]["id"]
                    document_ids.append(document_id)
                    process = test_client.post(f"/api/documents/{document_id}/process", headers=headers)
                    process.raise_for_status()

                report = test_client.post(
                    f"/api/organizations/{organization_id}/reports",
                    headers=headers,
                    json={
                        "title": "Quality Benchmark Report",
                        "report_type": benchmark["report_type"],
                        "selected_document_ids": document_ids,
                    },
                )
                report.raise_for_status()
                report_id = report.json()["id"]
                analyze = test_client.post(f"/api/reports/{report_id}/analyze", headers=headers)
                analyze.raise_for_status()

                predicted_requirements = _predicted_requirements_from_api(test_client, headers, organization_id)
        finally:
            get_engine().dispose()
            get_settings.cache_clear()
            get_engine.cache_clear()
            get_session_factory.cache_clear()

            for key, value in previous_env.items():
                os.environ[key] = value
            celery_app.conf.task_always_eager = previous_celery_eager
            get_settings.cache_clear()
            get_engine.cache_clear()
            get_session_factory.cache_clear()

    extraction = evaluate_requirement_extraction(expected_requirements, predicted_requirements)
    matches = match_requirements(expected_requirements, predicted_requirements)
    evidence = evaluate_evidence_linking(matches)
    return {
        "benchmark_name": benchmark["name"],
        "scenario": benchmark["scenario"],
        "report_type": benchmark["report_type"],
        "expected_requirements": len(expected_requirements),
        "predicted_requirements": len(predicted_requirements),
        "requirement_extraction": extraction,
        "evidence_linking": evidence,
    }


def run_quality_benchmark_suite(benchmark_paths: list[Path]) -> dict[str, object]:
    reports = [run_quality_benchmark(path) for path in benchmark_paths]
    extraction_tp = sum(int(report["requirement_extraction"]["matched_total"]) for report in reports)
    extraction_predicted = sum(int(report["requirement_extraction"]["predicted_total"]) for report in reports)
    extraction_expected = sum(int(report["requirement_extraction"]["expected_total"]) for report in reports)
    evidence_tp = sum(int(report["evidence_linking"]["matched_total"]) for report in reports)
    evidence_predicted = sum(int(report["evidence_linking"]["predicted_total"]) for report in reports)
    evidence_expected = sum(int(report["evidence_linking"]["expected_total"]) for report in reports)

    return {
        "suite_size": len(reports),
        "benchmarks": reports,
        "aggregate": {
            "requirement_extraction": {
                **precision_recall_f1(
                    true_positive=extraction_tp,
                    predicted_total=extraction_predicted,
                    expected_total=extraction_expected,
                ),
                "category_accuracy_mean": _mean(
                    [float(report["requirement_extraction"]["category_accuracy"]) for report in reports]
                ),
                "status_accuracy_mean": _mean(
                    [float(report["requirement_extraction"]["status_accuracy"]) for report in reports]
                ),
            },
            "evidence_linking": {
                **precision_recall_f1(
                    true_positive=evidence_tp,
                    predicted_total=evidence_predicted,
                    expected_total=evidence_expected,
                ),
                "grounded_requirements_share_mean": _mean(
                    [float(report["evidence_linking"]["grounded_requirements_share"]) for report in reports]
                ),
            },
        },
    }
