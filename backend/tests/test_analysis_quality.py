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
    selected_ids = {fragment.id for fragment in selected}
    assert "fragment-3" in selected_ids
    assert len({"fragment-1", "fragment-2"} & selected_ids) == 1


def test_select_requirement_fragments_supports_gendered_obligation_markers():
    fragments = [
        FragmentStub(
            id="fragment-1",
            document_id="doc-1",
            fragment_text="Организация должна раскрывать сведения о педагогических работниках.",
        ),
        FragmentStub(
            id="fragment-2",
            document_id="doc-2",
            fragment_text="Сведения о педагогических работниках размещены на официальном сайте.",
        ),
    ]

    selected = analysis.select_requirement_fragments(fragments, limit=10)  # type: ignore[arg-type]

    assert len(selected) == 1
    assert selected[0].id == "fragment-1"


def test_applicability_for_report_accepts_pedagogical_staff_requirement_for_educational_scope():
    applicability, reason = analysis.applicability_for_report(
        "Организация должна раскрывать сведения о педагогических работниках.",
        {"organization_type": "educational"},
        "readiness_report",
    )

    assert applicability == ApplicabilityStatus.applicable
    assert "образовательному сценарию" in reason


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
    assert "fragment-3" not in ids


def test_rank_evidence_candidates_prefers_focus_evidence_over_generic_site_overlap(monkeypatch):
    fragments = [
        FragmentStub(
            id="fragment-1",
            document_id="doc-1",
            fragment_text='В разделе "Сведения об образовательной организации" опубликованы локальные нормативные акты.',
        ),
        FragmentStub(
            id="fragment-2",
            document_id="doc-2",
            fragment_text="website_sections_published | 2026 | 12",
        ),
        FragmentStub(
            id="fragment-3",
            document_id="doc-3",
            fragment_text="На официальном сайте организации размещены сведения о лицензии на образовательную деятельность.",
        ),
    ]

    monkeypatch.setattr(
        analysis,
        "rank_fragments",
        lambda db, **kwargs: [
            RankedFragment(fragment=fragments[2], score=0.9, keyword_score=0.84, vector_score=0.86),
            RankedFragment(fragment=fragments[0], score=0.81, keyword_score=0.76, vector_score=0.79),
            RankedFragment(fragment=fragments[1], score=0.72, keyword_score=0.61, vector_score=0.63),
        ],
    )

    ranked = analysis.rank_evidence_candidates(
        db=None,  # type: ignore[arg-type]
        requirement_text="На официальном сайте требуется опубликовать локальные нормативные акты и сведения о контингенте.",
        fragments=fragments,  # type: ignore[arg-type]
        category="Официальный сайт",
        limit=2,
    )

    ids = [fragment.id for fragment, _score in ranked]
    assert ids == ["fragment-1", "fragment-2"]
    assert "fragment-3" not in ids


def test_rank_evidence_candidates_prefers_local_acts_structured_row_over_generic_site_registry(monkeypatch):
    fragments = [
        FragmentStub(
            id="fragment-1",
            document_id="doc-1",
            fragment_text='В разделе "Сведения об образовательной организации" размещены локальные нормативные акты.',
        ),
        FragmentStub(
            id="fragment-2",
            document_id="doc-2",
            fragment_text="website_sections_published | 2026 | 16",
        ),
        FragmentStub(
            id="fragment-3",
            document_id="doc-2",
            fragment_text="local_acts_published | 2026 | 21",
        ),
    ]

    monkeypatch.setattr(
        analysis,
        "rank_fragments",
        lambda db, **kwargs: [
            RankedFragment(fragment=fragments[0], score=0.88, keyword_score=0.8, vector_score=0.82),
            RankedFragment(fragment=fragments[1], score=0.84, keyword_score=0.73, vector_score=0.75),
            RankedFragment(fragment=fragments[2], score=0.83, keyword_score=0.72, vector_score=0.74),
        ],
    )

    ranked = analysis.rank_evidence_candidates(
        db=None,  # type: ignore[arg-type]
        requirement_text="На официальном сайте требуется опубликовать локальные нормативные акты.",
        fragments=fragments,  # type: ignore[arg-type]
        category="Официальный сайт",
        limit=2,
    )

    ids = [fragment.id for fragment, _score in ranked]
    assert ids == ["fragment-1", "fragment-3"]
    assert "fragment-2" not in ids


