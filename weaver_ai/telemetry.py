"""Telemetry and observability using Pydantic Logfire."""

from __future__ import annotations

import hashlib
import json
import logging
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, datetime
from typing import Any

import jwt

try:
    import logfire

    LOGFIRE_AVAILABLE = True
except ImportError:
    LOGFIRE_AVAILABLE = False
    logfire = None  # type: ignore[assignment]

from pydantic import BaseModel

logger = logging.getLogger(__name__)


class TelemetryConfig(BaseModel):
    """Configuration for telemetry."""

    enabled: bool = True
    service_name: str = "weaver-ai"
    environment: str = "development"
    logfire_token: str | None = None
    send_to_logfire: bool = False  # Set to True to send to Logfire cloud
    signing_enabled: bool = True  # Sign critical security events
    signing_key: str | None = None  # RSA private key for signing


class SignedEvent(BaseModel):
    """Signed telemetry event for tamper-evident audit trails."""

    timestamp: str
    event_type: str
    data: dict[str, Any]
    signature: str
    event_hash: str  # SHA-256 hash of event data


def configure_telemetry(config: TelemetryConfig) -> None:
    """Configure Logfire telemetry.

    Args:
        config: Telemetry configuration
    """
    if not config.enabled:
        logger.info("Telemetry disabled")
        return

    if not LOGFIRE_AVAILABLE:
        logger.warning(
            "Logfire not available - install with: pip install logfire>=0.49.0"
        )
        return

    try:
        # Configure Logfire
        logfire.configure(
            service_name=config.service_name,
            service_version="0.1.0",
            environment=config.environment,
            token=config.logfire_token if config.send_to_logfire else None,
            send_to_logfire=config.send_to_logfire,
            console=logfire.ConsoleOptions(
                colors="auto",
                verbose=True if config.environment == "development" else False,
            ),
        )

        logger.info(
            f"Logfire telemetry configured: service={config.service_name}, "
            f"env={config.environment}, cloud={'enabled' if config.send_to_logfire else 'disabled'}"
        )
    except Exception as e:
        logger.error(f"Failed to configure Logfire: {e}")


def instrument_all() -> None:
    """Auto-instrument common libraries used by weaver.ai.

    This function should be called after configure_telemetry().
    """
    if not LOGFIRE_AVAILABLE:
        return

    try:
        # Instrument FastAPI (will be applied when app is created)
        logger.debug("Logfire auto-instrumentation enabled for FastAPI")

        # Instrument Redis operations
        try:
            logfire.instrument_redis()
            logger.debug("Logfire instrumentation enabled for Redis")
        except Exception as e:
            logger.warning(f"Could not instrument Redis: {e}")

        # Instrument HTTPX (for model provider API calls)
        try:
            logfire.instrument_httpx()
            logger.debug("Logfire instrumentation enabled for HTTPX")
        except Exception as e:
            logger.warning(f"Could not instrument HTTPX: {e}")

        # Instrument system metrics (CPU, memory, disk)
        try:
            logfire.instrument_system_metrics()
            logger.debug("Logfire system metrics instrumentation enabled")
        except Exception as e:
            logger.warning(f"Could not instrument system metrics: {e}")

        logger.info("Logfire auto-instrumentation completed")
    except Exception as e:
        logger.error(f"Failed to auto-instrument with Logfire: {e}")


@contextmanager
def start_span(name: str, **attrs: Any) -> Iterator[None]:
    """Create a telemetry span for tracing operations.

    Args:
        name: Span name
        **attrs: Additional span attributes

    Yields:
        None
    """
    if not LOGFIRE_AVAILABLE or logfire is None:
        # Fallback to no-op if Logfire not available
        yield
        return

    with logfire.span(name, **attrs):
        yield


def log_info(message: str, **attrs: Any) -> None:
    """Log an info-level message with structured attributes.

    Args:
        message: Log message
        **attrs: Additional structured attributes
    """
    if LOGFIRE_AVAILABLE and logfire is not None:
        logfire.info(message, **attrs)
    else:
        logger.info(f"{message} {attrs}")


