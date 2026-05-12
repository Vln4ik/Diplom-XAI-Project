from __future__ import annotations

from dataclasses import dataclass

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
HIGH_SIGNAL_TOKENS = {"лиценз", "аккред", "сайт", "кадр", "программ", "локальн", "норматив", "официал"}
TEXT_HINT_MARKERS = {
    "website_sections_published": {"официал", "сайт", "опублик", "раздел"},
    "local_acts_published": {"локальн", "норматив", "акты", "опублик"},
    "licensed_programs": {"лиценз", "программ"},
    "teachers_total": {"кадр", "педагог", "преподав"},
    "students_total": {"континг", "обуча", "студент"},
    "has_accreditation": {"аккред"},
    "has_official_website": {"официал", "сайт"},
    "regulatory_scope": {"лиценз", "аккред"},
    "programs": {"программ"},
}
CATEGORY_HINT_MARKERS = {
    "Официальный сайт": {"website_sections_published", "local_acts_published", "has_official_website"},
    "Лицензия и аккредитация": {"has_accreditation"},
    "Кадровое обеспечение": {"teachers_total"},
    "Контингент обучающихся": {"students_total"},
}
TOKEN_SUFFIXES = (
    "ирование",
    "ирования",
    "иями",
    "ями",
    "ами",
    "ого",
    "ему",
    "ыми",
    "ими",
    "ией",
    "иях",
    "иях",
    "иях",
    "ить",
    "ать",
    "ять",
    "ять",
    "ние",
    "ния",
    "ций",
    "ция",
    "ции",
    "ость",
    "ости",
    "ов",
    "ев",
    "ом",
    "ем",
    "ам",
    "ям",
    "ах",
    "ях",
    "ия",
    "ие",
    "ый",
    "ий",
    "ая",
    "ое",
    "ые",
    "ой",
    "ей",
    "ую",
    "юю",
    "ов",
    "ев",
    "а",
    "я",
    "ы",
    "и",
    "е",
    "у",
    "ю",
    "о",
)


@dataclass(frozen=True)
class EvidenceCandidate:
    fragment: DocumentFragment
    score: float
    retrieval_score: float
    lexical_score: float
    coverage_score: float
    matched_count: int


def _roots_match(left: str, right: str) -> bool:
    if left == right:
        return True
    if len(left) >= 5 and len(right) >= 5 and (left.startswith(right) or right.startswith(left)):
        return True
    return False


def overlapping_roots(left_roots: set[str], right_roots: set[str]) -> set[str]:
    matches: set[str] = set()
    for left in left_roots:
        if any(_roots_match(left, right) for right in right_roots):
            matches.add(left)
    return matches


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


def normalize_token_root(token: str) -> str:
    normalized = token.lower()
    for suffix in TOKEN_SUFFIXES:
        if len(normalized) - len(suffix) < 4:
            continue
        if normalized.endswith(suffix):
            normalized = normalized[: -len(suffix)]
            break
    return normalized[:8]


def significant_token_roots(text: str) -> list[str]:
    seen: set[str] = set()
    tokens: list[str] = []
    for token in unique_significant_tokens(text):
        root = normalize_token_root(token)
        if len(root) < 3 or root in seen:
            continue
        seen.add(root)
        tokens.append(root)
    return tokens


def contextual_token_roots(text: str) -> list[str]:
    roots = significant_token_roots(text)
    lowered = text.lower()
    seen = set(roots)
    for marker, hinted_roots in TEXT_HINT_MARKERS.items():
        if marker not in lowered:
            continue
        for root in hinted_roots:
            if root in seen:
                continue
            seen.add(root)
            roots.append(root)
    return roots


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
    return significant_token_roots(text)[:8]


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
    left_tokens = set(contextual_token_roots(left))
    right_tokens = set(contextual_token_roots(right))
    if not left_tokens or not right_tokens:
        return 0.0
    overlap = overlapping_roots(left_tokens, right_tokens)
    jaccard = len(overlap) / len(left_tokens | right_tokens)
    containment = len(overlap) / min(len(left_tokens), len(right_tokens))
    left_signal = {token for token in left_tokens if token in HIGH_SIGNAL_TOKENS}
    right_signal = {token for token in right_tokens if token in HIGH_SIGNAL_TOKENS}
    signal_overlap = (
        len(left_signal & right_signal) / len(left_signal | right_signal)
        if left_signal and right_signal
        else 0.0
    )
    return round(min(1.0, max(jaccard, containment * 0.88, signal_overlap * 0.95)), 4)


