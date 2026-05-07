from __future__ import annotations

from collections import defaultdict

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.llm.local import get_llm_provider
from app.models import (
    ApplicabilityStatus,
    Document,
    DocumentCategory,
    DocumentFragment,
    Evidence,
    Explanation,
    Report,
    ReportSection,
    ReportStatus,
    ReportVersion,
    Requirement,
    RequirementStatus,
    Risk,
    RiskLevel,
    RiskStatus,
)
from app.services.analysis import (
    applicability_for_report,
    build_requirement_title,
    category_for_text,
    derive_requirement_confidence,
    rank_evidence_candidates,
    required_data_from_text,
    select_requirement_fragments,
)
from app.services.audit import log_action
from app.services.notifications import (
    notify_report_approved,
    notify_report_returned_to_revision,
    notify_report_submitted_for_approval,
)
from app.services.xai import build_requirement_artifacts

SECTION_BLUEPRINT = [
    "Титульная часть",
    "Общие сведения об организации",
    "Основания подготовки отчета",
    "Перечень применимых требований",
    "Сведения, подтверждающие выполнение требований",
    "Выявленные несоответствия и недостающие данные",
    "Риски",
    "Рекомендации",
    "Заключение",
]

REQUIREMENT_SOURCE_CATEGORIES = {
    DocumentCategory.normative,
    DocumentCategory.methodological,
    DocumentCategory.template,
    DocumentCategory.internal_policy,
    DocumentCategory.local_act,
    DocumentCategory.prescription,
    DocumentCategory.inspection_act,
    DocumentCategory.previous_report,
}

STRUCTURED_SECTION_TITLES = {
    "Титульная часть",
    "Основания подготовки отчета",
    "Перечень применимых требований",
    "Риски",
    "Рекомендации",
}


READY_REQUIREMENT_STATUSES = {
    RequirementStatus.data_found,
    RequirementStatus.confirmed,
    RequirementStatus.included_in_report,
    RequirementStatus.not_applicable,
}
GAP_REQUIREMENT_STATUSES = {
    RequirementStatus.data_missing,
    RequirementStatus.data_partial,
    RequirementStatus.needs_clarification,
    RequirementStatus.rejected,
}


def _requirement_status(
    applicability_status: ApplicabilityStatus,
    found_count: int,
    confidence: float,
) -> RequirementStatus:
    if applicability_status == ApplicabilityStatus.not_applicable:
        return RequirementStatus.not_applicable
    if applicability_status == ApplicabilityStatus.needs_clarification and found_count == 0:
        return RequirementStatus.needs_clarification
    if found_count == 0:
        return RequirementStatus.data_missing
    if confidence < 0.55:
        return RequirementStatus.data_partial
    return RequirementStatus.data_found


def _risk_level(
    status: RequirementStatus,
    confidence: float,
    applicability_status: ApplicabilityStatus,
) -> RiskLevel:
    if applicability_status == ApplicabilityStatus.not_applicable:
        return RiskLevel.low
    if status == RequirementStatus.data_missing:
        return RiskLevel.high
    if status in {RequirementStatus.data_partial, RequirementStatus.needs_clarification} or confidence < 0.55:
        return RiskLevel.medium
    return RiskLevel.low


