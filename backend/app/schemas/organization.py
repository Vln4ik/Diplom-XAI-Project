from __future__ import annotations

from pydantic import BaseModel, Field

from app.models.enums import MemberRole, MemberStatus, OrganizationType
from app.schemas.common import SchemaModel, TimestampedModel


class OrganizationCreate(BaseModel):
    name: str
    short_name: str | None = None
    inn: str | None = None
    kpp: str | None = None
    ogrn: str | None = None
    legal_address: str | None = None
    actual_address: str | None = None
    organization_type: OrganizationType = OrganizationType.educational
    okved: str | None = None
    website: str | None = None
    email: str | None = None
    phone: str | None = None
    director_name: str | None = None
    responsible_person: str | None = None
    profile_json: dict = Field(default_factory=dict)


class OrganizationUpdate(BaseModel):
    name: str | None = None
    short_name: str | None = None
    inn: str | None = None
    kpp: str | None = None
    ogrn: str | None = None
    legal_address: str | None = None
    actual_address: str | None = None
    organization_type: OrganizationType | None = None
    okved: str | None = None
    website: str | None = None
    email: str | None = None
    phone: str | None = None
    director_name: str | None = None
    responsible_person: str | None = None
    profile_json: dict | None = None


class OrganizationResponse(TimestampedModel):
    name: str
    short_name: str | None
    inn: str | None
    kpp: str | None
    ogrn: str | None
    legal_address: str | None
    actual_address: str | None
    organization_type: OrganizationType
    okved: str | None
    website: str | None
    email: str | None
    phone: str | None
    director_name: str | None
    responsible_person: str | None
    profile_json: dict


class MemberCreate(BaseModel):
    full_name: str
    email: str
    password: str | None = None
    role: MemberRole = MemberRole.specialist


class MemberUpdate(BaseModel):
    role: MemberRole | None = None
    status: MemberStatus | None = None


class MemberResponse(SchemaModel):
    id: str
    organization_id: str
    user_id: str
    role: MemberRole
    status: MemberStatus
    email: str
    full_name: str


class DashboardResponse(BaseModel):
    organization_id: str
    organization_name: str
    active_reports: int
    reports_awaiting_approval: int
    processed_documents: int
    total_requirements: int
    high_risks: int
    readiness_percent: float
    unread_notifications: int