def requirement_signature(text: str, category: str | None = None) -> tuple[str, tuple[str, ...]]:
    roots = significant_token_roots(text)
    if not roots:
        return (category or "", tuple())
    focus = [
        root
        for root in roots
        if root in HIGH_SIGNAL_TOKENS
        or any(root.startswith(marker) or marker.startswith(root) for marker in HIGH_SIGNAL_TOKENS)
    ]
    if len(focus) < 2:
        focus = roots[:5]
    return (category or "", tuple(sorted(focus[:5])))


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
    selected_signatures: set[tuple[str, tuple[str, ...]]] = set()
    for fragment in sorted(candidates, key=sort_key, reverse=True):
        category = category_for_text(fragment.fragment_text)
        signature = requirement_signature(fragment.fragment_text, category)
        if len(significant_token_roots(fragment.fragment_text)) < 3:
            continue
        if signature in selected_signatures:
            continue
        if any(requirement_similarity(fragment.fragment_text, existing) >= 0.82 for existing in selected_texts):
            continue
        selected.append(fragment)
        selected_texts.append(fragment.fragment_text)
        selected_signatures.add(signature)
        if len(selected) >= limit:
            break

    return selected if selected else candidates[:limit]


def evidence_match_metrics(requirement_text: str, fragment_text: str) -> tuple[float, int, float]:
    requirement_tokens = set(contextual_token_roots(requirement_text))
    fragment_tokens = set(contextual_token_roots(fragment_text))
    if not requirement_tokens or not fragment_tokens:
        return 0.0, 0, 0.0

    overlap = overlapping_roots(requirement_tokens, fragment_tokens)
    coverage = len(overlap) / len(requirement_tokens)
    precision = len(overlap) / len(fragment_tokens)
    harmonic = 0.0 if coverage == 0.0 or precision == 0.0 else 2 * coverage * precision / (coverage + precision)
    return round(coverage, 4), len(overlap), round(harmonic, 4)


def direct_evidence_match_metrics(requirement_text: str, fragment_text: str) -> tuple[float, int, float]:
    requirement_tokens = set(significant_token_roots(requirement_text))
    fragment_tokens = set(significant_token_roots(fragment_text))
    if not requirement_tokens or not fragment_tokens:
        return 0.0, 0, 0.0

    overlap = overlapping_roots(requirement_tokens, fragment_tokens)
    coverage = len(overlap) / len(requirement_tokens)
    precision = len(overlap) / len(fragment_tokens)
    harmonic = 0.0 if coverage == 0.0 or precision == 0.0 else 2 * coverage * precision / (coverage + precision)
    return round(coverage, 4), len(overlap), round(harmonic, 4)


def fragment_hint_markers(text: str) -> set[str]:
    lowered = text.lower()
    return {marker for marker in TEXT_HINT_MARKERS if marker in lowered}


def fragment_specificity_penalty(
    fragment_text: str,
    category: str,
    *,
    direct_matched_count: int,
    contextual_matched_count: int,
) -> float:
    normalized = fragment_text.strip()
    lowered = normalized.lower()
    markers = fragment_hint_markers(fragment_text)
    allowed_markers = CATEGORY_HINT_MARKERS.get(category, set())
    penalty = 0.0

    if normalized in {"{", "}", "[", "]"}:
        return 0.25
    if normalized.endswith(": [") or normalized.endswith('": [') or normalized.endswith(": {") or normalized.endswith('": {'):
        penalty += 0.18
    if normalized.startswith('"') and normalized.endswith('",') and len(unique_significant_tokens(normalized)) <= 1:
        penalty += 0.12
    if markers and direct_matched_count == 0 and contextual_matched_count > 0:
        penalty += 0.04 if markers & allowed_markers else 0.14
    if "|" in normalized and direct_matched_count == 0 and not (markers & allowed_markers):
        penalty += 0.08
    if lowered.startswith('"') and lowered.endswith('",') and direct_matched_count == 0 and not (markers & allowed_markers):
        penalty += 0.05
    return round(min(0.35, penalty), 4)


