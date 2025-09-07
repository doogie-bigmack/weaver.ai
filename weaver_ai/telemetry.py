from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime
from typing import Any, Iterator

from pydantic import BaseModel

from .settings import AppSettings


class TelemetryEvent(BaseModel):
    span: str
    attrs: dict[str, Any]
    ts: datetime


@contextmanager
def start_span(name: str, **attrs: Any) -> Iterator[None]:
    yield


def setup_otel(service_name: str) -> None:  # pragma: no cover - simple stub
    return None
