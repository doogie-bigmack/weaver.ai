from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path

from ..settings import AppSettings
from ..telemetry import log_security_event


@dataclass
class AuditEvent:
    ts: str
    user_id: str
    action: str
    detail: str


def log_event(event: AuditEvent, settings: AppSettings) -> None:
    """Log audit event to file.

    Args:
        event: Audit event to log
        settings: Application settings
    """
    path = Path(settings.audit_path)
    line = json.dumps(asdict(event))
    with path.open("a") as f:
        f.write(line + "\n")


def log_security_audit(
    action: str, user_id: str, detail: str, settings: AppSettings
) -> None:
    """Log security-critical audit event with optional signing.

    This function logs both to the audit file and telemetry system.
    If telemetry signing is enabled, events are cryptographically signed.

    Args:
        action: Action performed (e.g., "auth_failure", "policy_violation")
        user_id: User or agent ID
        detail: Additional details about the event
        settings: Application settings

    Example:
        log_security_audit(
            action="auth_failure",
            user_id="user@example.com",
            detail="Invalid JWT token",
            settings=app_settings
        )
    """
    # Create audit event
    timestamp = datetime.now(UTC).isoformat()
    event = AuditEvent(ts=timestamp, user_id=user_id, action=action, detail=detail)

    # Log to audit file
    log_event(event, settings)

    # Log to telemetry with signing if enabled
    signing_key = (
        settings.telemetry_signing_key if settings.telemetry_signing_enabled else None
    )

    log_security_event(
        event_type=action,
        signing_key=signing_key,
        user_id=user_id,
        detail=detail,
        timestamp=timestamp,
    )
