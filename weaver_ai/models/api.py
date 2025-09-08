"""API request and response models."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class QueryRequest(BaseModel):
    user_id: str
    query: str
    tenant_id: str | None = None


class Citation(BaseModel):
    source: str
    context: str | None = None


class QueryResponse(BaseModel):
    answer: str
    citations: list[Citation] = Field(default_factory=list)
    metrics: dict[str, Any] = Field(default_factory=dict)


class ErrorResponse(BaseModel):
    detail: str


class TelemetryEvent(BaseModel):
    span: str
    attrs: dict[str, Any] = Field(default_factory=dict)
    ts: datetime