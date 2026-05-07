from __future__ import annotations

from pydantic import BaseModel

from app.models.enums import ApplicabilityStatus, RequirementStatus, RiskLevel
from app.schemas.common import SchemaModel, TimestampedModel


class RequirementResponse(TimestampedModel):
    organization_id: str
    report_id: str | None
    regulator: str
    category: str
    title: str
    text: str
    source_document_id: str | None
    source_fragment_id: str | None
    applicability_status: ApplicabilityStatus
    applicability_reason: str | None
    required_data: list[str]
    found_data: list[str]
    status: RequirementStatus
    confidence_score: float
    risk_level: RiskLevel
    user_comment: str | None


class RequirementUpdate(BaseModel):
    title: str | None = None
    category: str | None = None
    text: str | None = None
    applicability_status: ApplicabilityStatus | None = None
    applicability_reason: str | None = None
    user_comment: str | None = None
    status: RequirementStatus | None = None


class RequirementBulkUpdate(BaseModel):
    requirement_ids: list[str]
    status: RequirementStatus | None = None
    applicability_status: ApplicabilityStatus | None = None
    user_comment: str | None = None


class ExplanationResponse(TimestampedModel):
    organization_id: str
    requirement_id: str
    report_section_id: str | None
    conclusion: str
    logic_json: list[str]
    source_document_id: str | None
    source_fragment_id: str | None
    evidence_json: list[dict]
    confidence_score: float
    risk_level: RiskLevel
    explanation_text: str
    recommended_action: str | None
