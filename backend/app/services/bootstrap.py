from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models import MemberRole, MemberStatus, Organization, OrganizationMember, OrganizationType, User
from app.services.auth import create_user


def bootstrap_system_admin(db: Session) -> None:
    settings = get_settings()
    if not settings.bootstrap_admin_email or not settings.bootstrap_admin_password:
        return

    user = db.scalar(select(User).where(User.email == settings.bootstrap_admin_email.lower()))
    if user is None:
        user = create_user(
            db,
            full_name=settings.bootstrap_admin_full_name,
            email=settings.bootstrap_admin_email,
            password=settings.bootstrap_admin_password,
        )

    organization = db.scalar(select(Organization).where(Organization.name == "System Workspace"))
    if organization is None:
        organization = Organization(name="System Workspace", organization_type=OrganizationType.other)
        db.add(organization)
        db.commit()
        db.refresh(organization)

    member = db.scalar(
        select(OrganizationMember).where(
            OrganizationMember.organization_id == organization.id,
            OrganizationMember.user_id == user.id,
        )
    )
    if member is None:
        db.add(
            OrganizationMember(
                organization_id=organization.id,
                user_id=user.id,
                role=MemberRole.system_admin,
                status=MemberStatus.active,
            )
        )
        db.commit()
