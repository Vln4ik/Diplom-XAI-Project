from __future__ import annotations

from sqlalchemy.orm import Session

from app.models import ApplicabilityStatus, DocumentFragment
from app.services.retrieval import keyword_overlap_score, rank_fragments, tokenize

REQUIREMENT_MARKERS = ("должен", "обязан", "требуется", "необходимо", "предоставить", "разместить")
STOPWORDS = {
    "будет",
    "быть",
    "должен",
    "должна",
    "должны",
    "если",
    "или",
    "для",
    "его",
    "ее",
    "это",
    "при",
    "надо",
    "нужно",
    "обязан",
    "обязана",
    "обязаны",
    "организация",
    "отчет",
    "сведения",
    "также",
    "требуется",
    "требование",
    "необходимо",
}
CATEGORY_MARKERS = {
    "Лицензия и аккредитация": {"лиценз", "аккред"},
    "Образовательные программы": {"программ", "учебн", "дисциплин"},
    "Официальный сайт": {"сайт", "размест", "опублик", "страниц"},
    "Кадровое обеспечение": {"кадр", "педагог", "преподав"},
    "Материально-техническая база": {"материаль", "техническ", "оборуд", "аудитор"},
    "Контингент обучающихся": {"континг", "обуча", "студент"},
    "Сведения о выпускниках": {"выпуск", "трудоустр"},
}
HIGH_SIGNAL_TOKENS = {"лиценз", "аккред", "сайт", "кадр", "программ", "локальн", "норматив"}


def unique_significant_tokens(text: str) -> list[str]:
    seen: set[str] = set()
    tokens: list[str] = []
    for token in tokenize(text):
        if len(token) < 4 or token in STOPWORDS:
            continue
        if token in seen:
            continue
        seen.add(token)
        tokens.append(token)
    return tokens


def build_requirement_title(text: str) -> str:
    normalized = " ".join(text.replace("\n", " ").split())
    if not normalized:
        return "Требование без заголовка"
    for separator in (".", ";"):
        if separator in normalized:
            candidate = normalized.split(separator, 1)[0].strip()
            if len(candidate) >= 16:
                return candidate[:180]
    return normalized[:180]


def category_for_text(text: str) -> str:
    lowered = text.lower()
    for category, markers in CATEGORY_MARKERS.items():
        if any(marker in lowered for marker in markers):
            return category
    return "Общие сведения об организации"


def required_data_from_text(text: str) -> list[str]:
    return unique_significant_tokens(text)[:8]


def allowed_source_tokens(organization_profile: dict, report_type: str) -> set[str]:
    allowed = {"образователь", "обуча", "лиценз", "сайт", "кадр", "континг", "выпуск", "программ"}
    profile_text = " ".join(str(value).lower() for value in organization_profile.values() if value)
    if "аккред" in profile_text:
        allowed.add("аккред")
    if "website" in profile_text or "официаль" in profile_text:
        allowed.add("сайт")
    if "readiness" in report_type:
        allowed.update({"разместить", "предоставить"})
    return allowed


def applicability_for_report(
    text: str,
    organization_profile: dict,
    report_type: str,
) -> tuple[ApplicabilityStatus, str]:
    lowered = text.lower()
    matched = [token for token in allowed_source_tokens(organization_profile, report_type) if token in lowered]
    if matched:
        return (
            ApplicabilityStatus.applicable,
            f"Требование относится к образовательному сценарию по признакам: {', '.join(sorted(matched)[:4])}.",
        )
    return ApplicabilityStatus.needs_clarification, "Требуется дополнительная ручная проверка применимости."


def requirement_similarity(left: str, right: str) -> float:
    left_tokens = set(unique_significant_tokens(left))
    right_tokens = set(unique_significant_tokens(right))
    if not left_tokens or not right_tokens:
        return 0.0
    return len(left_tokens & right_tokens) / len(left_tokens | right_tokens)