def analyze_report(db: Session, report: Report) -> Report:
    existing_requirement_ids = list(db.scalars(select(Requirement.id).where(Requirement.report_id == report.id)))
    if existing_requirement_ids:
        db.execute(delete(Evidence).where(Evidence.requirement_id.in_(existing_requirement_ids)))
        db.execute(delete(Explanation).where(Explanation.requirement_id.in_(existing_requirement_ids)))
    db.execute(delete(Risk).where(Risk.organization_id == report.organization_id, Risk.report_id == report.id))
    db.execute(delete(Requirement).where(Requirement.organization_id == report.organization_id, Requirement.report_id == report.id))
    db.commit()

    organization_profile = report.organization.profile_json if report.organization is not None else {}
    documents_query = select(Document).where(Document.organization_id == report.organization_id)
    if report.selected_document_ids:
        documents_query = documents_query.where(Document.id.in_(report.selected_document_ids))
    selected_documents = list(db.scalars(documents_query))
    selected_document_index = {document.id: document for document in selected_documents}

    fragments_query = select(DocumentFragment).where(DocumentFragment.organization_id == report.organization_id)
    if selected_document_index:
        fragments_query = fragments_query.where(DocumentFragment.document_id.in_(selected_document_index))
    fragments = list(db.scalars(fragments_query))
    preferred_requirement_fragments = [
        fragment
        for fragment in fragments
        if selected_document_index.get(fragment.document_id) is not None
        and selected_document_index[fragment.document_id].category in REQUIREMENT_SOURCE_CATEGORIES
    ]
    candidates = select_requirement_fragments(preferred_requirement_fragments or fragments, limit=25)

    created = 0
    for fragment in candidates:
        title = build_requirement_title(fragment.fragment_text)
        category = category_for_text(fragment.fragment_text)
        applicability_status, applicability_reason = applicability_for_report(
            fragment.fragment_text,
            organization_profile,
            report.report_type,
        )
        related = rank_evidence_candidates(
            db,
            fragment.fragment_text,
            fragments,
            category,
            exclude_fragment_id=fragment.id,
            exclude_document_ids={fragment.document_id} if fragment.document_id else None,
            limit=5,
        )
        confidence = derive_requirement_confidence(applicability_status, fragment.fragment_text, related)
        status = _requirement_status(applicability_status, len(related), confidence)
        risk_level = _risk_level(status, confidence, applicability_status)
        source_documents_count = len({item.document_id for item, _score in related if item.document_id})
        required_data = required_data_from_text(fragment.fragment_text)

        artifacts = build_requirement_artifacts(
            requirement_title=title,
            requirement_text=fragment.fragment_text,
            category=category,
            applicability_reason=applicability_reason,
            requirement_status=status,
            confidence=confidence,
            risk_level=risk_level,
            source_documents_count=source_documents_count,
            required_data=required_data,
            ranked_evidence=related,
        )

        requirement = Requirement(
            organization_id=report.organization_id,
            report_id=report.id,
            regulator=report.regulator,
            category=category,
            title=title,
            text=fragment.fragment_text,
            source_document_id=fragment.document_id,
            source_fragment_id=fragment.id,
            applicability_status=applicability_status,
            applicability_reason=applicability_reason,
            required_data=required_data,
            found_data=artifacts.found_data,
            status=status,
            confidence_score=confidence,
            risk_level=risk_level,
        )
        db.add(requirement)
        db.flush()

        for related_fragment, score in related:
            evidence = Evidence(
                organization_id=report.organization_id,
                requirement_id=requirement.id,
                document_id=related_fragment.document_id,
                fragment_id=related_fragment.id,
                evidence_type="document_fragment",
                description=related_fragment.fragment_text[:250],
                confidence_score=score,
                status="candidate",
            )
            db.add(evidence)

        explanation = Explanation(
            organization_id=report.organization_id,
            requirement_id=requirement.id,
            conclusion=artifacts.conclusion,
            logic_json=artifacts.logic_json,
            source_document_id=fragment.document_id,
            source_fragment_id=fragment.id,
            evidence_json=artifacts.evidence_payload,
            confidence_score=confidence,
            risk_level=risk_level,
            explanation_text=artifacts.explanation_text,
            recommended_action=artifacts.recommended_action,
        )
        db.add(explanation)

        if risk_level != RiskLevel.low:
            db.add(
                Risk(
                    organization_id=report.organization_id,
                    report_id=report.id,
                    requirement_id=requirement.id,
                    title=artifacts.risk_title,
                    description=artifacts.risk_description,
                    risk_level=risk_level,
                    status=RiskStatus.new,
                    recommended_action=artifacts.recommended_action,
                )
            )
        created += 1

    report.status = ReportStatus.requires_review
    report.readiness_percent = round(
        0.0 if created == 0 else len([1 for requirement in db.scalars(select(Requirement).where(Requirement.report_id == report.id)) if requirement.status == RequirementStatus.data_found]) / created * 100,
        2,
    )
    db.add(report)
    log_action(
        db,
        action="report_analyzed",
        entity_type="report",
        entity_id=report.id,
        organization_id=report.organization_id,
        user_id=report.responsible_user_id,
        details={"requirements_created": created},
    )
    db.commit()
    db.refresh(report)
    return report


