from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.deps import ensure_org_access, get_current_user, get_db, get_membership
from app.models import (
    Document,
    MemberRole,
    MemberStatus,
    Notification,
    NotificationStatus,
    Organization,
    OrganizationMember,
    Report,
    ReportStatus,
    Requirement,
    Risk,
    RiskLevel,
    User,
)
from app.schemas import (
    DashboardResponse,
    MemberCreate,
    MemberResponse,
    MemberUpdate,
    OrganizationCreate,
    OrganizationResponse,
    OrganizationUpdate,
)
from app.services.audit import log_action
from app.services.auth import create_user

router = APIRouter(prefix="/organizations", tags=["organizations"])


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

    active_reports = db.scalar(select(func.count()).select_from(Report).where(Report.organization_id == organization_id)) or 0
    reports_awaiting_approval = db.scalar(
        select(func.count()).select_from(Report).where(
            Report.organization_id == organization_id,
            Report.status == ReportStatus.awaiting_approval,
        )
    ) or 0
    processed_documents = db.scalar(
        select(func.count()).select_from(Document).where(Document.organization_id == organization_id)
    )
    total_requirements = db.scalar(select(func.count()).select_from(Requirement).where(Requirement.organization_id == organization_id)) or 0
    high_risks = db.scalar(
        select(func.count()).select_from(Risk).where(Risk.organization_id == organization_id, Risk.risk_level.in_([RiskLevel.high, RiskLevel.critical]))
    ) or 0
    readiness_values = list(db.scalars(select(Report.readiness_percent).where(Report.organization_id == organization_id)))
    readiness = round(sum(readiness_values) / len(readiness_values), 2) if readiness_values else 0.0
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
        processed_documents=processed_documents or 0,
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
