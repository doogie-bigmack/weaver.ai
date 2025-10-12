"""API request and response models."""

from __future__ import annotations

import re
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator


class QueryRequest(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    user_id: str = Field(..., min_length=1, max_length=256)
    query: str = Field(..., min_length=1, max_length=10000)
    tenant_id: str | None = Field(None, max_length=256)

    @field_validator("query")
    @classmethod
    def validate_query(cls, v: str) -> str:
        """Validate query input for security."""
        from weaver_ai.security.validation import SecurityValidator

        if not v or not v.strip():
            raise ValueError("Query cannot be empty")

        # Use comprehensive input validation
        try:
            v = SecurityValidator.sanitize_user_input(
                v,
                max_length=10000,
                allow_html=False,
                allow_newlines=True,
            )
        except ValueError as e:
            raise ValueError(f"Invalid query: {e}") from e

        # Additional checks for SQL injection
        if SecurityValidator.detect_sql_injection(v):
            raise ValueError("Potential SQL injection detected in query")

        # Check for Unicode spoofing
        if SecurityValidator.detect_unicode_spoofing(v):
            raise ValueError("Unicode spoofing characters detected in query")

        return v

    @field_validator("user_id")
    @classmethod
    def validate_user_id(cls, v: str) -> str:
        """Validate user_id format."""
        if not v or not v.strip():
            raise ValueError("User ID cannot be empty")

        # Allow alphanumeric, underscore, hyphen, and @ for email-like IDs
        if not re.match(r"^[a-zA-Z0-9_\-@\.]+$", v):
            raise ValueError("Invalid user ID format")

        return v

    @field_validator("tenant_id")
    @classmethod
    def validate_tenant_id(cls, v: str | None) -> str | None:
        """Validate tenant_id format."""
        if v is None:
            return v

        if not v.strip():
            return None

        # Allow alphanumeric, underscore, and hyphen
        if not re.match(r"^[a-zA-Z0-9_\-]+$", v):
            raise ValueError("Invalid tenant ID format")

        return v


class Citation(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    source: str = Field(..., min_length=1, max_length=1000)
    context: str | None = Field(None, max_length=5000)

    @field_validator("source")
    @classmethod
    def validate_source(cls, v: str) -> str:
        """Validate source field."""
        if not v or not v.strip():
            raise ValueError("Source cannot be empty")
        return v


class QueryResponse(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    answer: str = Field(..., min_length=1, max_length=50000)
    citations: list[Citation] = Field(default_factory=list, max_length=100)
    metrics: dict[str, Any] = Field(default_factory=dict)

    @field_validator("metrics")
    @classmethod
    def validate_metrics(cls, v: dict) -> dict:
        """Validate metrics dictionary."""
        # Limit the size of metrics to prevent abuse
        if len(str(v)) > 10000:
            raise ValueError("Metrics data too large")
        return v


class ErrorResponse(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    detail: str = Field(..., min_length=1, max_length=1000)


class TelemetryEvent(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    span: str = Field(..., min_length=1, max_length=256)
    attrs: dict[str, Any] = Field(default_factory=dict)
    ts: datetime

    @field_validator("span")
    @classmethod
    def validate_span(cls, v: str) -> str:
        """Validate span name."""
        if not re.match(r"^[a-zA-Z0-9_\-\.]+$", v):
            raise ValueError("Invalid span name format")
        return v

    @field_validator("attrs")
    @classmethod
    def validate_attrs(cls, v: dict) -> dict:
        """Validate attributes dictionary."""
        # Limit the size of attributes to prevent abuse
        if len(str(v)) > 10000:
            raise ValueError("Attributes data too large")
        return v
