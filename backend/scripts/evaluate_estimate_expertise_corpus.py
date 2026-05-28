#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

BACKEND_ROOT = Path(__file__).resolve().parents[1]
PROJECT_ROOT = BACKEND_ROOT.parent
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.models import Document, DocumentCategory, DocumentStatus  # noqa: E402
from app.services.estimate_expertise import (  # noqa: E402
    MODEL_VERSION,
    RULE_VERSION,
    _build_completeness_findings,
    _build_filename_findings,
    _build_quality_findings,
)

TIMEZONE = "Europe/Moscow"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Evaluate estimate expertise workflow targets on a local corpus.")
    parser.add_argument(
        "--manifest",
        type=Path,
        default=PROJECT_ROOT / "samples" / "estimate_expertise_corpus" / "manifest.json",
    )
    parser.add_argument(
        "--output-json",
        type=Path,
        default=PROJECT_ROOT / "docs" / "estimate-expertise-corpus-evaluation.json",
    )
    parser.add_argument(
        "--output-md",
        type=Path,
        default=PROJECT_ROOT / "docs" / "estimate-expertise-corpus-evaluation.md",
    )
    parser.add_argument("--timezone", default=TIMEZONE)
    return parser.parse_args()


def _captured_at(timezone_name: str) -> str:
    return datetime.now(ZoneInfo(timezone_name)).isoformat()


def _document_from_payload(case_id: str, index: int, payload: dict) -> Document:
    file_name = str(payload["file_name"])
    return Document(
        id=f"{case_id}-{index}",
        organization_id=f"{case_id}-organization",
        uploaded_by_id=None,
        file_name=file_name,
        original_file_name=file_name,
        relative_path=str(payload.get("relative_path") or file_name),
        file_type=str(payload.get("file_type") or "text/plain"),
        file_size=len(str(payload.get("text") or "").encode("utf-8")),
        category=DocumentCategory.evidence,
        storage_path=f"/tmp/{case_id}/{file_name}",
        status=DocumentStatus.processed,
        extracted_text=str(payload.get("text") or ""),
        page_count=int(payload.get("page_count") or 1),
        tags=[],
    )


def _build_stage_findings(documents: list[Document]) -> list[dict]:
    stage_findings = [
        *_build_filename_findings(documents),
        *_build_completeness_findings(documents),
        *_build_quality_findings(documents),
    ]
    return sorted(stage_findings, key=lambda item: (str(item["stage_key"]), str(item["title"])))


def _matches_target(finding: dict, target: dict) -> bool:
    if target.get("stage_key") and finding.get("stage_key") != target["stage_key"]:
        return False
    if target.get("severity") and finding.get("severity") != target["severity"]:
        return False
    title_contains = str(target.get("title_contains") or "").lower()
    if title_contains and title_contains not in str(finding.get("title") or "").lower():
        return False
    text_contains = str(target.get("text_contains") or "").lower()
    if text_contains:
        haystack = " ".join(
            [
                str(finding.get("title") or ""),
                str(finding.get("description") or ""),
                str(finding.get("normative_basis") or ""),
                " ".join(str(item) for item in finding.get("xai_json") or []),
            ]
        ).lower()
        if text_contains not in haystack:
            return False
    return True


def _evaluate_target(findings: list[dict], target: dict) -> dict:
    matches = [finding for finding in findings if _matches_target(finding, target)]
    expected_absent = bool(target.get("expected_absent"))
    passed = not matches if expected_absent else bool(matches)
    return {
        "stage_key": target.get("stage_key"),
        "title_contains": target.get("title_contains"),
        "severity": target.get("severity"),
        "expected_absent": expected_absent,
        "passed": passed,
        "matched_count": len(matches),
        "matched_titles": [str(finding.get("title")) for finding in matches[:5]],
    }


def _summarize_findings(findings: list[dict]) -> dict:
    severity_counts = Counter(str(finding.get("severity")) for finding in findings)
    stage_counts = Counter(str(finding.get("stage_key")) for finding in findings)
    return {
        "total": len(findings),
        "by_severity": dict(sorted(severity_counts.items())),
        "by_stage": dict(sorted(stage_counts.items())),
    }


