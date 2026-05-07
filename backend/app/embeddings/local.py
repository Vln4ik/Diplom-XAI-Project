from __future__ import annotations

import re
from collections import Counter
from collections.abc import Sequence
from functools import lru_cache

from app.core.config import get_settings
from app.embeddings.base import EmbeddingProvider, adapt_vector, normalize_vector
from app.integrations.ollama import OllamaError, has_model, list_models, request_json

TOKEN_RE = re.compile(r"[A-Za-zА-Яа-я0-9_]+")


def _tokenize(text: str) -> list[str]:
    return [token.lower() for token in TOKEN_RE.findall(text)]


class HashEmbeddingProvider(EmbeddingProvider):
    def __init__(self, vector_size: int) -> None:
        self.vector_size = vector_size

    @property
    def provider_name(self) -> str:
        return "hash-fallback"

    def embed_text(self, text: str) -> list[float]:
        bucket = [0.0] * self.vector_size
        for token, count in Counter(_tokenize(text)).items():
            bucket[hash(token) % self.vector_size] += float(count)
        return normalize_vector(bucket)

    def status(self) -> dict[str, object]:
        return {
            "provider": self.provider_name,
            "vector_size": self.vector_size,
            "mode": "fallback",
        }


class SentenceTransformersEmbeddingProvider(EmbeddingProvider):
    def __init__(self) -> None:
        settings = get_settings()
        self.provider = settings.embedding_provider.lower()
        self.target_vector_size = settings.embedding_size
        self.model_name = settings.embedding_model_name
        self.model_path = settings.embedding_model_path
        self._fallback = HashEmbeddingProvider(settings.embedding_size)
        self._encoder = None
        self._load_attempted = False
        self._load_error: str | None = None
        self._raw_vector_size: int | None = None

    @property
    def provider_name(self) -> str:
        return "sentence-transformers"

    def _is_enabled(self) -> bool:
        return self.provider in {"local", "sentence_transformers", "sentence-transformers"}

    def _model_source(self) -> str | None:
        return self.model_path or self.model_name

    def _ensure_encoder(self):
        if not self._is_enabled():
            return None
        if self._encoder is not None:
            return self._encoder
        if self._load_attempted:
            return None

        self._load_attempted = True
        source = self._model_source()
        if not source:
            self._load_error = "Embedding model is not configured."
            return None

        try:
            from sentence_transformers import SentenceTransformer
        except Exception as exc:  # pragma: no cover - depends on optional runtime package
            self._load_error = f"sentence-transformers is unavailable: {exc}"
            return None

        try:
            self._encoder = SentenceTransformer(source)
            self._raw_vector_size = int(self._encoder.get_sentence_embedding_dimension() or 0) or None
        except Exception as exc:  # pragma: no cover - depends on model availability
            self._load_error = str(exc)
            self._encoder = None
        return self._encoder

    def _adapt(self, values: Sequence[float]) -> list[float]:
        return adapt_vector(values, self.target_vector_size)

    def embed_many(self, texts: Sequence[str]) -> list[list[float]]:
        encoder = self._ensure_encoder()
        if encoder is None:
            return self._fallback.embed_many(texts)

        try:
            raw_vectors = encoder.encode(list(texts), show_progress_bar=False, normalize_embeddings=False)
        except Exception:  # pragma: no cover - depends on model runtime
            return self._fallback.embed_many(texts)

        embedded: list[list[float]] = []
        for values in raw_vectors:
            if hasattr(values, "tolist"):
                embedded.append(self._adapt(values.tolist()))
            else:
                embedded.append(self._adapt(list(values)))
        return embedded

    def embed_text(self, text: str) -> list[float]:
        return self.embed_many([text])[0]

    def status(self) -> dict[str, object]:
        mode = "model" if self._encoder is not None else "fallback"
        return {
            "provider": self.provider_name,
            "configured_provider": self.provider,
            "configured_model": self._model_source(),
            "vector_size": self.target_vector_size,
            "raw_vector_size": self._raw_vector_size,
            "load_attempted": self._load_attempted,
            "loaded": self._encoder is not None,
            "mode": mode,
            "fallback_provider": self._fallback.provider_name,
            "load_error": self._load_error,
        }


class OllamaEmbeddingProvider(EmbeddingProvider):
    def __init__(self) -> None:
        settings = get_settings()
        self.base_url = settings.ollama_base_url
        self.model_name = settings.ollama_embedding_model
        self.timeout = settings.ollama_request_timeout_seconds
        self.keep_alive = settings.ollama_keep_alive
        self.target_vector_size = settings.embedding_size
        self._fallback = HashEmbeddingProvider(settings.embedding_size)
        self._last_error: str | None = None

    @property
    def provider_name(self) -> str:
        return "ollama"

    def embed_many(self, texts: Sequence[str]) -> list[list[float]]:
        payload = {
            "model": self.model_name,
            "input": list(texts),
            "truncate": True,
            "dimensions": self.target_vector_size,
            "keep_alive": self.keep_alive,
        }
        try:
            response = request_json(
                method="POST",
                base_url=self.base_url,
                path="/embed",
                timeout=self.timeout,
                payload=payload,
            )
        except OllamaError as exc:
            self._last_error = str(exc)
            return self._fallback.embed_many(texts)

        raw_vectors = response.get("embeddings", [])
        if not isinstance(raw_vectors, list) or len(raw_vectors) != len(texts):
            self._last_error = "Ollama returned invalid embeddings payload."
            return self._fallback.embed_many(texts)

        vectors: list[list[float]] = []
        for values in raw_vectors:
            if not isinstance(values, list):
                self._last_error = "Ollama returned non-list embedding vector."
                return self._fallback.embed_many(texts)
            vectors.append(adapt_vector(values, self.target_vector_size))
        self._last_error = None
        return vectors

    def embed_text(self, text: str) -> list[float]:
        return self.embed_many([text])[0]

    def status(self) -> dict[str, object]:
        available_models: list[str] | None = None
        reachable = False
        check_error: str | None = None
        try:
            available_models = list_models(self.base_url, self.timeout)
            reachable = True
        except OllamaError as exc:
            check_error = str(exc)
        model_available = has_model(available_models, self.model_name)

        return {
            "provider": self.provider_name,
            "configured_model": self.model_name,
            "base_url": self.base_url,
            "vector_size": self.target_vector_size,
            "reachable": reachable,
            "model_available": model_available,
            "available_models": available_models,
            "mode": "model" if reachable and model_available else "fallback",
            "fallback_provider": self._fallback.provider_name,
            "load_error": self._last_error or check_error,
        }


@lru_cache(maxsize=1)
def get_embedding_provider() -> EmbeddingProvider:
    settings = get_settings()
    provider = settings.embedding_provider.lower()
    if provider == "ollama":
        return OllamaEmbeddingProvider()
    if provider in {"local", "sentence_transformers", "sentence-transformers"}:
        return SentenceTransformersEmbeddingProvider()
    return HashEmbeddingProvider(settings.embedding_size)


def describe_embedding_provider() -> dict[str, object]:
    return get_embedding_provider().status()
