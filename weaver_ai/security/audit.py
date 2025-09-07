from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path

from ..settings import AppSettings


@dataclass
class AuditEvent:
    ts: str
    user_id: str
    action: str
    detail: str


def log_event(event: AuditEvent, settings: AppSettings) -> None:
    path = Path(settings.audit_path)
    line = json.dumps(asdict(event))
    with path.open("a") as f:
        f.write(line + "\n")
