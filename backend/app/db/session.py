from __future__ import annotations

from collections.abc import Generator
from functools import lru_cache

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import get_settings


def _connect_args() -> dict[str, object]:
    if get_settings().database_url.startswith("sqlite"):
        return {"check_same_thread": False}
    return {}


@lru_cache(maxsize=1)
def get_engine():
    settings = get_settings()
    return create_engine(settings.database_url, future=True, pool_pre_ping=True, connect_args=_connect_args())


@lru_cache(maxsize=1)
def get_session_factory():
    return sessionmaker(bind=get_engine(), autoflush=False, autocommit=False, class_=Session, expire_on_commit=False)


def get_db_session() -> Generator[Session, None, None]:
    session = get_session_factory()()
    try:
        yield session
    finally:
        session.close()
