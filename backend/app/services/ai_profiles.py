from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache

from app.core.config import get_settings
from app.integrations.ollama import has_model


@dataclass(frozen=True)
class AIRuntimeProfile:
    profile_id: str
    label: str
    objective: str
    embedding_candidates: tuple[str, ...]
    llm_candidates: tuple[str, ...]


@dataclass(frozen=True)
class ResolvedAIModelChoice:
    profile_id: str
    configured_model: str
    preferred_model: str
    resolved_model: str
    candidate_models: tuple[str, ...]
    available_models: tuple[str, ...] | None
    from_profile_candidate: bool
    model_available: bool


PROFILE_REGISTRY: dict[str, AIRuntimeProfile] = {
    "baseline": AIRuntimeProfile(
        profile_id="baseline",
        label="Baseline",
        objective="Скорость и минимальные требования к локальному runtime.",
        embedding_candidates=("all-minilm",),
        llm_candidates=("gemma3:270m",),
    ),
    "quality": AIRuntimeProfile(
        profile_id="quality",
        label="Quality",
        objective="Лучшее качество retrieval и section generation при умеренном росте runtime-стоимости.",
        embedding_candidates=("nomic-embed-text", "mxbai-embed-large", "all-minilm"),
        llm_candidates=("qwen2.5:3b", "llama3.2:3b", "gemma3:1b", "gemma3:270m"),
    ),
    "quality_plus": AIRuntimeProfile(
        profile_id="quality_plus",
        label="Quality Plus",
        objective="Максимально сильный локальный профиль для более тяжёлых benchmark и demo-сценариев.",
        embedding_candidates=("mxbai-embed-large", "nomic-embed-text", "all-minilm"),
        llm_candidates=("qwen2.5:7b", "llama3.1:8b", "qwen2.5:3b", "llama3.2:3b", "gemma3:1b", "gemma3:270m"),
    ),
}


def _dedupe(values: list[str]) -> tuple[str, ...]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        normalized = value.strip()
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        result.append(normalized)
    return tuple(result)


def normalize_ai_runtime_profile(value: str | None) -> str:
    normalized = (value or "").strip().lower().replace("-", "_")
    if normalized in PROFILE_REGISTRY:
        return normalized
    return "baseline"


@lru_cache(maxsize=1)
def get_ai_runtime_profile() -> AIRuntimeProfile:
    profile_id = normalize_ai_runtime_profile(get_settings().ai_runtime_profile)
    return PROFILE_REGISTRY[profile_id]


def clear_ai_runtime_profile_cache() -> None:
    get_ai_runtime_profile.cache_clear()


def _ordered_candidates(
    *,
    configured_model: str | None,
    profile_candidates: tuple[str, ...],
    prefer_profile_candidates: bool,
) -> tuple[str, ...]:
    configured = (configured_model or "").strip()
    ordered: list[str] = []
    if prefer_profile_candidates:
        ordered.extend(profile_candidates)
        if configured:
            ordered.append(configured)
    else:
        if configured:
            ordered.append(configured)
        ordered.extend(profile_candidates)
    return _dedupe(ordered)


def resolve_ai_model_choice(
    *,
    configured_model: str | None,
    profile_candidates: tuple[str, ...],
    available_models: list[str] | None,
    prefer_profile_candidates: bool,
    profile_id: str,
) -> ResolvedAIModelChoice:
    candidates = _ordered_candidates(
        configured_model=configured_model,
        profile_candidates=profile_candidates,
        prefer_profile_candidates=prefer_profile_candidates,
    )
    preferred_model = candidates[0] if candidates else (configured_model or "")
    resolved_model = preferred_model
    model_available = False
    available = tuple(available_models) if available_models else None

    if available_models:
        for candidate in candidates:
            if has_model(available_models, candidate):
                resolved_model = candidate
                model_available = True
                break

    from_profile_candidate = resolved_model in profile_candidates
    return ResolvedAIModelChoice(
        profile_id=profile_id,
        configured_model=(configured_model or "").strip(),
        preferred_model=preferred_model,
        resolved_model=resolved_model,
        candidate_models=candidates,
        available_models=available,
        from_profile_candidate=from_profile_candidate,
        model_available=model_available,
    )


def describe_ai_runtime_profile() -> dict[str, object]:
    profile = get_ai_runtime_profile()
    return {
        "profile_id": profile.profile_id,
        "label": profile.label,
        "objective": profile.objective,
        "embedding_candidates": list(profile.embedding_candidates),
        "llm_candidates": list(profile.llm_candidates),
    }
