from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

VALID_REDACTION_LEVELS = {
    "synthetic",
    "redacted_real_like",
    "anonymized_real",
}
VALID_CASE_STATUSES = {
    "draft",
    "pilot",
    "benchmark_ready",
}
VALID_DIFFICULTY_LEVELS = {
    "low",
    "medium",
    "high",
}
QUALITY_TARGET_FIELDS = (
    "requirement_f1_min",
    "status_accuracy_min",
    "evidence_f1_min",
    "section_coverage_min",
)


def _load_json(path: Path) -> dict[str, object]:
    return json.loads(path.read_text(encoding="utf-8"))


def infer_project_root(path: Path) -> Path:
    resolved = path.resolve()
    for candidate in [resolved, *resolved.parents]:
        if (candidate / "backend").exists() and (candidate / "samples").exists():
            return candidate
    raise ValueError(f"Could not infer project root from {path}")


def resolve_project_relative_path(project_root: Path, raw_path: str) -> Path:
    relative_path = raw_path.strip()
    if not relative_path:
        raise ValueError("Path entry must not be empty")
    return (project_root / relative_path).resolve()


def load_real_corpus_case_paths(corpus_manifest_path: Path) -> list[Path]:
    payload = _load_json(corpus_manifest_path)
    case_entries = payload.get("cases", [])
    if not isinstance(case_entries, list) or not case_entries:
        raise ValueError("Real corpus manifest must contain non-empty 'cases' list")

    project_root = infer_project_root(corpus_manifest_path)
    case_paths: list[Path] = []
    for entry in case_entries:
        case_path = resolve_project_relative_path(project_root, str(entry))
        if not case_path.exists():
            raise FileNotFoundError(f"Case manifest not found: {case_path}")
        case_paths.append(case_path)
    return case_paths


def validate_real_corpus_case_manifest(case_manifest_path: Path) -> dict[str, object]:
    payload = _load_json(case_manifest_path)
    project_root = infer_project_root(case_manifest_path)
    case_id = str(payload.get("case_id") or "").strip()
    scenario = str(payload.get("scenario") or "").strip()
    report_type = str(payload.get("report_type") or "").strip()
    regulator = str(payload.get("regulator") or "").strip()
    organization_type = str(payload.get("organization_type") or "").strip()
    status = str(payload.get("status") or "").strip()
    redaction_level = str(payload.get("redaction_level") or "").strip()
    difficulty = str(payload.get("difficulty") or "").strip()
    tags = [str(tag).strip() for tag in list(payload.get("tags") or []) if str(tag).strip()]
    analysis_focus = [str(item).strip() for item in list(payload.get("analysis_focus") or []) if str(item).strip()]
    documents = list(payload.get("documents") or [])
    annotations = dict(payload.get("annotations") or {})
    quality_targets_payload = dict(payload.get("quality_targets") or {})

    issues: list[str] = []
    if not case_id:
        issues.append("missing case_id")
    if not scenario:
        issues.append("missing scenario")
    if not report_type:
        issues.append("missing report_type")
    if not regulator:
        issues.append("missing regulator")
    if not organization_type:
        issues.append("missing organization_type")
    if status not in VALID_CASE_STATUSES:
        issues.append(f"invalid status: {status or '<empty>'}")
    if redaction_level not in VALID_REDACTION_LEVELS:
        issues.append(f"invalid redaction_level: {redaction_level or '<empty>'}")
    if difficulty and difficulty not in VALID_DIFFICULTY_LEVELS:
        issues.append(f"invalid difficulty: {difficulty}")
    if not documents:
        issues.append("missing documents")
    if not analysis_focus:
        issues.append("missing analysis_focus")

    quality_targets: dict[str, float] = {}
    for field in QUALITY_TARGET_FIELDS:
        if field not in quality_targets_payload:
            continue
        try:
            value = float(quality_targets_payload[field])
        except (TypeError, ValueError):
            issues.append(f"invalid quality target value for {field}")
            continue
        if value < 0.0 or value > 1.0:
            issues.append(f"quality target out of range for {field}")
            continue
        quality_targets[field] = round(value, 4)

    document_reports: list[dict[str, object]] = []
    document_paths: set[Path] = set()
    for index, item in enumerate(documents):
        if not isinstance(item, dict):
            issues.append(f"document #{index + 1} is not an object")
            continue
        raw_path = str(item.get("path") or "").strip()
        category = str(item.get("category") or "").strip()
        source_type = str(item.get("source_type") or "").strip()
        description = str(item.get("description") or "").strip()
        local_issues: list[str] = []
        if not raw_path:
            local_issues.append("missing path")
            resolved_path = None
        else:
            resolved_path = resolve_project_relative_path(project_root, raw_path)
            if not resolved_path.exists():
                local_issues.append("file not found")
            else:
                document_paths.add(resolved_path)
        if not category:
            local_issues.append("missing category")
        if not source_type:
            local_issues.append("missing source_type")
        if not description:
            local_issues.append("missing description")
        if local_issues:
            issues.extend(f"document {raw_path or index + 1}: {issue}" for issue in local_issues)
        document_reports.append(
            {
                "path": raw_path,
                "exists": bool(resolved_path and resolved_path.exists()),
                "category": category,
                "source_type": source_type,
                "format": resolved_path.suffix.lower().lstrip(".") if resolved_path else "",
            }
        )

    benchmark_path_value = str(annotations.get("benchmark_path") or "").strip()
    review_notes_path_value = str(annotations.get("review_notes_path") or "").strip()
    benchmark_path = None
    review_notes_path = None
    benchmark_payload: dict[str, object] | None = None
    if not benchmark_path_value:
        issues.append("missing annotations.benchmark_path")
    else:
        benchmark_path = resolve_project_relative_path(project_root, benchmark_path_value)
        if not benchmark_path.exists():
            issues.append(f"benchmark file not found: {benchmark_path_value}")
        else:
            benchmark_payload = _load_json(benchmark_path)
    if review_notes_path_value:
        review_notes_path = resolve_project_relative_path(project_root, review_notes_path_value)
        if not review_notes_path.exists():
            issues.append(f"review notes file not found: {review_notes_path_value}")

    benchmark_document_paths: list[str] = []
    if benchmark_payload is not None:
        benchmark_scenario = str(benchmark_payload.get("scenario") or "").strip()
        benchmark_report_type = str(benchmark_payload.get("report_type") or "").strip()
        if benchmark_scenario and scenario and benchmark_scenario != scenario:
            issues.append("benchmark scenario mismatch")
        if benchmark_report_type and report_type and benchmark_report_type != report_type:
            issues.append("benchmark report_type mismatch")
        benchmark_documents = list(benchmark_payload.get("documents") or [])
        if not benchmark_documents:
            issues.append("benchmark documents list is empty")
        if not list(benchmark_payload.get("expected_requirements") or []):
            issues.append("benchmark expected_requirements list is empty")
        for item in benchmark_documents:
            if not isinstance(item, dict):
                issues.append("benchmark document entry is not an object")
                continue
            raw_path = str(item.get("path") or "").strip()
            benchmark_document_paths.append(raw_path or str(item.get("filename") or ""))
            if not raw_path:
                continue
            resolved_path = resolve_project_relative_path(project_root, raw_path)
            if not resolved_path.exists():
                issues.append(f"benchmark document path not found: {raw_path}")
                continue
            if resolved_path not in document_paths:
                issues.append(f"benchmark document path not declared in case manifest: {raw_path}")

    category_counts = Counter(item["category"] for item in document_reports if item["category"])
    source_type_counts = Counter(item["source_type"] for item in document_reports if item["source_type"])
    format_counts = Counter(item["format"] for item in document_reports if item["format"])

    return {
        "case_id": case_id,
        "scenario": scenario,
        "regulator": regulator,
        "organization_type": organization_type,
        "report_type": report_type,
        "status": status,
        "redaction_level": redaction_level,
        "difficulty": difficulty,
        "tags": tags,
        "analysis_focus": analysis_focus,
        "quality_targets": quality_targets,
        "document_total": len(document_reports),
        "documents": document_reports,
        "benchmark_path": benchmark_path_value,
        "review_notes_path": review_notes_path_value,
        "benchmark_document_paths": benchmark_document_paths,
        "category_counts": dict(sorted(category_counts.items())),
        "source_type_counts": dict(sorted(source_type_counts.items())),
        "format_counts": dict(sorted(format_counts.items())),
        "benchmark_ready": not issues,
        "issues": issues,
    }


