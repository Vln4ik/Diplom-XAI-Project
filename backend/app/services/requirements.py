from __future__ import annotations

from enum import Enum

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.services.analysis import derive_requirement_confidence, rank_evidence_candidates, required_data_from_text
from app.services.xai import build_requirement_artifacts, recommended_action_for_status
from app.models import (
    ApplicabilityStatus,
    DocumentFragment,
    Evidence,
    Explanation,
    Report,
    Requirement,
    RequirementStatus,
    Risk,
    RiskLevel,
    RiskStatus,
)
from app.services.audit import log_action

MANUAL_STATUS_LOCKS = {
    RequirementStatus.confirmed,
    RequirementStatus.rejected,
    RequirementStatus.included_in_report,
}
READY_REQUIREMENT_STATUSES = {
    RequirementStatus.data_found,
    RequirementStatus.confirmed,
    RequirementStatus.included_in_report,
    RequirementStatus.not_applicable,
}


def get_requirement_explanation(db: Session, requirement_id: str) -> Explanation | None:
    return db.scalar(select(Explanation).where(Explanation.requirement_id == requirement_id))


def _serialize_detail(value: object) -> object:
    if isinstance(value, Enum):
        return value.value
    return value


def _derive_requirement_status(
    current_status: RequirementStatus,
    applicability_status: ApplicabilityStatus,
    related_count: int,
    confidence: float,
) -> RequirementStatus:
    if current_status in MANUAL_STATUS_LOCKS:
        return current_status
    if applicability_status == ApplicabilityStatus.not_applicable:
        return RequirementStatus.not_applicable
    if applicability_status == ApplicabilityStatus.needs_clarification and related_count == 0:
        return RequirementStatus.needs_clarification
    if related_count == 0:
        return RequirementStatus.data_missing
    if confidence < 0.5:
        return RequirementStatus.data_partial
    return RequirementStatus.data_found


def _derive_risk_level(
    requirement_status: RequirementStatus,
    confidence: float,
    applicability_status: ApplicabilityStatus,
) -> RiskLevel:
    if applicability_status == ApplicabilityStatus.not_applicable:
        return RiskLevel.low
    if requirement_status in {RequirementStatus.confirmed, RequirementStatus.included_in_report}:
        return RiskLevel.low
    if requirement_status in {RequirementStatus.data_missing, RequirementStatus.rejected}:
        return RiskLevel.high
    if requirement_status in {RequirementStatus.needs_clarification, RequirementStatus.data_partial} or confidence < 0.5:
        return RiskLevel.medium
    return RiskLevel.low


def refresh_report_readiness(db: Session, report_id: str | None) -> Report | None:
    if report_id is None:
        return None
    report = db.scalar(select(Report).where(Report.id == report_id))
    if report is None:
        return None
    requirements = list(db.scalars(select(Requirement.status).where(Requirement.report_id == report_id)))
    total = len(requirements)
    ready = sum(1 for status in requirements if status in READY_REQUIREMENT_STATUSES)
    report.readiness_percent = round(0.0 if total == 0 else ready / total * 100, 2)
    db.add(report)
    return report


def update_requirement(
    db: Session,
    requirement: Requirement,
    *,
    changes: dict,
    user_id: str | None = None,
) -> Requirement:
    changed_fields: dict[str, dict[str, object | None]] = {}
    for field, value in changes.items():
        current_value = getattr(requirement, field)
        if current_value == value:
            continue
        changed_fields[field] = {
            "from": _serialize_detail(current_value),
            "to": _serialize_detail(value),
        }
        setattr(requirement, field, value)

    db.add(requirement)
    if changed_fields:
        log_action(
            db,
            action="requirement_updated",
            entity_type="requirement",
            entity_id=requirement.id,
            organization_id=requirement.organization_id,
            user_id=user_id,
            details={"report_id": requirement.report_id, "changes": changed_fields},
        )
    db.commit()
    db.refresh(requirement)
    return requirement


