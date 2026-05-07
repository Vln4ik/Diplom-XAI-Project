from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.router import api_router
from app.core.config import get_settings
from app.db.session import get_session_factory
from app.services.bootstrap import bootstrap_system_admin

settings = get_settings()


@asynccontextmanager
async def lifespan(_: FastAPI):
    session = get_session_factory()()
    try:
        bootstrap_system_admin(session)
    finally:
        session.close()
    yield


app = FastAPI(title=settings.app_name, version="0.1.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(api_router, prefix=settings.api_prefix)


@app.get("/")
def root() -> dict[str, str]:
    return {"service": "xai-report-builder-api", "status": "ok"}
