"""Tests for configuration validation."""

from unittest.mock import patch

import pytest

from weaver_ai.config_validator import (
    ConfigurationError,
    validate_all,
    validate_settings,
)
from weaver_ai.settings import AppSettings


def test_validate_settings_success():
    """Test successful configuration validation."""
    with patch.dict(
        "os.environ",
        {
            "WEAVER_MODEL_PROVIDER": "openai",
            "WEAVER_MODEL_NAME": "gpt-4o",
            "WEAVER_MODEL_API_KEY": "sk-test-key",
            "WEAVER_AUTH_MODE": "api_key",
            "WEAVER_ALLOWED_API_KEYS": '["test-key-1", "test-key-2"]',
        },
    ):
        settings = AppSettings()
        validate_settings(settings)


def test_validate_settings_missing_model_api_key():
    """Test validation fails when model_api_key is missing."""
    with patch.dict(
        "os.environ",
        {
            "WEAVER_MODEL_PROVIDER": "openai",
            "WEAVER_MODEL_NAME": "gpt-4o",
        },
        clear=True,
    ):
        settings = AppSettings()

        with pytest.raises(ConfigurationError) as exc_info:
            validate_settings(settings)

        assert "MODEL_API_KEY must be set" in str(exc_info.value)


def test_validate_settings_api_key_auth_missing_allowed_keys():
    """Test validation fails when auth_mode is api_key but allowed_api_keys is empty."""
    with patch.dict(
        "os.environ",
        {
            "WEAVER_MODEL_PROVIDER": "openai",
            "WEAVER_MODEL_NAME": "gpt-4o",
            "WEAVER_MODEL_API_KEY": "sk-test-key",
            "WEAVER_AUTH_MODE": "api_key",
            "WEAVER_ALLOWED_API_KEYS": "[]",
        },
        clear=True,
    ):
        settings = AppSettings()

        with pytest.raises(ConfigurationError) as exc_info:
            validate_settings(settings)

        assert "ALLOWED_API_KEYS must be set when auth_mode is 'api_key'" in str(
            exc_info.value
        )


def test_validate_settings_jwt_auth_missing_public_key():
    """Test validation fails when auth_mode is jwt but jwt_public_key is missing."""
    with patch.dict(
        "os.environ",
        {
            "WEAVER_MODEL_PROVIDER": "openai",
            "WEAVER_MODEL_NAME": "gpt-4o",
            "WEAVER_MODEL_API_KEY": "sk-test-key",
            "WEAVER_AUTH_MODE": "jwt",
        },
        clear=True,
    ):
        settings = AppSettings()

        with pytest.raises(ConfigurationError) as exc_info:
            validate_settings(settings)

        assert "JWT_PUBLIC_KEY must be set when auth_mode is 'jwt'" in str(
            exc_info.value
        )


def test_validate_settings_invalid_ratelimit_rps():
    """Test validation fails when ratelimit_rps is <= 0."""
    with patch.dict(
        "os.environ",
        {
            "WEAVER_MODEL_PROVIDER": "openai",
            "WEAVER_MODEL_NAME": "gpt-4o",
            "WEAVER_MODEL_API_KEY": "sk-test-key",
            "WEAVER_AUTH_MODE": "api_key",
            "WEAVER_ALLOWED_API_KEYS": '["test-key"]',
            "WEAVER_RATELIMIT_RPS": "0",
        },
        clear=True,
    ):
        settings = AppSettings()

        with pytest.raises(ConfigurationError) as exc_info:
            validate_settings(settings)

        assert "RATELIMIT_RPS must be > 0" in str(exc_info.value)


def test_validate_settings_invalid_ratelimit_burst():
    """Test validation fails when ratelimit_burst is <= 0."""
    with patch.dict(
        "os.environ",
        {
            "WEAVER_MODEL_PROVIDER": "openai",
            "WEAVER_MODEL_NAME": "gpt-4o",
            "WEAVER_MODEL_API_KEY": "sk-test-key",
            "WEAVER_AUTH_MODE": "api_key",
            "WEAVER_ALLOWED_API_KEYS": '["test-key"]',
            "WEAVER_RATELIMIT_RPS": "10",
            "WEAVER_RATELIMIT_BURST": "0",
        },
        clear=True,
    ):
        settings = AppSettings()

        with pytest.raises(ConfigurationError) as exc_info:
            validate_settings(settings)

        assert "RATELIMIT_BURST must be > 0" in str(exc_info.value)