def log_error(message: str, **attrs: Any) -> None:
    """Log an error-level message with structured attributes.

    Args:
        message: Log message
        **attrs: Additional structured attributes
    """
    if LOGFIRE_AVAILABLE and logfire is not None:
        logfire.error(message, **attrs)
    else:
        logger.error(f"{message} {attrs}")


def log_warning(message: str, **attrs: Any) -> None:
    """Log a warning-level message with structured attributes.

    Args:
        message: Log message
        **attrs: Additional structured attributes
    """
    if LOGFIRE_AVAILABLE and logfire is not None:
        logfire.warn(message, **attrs)
    else:
        logger.warning(f"{message} {attrs}")


def _compute_event_hash(event_data: dict[str, Any]) -> str:
    """Compute SHA-256 hash of event data for integrity verification.

    Args:
        event_data: Event data dictionary

    Returns:
        Hex-encoded SHA-256 hash
    """
    canonical = json.dumps(event_data, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode()).hexdigest()


def _sign_event(
    event_type: str, event_data: dict[str, Any], signing_key: str
) -> SignedEvent:
    """Sign a telemetry event for tamper-evident audit trails.

    Args:
        event_type: Type of event (e.g., "auth_failure", "policy_violation")
        event_data: Event data dictionary
        signing_key: RSA private key for signing

    Returns:
        Signed event with signature and hash
    """
    timestamp = datetime.now(UTC).isoformat()
    event_hash = _compute_event_hash(event_data)

    # Create payload to sign
    payload = {
        "timestamp": timestamp,
        "event_type": event_type,
        "event_hash": event_hash,
    }

    # Sign with RSA-256
    signature = jwt.encode(payload, signing_key, algorithm="RS256")

    return SignedEvent(
        timestamp=timestamp,
        event_type=event_type,
        data=event_data,
        signature=signature,
        event_hash=event_hash,
    )


def verify_event_signature(event: SignedEvent, public_key: str) -> bool:
    """Verify the signature of a signed telemetry event.

    Args:
        event: Signed event to verify
        public_key: RSA public key for verification

    Returns:
        True if signature is valid, False otherwise
    """
    try:
        # Decode and verify signature
        decoded = jwt.decode(event.signature, public_key, algorithms=["RS256"])

        # Verify payload matches
        if decoded.get("timestamp") != event.timestamp:
            return False
        if decoded.get("event_type") != event.event_type:
            return False
        if decoded.get("event_hash") != event.event_hash:
            return False

        # Verify hash matches data
        computed_hash = _compute_event_hash(event.data)
        if computed_hash != event.event_hash:
            return False

        return True
    except jwt.PyJWTError:
        return False


def log_security_event(
    event_type: str, signing_key: str | None = None, **event_data: Any
) -> None:
    """Log a signed security event for audit trails.

    Critical security events are signed to provide non-repudiation and
    tamper-evidence. Events include: auth failures, policy violations,
    privilege escalations, tool executions.

    Args:
        event_type: Type of security event
        signing_key: Optional RSA private key for signing (if None, logs unsigned)
        **event_data: Event attributes

    Example:
        log_security_event(
            "auth_failure",
            signing_key=settings.telemetry_signing_key,
            user_id="user@example.com",
            reason="invalid_token",
            ip_address="203.0.113.42"
        )
    """
    if signing_key:
        # Sign critical events
        signed_event = _sign_event(event_type, event_data, signing_key)
        log_error(
            f"Security event: {event_type}",
            signed_event=signed_event.model_dump(),
            **event_data,
        )
    else:
        # Log without signing (for non-critical or when signing disabled)
        log_error(f"Security event: {event_type}", **event_data)


# Legacy compatibility function
def setup_otel(service_name: str) -> None:
    """Legacy function for backward compatibility.

    Args:
        service_name: Service name for telemetry

    Note:
        Use configure_telemetry() instead for full configuration.
    """
    config = TelemetryConfig(service_name=service_name)
    configure_telemetry(config)