def test_rank_evidence_candidates_prefers_human_readable_accreditation_value_over_boolean_flag(monkeypatch):
    fragments = [
        FragmentStub(
            id="fragment-1",
            document_id="doc-1",
            fragment_text="Кадровый состав и сведения о реализуемых образовательных программах доступны в открытом доступе.",
        ),
        FragmentStub(
            id="fragment-2",
            document_id="doc-2",
            fragment_text='На официальном сайте организации размещены сведения о лицензии на образовательную деятельность.',
        ),
        FragmentStub(
            id="fragment-3",
            document_id="doc-3",
            fragment_text='"has_accreditation": true',
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
            RankedFragment(fragment=fragments[0], score=0.87, keyword_score=0.78, vector_score=0.8),
            RankedFragment(fragment=fragments[2], score=0.84, keyword_score=0.72, vector_score=0.74),
            RankedFragment(fragment=fragments[1], score=0.82, keyword_score=0.76, vector_score=0.77),
            RankedFragment(fragment=fragments[3], score=0.76, keyword_score=0.67, vector_score=0.69),
        ],
    )

    ranked = analysis.rank_evidence_candidates(
        db=None,  # type: ignore[arg-type]
        requirement_text="Необходимо предоставить сведения о лицензии, аккредитации и кадровом составе.",
        fragments=fragments,  # type: ignore[arg-type]
        category="Лицензия и аккредитация",
        limit=3,
    )

    ids = [fragment.id for fragment, _score in ranked]
    assert "fragment-1" in ids
    assert "fragment-2" in ids
    assert "fragment-4" in ids
    assert "fragment-3" not in ids


def test_rank_evidence_candidates_trims_redundant_program_supporting_tail(monkeypatch):
    fragments = [
        FragmentStub(
            id="fragment-1",
            document_id="doc-1",
            fragment_text="Кадровый состав и сведения о реализуемых образовательных программах доступны в открытом доступе.",
        ),
        FragmentStub(
            id="fragment-2",
            document_id="doc-2",
            fragment_text='"Информационные системы и программирование",',
        ),
        FragmentStub(
            id="fragment-3",
            document_id="doc-3",
            fragment_text="licensed_programs | 2026 | 2",
        ),
    ]

    monkeypatch.setattr(
        analysis,
        "rank_fragments",
        lambda db, **kwargs: [
            RankedFragment(fragment=fragments[0], score=0.9, keyword_score=0.82, vector_score=0.84),
            RankedFragment(fragment=fragments[2], score=0.81, keyword_score=0.71, vector_score=0.73),
            RankedFragment(fragment=fragments[1], score=0.79, keyword_score=0.68, vector_score=0.7),
        ],
    )

    ranked = analysis.rank_evidence_candidates(
        db=None,  # type: ignore[arg-type]
        requirement_text="Организация должна разместить сведения о реализуемых образовательных программах.",
        fragments=fragments,  # type: ignore[arg-type]
        category="Образовательные программы",
        limit=3,
    )

    ids = [fragment.id for fragment, _score in ranked]
    assert ids == ["fragment-1"]


def test_rank_evidence_candidates_prefers_specific_license_fragments_over_mixed_ocr_sentence(monkeypatch):
    fragments = [
        FragmentStub(
            id="fragment-1",
            document_id="doc-1",
            fragment_text="На официальном сайте организации размещены сведения о лицензии на образовательную деятельность.",
        ),
        FragmentStub(
            id="fragment-2",
            document_id="doc-2",
            fragment_text="Кадровый состав и сведения о реализуемых образовательных программах доступны в открытом доступе.",
        ),
        FragmentStub(
            id="fragment-3",
            document_id="doc-3",
            fragment_text='"Государственная аккредитация"',
        ),
        FragmentStub(
            id="fragment-4",
            document_id="doc-4",
            fragment_text="Лицензия и аккредитация размещены на сайте. Teachers total: 48. Локальные акты опубликованы.",
        ),
    ]

    monkeypatch.setattr(
        analysis,
        "rank_fragments",
        lambda db, **kwargs: [
            RankedFragment(fragment=fragments[3], score=0.91, keyword_score=0.84, vector_score=0.86),
            RankedFragment(fragment=fragments[0], score=0.84, keyword_score=0.79, vector_score=0.81),
            RankedFragment(fragment=fragments[1], score=0.83, keyword_score=0.77, vector_score=0.79),
            RankedFragment(fragment=fragments[2], score=0.8, keyword_score=0.71, vector_score=0.72),
        ],
    )

    ranked = analysis.rank_evidence_candidates(
        db=None,  # type: ignore[arg-type]
        requirement_text="Необходимо предоставить сведения о лицензии, аккредитации и кадровом составе.",
        fragments=fragments,  # type: ignore[arg-type]
        category="Лицензия и аккредитация",
        limit=3,
    )

    ids = [fragment.id for fragment, _score in ranked]
    assert set(ids) == {"fragment-1", "fragment-2", "fragment-3"}
    assert "fragment-4" not in ids