def sync_requirement_artifacts(
    db: Session,
    requirement: Requirement,
    *,
    user_id: str | None = None,
    commit: bool = True,
) -> Requirement:
    report = db.scalar(select(Report).where(Report.id == requirement.report_id)) if requirement.report_id else None
    fragments_query = select(DocumentFragment).where(DocumentFragment.organization_id == requirement.organization_id)
    if report is not None and report.selected_document_ids:
        fragments_query = fragments_query.where(DocumentFragment.document_id.in_(report.selected_document_ids))
    fragments = list(db.scalars(fragments_query))

    ranked_evidence = rank_evidence_candidates(
        db,
        requirement.text,
        fragments,
        requirement.category,
        exclude_fragment_id=requirement.source_fragment_id,
        limit=5,
    )
    confidence = derive_requirement_confidence(requirement.applicability_status, ranked_evidence)
    if requirement.applicability_status == ApplicabilityStatus.not_applicable:
        confidence = max(confidence, 0.85)

    derived_status = _derive_requirement_status(
        requirement.status,
        requirement.applicability_status,
        len(ranked_evidence),
        confidence,
    )
    derived_risk_level = _derive_risk_level(
        derived_status,
        confidence,
        requirement.applicability_status,
    )

    requirement.required_data = required_data_from_text(requirement.text)
    manual_lock_note = (
        "Статус требования зафиксирован вручную пользователем."
        if requirement.status in MANUAL_STATUS_LOCKS
        else "Статус требования пересчитан автоматически по evidence."
    )
    source_documents_count = len({fragment.document_id for fragment, _score in ranked_evidence if fragment.document_id})
    artifacts = build_requirement_artifacts(
        requirement_title=requirement.title,
        requirement_text=requirement.text,
        category=requirement.category,
        applicability_reason=requirement.applicability_reason,
        requirement_status=derived_status,
        confidence=confidence,
        risk_level=derived_risk_level,
        source_documents_count=source_documents_count,
        required_data=requirement.required_data,
        ranked_evidence=ranked_evidence,
        manual_lock_note=manual_lock_note,
    )
    requirement.found_data = artifacts.found_data
    requirement.confidence_score = confidence
    requirement.status = derived_status
    requirement.risk_level = derived_risk_level
    db.add(requirement)

    db.execute(delete(Evidence).where(Evidence.requirement_id == requirement.id))
    for fragment, score in ranked_evidence:
        db.add(
            Evidence(
                organization_id=requirement.organization_id,
                requirement_id=requirement.id,
                document_id=fragment.document_id,
                fragment_id=fragment.id,
                evidence_type="document_fragment",
                description=fragment.fragment_text[:250],
                confidence_score=score,
                status="candidate",
            )
        )

    explanation = get_requirement_explanation(db, requirement.id)
    if explanation is None:
        explanation = Explanation(
            organization_id=requirement.organization_id,
            requirement_id=requirement.id,
        )
    explanation.conclusion = artifacts.conclusion
    explanation.logic_json = artifacts.logic_json
    explanation.source_document_id = requirement.source_document_id or (ranked_evidence[0][0].document_id if ranked_evidence else None)
    explanation.source_fragment_id = requirement.source_fragment_id or (ranked_evidence[0][0].id if ranked_evidence else None)
    explanation.evidence_json = artifacts.evidence_payload
    explanation.confidence_score = confidence
    explanation.risk_level = derived_risk_level
    explanation.explanation_text = artifacts.explanation_text
    explanation.recommended_action = artifacts.recommended_action
    db.add(explanation)

    risk = db.scalar(
        select(Risk)
        .where(Risk.requirement_id == requirement.id, Risk.report_id == requirement.report_id)
        .order_by(Risk.created_at.desc())
    )
    needs_open_risk = derived_risk_level != RiskLevel.low and requirement.status not in {
        RequirementStatus.confirmed,
        RequirementStatus.not_applicable,
        RequirementStatus.included_in_report,
    }
    if needs_open_risk:
        if risk is None:
            risk = Risk(
                organization_id=requirement.organization_id,
                report_id=requirement.report_id,
                requirement_id=requirement.id,
                title=artifacts.risk_title,
                description=artifacts.risk_description,
                risk_level=derived_risk_level,
                status=RiskStatus.new,
                recommended_action=artifacts.recommended_action,
            )
        else:
            risk.title = artifacts.risk_title
            risk.description = artifacts.risk_description
            risk.risk_level = derived_risk_level
            risk.recommended_action = artifacts.recommended_action
            if risk.status == RiskStatus.resolved:
                risk.status = RiskStatus.needs_review
        db.add(risk)
    elif risk is not None and risk.status != RiskStatus.resolved:
        risk.status = RiskStatus.resolved
        risk.risk_level = derived_risk_level
        risk.description = (
            f"Риск автоматически закрыт после синхронизации требования. "
            f"Текущий статус требования: {requirement.status.value}."
        )
        risk.recommended_action = recommended_action_for_status(requirement.status)
        db.add(risk)

    db.flush()
    refresh_report_readiness(db, requirement.report_id)
    log_action(
        db,
        action="requirement_artifacts_refreshed",
        entity_type="requirement",
        entity_id=requirement.id,
        organization_id=requirement.organization_id,
        user_id=user_id,
        details={
            "report_id": requirement.report_id,
            "evidence_count": len(ranked_evidence),
            "status": requirement.status.value,
            "confidence_score": confidence,
            "risk_level": derived_risk_level.value,
        },
    )

    if commit:
        db.commit()
        db.refresh(requirement)
    return requirement


def bulk_update_requirements(
    db: Session,
    requirements: list[Requirement],
    *,
    changes: dict,
    user_id: str | None = None,
) -> list[Requirement]:
    normalized_changes = {field: value for field, value in changes.items()}
    if not requirements or not normalized_changes:
        return requirements

    updated_ids: list[str] = []
    for requirement in requirements:
        changed_any = False
        for field, value in normalized_changes.items():
            if getattr(requirement, field) == value:
                continue
            setattr(requirement, field, value)
            changed_any = True
        db.add(requirement)
        if changed_any:
            updated_ids.append(requirement.id)

    if updated_ids:
        log_action(
            db,
            action="requirement_bulk_updated",
            entity_type="requirement_batch",
            entity_id=updated_ids[0] if len(updated_ids) == 1 else None,
            organization_id=requirements[0].organization_id,
            user_id=user_id,
            details={
                "requirement_ids": updated_ids,
                "changes": {field: _serialize_detail(value) for field, value in normalized_changes.items()},
            },
        )
    db.commit()
    for requirement in requirements:
        db.refresh(requirement)
    return requirements


def set_requirement_status(
    db: Session,
    requirement: Requirement,
    status: RequirementStatus,
    *,
    user_id: str | None = None,
) -> Requirement:
    requirement = update_requirement(db, requirement, changes={"status": status}, user_id=user_id)
    log_action(
        db,
        action=f"requirement_{status.value}",
        entity_type="requirement",
        entity_id=requirement.id,
        organization_id=requirement.organization_id,
        user_id=user_id,
        details={"report_id": requirement.report_id, "status": status.value},
    )
    db.commit()
    db.refresh(requirement)
    return requirement
