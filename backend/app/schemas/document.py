from __future__ import annotations

from datetime import date, datetime

from pydantic import BaseModel

from app.models.enums import DocumentCategory, DocumentStatus, FragmentType
from app.schemas.common import SchemaModel, TimestampedModel


class DocumentResponse(TimestampedModel):
    organization_id: str
    uploaded_by_id: str | None
    file_name: str
    original_file_name: str
    file_type: str
    file_size: int
    category: DocumentCategory
    storage_path: str
    status: DocumentStatus
    extracted_text: str | None
    page_count: int | None
    processed_at: datetime | None
    version: int
    tags: list[str]
    document_date: date | None
    validity_until: date | None
    processing_error: str | None


class DocumentFragmentResponse(SchemaModel):
    id: str
    document_id: str
    fragment_text: str
    search_text: str
    page_number: int | None
    sheet_name: str | None
    row_start: int | None
    row_end: int | None
    paragraph_number: int | None
    fragment_type: FragmentType


class DocumentProcessResponse(BaseModel):
    document_id: str
    status: DocumentStatus
    task_id: str | None = None


class DocumentSearchMatchResponse(BaseModel):
    fragment_id: str
    document_id: str
    document_name: str
    fragment_text: str
    score: float
    keyword_score: float | None = None
    vector_score: float | None = None
    page_number: int | None = None
    sheet_name: str | None = None