def test_rank_evidence_candidates_drops_redundant_accreditation_quote_when_narratives_cover_focus(monkeypatch):
    fragments = [
        FragmentStub(
            id="fragment-1",
            document_id="doc-1",
            fragment_text="Размещены сведения о лицензии на образовательную деятельность и государственной аккредитации.",
        ),
        FragmentStub(
            id="fragment-2",
            document_id="doc-2",
            fragment_text='"Государственная аккредитация",',
        ),
        FragmentStub(
            id="fragment-3",
            document_id="doc-3",
            fragment_text="Сведения о педагогических работниках размещены на официальном сайте.",
        ),
    ]

    monkeypatch.setattr(
        analysis,
        "rank_fragments",
        lambda db, **kwargs: [
            RankedFragment(fragment=fragments[1], score=0.92, keyword_score=0.85, vector_score=0.86),
            RankedFragment(fragment=fragments[0], score=0.89, keyword_score=0.84, vector_score=0.85),
            RankedFragment(fragment=fragments[2], score=0.83, keyword_score=0.77, vector_score=0.78),
        ],
    )

    ranked = analysis.rank_evidence_candidates(
        db=None,  # type: ignore[arg-type]
        requirement_text="Необходимо предоставить сведения о лицензии, государственной аккредитации и педагогических работниках.",
        fragments=fragments,  # type: ignore[arg-type]
        category="Лицензия и аккредитация",
        limit=3,
    )

    ids = [fragment.id for fragment, _score in ranked]
    assert ids == ["fragment-1", "fragment-3"]


def test_rank_evidence_candidates_keeps_accreditation_quote_when_it_adds_uncovered_focus(monkeypatch):
    fragments = [
        FragmentStub(
            id="fragment-1",
            document_id="doc-1",
            fragment_text="Официальный сайт содержит сведения о лицензии и кадрах. Teachers total: 48.",
        ),
        FragmentStub(
            id="fragment-2",
            document_id="doc-2",
            fragment_text='"Государственная аккредитация"',
        ),
    ]

    monkeypatch.setattr(
        analysis,
        "rank_fragments",
        lambda db, **kwargs: [
            RankedFragment(fragment=fragments[1], score=0.88, keyword_score=0.79, vector_score=0.8),
            RankedFragment(fragment=fragments[0], score=0.84, keyword_score=0.76, vector_score=0.77),
        ],
    )

    ranked = analysis.rank_evidence_candidates(
        db=None,  # type: ignore[arg-type]
        requirement_text="Необходимо предоставить сведения о лицензии, государственной аккредитации и кадровом составе.",
        fragments=fragments,  # type: ignore[arg-type]
        category="Лицензия и аккредитация",
        limit=2,
    )

    ids = [fragment.id for fragment, _score in ranked]
    assert ids == ["fragment-2", "fragment-1"] or ids == ["fragment-1", "fragment-2"]


def test_rank_evidence_candidates_supports_program_requirement_inside_merged_ocr_clause(monkeypatch):
    fragments = [
        FragmentStub(
            id="fragment-1",
            document_id="doc-1",
            fragment_text="На сайте размещены локальные нормативные акты. Программы обучения опубликованы. 2026",
        ),
    ]

    monkeypatch.setattr(
        analysis,
        "rank_fragments",
        lambda db, **kwargs: [
            RankedFragment(fragment=fragments[0], score=0.41, keyword_score=0.22, vector_score=0.23),
        ],
    )

    ranked = analysis.rank_evidence_candidates(
        db=None,  # type: ignore[arg-type]
        requirement_text="Организация должна разместить сведения о реализуемых образовательных программах.",
        fragments=fragments,  # type: ignore[arg-type]
        category="Образовательные программы",
        limit=1,
    )

    assert len(ranked) == 1
    assert ranked[0][1] >= 0.42

    confidence = analysis.derive_requirement_confidence(
        ApplicabilityStatus.applicable,
        "Организация должна разместить сведения о реализуемых образовательных программах.",
        ranked,  # type: ignore[arg-type]
    )

    assert confidence >= analysis.data_found_confidence_threshold()


