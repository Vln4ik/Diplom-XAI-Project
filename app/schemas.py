from __future__ import annotations

from typing import Any
from typing import Literal

from pydantic import BaseModel, Field


class ReportCreateRequest(BaseModel):
    title: str = Field(min_length=3, max_length=180)
    profile_id: str


class ReportCreateResponse(BaseModel):
    report_id: str
    status: str


class ValidationRequest(BaseModel):
    section_id: str
    decision: Literal["approved", "needs_revision", "rejected"]
    reviewer: str = "expert"
    comment: str | None = None


class ValidationResponse(BaseModel):
    report_id: str
    section_id: str
    decision: str
    status: str


class ChatModelInfo(BaseModel):
    id: str
    title: str
    description: str
    available: bool
    reason: str


class ChatMessageResponse(BaseModel):
    report_id: str = ""
    profile_id: str
    model_id: str
    actions: list[str]
    reply: str
    explanation: str = ""
    data: dict[str, Any] = Field(default_factory=dict)
