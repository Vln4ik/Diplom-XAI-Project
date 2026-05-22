from __future__ import annotations

from app.core.config import get_settings
from app.services.analysis import clear_analysis_calibration_cache, get_analysis_calibration


def test_analysis_calibration_reads_env_overrides(monkeypatch):
    monkeypatch.setenv("XAI_APP_REQUIREMENT_DATA_FOUND_CONFIDENCE_THRESHOLD", "0.61")
    monkeypatch.setenv("XAI_APP_EVIDENCE_BOOLEAN_PENALTY", "0.2")

    get_settings.cache_clear()
    clear_analysis_calibration_cache()

    profile = get_analysis_calibration()

    assert profile.data_found_confidence_threshold == 0.61
    assert profile.evidence_boolean_penalty == 0.2

    get_settings.cache_clear()
    clear_analysis_calibration_cache()
