from __future__ import annotations

from datetime import datetime

from app.schemas.common import SchemaModel


class AuditLogResponse(SchemaModel):
    id: str
    organization_id: str | None
    user_id: str | None
    user_email: str | None = None
    user_full_name: str | None = None
    entity_type: str
    entity_id: str | None
    action: str
    details: dict
    created_at: datetime