def evaluate_manifest(manifest_path: Path, *, timezone_name: str) -> dict:
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    case_results: list[dict] = []
    stage_target_totals: dict[str, int] = defaultdict(int)
    stage_target_passed: dict[str, int] = defaultdict(int)
    cases_passed = 0
    targets_passed = 0
    target_total = 0

    for case in manifest["cases"]:
        case_id = str(case["case_id"])
        documents = [_document_from_payload(case_id, index, document) for index, document in enumerate(case["documents"], start=1)]
        findings = _build_stage_findings(documents)
        target_results = [_evaluate_target(findings, target) for target in case.get("targets", [])]
        case_passed = all(result["passed"] for result in target_results)
        if case_passed:
            cases_passed += 1
        for result in target_results:
            target_total += 1
            stage_key = str(result.get("stage_key") or "unknown")
            stage_target_totals[stage_key] += 1
            if result["passed"]:
                targets_passed += 1
                stage_target_passed[stage_key] += 1

        case_results.append(
            {
                "case_id": case_id,
                "scenario": case.get("scenario"),
                "document_count": len(documents),
                "case_passed": case_passed,
                "findings_summary": _summarize_findings(findings),
                "targets": target_results,
            }
        )

    return {
        "captured_at": _captured_at(timezone_name),
        "manifest_name": manifest["manifest_name"],
        "manifest_version": manifest.get("version"),
        "model_version": MODEL_VERSION,
        "rule_version": RULE_VERSION,
        "case_total": len(case_results),
        "cases_passed": cases_passed,
        "target_total": target_total,
        "targets_passed": targets_passed,
        "target_pass_rate": round(targets_passed / target_total, 4) if target_total else 0.0,
        "stage_target_summary": {
            stage_key: {
                "passed": stage_target_passed[stage_key],
                "total": stage_target_totals[stage_key],
                "pass_rate": round(stage_target_passed[stage_key] / stage_target_totals[stage_key], 4),
            }
            for stage_key in sorted(stage_target_totals)
        },
        "cases": case_results,
    }


def render_markdown(report: dict, *, timezone_name: str) -> str:
    captured_at = datetime.fromisoformat(str(report["captured_at"])).astimezone(ZoneInfo(timezone_name))
    lines = [
        "# Benchmark проектно-сметного спецworkflow",
        "",
        f"Дата фиксации: `{captured_at:%Y-%m-%d}`",
        "",
        "## 1. Сводка",
        "",
        f"- manifest: `{report['manifest_name']}`",
        f"- manifest_version: `{report['manifest_version']}`",
        f"- model_version: `{report['model_version']}`",
        f"- rule_version: `{report['rule_version']}`",
        f"- cases: `{report['case_total']}`",
        f"- cases_passed: `{report['cases_passed']}/{report['case_total']}`",
        f"- targets_passed: `{report['targets_passed']}/{report['target_total']}`",
        f"- target_pass_rate: `{report['target_pass_rate']:.4f}`",
        "",
        "## 2. Метрики по этапам",
        "",
    ]
    for stage_key, summary in report["stage_target_summary"].items():
        lines.append(
            f"- `{stage_key}`: `{summary['passed']}/{summary['total']}` targets, pass_rate `{summary['pass_rate']:.4f}`"
        )
    lines.extend(["", "## 3. Кейсы", ""])
    for case in report["cases"]:
        lines.extend(
            [
                f"### {case['case_id']}",
                "",
                f"- scenario: {case['scenario']}",
                f"- documents: `{case['document_count']}`",
                f"- case_passed: `{case['case_passed']}`",
                f"- findings_total: `{case['findings_summary']['total']}`",
                f"- findings_by_stage: `{case['findings_summary']['by_stage']}`",
                f"- findings_by_severity: `{case['findings_summary']['by_severity']}`",
                "",
                "Targets:",
            ]
        )
        for target in case["targets"]:
            expectation = "absent" if target["expected_absent"] else "present"
            lines.append(
                f"- `{target['stage_key']}` / `{target['title_contains']}` / `{target.get('severity')}` / `{expectation}` -> `{target['passed']}`"
            )
        lines.append("")
    lines.extend(
        [
            "## 4. Интерпретация",
            "",
            "Этот benchmark является synthetic pilot corpus для регрессионной проверки инженерной логики спецworkflow.",
            "Он не заменяет расширенный обезличенный реальный корпус проектно-сметной документации.",
            "Следующий шаг MVP 2/3 — добавить реальные обезличенные кейсы и проверить precision/recall по каждому stage.",
            "",
        ]
    )
    return "\n".join(lines)


def main() -> int:
    args = parse_args()
    report = evaluate_manifest(args.manifest, timezone_name=args.timezone)
    args.output_json.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    args.output_md.write_text(render_markdown(report, timezone_name=args.timezone) + "\n", encoding="utf-8")
    print(f"Written {args.output_json}")
    print(f"Written {args.output_md}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
