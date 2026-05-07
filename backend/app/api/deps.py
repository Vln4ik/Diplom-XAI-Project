from __future__ import annotations

from collections.abc import Iterable

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.security import decode_token
from app.db.session import get_db_session
from app.models import MemberRole, OrganizationMember, User

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login")


def get_db() -> Session:
    yield from get_db_session()


def get_current_user(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)) -> User:
    try:
        payload = decode_token(token)
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token") from exc

    if payload.get("type") != "access":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token type")

    user = db.scalar(select(User).where(User.id == payload["sub"]))
    if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")
    return user


def get_membership(db: Session, *, organization_id: str, user_id: str) -> OrganizationMember | None:
    return db.scalar(
        select(OrganizationMember).where(
            OrganizationMember.organization_id == organization_id,
            OrganizationMember.user_id == user_id,
        )
    )


def ensure_org_access(
    db: Session,
    *,
    organization_id: str,
    user: User,
    allowed_roles: Iterable[MemberRole] | None = None,
) -> OrganizationMember | None:
    memberships = list(db.scalars(select(OrganizationMember).where(OrganizationMember.user_id == user.id)))
    if any(member.role == MemberRole.system_admin for member in memberships):
        return memberships[0] if memberships else None

    membership = get_membership(db, organization_id=organization_id, user_id=user.id)
    if membership is None:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Organization access denied")

    if allowed_roles and membership.role not in set(allowed_roles):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient role")
    return membership
