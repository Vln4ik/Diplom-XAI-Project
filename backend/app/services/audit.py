from __future__ import annotations

from sqlalchemy.orm import Session

from app.models import AuditLog


def log_action(
    db: Session,
    *,
    action: str,
    entity_type: str,
    entity_id: str | None = None,
    organization_id: str | None = None,
    user_id: str | None = None,
    details: dict | None = None,
) -> None:
    db.add(
        AuditLog(
            action=action,
            entity_type=entity_type,
            entity_id=entity_id,
            organization_id=organization_id,
            user_id=user_id,
            details=details or {},
        )
    )
