from __future__ import annotations

from app.embeddings.base import adapt_vector
from app.embeddings.local import OllamaEmbeddingProvider
from app.integrations.ollama import has_model
from app.llm.local import OllamaLLMProvider


def test_ai_status_endpoint(client):
    test_client, _session_factory = client

    response = test_client.get("/api/system/ai-status")

    assert response.status_code == 200
    payload = response.json()
    assert "embeddings" in payload
    assert "llm" in payload
    assert "provider" in payload["embeddings"]
    assert "provider" in payload["llm"]


def test_adapt_vector_resizes_and_normalizes():
    vector = adapt_vector([1.0, 2.0, 3.0, 4.0], 2)

    assert len(vector) == 2
    assert round(sum(value * value for value in vector), 6) == 1.0


def test_ollama_embedding_provider_uses_remote_vectors(monkeypatch):
    monkeypatch.setattr(
        "app.embeddings.local.request_json",
        lambda **kwargs: {"embeddings": [[0.5] * 32]},
    )
    monkeypatch.setattr("app.embeddings.local.list_models", lambda *_args, **_kwargs: ["all-minilm"])

    provider = OllamaEmbeddingProvider()
    vector = provider.embed_text("Тестовая строка")

    assert len(vector) == 32
    assert provider.status()["mode"] == "model"


def test_ollama_model_match_accepts_latest_suffix():
    assert has_model(["all-minilm:latest"], "all-minilm")
    assert has_model(["gemma3:270m"], "gemma3:270m")
    assert not has_model(["all-minilm:latest"], "gemma3:270m")


def test_ollama_llm_provider_uses_remote_generation(monkeypatch):
    monkeypatch.setattr(
        "app.llm.local.request_json",
        lambda **kwargs: {"response": "Сгенерированный раздел"},
    )
    provider = OllamaLLMProvider()
    monkeypatch.setattr("app.llm.local.list_models", lambda *_args, **_kwargs: [provider.model_name])
    generated = provider.generate_section("Риски", "Контекст")

    assert generated == "Сгенерированный раздел"
    assert provider.status()["mode"] == "model"
