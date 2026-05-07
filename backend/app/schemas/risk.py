from __future__ import annotations

from pydantic import BaseModel

from app.models.enums import RiskLevel, RiskStatus
from app.schemas.common import TimestampedModel


class RiskResponse(TimestampedModel):
    organization_id: str
    report_id: str | None
    requirement_id: str | None
    title: str
    description: str
    risk_level: RiskLevel
    status: RiskStatus
    recommended_action: str | None
    assigned_to_id: str | None


class RiskUpdate(BaseModel):
    title: str | None = None
    description: str | None = None
    risk_level: RiskLevel | None = None
    status: RiskStatus | None = None
    recommended_action: str | None = None
    assigned_to_id: str | None = None
