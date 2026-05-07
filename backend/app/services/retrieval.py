from __future__ import annotations

import math
import re
from collections.abc import Callable, Sequence
from dataclasses import dataclass

from sqlalchemy import case, func, select
from sqlalchemy.orm import Session

from app.embeddings.local import get_embedding_provider
from app.models import DocumentFragment

TOKEN_RE = re.compile(r"[A-Za-zА-Яа-я0-9_]+")


@dataclass
class RankedFragment:
    fragment: DocumentFragment
    score: float
    keyword_score: float
    vector_score: float


@dataclass
class PostgresCandidateScore:
    keyword_score: float
    vector_score: float


def tokenize(text: str) -> list[str]:
    return [token.lower() for token in TOKEN_RE.findall(text)]


def compute_embedding(text: str) -> list[float]:
    return get_embedding_provider().embed_text(text)


def keyword_overlap_score(left: str, right: str) -> float:
    left_tokens = set(tokenize(left))
    right_tokens = set(tokenize(right))
    if not left_tokens or not right_tokens:
        return 0.0
    return len(left_tokens & right_tokens) / len(left_tokens | right_tokens)


def cosine_similarity(left: Sequence[float] | None, right: Sequence[float] | None) -> float:
    if left is None or right is None:
        return 0.0
    if len(left) == 0 or len(right) == 0 or len(left) != len(right):
        return 0.0
    numerator = sum(float(left_value) * float(right_value) for left_value, right_value in zip(left, right, strict=True))
    left_norm = math.sqrt(sum(float(value) * float(value) for value in left))
    right_norm = math.sqrt(sum(float(value) * float(value) for value in right))
    if left_norm == 0 or right_norm == 0:
        return 0.0
    return max(0.0, min(1.0, numerator / (left_norm * right_norm)))


def _normalize_ts_rank(value: float | None) -> float:
    if value is None:
        return 0.0
    normalized = 1.0 - math.exp(-4.0 * max(0.0, float(value)))
    return round(max(0.0, min(1.0, normalized)), 4)


def _distance_to_similarity(value: float | None) -> float:
    if value is None:
        return 0.0
    return round(max(0.0, min(1.0, 1.0 - float(value))), 4)


def _resolve_postgres_candidate_scores(
    db: Session,
    fragments: Sequence[DocumentFragment],
    query_text: str,
    query_embedding: list[float],
    limit: int,
) -> dict[str, PostgresCandidateScore]:
    bind = db.get_bind()
    if bind is None or bind.dialect.name != "postgresql":
        return {}

    fragment_ids = [fragment.id for fragment in fragments]
    if not fragment_ids:
        return {}

    candidate_limit = min(len(fragment_ids), max(limit * 8, 40))
    fragment_table = DocumentFragment.__table__
    search_vector = func.to_tsvector("russian", fragment_table.c.search_text)
    ts_query = func.plainto_tsquery("russian", query_text)
    keyword_match = search_vector.op("@@")(ts_query)
    keyword_rank = func.ts_rank_cd(search_vector, ts_query).label("keyword_rank")
    vector_distance = case(
        (fragment_table.c.embedding_vector.isnot(None), fragment_table.c.embedding_vector.cosine_distance(query_embedding)),
        else_=None,
    ).label("vector_distance")
    rows = db.execute(
        select(fragment_table.c.id, keyword_rank, vector_distance)
        .where(fragment_table.c.id.in_(fragment_ids))
        .order_by(
            keyword_match.desc(),
            keyword_rank.desc().nullslast(),
            vector_distance.asc().nullslast(),
            fragment_table.c.created_at.desc(),
        )
        .limit(candidate_limit)
    ).all()
    return {
        fragment_id: PostgresCandidateScore(
            keyword_score=_normalize_ts_rank(raw_keyword_rank),
            vector_score=_distance_to_similarity(raw_vector_distance),
        )
        for fragment_id, raw_keyword_rank, raw_vector_distance in rows
    }


def rank_fragments(
    db: Session,
    *,
    query_text: str,
    fragments: Sequence[DocumentFragment],
    limit: int,
    min_score: float = 0.0,
    max_per_document: int | None = None,
    bonus_resolver: Callable[[DocumentFragment, set[str]], float] | None = None,
) -> list[RankedFragment]:
    if not fragments:
        return []

    query_embedding = compute_embedding(query_text)
    query_tokens = set(tokenize(query_text))
    postgres_scores = _resolve_postgres_candidate_scores(db, fragments, query_text, query_embedding, limit)
    candidate_fragments = fragments
    if postgres_scores:
        candidate_ids = set(postgres_scores)
        candidate_fragments = [fragment for fragment in fragments if fragment.id in candidate_ids]

    ranked: list[RankedFragment] = []
    for fragment in candidate_fragments:
        python_keyword_score = round(keyword_overlap_score(query_text, fragment.fragment_text), 4)
        postgres_score = postgres_scores.get(fragment.id)
        keyword_score = round(max(python_keyword_score, postgres_score.keyword_score if postgres_score else 0.0), 4)
        vector_score = (
            postgres_score.vector_score
            if postgres_score is not None
            else round(cosine_similarity(query_embedding, fragment.embedding_vector), 4)
        )
        bonus = bonus_resolver(fragment, query_tokens) if bonus_resolver is not None else 0.0
        total_score = round(min(0.99, 0.56 * keyword_score + 0.34 * vector_score + bonus), 4)
        if total_score < min_score:
            continue
        ranked.append(
            RankedFragment(
                fragment=fragment,
                score=total_score,
                keyword_score=keyword_score,
                vector_score=vector_score,
            )
        )

    ranked.sort(key=lambda item: (item.score, item.keyword_score, item.vector_score), reverse=True)

    if max_per_document is None:
        return ranked[:limit]

    selected: list[RankedFragment] = []
    per_document_count: dict[str | None, int] = {}
    for item in ranked:
        document_count = per_document_count.get(item.fragment.document_id, 0)
        if document_count >= max_per_document:
            continue
        selected.append(item)
        per_document_count[item.fragment.document_id] = document_count + 1
        if len(selected) >= limit:
            break
    return selected
