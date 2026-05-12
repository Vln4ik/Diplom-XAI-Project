from __future__ import annotations

from dataclasses import dataclass

from app.models import ApplicabilityStatus
from app.services import analysis
from app.services.retrieval import RankedFragment


@dataclass
class FragmentStub:
    id: str
    document_id: str
    fragment_text: str
    embedding_vector: object | None = None


def test_select_requirement_fragments_deduplicates_by_signature():
    fragments = [
        FragmentStub(
            id="fragment-1",
            document_id="doc-1",
            fragment_text="На официальном сайте требуется опубликовать локальные нормативные акты организации.",
        ),
        FragmentStub(
            id="fragment-2",
            document_id="doc-1",
            fragment_text="Организация должна разместить локальные нормативные акты на официальном сайте.",
        ),
        FragmentStub(
            id="fragment-3",
            document_id="doc-2",
            fragment_text="Необходимо предоставить сведения о кадровом составе педагогических работников.",
        ),
    ]

    selected = analysis.select_requirement_fragments(fragments, limit=10)  # type: ignore[arg-type]

    assert len(selected) == 2
    assert {fragment.id for fragment in selected} == {"fragment-1", "fragment-3"}


def test_rank_evidence_candidates_prefers_diverse_documents(monkeypatch):
    fragments = [
        FragmentStub(
            id="fragment-1",
            document_id="doc-1",
            fragment_text="На официальном сайте опубликованы локальные нормативные акты и лицензия организации.",
        ),
        FragmentStub(
            id="fragment-2",
            document_id="doc-1",
            fragment_text="Копия лицензии и локальные нормативные акты размещены на официальном сайте учреждения.",
        ),
        FragmentStub(
            id="fragment-3",
            document_id="doc-2",
            fragment_text="Сведения о лицензии и локальных актах доступны в открытом разделе сайта колледжа.",
        ),
    ]

    monkeypatch.setattr(
        analysis,
        "rank_fragments",
        lambda db, **kwargs: [
            RankedFragment(fragment=fragments[0], score=0.92, keyword_score=0.84, vector_score=0.85),
            RankedFragment(fragment=fragments[1], score=0.9, keyword_score=0.82, vector_score=0.83),
            RankedFragment(fragment=fragments[2], score=0.81, keyword_score=0.75, vector_score=0.76),
        ],
    )

    ranked = analysis.rank_evidence_candidates(
        db=None,  # type: ignore[arg-type]
        requirement_text="Организация должна разместить локальные нормативные акты и сведения о лицензии на официальном сайте.",
        fragments=fragments,  # type: ignore[arg-type]
        category="Официальный сайт",
        limit=2,
    )

    assert len(ranked) == 2
    assert {fragment.document_id for fragment, _score in ranked} == {"doc-1", "doc-2"}
    assert any(fragment.id == "fragment-3" for fragment, _score in ranked)


def test_derive_requirement_confidence_penalizes_weak_single_source():
    requirement_text = "Организация должна разместить сведения о лицензии и локальных нормативных актах на официальном сайте."
    strong_evidence = [
        (
            FragmentStub(
                id="fragment-1",
                document_id="doc-1",
                fragment_text="На официальном сайте размещены сведения о лицензии организации.",
            ),
            0.87,
        ),
        (
            FragmentStub(
                id="fragment-2",
                document_id="doc-2",
                fragment_text="Локальные нормативные акты опубликованы на официальном сайте образовательной организации.",
            ),
            0.82,
        ),
    ]
    weak_evidence = [
        (
            FragmentStub(
                id="fragment-3",
                document_id="doc-3",
                fragment_text="В документе упоминается лицензия организации.",
            ),
            0.39,
        )
    ]

    strong_confidence = analysis.derive_requirement_confidence(
        ApplicabilityStatus.applicable,
        requirement_text,
        strong_evidence,  # type: ignore[arg-type]
    )
    weak_confidence = analysis.derive_requirement_confidence(
        ApplicabilityStatus.applicable,
        requirement_text,
        weak_evidence,  # type: ignore[arg-type]
    )

    assert strong_confidence > weak_confidence
    assert strong_confidence >= 0.7
    assert weak_confidence <= 0.55


def test_rank_evidence_candidates_filters_hint_only_structural_fragments(monkeypatch):
    fragments = [
        FragmentStub(
            id="fragment-1",
            document_id="doc-1",
            fragment_text='На официальном сайте организации размещены сведения о лицензии на образовательную деятельность.',
        ),
        FragmentStub(
            id="fragment-2",
            document_id="doc-2",
            fragment_text='"regulatory_scope": [',
        ),
        FragmentStub(
            id="fragment-3",
            document_id="doc-2",
            fragment_text='"Лицензирование",',
        ),
        FragmentStub(
            id="fragment-4",
            document_id="doc-3",
            fragment_text='"Государственная аккредитация"',
        ),
    ]

    monkeypatch.setattr(
        analysis,
        "rank_fragments",
        lambda db, **kwargs: [
            RankedFragment(fragment=fragments[1], score=0.88, keyword_score=0.7, vector_score=0.72),
            RankedFragment(fragment=fragments[0], score=0.84, keyword_score=0.8, vector_score=0.81),
            RankedFragment(fragment=fragments[2], score=0.78, keyword_score=0.66, vector_score=0.69),
            RankedFragment(fragment=fragments[3], score=0.76, keyword_score=0.65, vector_score=0.68),
        ],
    )

    ranked = analysis.rank_evidence_candidates(
        db=None,  # type: ignore[arg-type]
        requirement_text="Необходимо предоставить сведения о лицензии, аккредитации и кадровом составе.",
        fragments=fragments,  # type: ignore[arg-type]
        category="Лицензия и аккредитация",
        limit=3,
    )

    ids = {fragment.id for fragment, _score in ranked}
    assert "fragment-1" in ids
    assert "fragment-4" in ids
    assert "fragment-2" not in ids