def test_rank_evidence_candidates_drops_generic_site_registry_when_specific_local_acts_evidence_exists(monkeypatch):
    fragments = [
        FragmentStub(
            id="fragment-1",
            document_id="doc-1",
            fragment_text='В разделе "Сведения об образовательной организации" опубликованы локальные нормативные акты и правила приема.',
        ),
        FragmentStub(
            id="fragment-2",
            document_id="doc-2",
            fragment_text="local_acts_published | 2026 | 24",
        ),
        FragmentStub(
            id="fragment-3",
            document_id="doc-3",
            fragment_text="website_sections_published | 2026 | 18",
        ),
    ]

    monkeypatch.setattr(
        analysis,
        "rank_fragments",
        lambda db, **kwargs: [
            RankedFragment(fragment=fragments[2], score=0.91, keyword_score=0.73, vector_score=0.74),
            RankedFragment(fragment=fragments[1], score=0.87, keyword_score=0.75, vector_score=0.76),
            RankedFragment(fragment=fragments[0], score=0.84, keyword_score=0.82, vector_score=0.83),
        ],
    )

    ranked = analysis.rank_evidence_candidates(
        db=None,  # type: ignore[arg-type]
        requirement_text="На официальном сайте требуется опубликовать локальные нормативные акты и правила приема.",
        fragments=fragments,  # type: ignore[arg-type]
        category="Официальный сайт",
        limit=3,
    )

    ids = [fragment.id for fragment, _score in ranked]
    assert ids == ["fragment-1", "fragment-2"]


def test_rank_evidence_candidates_drops_program_like_quote_for_staff_requirement(monkeypatch):
    fragments = [
        FragmentStub(
            id="fragment-1",
            document_id="doc-1",
            fragment_text="Сведения о педагогических работниках размещены на официальном сайте.",
        ),
        FragmentStub(
            id="fragment-2",
            document_id="doc-2",
            fragment_text='"Педагогика дополнительного образования"',
        ),
        FragmentStub(
            id="fragment-3",
            document_id="doc-3",
            fragment_text="teachers_total | 2026 | 84",
        ),
    ]

    monkeypatch.setattr(
        analysis,
        "rank_fragments",
        lambda db, **kwargs: [
            RankedFragment(fragment=fragments[1], score=0.89, keyword_score=0.76, vector_score=0.77),
            RankedFragment(fragment=fragments[0], score=0.85, keyword_score=0.8, vector_score=0.81),
            RankedFragment(fragment=fragments[2], score=0.78, keyword_score=0.64, vector_score=0.65),
        ],
    )

    ranked = analysis.rank_evidence_candidates(
        db=None,  # type: ignore[arg-type]
        requirement_text="Организация должна раскрывать сведения о педагогических работниках.",
        fragments=fragments,  # type: ignore[arg-type]
        category="Кадровое обеспечение",
        limit=3,
    )

    ids = [fragment.id for fragment, _score in ranked]
    assert ids == ["fragment-1", "fragment-3"]


def test_rank_evidence_candidates_drops_secondary_licensed_programs_hint_for_license_requirement(monkeypatch):
    fragments = [
        FragmentStub(
            id="fragment-1",
            document_id="doc-1",
            fragment_text="На официальном сайте организации размещены сведения о лицензии на образовательную деятельность.",
        ),
        FragmentStub(
            id="fragment-2",
            document_id="doc-2",
            fragment_text='"Государственная аккредитация"',
        ),
        FragmentStub(
            id="fragment-3",
            document_id="doc-3",
            fragment_text="licensed_programs | 2026 | 2",
        ),
    ]

    monkeypatch.setattr(
        analysis,
        "rank_fragments",
        lambda db, **kwargs: [
            RankedFragment(fragment=fragments[0], score=0.87, keyword_score=0.8, vector_score=0.81),
            RankedFragment(fragment=fragments[2], score=0.83, keyword_score=0.7, vector_score=0.72),
            RankedFragment(fragment=fragments[1], score=0.79, keyword_score=0.69, vector_score=0.7),
        ],
    )

    ranked = analysis.rank_evidence_candidates(
        db=None,  # type: ignore[arg-type]
        requirement_text="Необходимо предоставить сведения о лицензии, аккредитации и кадровом составе.",
        fragments=fragments,  # type: ignore[arg-type]
        category="Лицензия и аккредитация",
        limit=3,
    )

    ids = [fragment.id for fragment, _score in ranked]
    assert ids == ["fragment-1", "fragment-2"]
