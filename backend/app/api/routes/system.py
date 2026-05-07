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
from app.services.runtime_metrics import runtime_metrics

router = APIRouter(prefix="/system", tags=["system"])


@router.get("/ai-status")
def get_ai_status() -> dict[str, dict[str, object]]:
    return {
        "embeddings": describe_embedding_provider(),
        "llm": describe_llm_provider(),
        "ocr": describe_ocr_provider(),
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
            "embedding_provider": get_settings().embedding_provider,
            "llm_provider": get_settings().llm_provider,
            "ocr_provider": get_settings().ocr_provider,
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
