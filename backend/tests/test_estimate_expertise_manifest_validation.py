from __future__ import annotations

import importlib.util
import json
from pathlib import Path


def _load_validator_module():
    project_root = Path(__file__).resolve().parents[2]
    script_path = project_root / "backend" / "scripts" / "validate_estimate_expertise_manifest.py"
    spec = importlib.util.spec_from_file_location("validate_estimate_expertise_manifest", script_path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_estimate_expertise_synthetic_manifest_is_valid():
    project_root = Path(__file__).resolve().parents[2]
    module = _load_validator_module()

    report = module.validate_manifest_report(
        project_root / "samples" / "estimate_expertise_corpus" / "manifest.json",
        timezone_name="Europe/Moscow",
    )

    assert report["valid"] is True
    assert report["case_total"] == 4
    assert report["document_total"] == 12
    assert report["target_total"] == 10
    assert report["stage_target_counts"]["completeness"] == 6
    assert report["warning_count"] >= 1


def test_estimate_expertise_real_corpus_template_is_strict_valid():
    project_root = Path(__file__).resolve().parents[2]
    module = _load_validator_module()

    report = module.validate_manifest_report(
        project_root / "samples" / "estimate_expertise_corpus" / "real-corpus-template.json",
        strict_real_corpus=True,
        timezone_name="Europe/Moscow",
    )

    assert report["valid"] is True
    assert report["case_total"] == 1
    assert report["warning_count"] == 1
    assert report["warnings"][0]["path"] == "$.privacy.allowed_for_repository"


def test_estimate_expertise_manifest_blocks_unsafe_repository_publication(tmp_path):
    module = _load_validator_module()
    manifest_path = tmp_path / "bad-manifest.json"
    manifest_path.write_text(
        json.dumps(
            {
                "manifest_name": "bad-real-corpus",
                "version": "2026-05-28",
                "privacy": {
                    "contains_public_data_only": False,
                    "anonymized": False,
                    "allowed_for_repository": True,
                },
                "cases": [
                    {
                        "case_id": "case-1",
                        "documents": [
                            {
                                "file_name": "secret.pdf",
                                "relative_path": "secret.pdf",
                                "file_type": "application/pdf",
                                "page_count": 1,
                                "text": "закрытый текст",
                            }
                        ],
                        "targets": [
                            {
                                "stage_key": "completeness",
                                "title_contains": "Сводный сметный расчет",
                                "severity": "danger",
                            }
                        ],
                    }
                ],
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    report = module.validate_manifest_report(manifest_path, strict_real_corpus=True, timezone_name="Europe/Moscow")

    assert report["valid"] is False
    assert any(error["path"] == "$.privacy.anonymized" for error in report["errors"])
    assert any(error["path"] == "$.privacy.allowed_for_repository" for error in report["errors"])
