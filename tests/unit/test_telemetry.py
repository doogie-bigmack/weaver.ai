"""Unit tests for telemetry module."""

from __future__ import annotations

from unittest.mock import Mock, patch

from weaver_ai.telemetry import (
    TelemetryConfig,
    configure_telemetry,
    log_error,
    log_info,
    log_warning,
    start_span,
)


class TestTelemetryConfig:
    """Tests for TelemetryConfig."""

    def test_default_config(self):
        """Test default configuration values."""
        config = TelemetryConfig()

        assert config.enabled is True
        assert config.service_name == "weaver-ai"
        assert config.environment == "development"
        assert config.logfire_token is None
        assert config.send_to_logfire is False

    def test_custom_config(self):
        """Test custom configuration values."""
        config = TelemetryConfig(
            enabled=False,
            service_name="custom-service",
            environment="production",
            logfire_token="test_token",
            send_to_logfire=True,
        )

        assert config.enabled is False
        assert config.service_name == "custom-service"
        assert config.environment == "production"
        assert config.logfire_token == "test_token"
        assert config.send_to_logfire is True


class TestConfigureTelemetry:
    """Tests for configure_telemetry function."""

    def test_configure_when_disabled(self):
        """Test that telemetry is skipped when disabled."""
        config = TelemetryConfig(enabled=False)

        # Should not raise any errors
        configure_telemetry(config)

    @patch("weaver_ai.telemetry.LOGFIRE_AVAILABLE", False)
    def test_configure_without_logfire(self):
        """Test configuration when Logfire is not available."""
        config = TelemetryConfig(enabled=True)

        # Should not raise any errors
        configure_telemetry(config)

    @patch("weaver_ai.telemetry.LOGFIRE_AVAILABLE", True)
    @patch("weaver_ai.telemetry.logfire")
    def test_configure_with_logfire(self, mock_logfire):
        """Test configuration with Logfire available."""
        config = TelemetryConfig(
            enabled=True,
            service_name="test-service",
            environment="test",
        )

        configure_telemetry(config)

        # Verify logfire.configure was called
        mock_logfire.configure.assert_called_once()
        call_kwargs = mock_logfire.configure.call_args[1]

        assert call_kwargs["service_name"] == "test-service"
        assert call_kwargs["environment"] == "test"


class TestStartSpan:
    """Tests for start_span context manager."""

    @patch("weaver_ai.telemetry.LOGFIRE_AVAILABLE", False)
    def test_span_without_logfire(self):
        """Test span creation without Logfire (fallback to no-op)."""
        with start_span("test_span", custom_attr="value"):
            # Should work without raising errors
            pass

    @patch("weaver_ai.telemetry.LOGFIRE_AVAILABLE", True)
    @patch("weaver_ai.telemetry.logfire")
    def test_span_with_logfire(self, mock_logfire):
        """Test span creation with Logfire available."""
        mock_span = Mock()
        mock_logfire.span.return_value.__enter__ = Mock(return_value=mock_span)
        mock_logfire.span.return_value.__exit__ = Mock(return_value=None)

        with start_span("test_span", custom_attr="value"):
            pass

        # Verify logfire.span was called with correct arguments
        mock_logfire.span.assert_called_once_with("test_span", custom_attr="value")


class TestStructuredLogging:
    """Tests for structured logging functions."""

    @patch("weaver_ai.telemetry.LOGFIRE_AVAILABLE", False)
    @patch("weaver_ai.telemetry.logger")
    def test_log_info_fallback(self, mock_logger):
        """Test log_info falls back to standard logger when Logfire unavailable."""
        log_info("Test message", key="value")

        mock_logger.info.assert_called_once()

    @patch("weaver_ai.telemetry.LOGFIRE_AVAILABLE", True)
    @patch("weaver_ai.telemetry.logfire")
    def test_log_info_with_logfire(self, mock_logfire):
        """Test log_info uses Logfire when available."""
        log_info("Test message", key="value")

        mock_logfire.info.assert_called_once_with("Test message", key="value")

    @patch("weaver_ai.telemetry.LOGFIRE_AVAILABLE", False)
    @patch("weaver_ai.telemetry.logger")
    def test_log_error_fallback(self, mock_logger):
        """Test log_error falls back to standard logger when Logfire unavailable."""
        log_error("Error message", error_code=500)

        mock_logger.error.assert_called_once()

    @patch("weaver_ai.telemetry.LOGFIRE_AVAILABLE", True)
    @patch("weaver_ai.telemetry.logfire")
    def test_log_error_with_logfire(self, mock_logfire):
        """Test log_error uses Logfire when available."""
        log_error("Error message", error_code=500)

        mock_logfire.error.assert_called_once_with("Error message", error_code=500)

    @patch("weaver_ai.telemetry.LOGFIRE_AVAILABLE", False)
    @patch("weaver_ai.telemetry.logger")
    def test_log_warning_fallback(self, mock_logger):
        """Test log_warning falls back to standard logger when Logfire unavailable."""
        log_warning("Warning message", warning_type="test")

        mock_logger.warning.assert_called_once()

    @patch("weaver_ai.telemetry.LOGFIRE_AVAILABLE", True)
    @patch("weaver_ai.telemetry.logfire")
    def test_log_warning_with_logfire(self, mock_logfire):
        """Test log_warning uses Logfire when available."""
        log_warning("Warning message", warning_type="test")

        mock_logfire.warn.assert_called_once_with(
            "Warning message", warning_type="test"
        )
