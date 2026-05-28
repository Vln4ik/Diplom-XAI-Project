from __future__ import annotations

import importlib.util
from pathlib import Path


def test_estimate_expertise_corpus_evaluator_passes_pilot_targets():
    project_root = Path(__file__).resolve().parents[2]
    script_path = project_root / "backend" / "scripts" / "evaluate_estimate_expertise_corpus.py"
    spec = importlib.util.spec_from_file_location("evaluate_estimate_expertise_corpus", script_path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    report = module.evaluate_manifest(
        project_root / "samples" / "estimate_expertise_corpus" / "manifest.json",
        timezone_name="Europe/Moscow",
    )

    assert report["case_total"] == 4
    assert report["cases_passed"] == 4
    assert report["target_total"] == 10
    assert report["targets_passed"] == 10
    assert report["stage_target_summary"]["completeness"]["passed"] == 6
    assert report["stage_target_summary"]["filename_content"]["passed"] == 1
    assert report["stage_target_summary"]["quality_spell_signature"]["passed"] == 3
