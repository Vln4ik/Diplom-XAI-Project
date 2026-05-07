from __future__ import annotations

from datetime import date, datetime

from pydantic import BaseModel, ConfigDict


class SchemaModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class MessageResponse(BaseModel):
    message: str


class TimestampedModel(SchemaModel):
    id: str
    created_at: datetime
    updated_at: datetime


class DateRange(BaseModel):
    period_start: date | None = None
    period_end: date | None = None
