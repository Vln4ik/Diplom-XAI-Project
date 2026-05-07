from __future__ import annotations

from dataclasses import dataclass

from app.models import DocumentFragment, RequirementStatus, RiskLevel
from app.services.analysis import significant_token_roots, unique_significant_tokens


@dataclass
class RequirementArtifacts:
    found_data: list[str]
    evidence_payload: list[dict[str, object]]
    conclusion: str
    logic_json: list[str]
    explanation_text: str
    recommended_action: str
    risk_title: str
    risk_description: str


def compact_text(text: str, *, limit: int = 140) -> str:
    normalized = " ".join(text.split())
    if len(normalized) <= limit:
        return normalized
    trimmed = normalized[: max(1, limit - 1)]
    if " " in trimmed:
        trimmed = trimmed.rsplit(" ", 1)[0]
    return f"{trimmed}…"


def recommended_action_for_status(requirement_status: RequirementStatus) -> str:
    if requirement_status == RequirementStatus.confirmed:
        return "Требование подтверждено пользователем. Можно использовать его в итоговом отчете."
    if requirement_status == RequirementStatus.rejected:
        return "Проверить формулировку требования и вручную уточнить комплект подтверждений."
    if requirement_status == RequirementStatus.not_applicable:
        return "Зафиксировать основание неприменимости и исключить требование из контрольного контура."
    if requirement_status == RequirementStatus.data_missing:
        return "Добавить недостающие документы или сведения, подтверждающие выполнение требования."
    if requirement_status == RequirementStatus.data_partial:
        return "Дополнить доказательную базу и перепроверить подобранные подтверждения."
    if requirement_status == RequirementStatus.needs_clarification:
        return "Уточнить применимость требования и проверить наличие профильных доказательств."
    return "Проверить доказательства вручную и при необходимости скорректировать статус требования."


def _matched_keywords(requirement_text: str, fragment_text: str) -> list[str]:
    requirement_tokens = set(unique_significant_tokens(requirement_text))
    fragment_tokens = set(unique_significant_tokens(fragment_text))
    return sorted(requirement_tokens & fragment_tokens)[:5]


def _matched_token_ratio(requirement_text: str, fragment_text: str) -> float:
    requirement_tokens = set(significant_token_roots(requirement_text))
    fragment_tokens = set(significant_token_roots(fragment_text))
    if not requirement_tokens or not fragment_tokens:
        return 0.0
    return round(len(requirement_tokens & fragment_tokens) / len(requirement_tokens), 2)


def build_found_data(requirement_text: str, ranked_evidence: list[tuple[DocumentFragment, float]], *, limit: int = 5) -> list[str]:
    found: list[str] = []
    seen: set[str] = set()
    for fragment, score in ranked_evidence:
        matched_keywords = _matched_keywords(requirement_text, fragment.fragment_text)
        snippet = compact_text(fragment.fragment_text, limit=95)
        label = snippet if not matched_keywords else f"{snippet} | признаки: {', '.join(matched_keywords[:3])}"
        item = f"{label} | score: {score}"
        if item in seen:
            continue
        seen.add(item)
        found.append(item)
        if len(found) >= limit:
            break
    return found


def build_requirement_artifacts(
    *,
    requirement_title: str,
    requirement_text: str,
    category: str,
    applicability_reason: str | None,
    requirement_status: RequirementStatus,
    confidence: float,
    risk_level: RiskLevel,
    source_documents_count: int,
    required_data: list[str],
    ranked_evidence: list[tuple[DocumentFragment, float]],
    manual_lock_note: str | None = None,
) -> RequirementArtifacts:
    found_data = build_found_data(requirement_text, ranked_evidence)
    recommended_action = recommended_action_for_status(requirement_status)

    evidence_payload: list[dict[str, object]] = []
    for fragment, score in ranked_evidence:
        evidence_payload.append(
            {
                "document_id": fragment.document_id,
                "fragment_id": fragment.id,
                "description": compact_text(fragment.fragment_text, limit=200),
                "confidence_score": score,
                "matched_keywords": _matched_keywords(requirement_text, fragment.fragment_text),
                "matched_token_ratio": _matched_token_ratio(requirement_text, fragment.fragment_text),
            }
        )

    best_fragment, best_score = ranked_evidence[0] if ranked_evidence else (None, 0.0)
    best_excerpt = compact_text(best_fragment.fragment_text, limit=160) if best_fragment is not None else "Подтверждающие фрагменты не найдены."
    strongest_signals = (
        ", ".join(evidence_payload[0]["matched_keywords"])  # type: ignore[index]
        if evidence_payload and evidence_payload[0].get("matched_keywords")
        else "не выделены"
    )
    best_coverage = evidence_payload[0]["matched_token_ratio"] if evidence_payload else 0.0

    logic_json = [
        applicability_reason or "Применимость не была уточнена вручную.",
        f"Категория требования: {category}.",
        f"Ключевые обязательные признаки: {', '.join(required_data[:5]) if required_data else 'не выделены'}.",
        f"Найдено подтверждающих фрагментов: {len(ranked_evidence)} из {source_documents_count} документ(ов).",
        f"Наиболее релевантное подтверждение: {best_excerpt}",
        f"Совпавшие признаки по лучшему evidence: {strongest_signals}.",
        f"Покрытие признаков по лучшему evidence: {best_coverage}.",
        f"Уровень уверенности: {confidence}.",
    ]
    if manual_lock_note:
        logic_json.append(manual_lock_note)

    conclusion = (
        f"Требование '{requirement_title}' оценено как {requirement_status.value}. "
        f"Уровень риска: {risk_level.value}."
    )
    explanation_text = (
        f"Требование отнесено к категории '{category}' и сопоставлено с {source_documents_count or 0} документ(ами) "
        f"организации. Статус: {requirement_status.value}. "
        f"Лучшее подтверждение: {best_excerpt}. "
        f"Рекомендуемое действие: {recommended_action}"
    )

    risk_description = (
        f"Статус требования: {requirement_status.value}. "
        f"Уверенность: {confidence}. "
        f"Лучшее подтверждение: {best_excerpt}"
    )
    return RequirementArtifacts(
        found_data=found_data,
        evidence_payload=evidence_payload,
        conclusion=conclusion,
        logic_json=logic_json,
        explanation_text=explanation_text,
        recommended_action=recommended_action,
        risk_title=f"Риск по требованию: {requirement_title[:80]}",
        risk_description=risk_description,
    )
