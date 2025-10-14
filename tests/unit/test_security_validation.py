"""Unit tests for security validation and sanitization."""

from __future__ import annotations

import pytest

from weaver_ai.security.validation import SecurityValidator


class TestRedisKeySanitization:
    """Test Redis key component sanitization."""

    def test_sanitize_valid_key(self):
        """Test sanitizing valid Redis key components."""
        assert SecurityValidator.sanitize_redis_key_component("user_123") == "user_123"
        assert (
            SecurityValidator.sanitize_redis_key_component("model-v1.0") == "model-v1.0"
        )
        assert SecurityValidator.sanitize_redis_key_component("test:key") == "test:key"

    def test_sanitize_dangerous_characters(self):
        """Test sanitizing dangerous Redis characters."""
        # Spaces should be replaced
        result = SecurityValidator.sanitize_redis_key_component("user 123")
        assert " " not in result
        assert "_20_" in result  # space is hex 20

        # Newlines should be replaced
        result = SecurityValidator.sanitize_redis_key_component("user\n123")
        assert "\n" not in result
        assert "_0a_" in result  # newline is hex 0a

        # Wildcards should be replaced
        result = SecurityValidator.sanitize_redis_key_component("user*123")
        assert "*" not in result
        assert "_2a_" in result  # asterisk is hex 2a

    def test_reject_null_bytes(self):
        """Test that null bytes are rejected."""
        with pytest.raises(ValueError, match="Null bytes not allowed"):
            SecurityValidator.sanitize_redis_key_component("user\x00123")

    def test_reject_empty_values(self):
        """Test that empty values are rejected."""
        with pytest.raises(ValueError, match="Value cannot be empty"):
            SecurityValidator.sanitize_redis_key_component("")

        with pytest.raises(ValueError, match="Value cannot be empty"):
            SecurityValidator.sanitize_redis_key_component("   ")

    def test_length_limit(self):
        """Test that length limits are enforced."""
        # Should pass with exact limit
        long_value = "a" * 256
        result = SecurityValidator.sanitize_redis_key_component(long_value)
        assert len(result) <= 256

        # Should fail over limit
        with pytest.raises(ValueError, match="exceeds maximum length"):
            SecurityValidator.sanitize_redis_key_component("a" * 257)


class TestModelNameValidation:
    """Test model name validation for Redis cache."""

    def test_valid_model_names(self):
        """Test validation of allowed model names."""
        assert SecurityValidator.validate_model_name("gpt-4") == "gpt-4"
        assert SecurityValidator.validate_model_name("claude-3-opus") == "claude-3-opus"
        assert (
            SecurityValidator.validate_model_name("GPT-4") == "gpt-4"
        )  # Should lowercase

    def test_invalid_model_names(self):
        """Test rejection of invalid model names."""
        with pytest.raises(ValueError, match="Invalid model name"):
            SecurityValidator.validate_model_name("malicious-model")

        with pytest.raises(ValueError, match="Invalid model name"):
            SecurityValidator.validate_model_name("../../etc/passwd")

        with pytest.raises(ValueError, match="Invalid model name"):
            SecurityValidator.validate_model_name("gpt-4; DROP TABLE users")

    def test_empty_model_name(self):
        """Test that empty model names are rejected."""
        with pytest.raises(ValueError, match="Model name cannot be empty"):
            SecurityValidator.validate_model_name("")

        with pytest.raises(ValueError, match="Model name cannot be empty"):
            SecurityValidator.validate_model_name("   ")


