from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from app.api.deps import ensure_org_access, get_current_user, get_db, get_membership
from app.models import (
    Document,
    DocumentStatus,
    MemberRole,
    MemberStatus,
    Notification,
    NotificationStatus,
    Organization,
    OrganizationMember,
    Report,
    ReportStatus,
    Requirement,
    RequirementStatus,
    Risk,
    RiskLevel,
    RiskStatus,
    User,
)
from app.schemas import (
    DashboardResponse,
    MemberCreate,
    MemberResponse,
    MemberUpdate,
    OrganizationAutofillResponse,
    OrganizationCreate,
    OrganizationResponse,
    OrganizationUpdate,
)
from app.services.audit import log_action
from app.services.auth import create_user
from app.services.organization_autofill import suggest_organization_profile_from_documents

router = APIRouter(prefix="/organizations", tags=["organizations"])


def _document_readiness_score(status: DocumentStatus) -> float:
    scores = {
        DocumentStatus.uploaded: 10.0,
        DocumentStatus.queued: 28.0,
        DocumentStatus.processing: 68.0,
        DocumentStatus.processed: 100.0,
        DocumentStatus.requires_review: 92.0,
        DocumentStatus.failed: 0.0,
        DocumentStatus.outdated: 45.0,
        DocumentStatus.archived: 0.0,
    }
    return scores.get(status, 0.0)


def _report_readiness_score(status: ReportStatus, readiness_percent: float | None) -> float:
    if readiness_percent and readiness_percent > 0:
        return min(100.0, max(0.0, readiness_percent))

    scores = {
        ReportStatus.draft: 12.0,
        ReportStatus.analyzing: 58.0,
        ReportStatus.requires_review: 72.0,
        ReportStatus.in_revision: 66.0,
        ReportStatus.awaiting_approval: 88.0,
        ReportStatus.approved: 100.0,
        ReportStatus.exported: 100.0,
        ReportStatus.archived: 100.0,
    }
    return scores.get(status, 0.0)


def _requirement_readiness_score(status: RequirementStatus) -> float:
    scores = {
        RequirementStatus.new: 8.0,
        RequirementStatus.applicable: 45.0,
        RequirementStatus.not_applicable: 100.0,
        RequirementStatus.needs_clarification: 25.0,
        RequirementStatus.data_found: 75.0,
        RequirementStatus.data_partial: 48.0,
        RequirementStatus.data_missing: 18.0,
        RequirementStatus.confirmed: 100.0,
        RequirementStatus.rejected: 100.0,
        RequirementStatus.included_in_report: 100.0,
        RequirementStatus.archived: 100.0,
    }
    return scores.get(status, 0.0)


def _risk_penalty(risk_level: RiskLevel) -> float:
    penalties = {
        RiskLevel.low: 5.0,
        RiskLevel.medium: 12.0,
        RiskLevel.high: 24.0,
        RiskLevel.critical: 35.0,
    }
    return penalties.get(risk_level, 0.0)


def _mean(values: list[float]) -> float:
    return sum(values) / len(values) if values else 0.0


