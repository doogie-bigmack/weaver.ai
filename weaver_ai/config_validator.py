"""Configuration validation for production deployments.

Validates all required settings and dependencies at startup to fail fast
with clear error messages if misconfigured.
"""

import logging

from weaver_ai.settings import AppSettings

logger = logging.getLogger(__name__)


class ConfigurationError(Exception):
    """Raised when configuration validation fails."""

    pass


def validate_settings(settings: AppSettings) -> None:
    """Validate all critical configuration settings.

    Args:
        settings: Settings instance to validate

    Raises:
        ConfigurationError: If any validation check fails
    """
    errors: list[str] = []

    # Validate model configuration
    if not settings.model_provider:
        errors.append("MODEL_PROVIDER must be set (e.g., 'openai', 'anthropic')")

    if not settings.model_name:
        errors.append(
            "MODEL_NAME must be set (e.g., 'gpt-4o', 'claude-3-5-sonnet-20241022')"
        )

    if not settings.model_api_key:
        errors.append(
            f"MODEL_API_KEY must be set for provider '{settings.model_provider}'"
        )

    # Validate authentication configuration
    if settings.auth_mode == "api_key":
        if not settings.allowed_api_keys:
            errors.append("ALLOWED_API_KEYS must be set when auth_mode is 'api_key'")
    elif settings.auth_mode == "jwt":
        if not settings.jwt_public_key:
            errors.append("JWT_PUBLIC_KEY must be set when auth_mode is 'jwt'")

    # Validate rate limiting
    if settings.ratelimit_rps <= 0:
        errors.append(f"RATELIMIT_RPS must be > 0, got {settings.ratelimit_rps}")

    if settings.ratelimit_burst <= 0:
        errors.append(f"RATELIMIT_BURST must be > 0, got {settings.ratelimit_burst}")

    if settings.ratelimit_burst < settings.ratelimit_rps:
        errors.append(
            f"RATELIMIT_BURST ({settings.ratelimit_burst}) must be >= "
            f"RATELIMIT_RPS ({settings.ratelimit_rps})"
        )

    # Redis configuration is not in AppSettings - it's configured per-agent
    # No validation needed here

    # Validate telemetry configuration
    if settings.telemetry_enabled:
        if settings.logfire_send_to_cloud and not settings.logfire_token:
            errors.append(
                "LOGFIRE_TOKEN must be set when LOGFIRE_SEND_TO_CLOUD is true"
            )

    # Raise error if any validations failed
    if errors:
        error_msg = "Configuration validation failed:\n" + "\n".join(
            f"  - {error}" for error in errors
        )
        raise ConfigurationError(error_msg)

    logger.info("Configuration validation passed")


def validate_redis_available() -> None:
    """Validate Redis package is available.

    Raises:
        ConfigurationError: If Redis package is not installed
    """
    try:
        import redis.asyncio  # noqa: F401  # type: ignore[import-untyped]

        logger.info("Redis package is available")
    except ImportError as e:
        raise ConfigurationError(
            "redis package not installed. Run: pip install redis"
        ) from e


def validate_all(settings: AppSettings) -> None:
    """Run all validation checks.

    Args:
        settings: AppSettings instance to validate

    Raises:
        ConfigurationError: If any validation check fails
    """
    logger.info("Starting configuration validation...")

    validate_settings(settings)
    validate_redis_available()

    logger.info("All configuration validation checks passed ✓")
