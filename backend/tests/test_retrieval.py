from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from app.services import retrieval
from app.services.retrieval import PostgresCandidateScore


@dataclass
class FragmentStub:
    id: str
    document_id: str
    fragment_text: str
    embedding_vector: object


def test_rank_fragments_uses_pgvector_score_without_eager_fallback(monkeypatch):
    fragments = [
        FragmentStub(
            id="fragment-1",
            document_id="doc-1",
            fragment_text="Требование о лицензии и локальных актах",
            embedding_vector=np.array([0.1, 0.2, 0.3]),
        )
    ]

    monkeypatch.setattr(
        retrieval,
        "_resolve_postgres_candidate_scores",
        lambda db, fragments, query_text, query_embedding, limit: {
            "fragment-1": PostgresCandidateScore(keyword_score=0.41, vector_score=0.77)
        },
    )

    ranked = retrieval.rank_fragments(
        db=None,  # type: ignore[arg-type]
        query_text="лицензия локальные акты",
        fragments=fragments,  # type: ignore[arg-type]
        limit=5,
    )

    assert len(ranked) == 1
    assert ranked[0].keyword_score == 0.41
    assert ranked[0].vector_score == 0.77


def test_rank_fragments_limits_to_postgres_candidates(monkeypatch):
    fragments = [
        FragmentStub(
            id="fragment-1",
            document_id="doc-1",
            fragment_text="Требование о лицензии и локальных актах",
            embedding_vector=np.array([0.1, 0.2, 0.3]),
        ),
        FragmentStub(
            id="fragment-2",
            document_id="doc-2",
            fragment_text="Несвязанный текст без совпадений",
            embedding_vector=np.array([0.3, 0.2, 0.1]),
        ),
    ]

    monkeypatch.setattr(
        retrieval,
        "_resolve_postgres_candidate_scores",
        lambda db, fragments, query_text, query_embedding, limit: {
            "fragment-1": PostgresCandidateScore(keyword_score=0.6, vector_score=0.8)
        },
    )

    ranked = retrieval.rank_fragments(
        db=None,  # type: ignore[arg-type]
        query_text="лицензия локальные акты",
        fragments=fragments,  # type: ignore[arg-type]
        limit=5,
    )

    assert [item.fragment.id for item in ranked] == ["fragment-1"]