class TestLDAPFilterValidation:
    """Test LDAP filter validation and escaping."""

    def test_escape_ldap_characters(self):
        """Test LDAP special character escaping."""
        assert SecurityValidator.escape_ldap_filter("user*") == "user\\2a"
        assert SecurityValidator.escape_ldap_filter("user(test)") == "user\\28test\\29"
        assert SecurityValidator.escape_ldap_filter("user\\name") == "user\\5cname"
        assert SecurityValidator.escape_ldap_filter("user/admin") == "user\\2fadmin"

    def test_validate_valid_ldap_filter(self):
        """Test validation of valid LDAP filters."""
        valid_filters = [
            "(cn=John Doe)",
            "(uid=jdoe)",
            "(&(objectClass=user)(department=IT))",
            "(|(cn=admin)(cn=root))",
            "(!(&(cn=test)(uid=test)))",
        ]

        for filter_str in valid_filters:
            result = SecurityValidator.validate_ldap_filter(filter_str)
            assert result == filter_str

    def test_reject_invalid_ldap_filter(self):
        """Test rejection of invalid LDAP filters."""
        # Missing parentheses
        with pytest.raises(ValueError, match="Invalid LDAP filter format"):
            SecurityValidator.validate_ldap_filter("cn=test")

        # Unbalanced parentheses - missing closing
        with pytest.raises(
            ValueError, match="Invalid LDAP filter format|Unbalanced parentheses"
        ):
            SecurityValidator.validate_ldap_filter("(cn=test")

        # Unbalanced parentheses - missing opening
        with pytest.raises(
            ValueError, match="Invalid LDAP filter format|Unbalanced parentheses"
        ):
            SecurityValidator.validate_ldap_filter("cn=test)")

    def test_ldap_filter_depth_limit(self):
        """Test LDAP filter nesting depth limit."""
        # Create deeply nested filter
        deep_filter = "(" * 11 + "cn=test" + ")" * 11

        with pytest.raises(ValueError, match="exceeds maximum depth"):
            SecurityValidator.validate_ldap_filter(deep_filter, max_depth=10)

    def test_sanitize_identity_name(self):
        """Test identity name sanitization."""
        # Valid names should pass through
        assert SecurityValidator.sanitize_identity_name("john.doe") == "john.doe"
        assert (
            SecurityValidator.sanitize_identity_name("user@example.com")
            == "user@example.com"
        )

        # Special characters should be escaped
        result = SecurityValidator.sanitize_identity_name("user*admin")
        assert "\\2a" in result

        # Control characters should be removed
        result = SecurityValidator.sanitize_identity_name("user\x00\x01test")
        assert "\x00" not in result
        assert "\x01" not in result


class TestSQLInjectionDetection:
    """Test SQL injection pattern detection."""

    def test_detect_sql_injection_patterns(self):
        """Test detection of common SQL injection patterns."""
        sql_injections = [
            "'; DROP TABLE users--",
            "1' OR '1'='1",
            "admin' --",
            "1 UNION SELECT * FROM passwords",
            "'; EXEC xp_cmdshell('dir')--",
            "1; WAITFOR DELAY '00:00:05'--",
            "' OR 1=1--",
            "; UPDATE users SET admin=1--",
        ]

        for injection in sql_injections:
            result = SecurityValidator.detect_sql_injection(injection)
            assert result is True, f"Failed to detect SQL injection: {injection}"

    def test_allow_legitimate_queries(self):
        """Test that legitimate queries are not flagged."""
        legitimate_queries = [
            "What is the weather today?",
            "Calculate 2+2",
            "Show me the user profile",
            "Find documents from last week",
            "How do I reset my password?",
        ]

        for query in legitimate_queries:
            assert SecurityValidator.detect_sql_injection(query) is False

    def test_detect_hex_encoding(self):
        """Test detection of hex encoding attempts."""
        # Legitimate hex values should be allowed
        assert SecurityValidator.detect_sql_injection("0xFF") is False
        assert SecurityValidator.detect_sql_injection("0x123ABC") is False

        # Suspicious hex patterns should be detected
        assert (
            SecurityValidator.detect_sql_injection(
                "0x73656c656374202a2066726f6d207573657273"
            )
            is True
        )

    def test_detect_excessive_semicolons(self):
        """Test detection of statement chaining."""
        # Normal use of semicolons is OK
        assert (
            SecurityValidator.detect_sql_injection("Hello; how are you; I'm fine")
            is False
        )

        # Excessive semicolons indicate SQL statement chaining
        assert (
            SecurityValidator.detect_sql_injection(";;;SELECT * FROM users;;;") is True
        )


class TestUnicodeSpoofingDetection:
    """Test Unicode spoofing and homoglyph detection."""

    def test_detect_control_characters(self):
        """Test detection of control characters."""
        # Non-printable control chars (not null byte which is handled separately)
        assert SecurityValidator.detect_unicode_spoofing("test\x01\x02\x03") is True

        # Allow common whitespace
        assert SecurityValidator.detect_unicode_spoofing("test\tdata") is False
        assert SecurityValidator.detect_unicode_spoofing("test\ndata") is False
        assert SecurityValidator.detect_unicode_spoofing("test data") is False

    def test_detect_zero_width_characters(self):
        """Test detection of zero-width characters."""
        # Zero-width space (U+200B)
        assert SecurityValidator.detect_unicode_spoofing("test\u200bdata") is True

        # Zero-width joiner (U+200D)
        assert SecurityValidator.detect_unicode_spoofing("test\u200ddata") is True

        # Right-to-left override (U+202E)
        assert SecurityValidator.detect_unicode_spoofing("test\u202edata") is True

    def test_detect_mixed_scripts(self):
        """Test detection of mixed script attacks."""
        # Mixed Latin and Cyrillic (homoglyphs)
        assert (
            SecurityValidator.detect_unicode_spoofing("pаypal") is True
        )  # 'а' is Cyrillic

        # Pure scripts should be OK
        assert SecurityValidator.detect_unicode_spoofing("paypal") is False
        assert SecurityValidator.detect_unicode_spoofing("test123") is False