def select_requirement_fragments(fragments: list[DocumentFragment], *, limit: int = 25) -> list[DocumentFragment]:
    candidates = [fragment for fragment in fragments if any(marker in fragment.fragment_text.lower() for marker in REQUIREMENT_MARKERS)]
    if not candidates:
        candidates = fragments[:10]

    def sort_key(fragment: DocumentFragment) -> tuple[int, int, int]:
        lowered = fragment.fragment_text.lower()
        marker_hits = sum(marker in lowered for marker in REQUIREMENT_MARKERS)
        token_count = len(unique_significant_tokens(fragment.fragment_text))
        return marker_hits, token_count, len(fragment.fragment_text)

    selected: list[DocumentFragment] = []
    selected_texts: list[str] = []
    for fragment in sorted(candidates, key=sort_key, reverse=True):
        if len(unique_significant_tokens(fragment.fragment_text)) < 3:
            continue
        if any(requirement_similarity(fragment.fragment_text, existing) >= 0.82 for existing in selected_texts):
            continue
        selected.append(fragment)
        selected_texts.append(fragment.fragment_text)
        if len(selected) >= limit:
            break

    return selected if selected else candidates[:limit]


def score_evidence_candidate(requirement_text: str, fragment_text: str, category: str) -> float:
    requirement_tokens = set(unique_significant_tokens(requirement_text))
    fragment_tokens = set(unique_significant_tokens(fragment_text))
    if not requirement_tokens or not fragment_tokens:
        return 0.0

    overlap = keyword_overlap_score(requirement_text, fragment_text)
    token_coverage = len(requirement_tokens & fragment_tokens) / len(requirement_tokens)
    category_bonus = 0.08 if CATEGORY_MARKERS.get(category, set()) & fragment_tokens else 0.0
    signal_bonus = 0.08 if HIGH_SIGNAL_TOKENS & fragment_tokens else 0.0
    density_bonus = min(0.08, 0.02 * len(requirement_tokens & fragment_tokens))

    return round(min(0.99, overlap * 0.52 + token_coverage * 0.32 + category_bonus + signal_bonus + density_bonus), 2)


def _evidence_bonus(fragment: DocumentFragment, query_tokens: set[str], category: str) -> float:
    fragment_tokens = set(unique_significant_tokens(fragment.fragment_text))
    if not fragment_tokens:
        return 0.0

    category_bonus = 0.08 if CATEGORY_MARKERS.get(category, set()) & fragment_tokens else 0.0
    signal_bonus = 0.08 if HIGH_SIGNAL_TOKENS & fragment_tokens else 0.0
    density_bonus = min(0.08, 0.02 * len(query_tokens & fragment_tokens))
    return round(category_bonus + signal_bonus + density_bonus, 4)


def rank_evidence_candidates(
    db: Session,
    requirement_text: str,
    fragments: list[DocumentFragment],
    category: str,
    *,
    exclude_fragment_id: str | None = None,
    limit: int = 5,
) -> list[tuple[DocumentFragment, float]]:
    candidates = [fragment for fragment in fragments if fragment.id != exclude_fragment_id]
    ranked = rank_fragments(
        db,
        query_text=requirement_text,
        fragments=candidates,
        limit=limit,
        min_score=0.16,
        max_per_document=2,
        bonus_resolver=lambda fragment, query_tokens: _evidence_bonus(fragment, query_tokens, category),
    )
    return [(item.fragment, round(max(item.score, score_evidence_candidate(requirement_text, item.fragment.fragment_text, category)), 2)) for item in ranked]


def derive_requirement_confidence(
    applicability_status: ApplicabilityStatus,
    ranked_evidence: list[tuple[DocumentFragment, float]],
) -> float:
    if applicability_status == ApplicabilityStatus.not_applicable:
        return 0.9

    evidence_count = len(ranked_evidence)
    average_score = sum(score for _fragment, score in ranked_evidence) / evidence_count if evidence_count else 0.0
    strongest_score = ranked_evidence[0][1] if ranked_evidence else 0.0
    document_diversity = len({fragment.document_id for fragment, _score in ranked_evidence if fragment.document_id})

    confidence = min(
        0.99,
        0.22
        + 0.18 * (applicability_status == ApplicabilityStatus.applicable)
        + 0.22 * average_score
        + 0.18 * strongest_score
        + 0.06 * min(3, evidence_count)
        + 0.05 * min(2, document_diversity),
    )
    return round(confidence, 2)
