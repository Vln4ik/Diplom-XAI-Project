from __future__ import annotations

from fastapi import APIRouter

from app.embeddings.local import describe_embedding_provider
from app.llm.local import describe_llm_provider

router = APIRouter(prefix="/system", tags=["system"])


@router.get("/ai-status")
def get_ai_status() -> dict[str, dict[str, object]]:
    return {
        "embeddings": describe_embedding_provider(),
        "llm": describe_llm_provider(),
    }
