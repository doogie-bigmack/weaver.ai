"""Test suite for security vulnerability fixes."""

import time
import uuid
from unittest.mock import MagicMock, patch

import jwt
import pytest
from fastapi import HTTPException

from weaver_ai.crypto_utils import generate_rsa_key_pair
from weaver_ai.mcp import MCPClient, MCPServer, ToolSpec
from weaver_ai.redis.nonce_store import SyncRedisNonceStore
from weaver_ai.security.auth import APIKeyMapping, authenticate, parse_api_key_mappings
from weaver_ai.settings import AppSettings


class TestJWTRS256Migration:
    """Test JWT migration from HS256 to RS256."""

    def test_generate_rsa_keys(self):
        """Test RSA key pair generation."""
        private_key, public_key = generate_rsa_key_pair(key_size=2048)

        assert (
            "BEGIN PRIVATE KEY" in private_key or "BEGIN RSA PRIVATE KEY" in private_key
        )
        assert "BEGIN PUBLIC KEY" in public_key
        assert len(private_key) > 1000  # RSA 2048 private key is ~1600 chars
        assert len(public_key) > 300  # RSA 2048 public key is ~400 chars

    def test_rs256_jwt_signing_and_verification(self):
        """Test JWT signing with RS256."""
        private_key, public_key = generate_rsa_key_pair()

        # Create token with private key
        payload = {
            "sub": "user123",
            "exp": int(time.time()) + 3600,
            "roles": ["admin"],
            "scopes": ["read", "write"],
        }

        token = jwt.encode(payload, private_key, algorithm="RS256")

        # Verify with public key
        decoded = jwt.decode(token, public_key, algorithms=["RS256"])

        assert decoded["sub"] == "user123"
        assert decoded["roles"] == ["admin"]
        assert decoded["scopes"] == ["read", "write"]

    def test_rs256_prevents_algorithm_confusion(self):
        """Test that RS256 prevents algorithm confusion attack."""
        private_key, public_key = generate_rsa_key_pair()

        # Create legitimate RS256 token
        payload = {"sub": "user123", "exp": int(time.time()) + 3600}
        token = jwt.encode(payload, private_key, algorithm="RS256")

        # Try to verify with HS256 using public key (attack scenario)
        with pytest.raises(jwt.InvalidTokenError):
            jwt.decode(token, public_key, algorithms=["HS256"])

        # Try to create HS256 token with public key and verify as RS256 (attack)
        # Modern PyJWT correctly rejects using RSA keys for HMAC
        with pytest.raises((jwt.InvalidKeyError, jwt.InvalidSignatureError)):
            fake_token = jwt.encode(payload, public_key, algorithm="HS256")
            jwt.decode(fake_token, public_key, algorithms=["RS256"])

    def test_mcp_with_rs256(self):
        """Test MCP server and client with RS256."""
        private_key, public_key = generate_rsa_key_pair()

        # Create server with RS256
        server = MCPServer(
            server_id="test-server",
            private_key=private_key,
            use_rs256=True,
            use_redis_nonces=False,  # Use in-memory for testing
        )

        # Add a test tool
        def test_tool(args: dict) -> dict:
            return {"result": "success", "input": args}

        spec = ToolSpec(
            name="test", description="Test tool", input_schema={}, output_schema={}
        )
        server.add_tool(spec, test_tool)

        # Create client with RS256
        client = MCPClient(server=server, public_key=public_key, use_rs256=True)

        # Call tool
        result = client.call("test", {"foo": "bar"})
        assert result["result"] == "success"
        assert result["input"]["foo"] == "bar"

    def test_backward_compatibility_hs256(self):
        """Test backward compatibility with HS256."""
        shared_secret = "test-secret-key"

        # Create server with HS256 (backward compatibility)
        server = MCPServer(
            server_id="test-server",
            private_key=shared_secret,
            use_rs256=False,  # Use HS256
            use_redis_nonces=False,
        )

        # Add a test tool
        def test_tool(args: dict) -> dict:
            return {"result": "hs256-success"}

        spec = ToolSpec(
            name="test", description="Test tool", input_schema={}, output_schema={}
        )
        server.add_tool(spec, test_tool)

        # Create client with HS256
        client = MCPClient(server=server, public_key=shared_secret, use_rs256=False)

        # Call tool
        result = client.call("test", {})
        assert result["result"] == "hs256-success"


