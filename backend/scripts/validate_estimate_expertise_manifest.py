#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

ALLOWED_STAGES = {"filename_content", "completeness", "quality_spell_signature"}
ALLOWED_SEVERITIES = {"danger", "warning", "info", None}
TIMEZONE = "Europe/Moscow"
PROJECT_ROOT = Path(__file__).resolve().parents[2]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Validate an estimate expertise corpus manifest.")
    parser.add_argument(
        "manifest",
        type=Path,
        nargs="?",
        default=PROJECT_ROOT / "samples" / "estimate_expertise_corpus" / "manifest.json",
    )
    parser.add_argument("--allow-non-anonymized", action="store_true")
    parser.add_argument("--strict-real-corpus", action="store_true")
    parser.add_argument(
        "--output-json",
        type=Path,
        default=PROJECT_ROOT / "docs" / "estimate-expertise-corpus-validation.json",
    )
    parser.add_argument(
        "--output-md",
        type=Path,
        default=PROJECT_ROOT / "docs" / "estimate-expertise-corpus-validation.md",
    )
    parser.add_argument("--timezone", default=TIMEZONE)
    return parser.parse_args()


def _captured_at(timezone_name: str) -> str:
    return datetime.now(ZoneInfo(timezone_name)).isoformat()


def _issue(path: str, message: str) -> dict[str, str]:
    return {"path": path, "message": message}


def _is_bool(value: object) -> bool:
    return isinstance(value, bool)


def _display_path(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(PROJECT_ROOT.resolve()))
    except ValueError:
        return str(path)


