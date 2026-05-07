from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.security import create_access_token, create_refresh_token, hash_password, verify_password
from app.models import User, UserStatus


def authenticate_user(db: Session, email: str, password: str) -> User | None:
    user = db.scalar(select(User).where(User.email == email.lower()))
    if user is None or user.status == UserStatus.blocked:
        return None
    if not verify_password(password, user.password_hash):
        return None
    user.last_login_at = datetime.now(UTC)
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def issue_tokens(user: User) -> dict[str, str]:
    return {
        "access_token": create_access_token(user.id),
        "refresh_token": create_refresh_token(user.id),
    }


def create_user(db: Session, *, full_name: str, email: str, password: str, status: UserStatus = UserStatus.active) -> User:
    user = User(full_name=full_name, email=email.lower(), password_hash=hash_password(password), status=status)
    db.add(user)
    db.commit()
    db.refresh(user)
    return user