class TestAPIKeyUserMapping:
    """Test API key to user mapping security fix."""

    def test_parse_api_key_mappings_simple(self):
        """Test parsing simple API key format."""
        keys = ["key1", "key2"]
        mappings = parse_api_key_mappings(keys)

        assert mappings["key1"]["user_id"] == "anonymous"
        assert mappings["key2"]["user_id"] == "anonymous"
        assert mappings["key1"]["roles"] == []
        assert mappings["key1"]["scopes"] == []

    def test_parse_api_key_mappings_with_user(self):
        """Test parsing API key with user ID."""
        keys = ["key1:user1", "key2:user2"]
        mappings = parse_api_key_mappings(keys)

        assert mappings["key1"]["user_id"] == "user1"
        assert mappings["key2"]["user_id"] == "user2"

    def test_parse_api_key_mappings_full_format(self):
        """Test parsing API key with full format."""
        keys = ["key1:user1:admin,user:read,write", "key2:user2:developer:read"]
        mappings = parse_api_key_mappings(keys)

        assert mappings["key1"]["user_id"] == "user1"
        assert mappings["key1"]["roles"] == ["admin", "user"]
        assert mappings["key1"]["scopes"] == ["read", "write"]

        assert mappings["key2"]["user_id"] == "user2"
        assert mappings["key2"]["roles"] == ["developer"]
        assert mappings["key2"]["scopes"] == ["read"]

    def test_api_key_constant_time_comparison(self):
        """Test that API key comparison is constant-time."""
        mappings = {"correct-key": {"user_id": "user1", "roles": [], "scopes": []}}

        key_mapper = APIKeyMapping(mappings)

        # Test correct key
        assert key_mapper.get_user_info("correct-key") is not None

        # Test wrong keys (should use constant-time comparison)
        assert key_mapper.get_user_info("wrong-key") is None
        assert key_mapper.get_user_info("correct-key-extra") is None
        assert key_mapper.get_user_info("") is None

    def test_authenticate_api_key_prevents_impersonation(self):
        """Test that API key authentication prevents user impersonation."""
        settings = AppSettings(
            auth_mode="api_key", allowed_api_keys=["key123:user1:admin:read,write"]
        )

        # Test legitimate request (no x-user-id header)
        headers = {"x-api-key": "key123"}
        user = authenticate(headers, settings)
        assert user.user_id == "user1"
        assert user.roles == ["admin"]
        assert user.scopes == ["read", "write"]

        # Test legitimate request (matching x-user-id)
        headers = {"x-api-key": "key123", "x-user-id": "user1"}
        user = authenticate(headers, settings)
        assert user.user_id == "user1"

        # Test impersonation attempt (mismatched x-user-id)
        headers = {"x-api-key": "key123", "x-user-id": "user2"}
        with pytest.raises(HTTPException) as exc_info:
            authenticate(headers, settings)
        assert exc_info.value.status_code == 403
        assert "does not match" in exc_info.value.detail

    def test_authenticate_invalid_api_key(self):
        """Test authentication with invalid API key."""
        settings = AppSettings(auth_mode="api_key", allowed_api_keys=["key123:user1"])

        # Test wrong API key
        headers = {"x-api-key": "wrong-key"}
        with pytest.raises(HTTPException) as exc_info:
            authenticate(headers, settings)
        assert exc_info.value.status_code == 401
        assert "Invalid API key" in exc_info.value.detail

        # Test missing API key
        headers = {}
        with pytest.raises(HTTPException) as exc_info:
            authenticate(headers, settings)
        assert exc_info.value.status_code == 401
        assert "Missing API key" in exc_info.value.detail


class TestRedisNonceStorage:
    """Test Redis-backed nonce storage for replay attack prevention."""

    @patch("weaver_ai.redis.nonce_store.redis.from_url")
    def test_redis_nonce_store_check_and_add(self, mock_redis_from_url):
        """Test Redis nonce store check and add functionality."""
        # Mock Redis client
        mock_redis = MagicMock()
        mock_redis_from_url.return_value = mock_redis

        # Mock SET NX operation
        mock_redis.set.return_value = True  # First time: success

        store = SyncRedisNonceStore(
            redis_url="redis://localhost:6379/0",
            namespace="test",
            ttl_seconds=300,
            fallback_to_memory=False,
        )

        nonce = str(uuid.uuid4())

        # First check should succeed
        assert store.check_and_add(nonce) is True

        # Verify Redis SET was called with correct parameters
        mock_redis.set.assert_called_once()
        call_args = mock_redis.set.call_args
        assert call_args[1]["nx"] is True  # SET NX flag
        assert call_args[1]["ex"] == 300  # TTL

        # Mock replay attempt
        mock_redis.set.return_value = None  # SET NX returns None if key exists

        # Second check should fail (replay detected)
        assert store.check_and_add(nonce) is False

    def test_redis_nonce_store_fallback_to_memory(self):
        """Test fallback to in-memory storage when Redis is unavailable."""
        store = SyncRedisNonceStore(
            redis_url="redis://invalid:6379/0",  # Invalid Redis URL
            namespace="test",
            ttl_seconds=300,
            fallback_to_memory=True,
        )

        nonce = str(uuid.uuid4())

        # Should fallback to memory storage
        assert store.check_and_add(nonce) is True

        # Check in-memory store
        assert nonce in store._memory_store

        # Second check should fail (replay detected in memory)
        assert store.check_and_add(nonce) is False

    def test_redis_nonce_store_ttl_cleanup(self):
        """Test TTL-based cleanup of expired nonces."""
        store = SyncRedisNonceStore(
            redis_url="redis://invalid:6379/0",
            namespace="test",
            ttl_seconds=1,  # 1 second TTL for testing
            fallback_to_memory=True,
        )

        nonce1 = "nonce1"
        nonce2 = "nonce2"

        # Add first nonce
        assert store.check_and_add(nonce1) is True

        # Wait for TTL to expire
        time.sleep(1.1)

        # Add second nonce (should trigger cleanup)
        assert store.check_and_add(nonce2) is True

        # First nonce should be cleaned up
        assert nonce1 not in store._memory_store
        assert nonce2 in store._memory_store

        # Can reuse expired nonce
        assert store.check_and_add(nonce1) is True

    def test_redis_nonce_store_max_size_limit(self):
        """Test maximum size limit for in-memory fallback."""
        store = SyncRedisNonceStore(
            redis_url="redis://invalid:6379/0",
            namespace="test",
            ttl_seconds=3600,
            fallback_to_memory=True,
        )

        # Reduce max size for testing
        store._max_memory_nonces = 5

        # Add nonces up to limit
        nonces = []
        for i in range(6):
            nonce = f"nonce-{i}"
            nonces.append(nonce)
            store.check_and_add(nonce)

        # Should have removed oldest nonce
        assert len(store._memory_store) == 5
        assert nonces[0] not in store._memory_store  # First one removed
        assert nonces[5] in store._memory_store  # Last one present

    def test_mcp_server_with_redis_nonces(self):
        """Test MCP server with Redis nonce storage."""
        private_key, public_key = generate_rsa_key_pair()

        # Create server with Redis nonces (will fallback to memory if Redis unavailable)
        server = MCPServer(
            server_id="test-server",
            private_key=private_key,
            use_rs256=True,
            use_redis_nonces=True,
        )

        # Test nonce replay prevention
        request = {"tool": "test", "args": {}, "nonce": "test-nonce-123"}

        # Add test tool
        server.tools["test"] = lambda args: {"result": "success"}

        # First request should succeed
        response = server.handle(request)
        assert response["result"]["result"] == "success"

        # Replay attempt should fail
        with pytest.raises(ValueError, match="Nonce replay detected"):
            server.handle(request)


