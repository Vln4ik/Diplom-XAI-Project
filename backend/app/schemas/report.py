from __future__ import annotations

from datetime import date

from pydantic import BaseModel, Field

from app.models.enums import ExportStatus, ExportType, ReportStatus
from app.schemas.common import SchemaModel, TimestampedModel


class ReportCreate(BaseModel):
    title: str
    regulator: str = "rosobrnadzor"
    report_type: str = "readiness_report"
    period_start: date | None = None
    period_end: date | None = None
    responsible_user_id: str | None = None
    comment: str | None = None
    selected_document_ids: list[str] = Field(default_factory=list)


class ReportUpdate(BaseModel):
    title: str | None = None
    report_type: str | None = None
    status: ReportStatus | None = None
    responsible_user_id: str | None = None
    comment: str | None = None
    selected_document_ids: list[str] | None = None


class ReportResponse(TimestampedModel):
    organization_id: str
    title: str
    regulator: str
    report_type: str
    period_start: date | None
    period_end: date | None
    status: ReportStatus
    readiness_percent: float
    responsible_user_id: str | None
    comment: str | None
    selected_document_ids: list[str]


class ReportSectionResponse(TimestampedModel):
    organization_id: str
    report_id: str
    title: str
    content: str
    order_number: int
    status: str
    source_requirement_ids: list[str]


class ReportSectionUpdate(BaseModel):
    title: str | None = None
    content: str | None = None
    status: str | None = None


class ExportFileResponse(TimestampedModel):
    organization_id: str
    report_id: str | None
    created_by_id: str | None
    export_type: ExportType
    file_name: str
    storage_path: str
    status: ExportStatus


class ReportMatrixRowResponse(BaseModel):
    requirement_id: str
    category: str
    title: str
    text: str
    applicability_status: str
    source_document_name: str | None = None
    source_fragment_text: str | None = None
    required_data: list[str]
    found_data: list[str]
    evidence: list[dict]
    status: str
    confidence_score: float
    risk_level: str
    system_comment: str | None = None
    user_comment: str | None = None
    included_in_report: bool


class ReportVersionResponse(TimestampedModel):
    organization_id: str
    report_id: str
    version_number: int
    created_by_id: str | None
    report_status: str
    title: str
    report_type: str
    readiness_percent: float
    comment: str | None
    sections_json: list[dict]
    matrix_json: list[dict]
    explanations_json: list[dict]
