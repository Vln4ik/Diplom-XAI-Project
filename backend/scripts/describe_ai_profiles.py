#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

SCRIPT_ROOT = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_ROOT.parents[1]
BACKEND_ROOT = PROJECT_ROOT / "backend"
VENV_PYTHON = PROJECT_ROOT / ".venv" / "bin" / "python"
VENV_ROOT = PROJECT_ROOT / ".venv"

if VENV_PYTHON.exists() and Path(sys.prefix).resolve() != VENV_ROOT.resolve():
    completed = subprocess.run([str(VENV_PYTHON), __file__, *sys.argv[1:]], check=False)
    raise SystemExit(completed.returncode)

if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.core.config import get_settings  # noqa: E402
from app.integrations.ollama import OllamaError, list_models  # noqa: E402
from app.services.ai_profiles import (  # noqa: E402
    describe_ai_runtime_profile,
    resolve_ai_model_choice,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Describe configured AI runtime profile and resolved Ollama models.")
    parser.add_argument("--profile", help="Override XAI_APP_AI_RUNTIME_PROFILE for this command.")
    parser.add_argument("--base-url", default=None, help="Override Ollama base URL.")
    parser.add_argument("--json", action="store_true", help="Print JSON payload.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.profile:
        os.environ["XAI_APP_AI_RUNTIME_PROFILE"] = args.profile
    if args.base_url:
        os.environ["XAI_APP_OLLAMA_BASE_URL"] = args.base_url

    get_settings.cache_clear()
    settings = get_settings()
    profile = describe_ai_runtime_profile()

    available_models: list[str] | None = None
    availability_error: str | None = None
    try:
        available_models = list_models(settings.ollama_base_url, settings.ollama_request_timeout_seconds)
    except OllamaError as exc:
        availability_error = str(exc)

    embedding_choice = resolve_ai_model_choice(
        configured_model=settings.ollama_embedding_model,
        profile_candidates=tuple(str(item) for item in profile["embedding_candidates"]),
        available_models=available_models,
        prefer_profile_candidates=profile["profile_id"] != "baseline",
        profile_id=str(profile["profile_id"]),
    )
    llm_choice = resolve_ai_model_choice(
        configured_model=settings.ollama_llm_model,
        profile_candidates=tuple(str(item) for item in profile["llm_candidates"]),
        available_models=available_models,
        prefer_profile_candidates=profile["profile_id"] != "baseline",
        profile_id=str(profile["profile_id"]),
    )

    payload = {
        "profile": profile,
        "ollama_base_url": settings.ollama_base_url,
        "available_models": available_models,
        "availability_error": availability_error,
        "embedding": {
            "configured_model": embedding_choice.configured_model,
            "preferred_model": embedding_choice.preferred_model,
            "resolved_model": embedding_choice.resolved_model,
            "candidate_models": list(embedding_choice.candidate_models),
            "model_available": embedding_choice.model_available,
            "from_profile_candidate": embedding_choice.from_profile_candidate,
        },
        "llm": {
            "configured_model": llm_choice.configured_model,
            "preferred_model": llm_choice.preferred_model,
            "resolved_model": llm_choice.resolved_model,
            "candidate_models": list(llm_choice.candidate_models),
            "model_available": llm_choice.model_available,
            "from_profile_candidate": llm_choice.from_profile_candidate,
        },
    }

    if args.json:
        print(json.dumps(payload, ensure_ascii=False))
        return 0

    print(f"profile: {profile['profile_id']} ({profile['label']})")
    print(f"objective: {profile['objective']}")
    print(f"ollama_base_url: {settings.ollama_base_url}")
    print(f"available_models: {', '.join(available_models or []) if available_models else 'unavailable'}")
    if availability_error:
        print(f"availability_error: {availability_error}")
    print(f"embedding_resolved_model: {embedding_choice.resolved_model}")
    print(f"llm_resolved_model: {llm_choice.resolved_model}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