def summarize_real_corpus_manifest(corpus_manifest_path: Path) -> dict[str, object]:
    payload = _load_json(corpus_manifest_path)
    case_paths = load_real_corpus_case_paths(corpus_manifest_path)
    case_reports = [validate_real_corpus_case_manifest(path) for path in case_paths]

    project_root = infer_project_root(corpus_manifest_path)
    case_status_counts = Counter(report["status"] for report in case_reports if report["status"])
    redaction_level_counts = Counter(report["redaction_level"] for report in case_reports if report["redaction_level"])
    difficulty_counts = Counter(report["difficulty"] for report in case_reports if report["difficulty"])
    tag_counts: Counter[str] = Counter()
    focus_counts: Counter[str] = Counter()
    category_counts: Counter[str] = Counter()
    source_type_counts: Counter[str] = Counter()
    format_counts: Counter[str] = Counter()
    for report in case_reports:
        tag_counts.update(report["tags"])
        focus_counts.update(report["analysis_focus"])
        category_counts.update(report["category_counts"])
        source_type_counts.update(report["source_type_counts"])
        format_counts.update(report["format_counts"])

    benchmark_ready_cases = [report for report in case_reports if report["benchmark_ready"]]
    issue_total = sum(len(report["issues"]) for report in case_reports)
    return {
        "manifest_name": str(payload.get("name") or "").strip(),
        "description": str(payload.get("description") or "").strip(),
        "project_root": str(project_root),
        "case_total": len(case_reports),
        "benchmark_ready_case_total": len(benchmark_ready_cases),
        "issue_total": issue_total,
        "case_status_counts": dict(sorted(case_status_counts.items())),
        "redaction_level_counts": dict(sorted(redaction_level_counts.items())),
        "difficulty_counts": dict(sorted(difficulty_counts.items())),
        "tag_counts": dict(sorted(tag_counts.items())),
        "focus_counts": dict(sorted(focus_counts.items())),
        "document_category_counts": dict(sorted(category_counts.items())),
        "document_source_type_counts": dict(sorted(source_type_counts.items())),
        "document_format_counts": dict(sorted(format_counts.items())),
        "cases": case_reports,
    }


def load_benchmark_paths_from_real_corpus_manifest(corpus_manifest_path: Path) -> list[Path]:
    project_root = infer_project_root(corpus_manifest_path)
    report = summarize_real_corpus_manifest(corpus_manifest_path)
    invalid_cases = [case["case_id"] or "<unknown>" for case in report["cases"] if not case["benchmark_ready"]]
    if invalid_cases:
        raise ValueError(f"Real corpus manifest contains non-benchmark-ready cases: {', '.join(invalid_cases)}")

    benchmark_paths: list[Path] = []
    for case in report["cases"]:
        benchmark_path = resolve_project_relative_path(project_root, str(case["benchmark_path"]))
        benchmark_paths.append(benchmark_path)
    return benchmark_paths