class TestIntegrationScenarios:
    """Integration tests for all security fixes."""

    def test_full_secure_flow_with_rs256_and_redis(self):
        """Test complete secure flow with RS256 JWT and Redis nonces."""
        # Generate RSA keys
        private_key, public_key = generate_rsa_key_pair()

        # Create secure MCP server
        server = MCPServer(
            server_id="secure-server",
            private_key=private_key,
            use_rs256=True,
            use_redis_nonces=True,
        )

        # Add tool
        def secure_tool(args: dict) -> dict:
            return {"status": "secure", "data": args.get("data", "none")}

        spec = ToolSpec(
            name="secure_operation",
            description="Secure operation",
            input_schema={"type": "object"},
            output_schema={"type": "object"},
        )
        server.add_tool(spec, secure_tool)

        # Create secure client
        client = MCPClient(server=server, public_key=public_key, use_rs256=True)

        # Execute secure operation
        result = client.call("secure_operation", {"data": "sensitive"})
        assert result["status"] == "secure"
        assert result["data"] == "sensitive"

    def test_api_key_with_roles_and_scopes(self):
        """Test API key authentication with roles and scopes."""
        settings = AppSettings(
            auth_mode="api_key",
            allowed_api_keys=[
                "admin-key:admin-user:admin,moderator:read,write,delete",
                "user-key:regular-user:user:read",
            ],
        )

        # Test admin access
        headers = {"x-api-key": "admin-key"}
        admin = authenticate(headers, settings)
        assert admin.user_id == "admin-user"
        assert "admin" in admin.roles
        assert "moderator" in admin.roles
        assert "write" in admin.scopes
        assert "delete" in admin.scopes

        # Test regular user access
        headers = {"x-api-key": "user-key"}
        user = authenticate(headers, settings)
        assert user.user_id == "regular-user"
        assert "user" in user.roles
        assert "read" in user.scopes
        assert "write" not in user.scopes  # No write scope

    def test_jwt_rs256_with_expiration(self):
        """Test JWT RS256 with expiration validation."""
        private_key, public_key = generate_rsa_key_pair()

        # Create expired token
        expired_payload = {
            "sub": "user123",
            "exp": int(time.time()) - 3600,  # Expired 1 hour ago
        }
        expired_token = jwt.encode(expired_payload, private_key, algorithm="RS256")

        # Should fail verification due to expiration
        with pytest.raises(jwt.ExpiredSignatureError):
            jwt.decode(expired_token, public_key, algorithms=["RS256"])

        # Create valid token
        valid_payload = {
            "sub": "user123",
            "exp": int(time.time()) + 3600,  # Valid for 1 hour
        }
        valid_token = jwt.encode(valid_payload, private_key, algorithm="RS256")

        # Should pass verification
        decoded = jwt.decode(valid_token, public_key, algorithms=["RS256"])
        assert decoded["sub"] == "user123"


if __name__ == "__main__":
    # Run tests
    pytest.main([__file__, "-v"])