def validate_manifest_report(
    manifest_path: Path,
    *,
    allow_non_anonymized: bool = False,
    strict_real_corpus: bool = False,
    timezone_name: str = TIMEZONE,
) -> dict[str, object]:
    errors: list[dict[str, str]] = []
    warnings: list[dict[str, str]] = []
    document_total = 0
    target_total = 0
    stage_target_counts: dict[str, int] = {}

    try:
        payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        errors.append(_issue("$", f"manifest cannot be read as JSON: {exc}"))
        return {
            "captured_at": _captured_at(timezone_name),
            "manifest_path": _display_path(manifest_path),
            "manifest_name": None,
            "manifest_version": None,
            "strict_real_corpus": strict_real_corpus,
            "valid": False,
            "case_total": 0,
            "document_total": 0,
            "target_total": 0,
            "stage_target_counts": {},
            "error_count": len(errors),
            "warning_count": len(warnings),
            "errors": errors,
            "warnings": warnings,
        }

    if not isinstance(payload, dict):
        errors.append(_issue("$", "manifest root must be an object"))
        payload = {}

    if not payload.get("manifest_name"):
        errors.append(_issue("$.manifest_name", "manifest_name is required"))
    if not payload.get("version"):
        errors.append(_issue("$.version", "version is required"))

    cases = payload.get("cases")
    if not isinstance(cases, list) or not cases:
        errors.append(_issue("$.cases", "cases must be a non-empty list"))
        cases = []

    privacy = payload.get("privacy") or {}
    if strict_real_corpus and not privacy:
        errors.append(_issue("$.privacy", "privacy block is required for strict real-corpus manifests"))
    if privacy and not isinstance(privacy, dict):
        errors.append(_issue("$.privacy", "privacy must be an object"))
        privacy = {}
    if isinstance(privacy, dict) and privacy:
        for key in ("contains_public_data_only", "anonymized", "allowed_for_repository"):
            if key in privacy and not _is_bool(privacy.get(key)):
                errors.append(_issue(f"$.privacy.{key}", f"privacy.{key} must be boolean"))
        anonymized = bool(privacy.get("anonymized"))
        allowed_for_repository = bool(privacy.get("allowed_for_repository"))
        if not anonymized and not allow_non_anonymized:
            errors.append(
                _issue(
                    "$.privacy.anonymized",
                    "privacy.anonymized must be true or --allow-non-anonymized must be passed",
                )
            )
        if allowed_for_repository and not anonymized:
            errors.append(
                _issue(
                    "$.privacy.allowed_for_repository",
                    "privacy.allowed_for_repository cannot be true when privacy.anonymized is false",
                )
            )
        if allowed_for_repository and not privacy.get("contains_public_data_only"):
            if not privacy.get("reviewed_by") or not privacy.get("reviewed_at"):
                errors.append(
                    _issue(
                        "$.privacy.reviewed_by",
                        "repository-allowed non-public corpus requires reviewed_by and reviewed_at",
                    )
                )
        if strict_real_corpus and not allowed_for_repository:
            warnings.append(
                _issue(
                    "$.privacy.allowed_for_repository",
                    "manifest is valid for local validation but not marked as safe for repository publication",
                )
            )
    if not privacy and not strict_real_corpus:
        warnings.append(_issue("$.privacy", "privacy block is absent; acceptable for synthetic corpus only"))

    seen_case_ids: set[str] = set()
    for case_index, case in enumerate(cases):
        prefix = f"cases[{case_index}]"
        if not isinstance(case, dict):
            errors.append(_issue(prefix, "case must be an object"))
            continue
        case_id = case.get("case_id")
        if not case_id:
            errors.append(_issue(f"{prefix}.case_id", "case_id is required"))
        elif case_id in seen_case_ids:
            errors.append(_issue(f"{prefix}.case_id", f"case_id '{case_id}' is duplicated"))
        else:
            seen_case_ids.add(str(case_id))
        if not case.get("scenario"):
            warnings.append(_issue(f"{prefix}.scenario", "scenario is recommended for corpus interpretation"))

        documents = case.get("documents")
        if not isinstance(documents, list) or not documents:
            errors.append(_issue(f"{prefix}.documents", "documents must be a non-empty list"))
        else:
            seen_paths: set[str] = set()
            for document_index, document in enumerate(documents):
                document_prefix = f"{prefix}.documents[{document_index}]"
                if not isinstance(document, dict):
                    errors.append(_issue(document_prefix, "document must be an object"))
                    continue
                document_total += 1
                if not document.get("file_name"):
                    errors.append(_issue(f"{document_prefix}.file_name", "file_name is required"))
                if not document.get("relative_path"):
                    errors.append(_issue(f"{document_prefix}.relative_path", "relative_path is required"))
                elif str(document["relative_path"]) in seen_paths:
                    warnings.append(_issue(f"{document_prefix}.relative_path", "relative_path is duplicated in case"))
                else:
                    seen_paths.add(str(document["relative_path"]))
                if not document.get("file_type"):
                    errors.append(_issue(f"{document_prefix}.file_type", "file_type is required"))
                try:
                    page_count = int(document.get("page_count"))
                except (TypeError, ValueError):
                    errors.append(_issue(f"{document_prefix}.page_count", "page_count must be a positive integer"))
                else:
                    if page_count <= 0:
                        errors.append(_issue(f"{document_prefix}.page_count", "page_count must be a positive integer"))
                if document.get("text") is None:
                    errors.append(
                        _issue(
                            f"{document_prefix}.text",
                            "text is required; use redacted extracted text if file is closed",
                        )
                    )
                elif document.get("text") == "":
                    warnings.append(_issue(f"{document_prefix}.text", "text is empty; valid only for scan/OCR-negative cases"))

        targets = case.get("targets")
        if not isinstance(targets, list) or not targets:
            errors.append(_issue(f"{prefix}.targets", "targets must be a non-empty list"))
        else:
            for target_index, target in enumerate(targets):
                target_prefix = f"{prefix}.targets[{target_index}]"
                if not isinstance(target, dict):
                    errors.append(_issue(target_prefix, "target must be an object"))
                    continue
                target_total += 1
                if target.get("stage_key") not in ALLOWED_STAGES:
                    errors.append(_issue(f"{target_prefix}.stage_key", f"stage_key must be one of {sorted(ALLOWED_STAGES)}"))
                else:
                    stage_key = str(target.get("stage_key"))
                    stage_target_counts[stage_key] = stage_target_counts.get(stage_key, 0) + 1
                if target.get("severity") not in ALLOWED_SEVERITIES:
                    errors.append(_issue(f"{target_prefix}.severity", "severity must be danger, warning, info, or omitted"))
                if not target.get("title_contains") and not target.get("text_contains"):
                    errors.append(_issue(target_prefix, "target must define title_contains or text_contains"))
                if "expected_absent" in target and not _is_bool(target.get("expected_absent")):
                    errors.append(_issue(f"{target_prefix}.expected_absent", "expected_absent must be boolean"))

    return {
        "captured_at": _captured_at(timezone_name),
        "manifest_path": _display_path(manifest_path),
        "manifest_name": payload.get("manifest_name"),
        "manifest_version": payload.get("version"),
        "strict_real_corpus": strict_real_corpus,
        "valid": not errors,
        "case_total": len(cases),
        "document_total": document_total,
        "target_total": target_total,
        "stage_target_counts": dict(sorted(stage_target_counts.items())),
        "error_count": len(errors),
        "warning_count": len(warnings),
        "errors": errors,
        "warnings": warnings,
    }