class TestComprehensiveInputSanitization:
    """Test comprehensive input sanitization."""

    def test_basic_sanitization(self):
        """Test basic input sanitization."""
        # Normal input should pass through
        result = SecurityValidator.sanitize_user_input("Hello, world!")
        assert result == "Hello, world!"

        # Whitespace should be trimmed
        result = SecurityValidator.sanitize_user_input("  Hello  ")
        assert result == "Hello"

    def test_reject_sql_injection(self):
        """Test rejection of SQL injection in general input."""
        with pytest.raises(ValueError, match="SQL injection"):
            SecurityValidator.sanitize_user_input("'; DROP TABLE users--")

    def test_reject_unicode_spoofing(self):
        """Test rejection of Unicode spoofing in general input."""
        with pytest.raises(ValueError, match="Unicode spoofing"):
            SecurityValidator.sanitize_user_input("test\u200bdata")

    def test_html_removal(self):
        """Test HTML tag removal when not allowed."""
        result = SecurityValidator.sanitize_user_input(
            "<script>alert('xss')</script>Hello",
            allow_html=False,
            strict_mode=False,  # Don't raise on content, just clean
        )
        assert "<script>" not in result
        assert "Hello" in result

    def test_length_limits(self):
        """Test enforcement of length limits."""
        # Within limit
        result = SecurityValidator.sanitize_user_input("a" * 100, max_length=100)
        assert len(result) == 100

        # Over limit
        with pytest.raises(ValueError, match="exceeds maximum length"):
            SecurityValidator.sanitize_user_input("a" * 101, max_length=100)

    def test_control_character_removal(self):
        """Test removal of control characters."""
        input_str = "Hello\x00\x01\x02World"
        # Test with strict_mode=False to just clean without raising
        result = SecurityValidator.sanitize_user_input(input_str, strict_mode=False)
        assert "\x00" not in result
        assert "\x01" not in result
        assert "\x02" not in result
        assert "HelloWorld" == result

        # Test that strict mode raises on null bytes
        with pytest.raises(ValueError, match="Null bytes not allowed"):
            SecurityValidator.sanitize_user_input(input_str, strict_mode=True)

    def test_javascript_url_removal(self):
        """Test removal of JavaScript URLs."""
        dangerous_inputs = [
            "javascript:alert('xss')",
            "data:text/html,<script>alert('xss')</script>",
            "vbscript:msgbox('xss')",
            '<a href="javascript:void(0)" onclick="alert(1)">Click</a>',
        ]

        for dangerous in dangerous_inputs:
            # Use strict_mode=False to clean without raising on detected patterns
            result = SecurityValidator.sanitize_user_input(
                dangerous, allow_html=False, strict_mode=False
            )
            assert "javascript:" not in result.lower()
            assert "vbscript:" not in result.lower()
            assert "onclick=" not in result.lower()


class TestJSONSizeValidation:
    """Test JSON size validation."""

    def test_valid_json_size(self):
        """Test that valid size JSON passes."""
        small_data = {"key": "value", "number": 123}
        SecurityValidator.validate_json_size(small_data, max_size=1024)

    def test_reject_oversized_json(self):
        """Test rejection of oversized JSON."""
        # Create large data
        large_data = {"key": "x" * 10000}

        with pytest.raises(ValueError, match="exceeds maximum size"):
            SecurityValidator.validate_json_size(large_data, max_size=1024)

    def test_nested_json_size(self):
        """Test size validation with nested structures."""
        nested_data = {
            "level1": {"level2": {"level3": ["item1", "item2", "item3"] * 100}}
        }

        # Should handle nested structures correctly
        import json

        actual_size = len(json.dumps(nested_data))

        if actual_size > 1024:
            with pytest.raises(ValueError, match="exceeds maximum size"):
                SecurityValidator.validate_json_size(nested_data, max_size=1024)
        else:
            SecurityValidator.validate_json_size(
                nested_data, max_size=actual_size + 100
            )


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