def build_report_matrix(db: Session, report: Report) -> list[dict]:
    requirements = list(db.scalars(select(Requirement).where(Requirement.report_id == report.id).order_by(Requirement.created_at)))
    if not requirements:
        return []

    requirement_ids = [item.id for item in requirements]
    explanations = {
        explanation.requirement_id: explanation
        for explanation in db.scalars(select(Explanation).where(Explanation.requirement_id.in_(requirement_ids)))
    }
    evidence_rows = list(db.scalars(select(Evidence).where(Evidence.requirement_id.in_(requirement_ids)).order_by(Evidence.created_at)))
    source_document_ids = {
        requirement.source_document_id for requirement in requirements if requirement.source_document_id is not None
    } | {evidence.document_id for evidence in evidence_rows if evidence.document_id is not None}
    source_fragment_ids = {
        requirement.source_fragment_id for requirement in requirements if requirement.source_fragment_id is not None
    } | {evidence.fragment_id for evidence in evidence_rows if evidence.fragment_id is not None}

    documents = {
        document.id: document
        for document in db.scalars(select(Document).where(Document.id.in_(source_document_ids)))
    } if source_document_ids else {}
    fragments = {
        fragment.id: fragment
        for fragment in db.scalars(select(DocumentFragment).where(DocumentFragment.id.in_(source_fragment_ids)))
    } if source_fragment_ids else {}
    evidence_by_requirement: dict[str, list[Evidence]] = defaultdict(list)
    for evidence in evidence_rows:
        evidence_by_requirement[evidence.requirement_id].append(evidence)

    included_in_report = {
        requirement_id
        for section in db.scalars(select(ReportSection).where(ReportSection.report_id == report.id))
        for requirement_id in section.source_requirement_ids
    }

    rows: list[dict] = []
    for requirement in requirements:
        explanation = explanations.get(requirement.id)
        source_document = documents.get(requirement.source_document_id) if requirement.source_document_id else None
        source_fragment = fragments.get(requirement.source_fragment_id) if requirement.source_fragment_id else None
        rows.append(
            {
                "requirement_id": requirement.id,
                "category": requirement.category,
                "title": requirement.title,
                "text": requirement.text,
                "applicability_status": requirement.applicability_status.value,
                "source_document_name": source_document.file_name if source_document else None,
                "source_fragment_text": source_fragment.fragment_text[:240] if source_fragment else None,
                "required_data": requirement.required_data,
                "found_data": requirement.found_data,
                "evidence": [
                    {
                        "document_name": documents[evidence.document_id].file_name if evidence.document_id in documents else None,
                        "fragment_text": fragments[evidence.fragment_id].fragment_text[:180] if evidence.fragment_id in fragments else evidence.description,
                        "confidence_score": evidence.confidence_score,
                    }
                    for evidence in evidence_by_requirement.get(requirement.id, [])
                ],
                "status": requirement.status.value,
                "confidence_score": requirement.confidence_score,
                "risk_level": requirement.risk_level.value,
                "system_comment": explanation.explanation_text if explanation else None,
                "user_comment": requirement.user_comment,
                "included_in_report": requirement.id in included_in_report or requirement.status == RequirementStatus.included_in_report,
            }
        )
    return rows


def _build_report_explanations_payload(db: Session, report: Report) -> list[dict]:
    requirement_ids = list(db.scalars(select(Requirement.id).where(Requirement.report_id == report.id)))
    if not requirement_ids:
        return []
    explanations = list(db.scalars(select(Explanation).where(Explanation.requirement_id.in_(requirement_ids)).order_by(Explanation.created_at)))
    return [
        {
            "requirement_id": explanation.requirement_id,
            "conclusion": explanation.conclusion,
            "logic": explanation.logic_json,
            "confidence_score": explanation.confidence_score,
            "risk_level": explanation.risk_level.value,
            "explanation_text": explanation.explanation_text,
            "recommended_action": explanation.recommended_action,
        }
        for explanation in explanations
    ]


def build_report_explanations_payload(db: Session, report: Report) -> list[dict]:
    return _build_report_explanations_payload(db, report)