def validate_manifest(manifest_path: Path, *, allow_non_anonymized: bool = False) -> list[str]:
    report = validate_manifest_report(manifest_path, allow_non_anonymized=allow_non_anonymized)
    return [f"{issue['path']}: {issue['message']}" for issue in report["errors"]]


def render_markdown(report: dict[str, object], *, timezone_name: str = TIMEZONE) -> str:
    captured_at = datetime.fromisoformat(str(report["captured_at"])).astimezone(ZoneInfo(timezone_name))
    lines = [
        "# Валидация корпуса проектно-сметной спецпроверки",
        "",
        f"Дата фиксации: `{captured_at:%Y-%m-%d}`",
        "",
        "## 1. Сводка",
        "",
        f"- manifest: `{report['manifest_name']}`",
        f"- version: `{report['manifest_version']}`",
        f"- path: `{report['manifest_path']}`",
        f"- strict_real_corpus: `{report['strict_real_corpus']}`",
        f"- valid: `{report['valid']}`",
        f"- cases: `{report['case_total']}`",
        f"- documents: `{report['document_total']}`",
        f"- targets: `{report['target_total']}`",
        f"- errors: `{report['error_count']}`",
        f"- warnings: `{report['warning_count']}`",
        "",
        "## 2. Targets по этапам",
        "",
    ]
    stage_counts = dict(report["stage_target_counts"])
    if stage_counts:
        lines.extend(f"- `{stage}`: `{count}`" for stage, count in stage_counts.items())
    else:
        lines.append("- targets не найдены")

    lines.extend(["", "## 3. Ошибки", ""])
    errors = list(report["errors"])
    if errors:
        lines.extend(f"- `{item['path']}`: {item['message']}" for item in errors)
    else:
        lines.append("- ошибок нет")

    lines.extend(["", "## 4. Предупреждения", ""])
    warnings = list(report["warnings"])
    if warnings:
        lines.extend(f"- `{item['path']}`: {item['message']}" for item in warnings)
    else:
        lines.append("- предупреждений нет")

    lines.extend(
        [
            "",
            "## 5. Интерпретация",
            "",
            "Этот отчет проверяет не качество AI-выводов, а готовность manifest к безопасному benchmark-прогону.",
            "Для реальных проектно-сметных документов нужно запускать validator в режиме `--strict-real-corpus`",
            "и хранить в репозитории только те данные, которые прошли обезличивание и publication review.",
        ]
    )
    return "\n".join(lines)


def main() -> int:
    args = parse_args()
    report = validate_manifest_report(
        args.manifest,
        allow_non_anonymized=args.allow_non_anonymized,
        strict_real_corpus=args.strict_real_corpus,
        timezone_name=args.timezone,
    )
    args.output_json.parent.mkdir(parents=True, exist_ok=True)
    args.output_md.parent.mkdir(parents=True, exist_ok=True)
    args.output_json.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    args.output_md.write_text(render_markdown(report, timezone_name=args.timezone) + "\n", encoding="utf-8")
    print(f"Written {args.output_json}")
    print(f"Written {args.output_md}")
    if not report["valid"]:
        for error in report["errors"]:
            print(f"ERROR: {error['path']}: {error['message']}")
        return 1
    print(f"OK: {args.manifest}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
