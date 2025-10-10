"""Security validation and sanitization utilities."""

from __future__ import annotations

import re
import string
import unicodedata
from typing import Any


class SecurityValidator:
    """Centralized security validation and sanitization."""

    # Allowed model names for Redis cache
    ALLOWED_MODEL_NAMES = {
        "gpt-3.5-turbo",
        "gpt-4",
        "gpt-4-turbo",
        "gpt-4o",
        "claude-3-opus",
        "claude-3-sonnet",
        "claude-3-haiku",
        "claude-3.5-sonnet",
        "llama-2-7b",
        "llama-2-13b",
        "llama-2-70b",
        "mistral-7b",
        "mixtral-8x7b",
        "gemini-pro",
        "gemini-ultra",
        "anthropic-claude",
        "openai-gpt",
        "local-model",
    }

    # LDAP special characters that need escaping
    LDAP_ESCAPE_CHARS = {
        "\\": "\\5c",
        "*": "\\2a",
        "(": "\\28",
        ")": "\\29",
        "\x00": "\\00",
        "/": "\\2f",
    }

    # SQL injection patterns
    SQL_INJECTION_PATTERNS = [
        r"(\bunion\b.*\bselect\b|\bselect\b.*\bunion\b)",
        r"(\bdrop\b.*\btable\b|\balter\b.*\btable\b)",
        r"(\bexec\b|\bexecute\b)\s*\(",
        r"(--|\#|\/\*|\*\/)",  # SQL comments
        r"(\bor\b\s+['\"]?\d+['\"]?\s*=\s*['\"]?\d+|\band\b\s+['\"]?\d+['\"]?\s*=\s*['\"]?\d+)",  # OR 1=1 variations
        r"('\s+or\s+'[^']*'\s*=\s*'[^']*')",  # '1'='1' pattern
        r"(\bwaitfor\b\s+\bdelay\b|\bsleep\b\s*\()",
        r"(\bxp_\w+|\bsp_\w+)",  # Extended stored procedures
        r";\s*(drop|delete|update|insert|alter)\s+",  # Statement chaining
    ]

    # Redis dangerous characters
    REDIS_DANGEROUS_CHARS = {"\n", "\r", " ", "*", "[", "]", "?", "$"}

    # Unicode confusables and spoofing characters
    UNICODE_SPOOFING_RANGES = [
        (0x0000, 0x001F),  # Control characters
        (0x007F, 0x009F),  # Delete and C1 control codes
        (0x200B, 0x200F),  # Zero-width characters
        (0x202A, 0x202E),  # Directional formatting
        (0x2060, 0x2069),  # Word joiners and directional isolates
        (0xFEFF, 0xFEFF),  # Zero-width no-break space
        (0xFFF0, 0xFFFF),  # Specials
    ]

    @classmethod
    def sanitize_redis_key_component(cls, value: str, max_length: int = 256) -> str:
        """Sanitize a value for use in Redis keys.

        Args:
            value: The value to sanitize
            max_length: Maximum allowed length

        Returns:
            Sanitized value safe for Redis keys

        Raises:
            ValueError: If value is invalid or dangerous
        """
        if not value or not value.strip():
            raise ValueError("Value cannot be empty")

        # Check length
        if len(value) > max_length:
            raise ValueError(f"Value exceeds maximum length of {max_length}")

        # Check for null bytes
        if "\x00" in value:
            raise ValueError("Null bytes not allowed")

        # Check for Redis dangerous characters
        for char in cls.REDIS_DANGEROUS_CHARS:
            if char in value:
                # Replace dangerous characters with safe alternatives
                value = value.replace(char, f"_{ord(char):02x}_")

        # Allow only alphanumeric, underscore, hyphen, dot, and colon
        if not re.match(r"^[a-zA-Z0-9_\-\.:]+$", value):
            # Encode non-matching characters
            safe_value = ""
            for char in value:
                if re.match(r"[a-zA-Z0-9_\-\.:]", char):
                    safe_value += char
                else:
                    safe_value += f"_{ord(char):04x}_"
            value = safe_value

        return value

    @classmethod
    def validate_model_name(cls, model: str) -> str:
        """Validate and sanitize model name for Redis cache.

        Args:
            model: Model name to validate

        Returns:
            Validated model name

        Raises:
            ValueError: If model name is invalid
        """
        if not model or not model.strip():
            raise ValueError("Model name cannot be empty")

        model = model.strip().lower()

        # Check against whitelist
        if model not in cls.ALLOWED_MODEL_NAMES:
            # Check if it's a versioned variant (e.g., gpt-4-0125)
            base_model = re.sub(r"-\d{4}$", "", model)
            if base_model not in cls.ALLOWED_MODEL_NAMES:
                raise ValueError(
                    f"Invalid model name: {model}. "
                    f"Allowed models: {', '.join(sorted(cls.ALLOWED_MODEL_NAMES))}"
                )

        return cls.sanitize_redis_key_component(model)

    @classmethod
    def escape_ldap_filter(cls, value: str) -> str:
        """Escape special characters in LDAP filter values.

        Args:
            value: The value to escape

        Returns:
            LDAP-safe escaped value
        """
        if not value:
            return value

        escaped = value
        for char, escape_seq in cls.LDAP_ESCAPE_CHARS.items():
            escaped = escaped.replace(char, escape_seq)

        return escaped

    @classmethod
    def validate_ldap_filter(cls, filter_str: str, max_depth: int = 10) -> str:
        """Validate and sanitize LDAP filter string.

        Args:
            filter_str: LDAP filter string
            max_depth: Maximum nesting depth

        Returns:
            Validated filter string

        Raises:
            ValueError: If filter is invalid or dangerous
        """
        if not filter_str:
            return filter_str

        filter_str = filter_str.strip()

        # Check for basic LDAP filter structure
        if not filter_str.startswith("(") or not filter_str.endswith(")"):
            raise ValueError("Invalid LDAP filter format")

        # Check nesting depth and balance (prevent DoS)
        depth = 0
        max_found_depth = 0
        for i, char in enumerate(filter_str):
            if char == "(":
                depth += 1
                max_found_depth = max(max_found_depth, depth)
            elif char == ")":
                depth -= 1
                if depth < 0:
                    raise ValueError("Unbalanced parentheses in LDAP filter")

        if depth != 0:
            raise ValueError("Unbalanced parentheses in LDAP filter")

        if max_found_depth > max_depth:
            raise ValueError(f"LDAP filter exceeds maximum depth of {max_depth}")

        # Validate operators
        allowed_ops = ["=", ">=", "<=", "~=", ":=", "&", "|", "!"]
        has_valid_op = any(op in filter_str for op in allowed_ops)
        if not has_valid_op:
            raise ValueError("LDAP filter must contain valid operators")

        return filter_str

    @classmethod
    def sanitize_identity_name(cls, name: str, max_length: int = 256) -> str:
        """Sanitize identity/account name for SailPoint.

        Args:
            name: Identity or account name
            max_length: Maximum allowed length

        Returns:
            Sanitized name

        Raises:
            ValueError: If name is invalid
        """
        if not name or not name.strip():
            raise ValueError("Identity name cannot be empty")

        name = name.strip()

        # Check length
        if len(name) > max_length:
            raise ValueError(f"Name exceeds maximum length of {max_length}")

        # Escape LDAP special characters
        name = cls.escape_ldap_filter(name)

        # Remove any remaining control characters
        name = "".join(char for char in name if ord(char) >= 32)

        return name

    @classmethod
    def detect_sql_injection(cls, value: str) -> bool:
        """Detect potential SQL injection patterns.

        Args:
            value: String to check

        Returns:
            True if SQL injection detected, False otherwise
        """
        if not value:
            return False

        value_lower = value.lower()

        # Check for SQL injection patterns
        for pattern in cls.SQL_INJECTION_PATTERNS:
            if re.search(pattern, value_lower, re.IGNORECASE):
                return True

        # Check for excessive semicolons (statement chaining)
        if value.count(";") > 2:
            return True

        # Check for hex encoding attempts
        if re.search(r"0x[0-9a-f]+", value_lower):
            # Allow legitimate hex values in specific contexts
            if not re.match(r"^0x[0-9a-f]{1,16}$", value_lower):
                return True

        return False

    @classmethod
    def detect_unicode_spoofing(cls, value: str) -> bool:
        """Detect Unicode spoofing and confusable characters.

        Args:
            value: String to check

        Returns:
            True if spoofing detected, False otherwise
        """
        if not value:
            return False

        for char in value:
            code_point = ord(char)

            # Allow common whitespace characters first
            if char in ["\t", "\n", "\r", " "]:
                continue

            # Check against spoofing ranges
            for start, end in cls.UNICODE_SPOOFING_RANGES:
                if start <= code_point <= end:
                    return True

            # Check for non-printable characters
            if unicodedata.category(char) in ["Cc", "Cf", "Co", "Cn"]:
                return True

        # Check for homoglyphs (basic check)
        if cls._has_mixed_scripts(value):
            return True

        return False

    @classmethod
    def _has_mixed_scripts(cls, value: str) -> bool:
        """Check if string contains mixed scripts (potential homoglyph attack).

        Args:
            value: String to check

        Returns:
            True if mixed scripts detected
        """
        scripts = set()
        for char in value:
            if char.isalpha():
                # Get the script name for the character
                script = unicodedata.name(char, "").split()[0] if char != " " else None
                if script:
                    scripts.add(script)

        # Allow Latin + common punctuation
        if len(scripts) <= 1:
            return False

        # Check for suspicious script mixing
        suspicious_combinations = [
            {"LATIN", "CYRILLIC"},
            {"LATIN", "GREEK"},
            {"LATIN", "ARMENIAN"},
        ]

        for combo in suspicious_combinations:
            if combo.issubset(scripts):
                return True

        return False

    @classmethod
    def sanitize_user_input(
        cls,
        value: str,
        max_length: int = 10000,
        allow_html: bool = False,
        allow_newlines: bool = True,
        strict_mode: bool = True,
    ) -> str:
        """Comprehensive input sanitization.

        Args:
            value: Input value to sanitize
            max_length: Maximum allowed length
            allow_html: Whether to allow HTML tags
            allow_newlines: Whether to allow newlines
            strict_mode: Whether to raise errors or clean silently

        Returns:
            Sanitized value

        Raises:
            ValueError: If input is invalid or dangerous (in strict mode)
        """
        if not value:
            return ""

        # Strip whitespace
        value = value.strip()

        # Check length
        if len(value) > max_length:
            if strict_mode:
                raise ValueError(f"Input exceeds maximum length of {max_length}")
            else:
                value = value[:max_length]

        # Remove control characters first (including null bytes)
        if allow_newlines:
            allowed_chars = {"\t", "\n", "\r"}
        else:
            allowed_chars = {"\t"}

        cleaned = ""
        has_null_byte = False
        for char in value:
            if char == "\x00":
                has_null_byte = True
                continue  # Always remove null bytes
            if ord(char) < 32 and char not in allowed_chars:
                continue
            cleaned += char

        value = cleaned

        # After cleaning, check for violations in strict mode
        if strict_mode:
            if has_null_byte:
                raise ValueError("Null bytes not allowed")

            # Check for SQL injection
            if cls.detect_sql_injection(value):
                raise ValueError("Potential SQL injection detected")

            # Check for Unicode spoofing
            if cls.detect_unicode_spoofing(value):
                raise ValueError("Unicode spoofing characters detected")

        # Remove HTML if not allowed
        if not allow_html:
            # Remove script-related content first (before tags)
            value = re.sub(
                r"(?i)(javascript:|data:text/html|vbscript:|onclick=|onerror=|onload=)",
                "",
                value,
            )
            # Basic HTML tag removal
            value = re.sub(r"<[^>]+>", "", value)

        return value

    @classmethod
    def validate_json_size(cls, data: Any, max_size: int = 1048576) -> None:
        """Validate JSON data size to prevent DoS.

        Args:
            data: JSON-serializable data
            max_size: Maximum size in bytes (default 1MB)

        Raises:
            ValueError: If data exceeds size limit
        """
        import json

        json_str = json.dumps(data)
        if len(json_str) > max_size:
            raise ValueError(f"JSON data exceeds maximum size of {max_size} bytes")
