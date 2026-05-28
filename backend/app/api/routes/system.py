from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter
from fastapi.responses import PlainTextResponse
from sqlalchemy import text

from app.core.config import get_settings
from app.db.session import get_engine
from app.embeddings.local import describe_embedding_provider
from app.integrations.catalog import describe_external_integrations
from app.integrations.ocr import describe_ocr_provider
from app.llm.local import describe_llm_provider
from app.services.ai_profiles import describe_ai_runtime_profile
from app.services.runtime_metrics import runtime_metrics
from app.services.terminology_quality import describe_terminology_quality_rules
from app.services.visual_quality import describe_visual_quality_provider
from app.services.visual_signatures import describe_visual_signature_provider

router = APIRouter(prefix="/system", tags=["system"])


@router.get("/ai-status")
def get_ai_status() -> dict[str, dict[str, object]]:
    return {
        "profile": describe_ai_runtime_profile(),
        "embeddings": describe_embedding_provider(),
        "llm": describe_llm_provider(),
        "ocr": describe_ocr_provider(),
        "vision": describe_visual_signature_provider(),
        "visual_quality": describe_visual_quality_provider(),
        "terminology_quality": describe_terminology_quality_rules(),
    }


@router.get("/health")
def get_system_health() -> dict[str, object]:
    database_ok = False
    database_error = None
    try:
        with get_engine().connect() as connection:
            connection.execute(text("SELECT 1"))
        database_ok = True
    except Exception as exc:  # pragma: no cover - defensive
        database_error = str(exc)

    storage_path = Path(get_settings().storage_path)
    return {
        "status": "ok" if database_ok else "degraded",
        "database": {"ok": database_ok, "error": database_error},
        "storage": {
            "path": str(storage_path),
            "exists": storage_path.exists(),
            "writable": storage_path.exists() and storage_path.is_dir(),
        },
        "runtime": {
            "celery_task_always_eager": get_settings().celery_task_always_eager,
            "ai_runtime_profile": get_settings().ai_runtime_profile,
            "embedding_provider": get_settings().embedding_provider,
            "llm_provider": get_settings().llm_provider,
            "ocr_provider": get_settings().ocr_provider,
            "visual_signature_provider": get_settings().visual_signature_provider,
            "visual_quality_provider": get_settings().visual_quality_provider,
            "esign_provider": get_settings().esign_provider,
        },
    }


@router.get("/integrations")
def get_system_integrations() -> dict[str, object]:
    return describe_external_integrations()


@router.get("/metrics")
def get_system_metrics() -> dict[str, object]:
    return runtime_metrics.snapshot()


@router.get("/metrics/prometheus", response_class=PlainTextResponse)
def get_system_metrics_prometheus() -> str:
    return runtime_metrics.render_prometheus()
