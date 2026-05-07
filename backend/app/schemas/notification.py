from __future__ import annotations

from pydantic import BaseModel

from app.models.enums import NotificationStatus
from app.schemas.common import TimestampedModel


class NotificationResponse(TimestampedModel):
    organization_id: str | None
    user_id: str | None
    title: str
    body: str
    status: NotificationStatus


class NotificationMarkAllResponse(BaseModel):
    updated: int
