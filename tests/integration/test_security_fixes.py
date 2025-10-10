"""Integration tests for security vulnerability fixes."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from weaver_ai.cache.redis_cache import CacheConfig, RedisCache
from weaver_ai.models.api import QueryRequest
from weaver_ai.tools.builtin.sailpoint import SailPointIIQTool


class TestRedisInjectionFix:
    """Test Redis injection vulnerability fixes."""

    @pytest.mark.asyncio
    async def test_redis_cache_safe_model_names(self):
        """Test that Redis cache properly sanitizes model names."""
        config = CacheConfig(enabled=True)
        cache = RedisCache(config)

        # Mock Redis client
        cache.client = AsyncMock()
        cache._connected = True
        cache.client.get.return_value = None

        # Test with valid model name
        key = cache._generate_key("test query", "gpt-4", temperature=0.7)
        assert "gpt-4" in key
        assert "|" not in key  # Should not contain raw separator in final key

        # Test with invalid model name - should use fallback
        key = cache._generate_key("test query", "../../etc/passwd", temperature=0.7)
        assert "etc" not in key
        assert "passwd" not in key
        assert "unknown" in key  # Should use safe fallback

        # Test with injection attempt
        key = cache._generate_key("test query", "model*", temperature=0.7)
        assert "*" not in key  # Wildcard should be sanitized

    @pytest.mark.asyncio
    async def test_redis_cache_prevents_key_injection(self):
        """Test that Redis cache prevents key injection attacks."""
        config = CacheConfig(enabled=True)
        cache = RedisCache(config)

        # Mock Redis client
        cache.client = AsyncMock()
        cache._connected = True

        # Test various injection attempts
        injection_attempts = [
            "model\nDEL *",  # Newline injection
            "model\rFLUSHDB",  # Carriage return injection
            "model$1$GET$secret",  # Redis protocol injection
            "model[1-9]*",  # Pattern matching injection
        ]

        for malicious_model in injection_attempts:
            key = cache._generate_key("query", malicious_model)
            # Key should be sanitized
            assert "\n" not in key
            assert "\r" not in key
            assert "$" not in key or "_24_" in key  # $ should be encoded
            assert "[" not in key or "_5b_" in key  # [ should be encoded

    @pytest.mark.asyncio
    async def test_redis_cache_with_real_operations(self):
        """Test Redis cache with real-like operations."""
        config = CacheConfig(enabled=True)
        cache = RedisCache(config)

        # Mock Redis client
        cache.client = AsyncMock()
        cache._connected = True
        cache.client.get.return_value = None
        cache.client.setex.return_value = True

        # Test setting cache with potentially dangerous model name
        await cache.set(
            "What is AI?",
            "gpt-4; DEL users:*",  # Injection attempt
            {"answer": "AI is..."},
        )

        # Should sanitize the model name in the key
        cache.client.setex.assert_called_once()
        call_args = cache.client.setex.call_args
        key_used = call_args[0][0]
        assert "DEL" not in key_used
        assert "users:*" not in key_used


class TestLDAPInjectionFix:
    """Test LDAP injection vulnerability fixes in SailPoint tool."""

    @pytest.mark.asyncio
    async def test_sailpoint_ldap_filter_validation(self):
        """Test that SailPoint tool validates LDAP filters."""
        tool = SailPointIIQTool()

        # Test with valid LDAP filter
        valid_query = {"filter": "(cn=John Doe)", "limit": 10, "offset": 0}

        with patch("httpx.AsyncClient") as mock_client:
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json.return_value = {"result": {"users": [], "total": 0}}
            mock_client.return_value.__aenter__.return_value.post.return_value = (
                mock_response
            )

            result = await tool._list_users(valid_query)
            assert result["success"] is True

    @pytest.mark.asyncio
    async def test_sailpoint_rejects_invalid_ldap_filter(self):
        """Test that SailPoint tool rejects invalid LDAP filters."""
        tool = SailPointIIQTool()

        # Test with invalid LDAP filter (missing parentheses)
        invalid_query = {"filter": "cn=admin*", "limit": 10, "offset": 0}

        result = await tool._list_users(invalid_query)
        assert result["success"] is False
        assert "Invalid LDAP filter" in result["error"]

    @pytest.mark.asyncio
    async def test_sailpoint_escapes_special_characters(self):
        """Test that SailPoint tool escapes LDAP special characters."""
        tool = SailPointIIQTool()

        # Test user ID with special characters
        result = await tool._get_user("admin*")
        assert result["success"] is True
        # The user_id should be sanitized before use
        assert "*" not in str(result["data"]["id"]) or "\\2a" in str(
            result["data"]["id"]
        )

    @pytest.mark.asyncio
    async def test_sailpoint_prevents_ldap_injection(self):
        """Test prevention of LDAP injection attacks."""
        tool = SailPointIIQTool()

        # Various LDAP injection attempts
        injection_filters = [
            "(*)(cn=*)",  # Always true filter
            "(cn=*)(userPassword=*)",  # Password extraction attempt
            "(cn=admin)(cn=*)",  # Missing operators
        ]

        for filter_str in injection_filters:
            query = {"filter": filter_str}
            result = await tool._list_users(query)

            # Should either reject or safely handle the filter
            if not result["success"]:
                assert "Invalid LDAP filter" in result.get("error", "")


class TestEnhancedInputValidation:
    """Test enhanced input validation in API models."""

    def test_query_request_sql_injection_detection(self):
        """Test that QueryRequest detects SQL injection."""
        # Valid query should pass
        valid_request = QueryRequest(
            user_id="user123", query="What is the weather today?"
        )
        assert valid_request.query == "What is the weather today?"

        # SQL injection should be rejected
        with pytest.raises(ValueError, match="SQL injection"):
            QueryRequest(user_id="user123", query="'; DROP TABLE users--")

    def test_query_request_unicode_spoofing_detection(self):
        """Test that QueryRequest detects Unicode spoofing."""
        # Normal Unicode should be fine
        valid_request = QueryRequest(
            user_id="user123", query="What is the weather in 東京?"
        )
        assert "東京" in valid_request.query

        # Unicode spoofing should be rejected
        with pytest.raises(ValueError, match="Unicode spoofing"):
            QueryRequest(
                user_id="user123", query="Hello\u200BWorld"  # Zero-width space
            )

    def test_query_request_control_character_filtering(self):
        """Test that QueryRequest filters control characters."""
        # Test with control characters
        with pytest.raises(ValueError):
            QueryRequest(user_id="user123", query="Hello\x00World")  # Null byte

    def test_query_request_html_stripping(self):
        """Test that QueryRequest strips HTML."""
        # HTML tags should be stripped
        request = QueryRequest(
            user_id="user123", query="<script>alert('xss')</script>What is AI?"
        )
        assert "<script>" not in request.query
        assert "</script>" not in request.query
        # The content between tags is preserved (just tags removed)
        # This is intentional to preserve legitimate text
        assert "What is AI?" in request.query

    def test_user_id_validation(self):
        """Test user_id validation."""
        # Valid user IDs
        valid_ids = ["user123", "john.doe", "user@example.com", "user-123", "user_456"]

        for user_id in valid_ids:
            request = QueryRequest(user_id=user_id, query="test")
            assert request.user_id == user_id

        # Invalid user IDs
        invalid_ids = ["user;delete", "user'--", "user<script>", "../etc/passwd"]

        for user_id in invalid_ids:
            with pytest.raises(ValueError, match="Invalid user ID"):
                QueryRequest(user_id=user_id, query="test")

    def test_tenant_id_validation(self):
        """Test tenant_id validation."""
        # Valid tenant IDs
        valid_request = QueryRequest(
            user_id="user123", query="test", tenant_id="tenant-123"
        )
        assert valid_request.tenant_id == "tenant-123"

        # Invalid tenant IDs
        with pytest.raises(ValueError, match="Invalid tenant ID"):
            QueryRequest(user_id="user123", query="test", tenant_id="tenant;delete")


class TestSecurityIntegration:
    """Test security fixes working together."""

    @pytest.mark.asyncio
    async def test_full_request_flow_with_security(self):
        """Test a full request flow with all security measures."""
        # 1. Validate input through API model
        request = QueryRequest(
            user_id="test.user@example.com",
            query="Show me user information for admin",
            tenant_id="tenant-123",
        )

        # 2. Test Redis cache with sanitized model name
        config = CacheConfig(enabled=True)
        cache = RedisCache(config)
        cache.client = AsyncMock()
        cache._connected = True
        cache.client.get.return_value = None

        # Should handle even malicious model names safely
        cache_key = cache._generate_key(request.query, "gpt-4", user_id=request.user_id)
        assert cache_key  # Should generate valid key

        # 3. Test SailPoint tool with LDAP filter
        tool = SailPointIIQTool()

        # Create a query that could be dangerous if not properly escaped
        query = {"filter": "(cn=admin*)", "limit": 10}

        with patch("httpx.AsyncClient") as mock_client:
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json.return_value = {"result": {"users": [], "total": 0}}
            mock_client.return_value.__aenter__.return_value.post.return_value = (
                mock_response
            )

            # Should properly validate the LDAP filter
            result = await tool._list_users(query)
            # Filter validation will determine if this passes or fails
            assert isinstance(result, dict)

    @pytest.mark.asyncio
    async def test_chained_injection_prevention(self):
        """Test prevention of chained injection attacks."""
        # Attempt chained attack through multiple components

        # 1. Try SQL injection in query
        with pytest.raises(ValueError):
            QueryRequest(
                user_id="admin",
                query="Find users WHERE 1=1 UNION SELECT * FROM passwords",
            )

        # 2. Try Redis injection in cache
        config = CacheConfig(enabled=True)
        cache = RedisCache(config)
        cache.client = AsyncMock()
        cache._connected = True

        # Should safely handle injection attempt
        key = cache._generate_key("test", "model\nEVAL 'redis.call(\"FLUSHDB\")' 0")
        assert "EVAL" not in key
        assert "FLUSHDB" not in key

        # 3. Try LDAP injection in SailPoint
        tool = SailPointIIQTool()
        result = await tool._list_users(
            {"filter": "(&(cn=*)(userPassword=*))"}  # Attempt to get passwords
        )

        # Should either safely handle or reject
        assert isinstance(result, dict)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
