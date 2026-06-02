from __future__ import annotations

from app.embeddings.local import HashEmbeddingProvider


def test_hash_embedding_provider_is_stable_across_instances():
    text = "EvidenceXAI проверяет комплект документов и строит XAI-объяснение."

    first = HashEmbeddingProvider(vector_size=32).embed_text(text)
    second = HashEmbeddingProvider(vector_size=32).embed_text(text)

    assert first == second
    assert sum(abs(value) for value in first) > 0