def score_evidence_candidate(requirement_text: str, fragment_text: str, category: str) -> float:
    requirement_tokens = set(contextual_token_roots(requirement_text))
    fragment_tokens = set(contextual_token_roots(fragment_text))
    if not requirement_tokens or not fragment_tokens:
        return 0.0

    overlap = keyword_overlap_score(requirement_text, fragment_text)
    token_coverage, matched_count, harmonic = evidence_match_metrics(requirement_text, fragment_text)
    category_bonus = 0.08 if overlapping_roots(CATEGORY_MARKERS.get(category, set()), fragment_tokens) else 0.0
    signal_overlap = overlapping_roots(HIGH_SIGNAL_TOKENS & requirement_tokens, fragment_tokens)
    signal_bonus = min(0.12, 0.04 * len(signal_overlap))
    density_bonus = min(0.1, 0.025 * matched_count)
    targeted_bonus = 0.06 if matched_count > 0 and (signal_overlap or token_coverage >= 0.35) else 0.0

    return round(
        min(
            0.99,
            overlap * 0.24
            + token_coverage * 0.26
            + harmonic * 0.18
            + category_bonus
            + signal_bonus
            + density_bonus
            + targeted_bonus,
        ),
        2,
    )


def _evidence_bonus(fragment: DocumentFragment, query_tokens: set[str], category: str) -> float:
    fragment_tokens = set(contextual_token_roots(fragment.fragment_text))
    if not fragment_tokens:
        return 0.0

    category_bonus = 0.08 if overlapping_roots(CATEGORY_MARKERS.get(category, set()), fragment_tokens) else 0.0
    signal_bonus = 0.08 if overlapping_roots(query_tokens, fragment_tokens) else 0.0
    density_bonus = min(0.08, 0.02 * len(query_tokens & fragment_tokens))
    return round(category_bonus + signal_bonus + density_bonus, 4)