def create_report_version(db: Session, report: Report, created_by_id: str | None) -> ReportVersion:
    latest_version = db.scalar(
        select(ReportVersion).where(ReportVersion.report_id == report.id).order_by(ReportVersion.version_number.desc())
    )
    next_version = 1 if latest_version is None else latest_version.version_number + 1
    sections_payload = [
        {
            "id": section.id,
            "title": section.title,
            "content": section.content,
            "order_number": section.order_number,
            "status": section.status,
            "source_requirement_ids": section.source_requirement_ids,
        }
        for section in db.scalars(select(ReportSection).where(ReportSection.report_id == report.id).order_by(ReportSection.order_number))
    ]
    version = ReportVersion(
        organization_id=report.organization_id,
        report_id=report.id,
        version_number=next_version,
        created_by_id=created_by_id,
        report_status=report.status,
        title=report.title,
        report_type=report.report_type,
        readiness_percent=report.readiness_percent,
        comment=report.comment,
        sections_json=sections_payload,
        matrix_json=build_report_matrix(db, report),
        explanations_json=build_report_explanations_payload(db, report),
    )
    db.add(version)
    db.flush()
    log_action(
        db,
        action="report_version_created",
        entity_type="report_version",
        entity_id=version.id,
        organization_id=report.organization_id,
        user_id=created_by_id,
        details={"report_id": report.id, "version_number": next_version},
    )
    return version


def restore_report_version(db: Session, version: ReportVersion, restored_by_id: str | None) -> Report:
    report = db.scalar(select(Report).where(Report.id == version.report_id))
    if report is None:
        raise ValueError("Report not found")

    db.execute(delete(ReportSection).where(ReportSection.report_id == report.id))
    db.flush()
    for item in sorted(version.sections_json, key=lambda section: section.get("order_number", 0)):
        db.add(
            ReportSection(
                organization_id=report.organization_id,
                report_id=report.id,
                title=item.get("title", "Раздел"),
                content=item.get("content", ""),
                order_number=item.get("order_number", 0),
                status=item.get("status", "draft"),
                source_requirement_ids=item.get("source_requirement_ids", []),
            )
        )

    report.title = version.title
    report.report_type = version.report_type
    report.comment = version.comment
    report.readiness_percent = version.readiness_percent
    report.status = ReportStatus.in_revision
    db.add(report)
    db.flush()

    create_report_version(db, report, restored_by_id)
    log_action(
        db,
        action="report_version_restored",
        entity_type="report",
        entity_id=report.id,
        organization_id=report.organization_id,
        user_id=restored_by_id,
        details={
            "source_version_id": version.id,
            "source_version_number": version.version_number,
        },
    )
    db.commit()
    db.refresh(report)
    return report


def _transition_report_status(
    db: Session,
    *,
    report: Report,
    new_status: ReportStatus,
    action: str,
    user_id: str | None,
) -> Report:
    report.status = new_status
    db.add(report)
    log_action(
        db,
        action=action,
        entity_type="report",
        entity_id=report.id,
        organization_id=report.organization_id,
        user_id=user_id,
        details={"status": new_status.value},
    )
    db.commit()
    db.refresh(report)
    return report


def submit_report_for_approval(db: Session, report: Report, user_id: str | None) -> Report:
    updated = _transition_report_status(
        db,
        report=report,
        new_status=ReportStatus.awaiting_approval,
        action="report_submitted_for_approval",
        user_id=user_id,
    )
    notify_report_submitted_for_approval(db, report=updated, triggered_by_id=user_id)
    db.commit()
    db.refresh(updated)
    return updated


def approve_report(db: Session, report: Report, user_id: str | None) -> Report:
    updated = _transition_report_status(
        db,
        report=report,
        new_status=ReportStatus.approved,
        action="report_approved",
        user_id=user_id,
    )
    notify_report_approved(db, report=updated, triggered_by_id=user_id)
    db.commit()
    db.refresh(updated)
    return updated


def return_report_to_revision(db: Session, report: Report, user_id: str | None) -> Report:
    updated = _transition_report_status(
        db,
        report=report,
        new_status=ReportStatus.in_revision,
        action="report_returned_to_revision",
        user_id=user_id,
    )
    notify_report_returned_to_revision(db, report=updated, triggered_by_id=user_id)
    db.commit()
    db.refresh(updated)
    return updated


