from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import ensure_org_access, get_current_user, get_db
from app.models import Notification, NotificationStatus, User
from app.schemas import NotificationMarkAllResponse, NotificationResponse
from app.services.notifications import list_notifications_for_user, mark_all_notifications_read, mark_notification_read

router = APIRouter(tags=["notifications"])


@router.get("/organizations/{organization_id}/notifications", response_model=list[NotificationResponse])
def list_notifications(
    organization_id: str,
    only_unread: bool = Query(default=False),
    limit: int = Query(default=50, ge=1, le=200),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[Notification]:
    ensure_org_access(db, organization_id=organization_id, user=user)
    return list_notifications_for_user(
        db,
        user_id=user.id,
        organization_id=organization_id,
        status=NotificationStatus.unread if only_unread else None,
        limit=limit,
    )


@router.post("/notifications/{notification_id}/read", response_model=NotificationResponse)
def read_notification(
    notification_id: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Notification:
    notification = db.scalar(select(Notification).where(Notification.id == notification_id))
    if notification is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Notification not found")
    if notification.user_id != user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Notification access denied")
    if notification.organization_id is not None:
        ensure_org_access(db, organization_id=notification.organization_id, user=user)
    return mark_notification_read(db, notification)


@router.post("/organizations/{organization_id}/notifications/read-all", response_model=NotificationMarkAllResponse)
def read_all_notifications(
    organization_id: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> NotificationMarkAllResponse:
    ensure_org_access(db, organization_id=organization_id, user=user)
    updated = mark_all_notifications_read(db, user_id=user.id, organization_id=organization_id)
    return NotificationMarkAllResponse(updated=updated)