def rank_evidence_candidates(
    db: Session,
    requirement_text: str,
    fragments: list[DocumentFragment],
    category: str,
    *,
    exclude_fragment_id: str | None = None,
    exclude_document_ids: set[str] | None = None,
    limit: int = 5,
) -> list[tuple[DocumentFragment, float]]:
    candidates = [
        fragment
        for fragment in fragments
        if fragment.id != exclude_fragment_id and fragment.document_id not in (exclude_document_ids or set())
    ]
    ranked = rank_fragments(
        db,
        query_text=requirement_text,
        fragments=candidates,
        limit=max(limit * 3, 12),
        min_score=0.12,
        max_per_document=3,
        bonus_resolver=lambda fragment, query_tokens: _evidence_bonus(fragment, query_tokens, category),
    )

    rescored: list[EvidenceCandidate] = []
    for item in ranked:
        lexical_score = score_evidence_candidate(requirement_text, item.fragment.fragment_text, category)
        coverage_score, matched_count, harmonic = evidence_match_metrics(requirement_text, item.fragment.fragment_text)
        direct_coverage, direct_matched_count, direct_harmonic = direct_evidence_match_metrics(
            requirement_text,
            item.fragment.fragment_text,
        )
        specificity_penalty = fragment_specificity_penalty(
            item.fragment.fragment_text,
            category,
            direct_matched_count=direct_matched_count,
            contextual_matched_count=matched_count,
        )
        final_score = round(
            min(
                0.99,
                item.score * 0.48
                + lexical_score * 0.28
                + coverage_score * 0.16
                + harmonic * 0.08
                + min(0.04, 0.01 * matched_count),
            )
            - specificity_penalty
            + min(0.04, 0.02 * direct_harmonic),
            2,
        )
        rescored.append(
            EvidenceCandidate(
                fragment=item.fragment,
                score=final_score,
                retrieval_score=round(item.score, 2),
                lexical_score=lexical_score,
                coverage_score=coverage_score,
                matched_count=matched_count,
            )
        )

    rescored.sort(
        key=lambda item: (item.score, item.coverage_score, item.matched_count, item.lexical_score, item.retrieval_score),
        reverse=True,
    )
    if not rescored:
        return []

    best_score = rescored[0].score
    score_floor = max(0.14, round(best_score * 0.42, 2))

    selected: list[EvidenceCandidate] = []
    per_document: dict[str | None, int] = {}
    deferred: list[EvidenceCandidate] = []
    diversity_target = min(limit, 3)
    covered_requirement_roots: set[str] = set()
    requirement_roots = set(contextual_token_roots(requirement_text))
    for candidate in rescored:
        fragment_roots = set(contextual_token_roots(candidate.fragment.fragment_text))
        overlap_roots = overlapping_roots(requirement_roots, fragment_roots)
        new_roots = overlap_roots - covered_requirement_roots
        direct_coverage, direct_matched_count, _direct_harmonic = direct_evidence_match_metrics(
            requirement_text,
            candidate.fragment.fragment_text,
        )

        if candidate.score < score_floor and candidate.coverage_score < 0.2 and direct_coverage < 0.15 and candidate.matched_count == 0:
            continue
        if candidate.score < 0.1:
            continue
        if not new_roots and candidate.score < 0.32 and direct_coverage < 0.2:
            continue
        if direct_matched_count == 0 and not new_roots and candidate.coverage_score < 0.25:
            continue
        if any(requirement_similarity(candidate.fragment.fragment_text, item.fragment.fragment_text) >= 0.9 for item in selected):
            continue
        document_hits = per_document.get(candidate.fragment.document_id, 0)
        if document_hits >= 1 and len(selected) < diversity_target:
            deferred.append(candidate)
            continue
        selected.append(candidate)
        per_document[candidate.fragment.document_id] = document_hits + 1
        covered_requirement_roots.update(overlap_roots)
        if len(selected) >= limit:
            break

    if len(selected) < limit:
        for candidate in deferred:
            if len(selected) >= limit:
                break
            if any(candidate.fragment.id == item.fragment.id for item in selected):
                continue
            fragment_roots = set(contextual_token_roots(candidate.fragment.fragment_text))
            overlap_roots = overlapping_roots(requirement_roots, fragment_roots)
            new_roots = overlap_roots - covered_requirement_roots
            direct_coverage, direct_matched_count, _direct_harmonic = direct_evidence_match_metrics(
                requirement_text,
                candidate.fragment.fragment_text,
            )
            if candidate.score < score_floor:
                continue
            if not new_roots and candidate.score < 0.38:
                continue
            if direct_matched_count == 0 and candidate.coverage_score < 0.25 and direct_coverage < 0.15:
                continue
            document_hits = per_document.get(candidate.fragment.document_id, 0)
            if document_hits >= 2:
                continue
            selected.append(candidate)
            per_document[candidate.fragment.document_id] = document_hits + 1
            covered_requirement_roots.update(overlap_roots)

    return [(item.fragment, item.score) for item in selected[:limit]]


def derive_requirement_confidence(
    applicability_status: ApplicabilityStatus,
    requirement_text: str,
    ranked_evidence: list[tuple[DocumentFragment, float]],
) -> float:
    if applicability_status == ApplicabilityStatus.not_applicable:
        return 0.9

    evidence_count = len(ranked_evidence)
    average_score = sum(score for _fragment, score in ranked_evidence) / evidence_count if evidence_count else 0.0
    strongest_score = ranked_evidence[0][1] if ranked_evidence else 0.0
    document_diversity = len({fragment.document_id for fragment, _score in ranked_evidence if fragment.document_id})
    coverage_scores = [evidence_match_metrics(requirement_text, fragment.fragment_text)[0] for fragment, _score in ranked_evidence]
    best_coverage = max(coverage_scores, default=0.0)
    mean_coverage = sum(coverage_scores) / len(coverage_scores) if coverage_scores else 0.0
    support_ratio = min(1.0, evidence_count / 3)
    diversity_ratio = 0.0 if evidence_count == 0 else document_diversity / evidence_count

    confidence = (
        0.16
        + 0.2 * (applicability_status == ApplicabilityStatus.applicable)
        + 0.2 * strongest_score
        + 0.16 * average_score
        + 0.16 * best_coverage
        + 0.1 * mean_coverage
        + 0.08 * support_ratio
        + 0.06 * diversity_ratio
    )
    if evidence_count == 0:
        confidence -= 0.12
    if strongest_score < 0.42:
        confidence -= 0.08
    if best_coverage < 0.25:
        confidence -= 0.08
    if evidence_count > 1 and document_diversity == 1:
        confidence -= 0.04

    confidence = min(
        0.99,
        max(
            0.05,
            confidence,
        ),
    )
    return round(confidence, 2)