@router.get("", response_model=list[OrganizationResponse])
def list_organizations(user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> list[Organization]:
    memberships = list(db.scalars(select(OrganizationMember).where(OrganizationMember.user_id == user.id)))
    if any(member.role == MemberRole.system_admin for member in memberships):
        return list(db.scalars(select(Organization).order_by(Organization.created_at)))
    organization_ids = [member.organization_id for member in memberships]
    if not organization_ids:
        return []
    return list(db.scalars(select(Organization).where(Organization.id.in_(organization_ids)).order_by(Organization.created_at)))


@router.post("", response_model=OrganizationResponse, status_code=status.HTTP_201_CREATED)
def create_organization(
    payload: OrganizationCreate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Organization:
    organization = Organization(**payload.model_dump())
    db.add(organization)
    db.commit()
    db.refresh(organization)

    membership = get_membership(db, organization_id=organization.id, user_id=user.id)
    if membership is None:
        db.add(
            OrganizationMember(
                organization_id=organization.id,
                user_id=user.id,
                role=MemberRole.org_admin,
                status=MemberStatus.active,
            )
        )
        db.commit()

    log_action(
        db,
        action="organization_created",
        entity_type="organization",
        entity_id=organization.id,
        organization_id=organization.id,
        user_id=user.id,
    )
    db.commit()
    return organization


@router.get("/{organization_id}", response_model=OrganizationResponse)
def get_organization(
    organization_id: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Organization:
    ensure_org_access(db, organization_id=organization_id, user=user)
    organization = db.scalar(select(Organization).where(Organization.id == organization_id))
    if organization is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Organization not found")
    return organization


@router.patch("/{organization_id}", response_model=OrganizationResponse)
def update_organization(
    organization_id: str,
    payload: OrganizationUpdate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Organization:
    ensure_org_access(db, organization_id=organization_id, user=user, allowed_roles=[MemberRole.org_admin, MemberRole.system_admin])
    organization = db.scalar(select(Organization).where(Organization.id == organization_id))
    if organization is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Organization not found")
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(organization, field, value)
    db.add(organization)
    db.commit()
    db.refresh(organization)
    return organization


@router.post("/{organization_id}/autofill", response_model=OrganizationAutofillResponse)
def autofill_organization_from_documents(
    organization_id: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> OrganizationAutofillResponse:
    ensure_org_access(db, organization_id=organization_id, user=user, allowed_roles=[MemberRole.org_admin, MemberRole.specialist, MemberRole.system_admin])
    organization = db.scalar(select(Organization).where(Organization.id == organization_id))
    if organization is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Organization not found")
    return suggest_organization_profile_from_documents(db, organization_id)


@router.delete("/{organization_id}", response_model=OrganizationResponse)
def delete_organization(
    organization_id: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> OrganizationResponse:
    ensure_org_access(db, organization_id=organization_id, user=user, allowed_roles=[MemberRole.org_admin, MemberRole.system_admin])
    organization = db.scalar(select(Organization).where(Organization.id == organization_id))
    if organization is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Organization not found")

    snapshot = OrganizationResponse.model_validate(organization)
    db.execute(delete(Organization).where(Organization.id == organization_id))
    db.commit()
    return snapshot


@router.get("/{organization_id}/dashboard", response_model=DashboardResponse)
def get_dashboard(
    organization_id: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> DashboardResponse:
    ensure_org_access(db, organization_id=organization_id, user=user)
    organization = db.scalar(select(Organization).where(Organization.id == organization_id))
    if organization is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Organization not found")

    document_statuses = list(db.scalars(select(Document.status).where(Document.organization_id == organization_id)))
    report_rows = list(db.execute(select(Report.status, Report.readiness_percent).where(Report.organization_id == organization_id)))
    requirement_statuses = list(db.scalars(select(Requirement.status).where(Requirement.organization_id == organization_id)))
    risk_rows = list(db.execute(select(Risk.risk_level, Risk.status).where(Risk.organization_id == organization_id)))

    active_reports = len(report_rows)
    reports_awaiting_approval = sum(1 for status_value, _readiness in report_rows if status_value == ReportStatus.awaiting_approval)
    processed_documents = sum(1 for status_value in document_statuses if status_value in [DocumentStatus.processed, DocumentStatus.requires_review])
    total_requirements = len(requirement_statuses)
    unresolved_risk_statuses = {RiskStatus.new, RiskStatus.in_progress, RiskStatus.needs_review}
    unresolved_risks = [(risk_level, status_value) for risk_level, status_value in risk_rows if status_value in unresolved_risk_statuses]
    high_risks = sum(1 for risk_level, _status_value in unresolved_risks if risk_level in [RiskLevel.high, RiskLevel.critical])

    document_progress = _mean([_document_readiness_score(status_value) for status_value in document_statuses])
    report_progress = _mean([_report_readiness_score(status_value, readiness_percent) for status_value, readiness_percent in report_rows])
    requirement_progress = _mean([_requirement_readiness_score(status_value) for status_value in requirement_statuses])
    risk_progress = max(0.0, 100.0 - sum(_risk_penalty(risk_level) for risk_level, _status_value in unresolved_risks)) if report_rows else 0.0
    readiness = round(
        document_progress * 0.35 + report_progress * 0.25 + requirement_progress * 0.25 + risk_progress * 0.15,
        2,
    )
    unread_notifications = db.scalar(
        select(func.count()).select_from(Notification).where(
            Notification.organization_id == organization_id,
            Notification.user_id == user.id,
            Notification.status == NotificationStatus.unread,
        )
    ) or 0
    return DashboardResponse(
        organization_id=organization.id,
        organization_name=organization.name,
        active_reports=active_reports,
        reports_awaiting_approval=reports_awaiting_approval,
        processed_documents=processed_documents,
        total_requirements=total_requirements,
        high_risks=high_risks,
        readiness_percent=readiness,
        unread_notifications=unread_notifications,
    )


@router.get("/{organization_id}/members", response_model=list[MemberResponse])
def list_members(
    organization_id: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[MemberResponse]:
    ensure_org_access(db, organization_id=organization_id, user=user)
    members = list(db.scalars(select(OrganizationMember).where(OrganizationMember.organization_id == organization_id).order_by(OrganizationMember.created_at)))
    return [
        MemberResponse(
            id=member.id,
            organization_id=member.organization_id,
            user_id=member.user_id,
            role=member.role,
            status=member.status,
            email=member.user.email,
            full_name=member.user.full_name,
        )
        for member in members
    ]


@router.post("/{organization_id}/members", response_model=MemberResponse, status_code=status.HTTP_201_CREATED)
def create_member(
    organization_id: str,
    payload: MemberCreate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> MemberResponse:
    ensure_org_access(db, organization_id=organization_id, user=user, allowed_roles=[MemberRole.org_admin, MemberRole.system_admin])
    existing_user = db.scalar(select(User).where(User.email == payload.email.lower()))
    if existing_user is None:
        existing_user = create_user(
            db,
            full_name=payload.full_name,
            email=payload.email,
            password=payload.password or "ChangeMe123!",
        )

    member = get_membership(db, organization_id=organization_id, user_id=existing_user.id)
    if member is None:
        member = OrganizationMember(
            organization_id=organization_id,
            user_id=existing_user.id,
            role=payload.role,
            status=MemberStatus.active,
        )
        db.add(member)
        db.commit()
        db.refresh(member)

    return MemberResponse(
        id=member.id,
        organization_id=member.organization_id,
        user_id=member.user_id,
        role=member.role,
        status=member.status,
        email=existing_user.email,
        full_name=existing_user.full_name,
    )


@router.patch("/{organization_id}/members/{member_id}", response_model=MemberResponse)
def update_member(
    organization_id: str,
    member_id: str,
    payload: MemberUpdate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> MemberResponse:
    ensure_org_access(db, organization_id=organization_id, user=user, allowed_roles=[MemberRole.org_admin, MemberRole.system_admin])
    member = db.scalar(select(OrganizationMember).where(OrganizationMember.id == member_id, OrganizationMember.organization_id == organization_id))
    if member is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Member not found")
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(member, field, value)
    db.add(member)
    db.commit()
    db.refresh(member)
    return MemberResponse(
        id=member.id,
        organization_id=member.organization_id,
        user_id=member.user_id,
        role=member.role,
        status=member.status,
        email=member.user.email,
        full_name=member.user.full_name,
    )