def _requirements_for_section(
    title: str,
    requirements: list[Requirement],
    risks: list[Risk],
) -> list[Requirement]:
    risk_requirement_ids = {risk.requirement_id for risk in risks if risk.requirement_id}
    if title == "Перечень применимых требований":
        selected = [item for item in requirements if item.applicability_status == ApplicabilityStatus.applicable]
    elif title == "Сведения, подтверждающие выполнение требований":
        selected = [item for item in requirements if item.status in READY_REQUIREMENT_STATUSES]
    elif title == "Выявленные несоответствия и недостающие данные":
        selected = [item for item in requirements if item.status in GAP_REQUIREMENT_STATUSES]
    elif title in {"Риски", "Рекомендации"}:
        selected = [item for item in requirements if item.id in risk_requirement_ids or item.status in GAP_REQUIREMENT_STATUSES]
    else:
        selected = requirements
    return selected[:10]


def _requirement_snapshot(requirement: Requirement, explanation: Explanation | None) -> str:
    evidence_count = len(explanation.evidence_json) if explanation is not None else 0
    parts = [
        requirement.title,
        f"категория: {requirement.category}",
        f"статус: {requirement.status.value}",
        f"риск: {requirement.risk_level.value}",
        f"применимость: {requirement.applicability_status.value}",
        f"уверенность: {requirement.confidence_score}",
        f"доказательств: {evidence_count}",
    ]
    if requirement.found_data:
        parts.append(f"подтверждения: {'; '.join(requirement.found_data[:2])}")
    if explanation is not None and explanation.recommended_action:
        parts.append(f"рекомендация: {explanation.recommended_action}")
    return " | ".join(parts)


def _build_section_context(
    db: Session,
    *,
    report: Report,
    title: str,
    requirements: list[Requirement],
    explanations: dict[str, Explanation],
    risks: list[Risk],
) -> tuple[str, list[str]]:
    organization = report.organization
    organization_name = organization.name if organization is not None else report.organization_id
    profile_json = organization.profile_json if organization is not None else {}
    documents_query = select(Document).where(Document.organization_id == report.organization_id)
    if report.selected_document_ids:
        documents_query = documents_query.where(Document.id.in_(report.selected_document_ids))
    source_documents = list(db.scalars(documents_query.order_by(Document.created_at.desc())))

    section_requirements = _requirements_for_section(title, requirements, risks)
    section_requirement_ids = [item.id for item in section_requirements]
    ready_requirements = [item for item in requirements if item.status in READY_REQUIREMENT_STATUSES]
    gap_requirements = [item for item in requirements if item.status in GAP_REQUIREMENT_STATUSES]

    if title == "Титульная часть":
        return (
            "\n".join(
                [
                    f"Отчет: {report.title}",
                    f"Организация: {organization_name}",
                    f"Регулятор: {report.regulator}",
                    f"Тип отчета: {report.report_type}",
                    f"Готовность: {report.readiness_percent}%",
                ]
            ),
            [],
        )

    if title == "Общие сведения об организации":
        profile_lines = [f"- {key}: {value}" for key, value in profile_json.items() if value]
        return (
            "\n".join(
                [
                    f"Организация: {organization_name}",
                    f"Тип: {organization.organization_type.value if organization is not None else 'unknown'}",
                    f"Готовность: {report.readiness_percent}%",
                    "Профиль организации:",
                    *(profile_lines or ["- Дополнительные сведения не заполнены."]),
                ]
            ),
            [],
        )

    if title == "Основания подготовки отчета":
        document_lines = [
            f"- {document.file_name} | категория: {document.category.value} | статус: {document.status.value}"
            for document in source_documents[:10]
        ]
        return (
            "\n".join(
                [
                    f"Отчет подготовлен для сценария '{report.report_type}' по регулятору '{report.regulator}'.",
                    f"Использовано документов: {len(source_documents)}.",
                    *(document_lines or ["- Документы для отчета пока не выбраны."]),
                ]
            ),
            [],
        )

    if title == "Перечень применимых требований":
        lines = [_requirement_snapshot(requirement, explanations.get(requirement.id)) for requirement in section_requirements]
        payload_lines = [f"- {line}" for line in lines] or ["- Требования не найдены."]
        return (
            "\n".join(
                [
                    f"Всего требований: {len(requirements)}. Применимых: {len(section_requirements)}.",
                    *payload_lines,
                ]
            ),
            section_requirement_ids,
        )

    if title == "Сведения, подтверждающие выполнение требований":
        lines = [_requirement_snapshot(requirement, explanations.get(requirement.id)) for requirement in section_requirements]
        payload_lines = [f"- {line}" for line in lines] or ["- Подтверждающие сведения пока не сформированы."]
        return (
            "\n".join(
                [
                    f"Подтвержденных или готовых требований: {len(ready_requirements)}.",
                    *payload_lines,
                ]
            ),
            section_requirement_ids,
        )

    if title == "Выявленные несоответствия и недостающие данные":
        lines = [_requirement_snapshot(requirement, explanations.get(requirement.id)) for requirement in section_requirements]
        payload_lines = [f"- {line}" for line in lines] or ["- Существенные пробелы не выявлены."]
        return (
            "\n".join(
                [
                    f"Требований с пробелами или замечаниями: {len(gap_requirements)}.",
                    *payload_lines,
                ]
            ),
            section_requirement_ids,
        )

    if title == "Риски":
        lines = [
            f"- {risk.title} | уровень: {risk.risk_level.value} | статус: {risk.status.value} | действие: {risk.recommended_action or 'не указано'}"
            for risk in risks
        ]
        return ("\n".join(lines) if lines else "Критические риски не обнаружены.", section_requirement_ids)

    if title == "Рекомендации":
        actions: list[str] = []
        for requirement in section_requirements:
            explanation = explanations.get(requirement.id)
            if explanation is not None and explanation.recommended_action:
                actions.append(f"- {requirement.title}: {explanation.recommended_action}")
        return ("\n".join(actions) if actions else "Дополнительные рекомендации не требуются.", section_requirement_ids)

    if title == "Заключение":
        open_risks = [risk for risk in risks if risk.status != RiskStatus.resolved]
        priority_requirements = gap_requirements or sorted(
            ready_requirements,
            key=lambda item: (item.risk_level.value, item.confidence_score),
            reverse=True,
        )
        return (
            "\n".join(
                [
                    f"Всего требований: {len(requirements)}.",
                    f"Готовых требований: {len(ready_requirements)}.",
                    f"Требований с пробелами: {len(gap_requirements)}.",
                    f"Открытых рисков: {len(open_risks)}.",
                    f"Итоговая готовность отчета: {report.readiness_percent}%.",
                ]
            ),
            [item.id for item in priority_requirements[:2]],
        )

    grouped: dict[str, list[Requirement]] = defaultdict(list)
    for requirement in section_requirements or requirements:
        grouped[requirement.category].append(requirement)
    lines: list[str] = []
    for category, items in grouped.items():
        lines.append(category)
        lines.extend(f"- {_requirement_snapshot(item, explanations.get(item.id))}" for item in items[:5])
    return ("\n".join(lines) if lines else "Недостаточно данных для генерации раздела.", section_requirement_ids)


