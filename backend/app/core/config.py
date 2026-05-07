from __future__ import annotations

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="XAI_APP_", case_sensitive=False, extra="ignore")

    app_name: str = "XAI Report Builder API"
    api_prefix: str = "/api"
    database_url: str = "sqlite:///./xai_report_builder.db"
    redis_url: str = "redis://localhost:6379/0"
    secret_key: str = "change-me"
    access_token_ttl_minutes: int = 60
    refresh_token_ttl_minutes: int = 60 * 24 * 3
    storage_path: str = "storage"
    bootstrap_admin_email: str | None = None
    bootstrap_admin_password: str | None = None
    bootstrap_admin_full_name: str = "System Administrator"
    celery_task_always_eager: bool = False
    embedding_provider: str = "hash"
    embedding_model_name: str | None = None
    embedding_model_path: str | None = None
    llm_provider: str = "fallback"
    local_llm_model_path: str | None = None
    local_llm_model_name: str | None = None
    local_llm_task: str = "text2text-generation"
    local_llm_max_input_chars: int = 4000
    local_llm_summary_max_new_tokens: int = 96
    local_llm_section_max_new_tokens: int = 256
    ocr_provider: str = "disabled"
    ocr_languages: str = "rus+eng"
    tesseract_cmd: str | None = None
    external_integrations_csv: str = ""
    esign_provider: str = "disabled"
    ollama_base_url: str = "http://localhost:11434/api"
    ollama_embedding_model: str = "all-minilm"
    ollama_llm_model: str = "gemma3:270m"
    ollama_request_timeout_seconds: float = 15.0
    ollama_keep_alive: str = "15m"
    embedding_size: int = 32
    allowed_origins: list[str] = Field(
        default_factory=lambda: ["http://localhost:5173", "http://127.0.0.1:5173", "http://localhost:8000"]
    )


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