def test_validate_settings_burst_less_than_rps():
    """Test validation fails when ratelimit_burst < ratelimit_rps."""
    with patch.dict(
        "os.environ",
        {
            "WEAVER_MODEL_PROVIDER": "openai",
            "WEAVER_MODEL_NAME": "gpt-4o",
            "WEAVER_MODEL_API_KEY": "sk-test-key",
            "WEAVER_AUTH_MODE": "api_key",
            "WEAVER_ALLOWED_API_KEYS": '["test-key"]',
            "WEAVER_RATELIMIT_RPS": "20",
            "WEAVER_RATELIMIT_BURST": "10",
        },
        clear=True,
    ):
        settings = AppSettings()

        with pytest.raises(ConfigurationError) as exc_info:
            validate_settings(settings)

        assert "RATELIMIT_BURST (10) must be >= RATELIMIT_RPS (20)" in str(
            exc_info.value
        )


def test_validate_settings_logfire_send_without_token():
    """Test validation fails when logfire_send_to_cloud is true but token is missing."""
    with patch.dict(
        "os.environ",
        {
            "WEAVER_MODEL_PROVIDER": "openai",
            "WEAVER_MODEL_NAME": "gpt-4o",
            "WEAVER_MODEL_API_KEY": "sk-test-key",
            "WEAVER_AUTH_MODE": "api_key",
            "WEAVER_ALLOWED_API_KEYS": '["test-key"]',
            "WEAVER_TELEMETRY_ENABLED": "true",
            "WEAVER_LOGFIRE_SEND_TO_CLOUD": "true",
        },
        clear=True,
    ):
        settings = AppSettings()

        with pytest.raises(ConfigurationError) as exc_info:
            validate_settings(settings)

        assert "LOGFIRE_TOKEN must be set when LOGFIRE_SEND_TO_CLOUD is true" in str(
            exc_info.value
        )


def test_validate_settings_multiple_errors():
    """Test validation collects multiple errors."""
    with patch.dict("os.environ", {}, clear=True):
        settings = AppSettings()
        # AppSettings will have defaults, so we need to override them
        settings.model_provider = "stub"  # This is the default
        settings.model_api_key = None
        settings.ratelimit_rps = 0
        settings.ratelimit_burst = -5

        with pytest.raises(ConfigurationError) as exc_info:
            validate_settings(settings)

        error_msg = str(exc_info.value)
        assert "MODEL_API_KEY must be set" in error_msg
        assert "RATELIMIT_RPS must be > 0" in error_msg
        assert "RATELIMIT_BURST must be > 0" in error_msg


def test_validate_all_success(caplog):
    """Test validate_all runs all checks successfully."""
    import logging

    caplog.set_level(logging.INFO, logger="weaver_ai.config_validator")

    with patch.dict(
        "os.environ",
        {
            "WEAVER_MODEL_PROVIDER": "openai",
            "WEAVER_MODEL_NAME": "gpt-4o",
            "WEAVER_MODEL_API_KEY": "sk-test-key",
            "WEAVER_AUTH_MODE": "api_key",
            "WEAVER_ALLOWED_API_KEYS": '["test-key"]',
        },
        clear=True,
    ):
        settings = AppSettings()
        validate_all(settings)

        # Check log messages
        assert "Starting configuration validation..." in caplog.text
        assert "Configuration validation passed" in caplog.text
        assert "All configuration validation checks passed ✓" in caplog.text


def test_validate_all_fails_on_invalid_settings():
    """Test validate_all fails when settings are invalid."""
    with patch.dict(
        "os.environ",
        {
            "WEAVER_MODEL_PROVIDER": "openai",
            "WEAVER_MODEL_NAME": "gpt-4o",
        },
        clear=True,
    ):
        settings = AppSettings()

        with pytest.raises(ConfigurationError) as exc_info:
            validate_all(settings)

        assert "MODEL_API_KEY must be set" in str(exc_info.value)