def generate_report_sections(db: Session, report: Report) -> Report:
    db.execute(delete(ReportSection).where(ReportSection.report_id == report.id))
    db.commit()

    provider = get_llm_provider()
    requirements = list(db.scalars(select(Requirement).where(Requirement.report_id == report.id).order_by(Requirement.created_at)))
    requirement_ids = [item.id for item in requirements]
    explanations = (
        {
            item.requirement_id: item
            for item in db.scalars(select(Explanation).where(Explanation.requirement_id.in_(requirement_ids)))
        }
        if requirement_ids
        else {}
    )
    risks = list(db.scalars(select(Risk).where(Risk.report_id == report.id).order_by(Risk.created_at)))

    for order, title in enumerate(SECTION_BLUEPRINT, start=1):
        context, section_requirement_ids = _build_section_context(
            db,
            report=report,
            title=title,
            requirements=requirements,
            explanations=explanations,
            risks=risks,
        )
        content = (
            f"{title}\n\n{context}".strip()
            if title in STRUCTURED_SECTION_TITLES
            else provider.generate_section(title, context)
        )
        db.add(
            ReportSection(
                organization_id=report.organization_id,
                report_id=report.id,
                title=title,
                content=content,
                order_number=order,
                status="draft",
                source_requirement_ids=section_requirement_ids,
            )
        )

    report.status = ReportStatus.draft
    db.add(report)
    db.flush()
    create_report_version(db, report, report.responsible_user_id)
    log_action(
        db,
        action="report_generated",
        entity_type="report",
        entity_id=report.id,
        organization_id=report.organization_id,
        user_id=report.responsible_user_id,
    )
    db.commit()
    db.refresh(report)
    return report
