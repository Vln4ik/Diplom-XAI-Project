from __future__ import annotations

import os
import sys
from collections.abc import Generator
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))


def build_alembic_config() -> Config:
    config = Config(str(BACKEND_ROOT / "alembic.ini"))
    config.set_main_option("script_location", str(BACKEND_ROOT / "alembic"))
    return config


@pytest.fixture()
def client(tmp_path, monkeypatch) -> Generator[tuple[TestClient, object], None, None]:
    monkeypatch.setenv("XAI_APP_DATABASE_URL", f"sqlite:///{tmp_path / 'test.db'}")
    monkeypatch.setenv("XAI_APP_STORAGE_PATH", str(tmp_path / "storage"))
    monkeypatch.setenv("XAI_APP_SECRET_KEY", "test-secret-key-with-enough-length-123")
    monkeypatch.setenv("XAI_APP_CELERY_TASK_ALWAYS_EAGER", "1")

    from app.core.config import get_settings
    from app.db.session import get_engine, get_session_factory

    get_settings.cache_clear()
    get_engine.cache_clear()
    get_session_factory.cache_clear()
    command.upgrade(build_alembic_config(), "head")

    from app.main import app

    with TestClient(app) as test_client:
        yield test_client, get_session_factory()

    get_engine().dispose()

    get_settings.cache_clear()
    get_engine.cache_clear()
    get_session_factory.cache_clear()
