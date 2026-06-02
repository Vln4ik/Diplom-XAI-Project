from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel

from app.schemas.common import TimestampedModel


class EstimateExpertiseDecisionRequest(BaseModel):
    comment: str | None = None


class EstimateExpertiseDecisionSummary(BaseModel):
    status: str
    label: str
    updated_at: datetime
    replacement_file_name: str | None = None
    replacement_progress: int = 0
    decision_type: str
    comment: str | None = None


class EstimateExpertiseDecisionLogResponse(TimestampedModel):
    organization_id: str
    report_id: str
    report_title: str
    report_type: str
    workflow_id: str
    finding_id: str
    finding_title: str
    finding_description: str
    finding_severity: str
    stage_key: str
    stage_title: str
    document_id: str | None = None
    document_name: str
    decision_status: str
    decision_type: str
    decision_label: str
    comment: str | None = None
    normative_basis: str
    source_ref: str
    recommendation: str
    confidence_score: float
    xai_summary: list[str]


class EstimateExpertiseFindingResponse(TimestampedModel):
    stage_id: str | None = None
    stage_key: str
    stage_title: str
    document_id: str | None = None
    document_name: str
    title: str
    description: str
    severity: str
    confidence_score: float
    normative_basis: str
    source_ref: str
    recommendation: str
    xai_summary: list[str]
    status: str
    decision: EstimateExpertiseDecisionSummary | None = None


class EstimateExpertiseStageResponse(TimestampedModel):
    stage_key: str
    title: str
    short_title: str
    order_number: int
    status: str
    progress: float
    checked_files: int
    total_files: int
    findings_count: int
    findings: list[EstimateExpertiseFindingResponse]


class EstimateExpertiseWorkflowResponse(TimestampedModel):
    organization_id: str
    report_id: str
    status: str
    progress: float
    eta_seconds: int
    checked_files: int
    total_files: int
    unresolved_findings: int
    current_stage_key: str | None = None
    model_version: str
    rule_version: str
    stages: list[EstimateExpertiseStageResponse]
