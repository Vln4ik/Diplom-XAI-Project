from __future__ import annotations

from app.services.ai_profiles import PROFILE_REGISTRY, normalize_ai_runtime_profile, resolve_ai_model_choice


def test_normalize_ai_runtime_profile_falls_back_to_baseline():
    assert normalize_ai_runtime_profile(None) == "baseline"
    assert normalize_ai_runtime_profile("QUALITY") == "quality"
    assert normalize_ai_runtime_profile("quality-plus") == "quality_plus"
    assert normalize_ai_runtime_profile("unknown") == "baseline"


def test_resolve_ai_model_choice_prefers_profile_candidates_for_quality_profile():
    profile = PROFILE_REGISTRY["quality"]

    choice = resolve_ai_model_choice(
        configured_model="gemma3:270m",
        profile_candidates=profile.llm_candidates,
        available_models=["gemma3:270m", "qwen2.5:3b"],
        prefer_profile_candidates=True,
        profile_id=profile.profile_id,
    )

    assert choice.resolved_model == "qwen2.5:3b"
    assert choice.preferred_model == "qwen2.5:3b"
    assert choice.from_profile_candidate is True
    assert choice.model_available is True


def test_resolve_ai_model_choice_keeps_configured_model_for_baseline_profile():
    profile = PROFILE_REGISTRY["baseline"]

    choice = resolve_ai_model_choice(
        configured_model="all-minilm",
        profile_candidates=profile.embedding_candidates,
        available_models=["all-minilm", "nomic-embed-text"],
        prefer_profile_candidates=False,
        profile_id=profile.profile_id,
    )

    assert choice.resolved_model == "all-minilm"
    assert choice.preferred_model == "all-minilm"
    assert choice.model_available is True


def test_resolve_ai_model_choice_falls_back_to_configured_when_profile_candidates_missing():
    profile = PROFILE_REGISTRY["quality_plus"]

    choice = resolve_ai_model_choice(
        configured_model="custom-llm:latest",
        profile_candidates=profile.llm_candidates,
        available_models=["custom-llm:latest"],
        prefer_profile_candidates=True,
        profile_id=profile.profile_id,
    )

    assert choice.resolved_model == "custom-llm:latest"
    assert choice.from_profile_candidate is False
    assert choice.model_available is True
