from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import ensure_org_access, get_current_user, get_db
from app.models import AuditLog, User
from app.schemas import AuditLogResponse

router = APIRouter(tags=["audit"])


@router.get("/organizations/{organization_id}/audit-logs", response_model=list[AuditLogResponse])
def list_audit_logs(
    organization_id: str,
    entity_type: str | None = None,
    action: str | None = None,
    limit: int = Query(default=100, ge=1, le=300),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[AuditLogResponse]:
    ensure_org_access(db, organization_id=organization_id, user=user)
    query = select(AuditLog).where(AuditLog.organization_id == organization_id)
    if entity_type:
        query = query.where(AuditLog.entity_type == entity_type)
    if action:
        query = query.where(AuditLog.action == action)
    logs = list(db.scalars(query.order_by(AuditLog.created_at.desc()).limit(limit)))
    user_ids = [item.user_id for item in logs if item.user_id]
    users = {
        item.id: item
        for item in db.scalars(select(User).where(User.id.in_(user_ids)))
    } if user_ids else {}
    return [
        AuditLogResponse(
            id=log.id,
            organization_id=log.organization_id,
            user_id=log.user_id,
            user_email=users[log.user_id].email if log.user_id in users else None,
            user_full_name=users[log.user_id].full_name if log.user_id in users else None,
            entity_type=log.entity_type,
            entity_id=log.entity_id,
            action=log.action,
            details=log.details,
            created_at=log.created_at,
        )
        for log in logs
    ]
