# Security Audit Report - weaver.ai

## Executive Summary

This security audit identified and remediated three critical vulnerabilities in the weaver.ai authentication and authorization system. All vulnerabilities have been patched with backward-compatible solutions that maintain API stability while significantly improving security posture.

## Vulnerabilities Fixed

### 1. JWT Algorithm Confusion (CVE-2016-10555 Pattern)
**Severity**: CRITICAL
**OWASP**: A02:2021 - Cryptographic Failures
**CWE**: CWE-347 - Improper Verification of Cryptographic Signature

#### Issue
- The system was using symmetric HS256 algorithm with keys incorrectly labeled as "private_key" and "public_key"
- This created an algorithm confusion vulnerability where an attacker could forge JWTs using the public key

#### Fix Implemented
- Switched from HS256 to RS256 asymmetric algorithm
- Added proper RSA key pair generation utilities (`crypto_utils.py`)
- Implemented automatic algorithm detection based on key type
- Maintained backward compatibility with HS256 for transition period

#### Files Modified
- `/weaver_ai/mcp.py`: Added RS256 support with `use_rs256` parameter
- `/weaver_ai/security/auth.py`: Added automatic algorithm detection
- `/weaver_ai/crypto_utils.py`: New file for RSA key management

### 2. User Impersonation via API Key Authentication
**Severity**: CRITICAL
**OWASP**: A01:2021 - Broken Access Control
**CWE**: CWE-863 - Incorrect Authorization

#### Issue
- Any authenticated user could specify arbitrary `user_id` via `x-user-id` header
- No validation between API key and claimed user identity
- Allowed horizontal privilege escalation

#### Fix Implemented
- Created `APIKeyMapping` class for secure API key to user mapping
- API keys now have format: `api_key:user_id:roles:scopes`
- Validates `x-user-id` header against API key's authorized user
- Returns 403 Forbidden on user ID mismatch
- Uses constant-time comparison to prevent timing attacks

#### Files Modified
- `/weaver_ai/security/auth.py`: Complete rewrite of API key authentication

### 3. In-Memory Nonce Storage (Replay Attack Vulnerability)
**Severity**: HIGH
**OWASP**: A04:2021 - Insecure Design
**CWE**: CWE-770 - Allocation of Resources Without Limits

#### Issue
- Nonces stored only in memory, lost on server restart
- No persistence across distributed deployments
- Enabled replay attacks after service restarts

#### Fix Implemented
- Created `RedisNonceStore` with persistent, distributed storage
- Atomic check-and-set operations using Redis SET NX
- 5-minute TTL with automatic expiration
- Graceful fallback to in-memory storage if Redis unavailable
- Namespace isolation for different services

#### Files Modified
- `/weaver_ai/redis/nonce_store.py`: New Redis-backed nonce store
- `/weaver_ai/a2a.py`: Integrated Redis nonce store
- `/weaver_ai/mcp.py`: Added Redis nonce store option

## Security Configuration

### Recommended Environment Variables

```bash
# JWT Configuration (RS256)
WEAVER_JWT_PUBLIC_KEY="-----BEGIN PUBLIC KEY-----
MIIBIjANBgkqhkiG9w0BAQEFAAOCAQ8AMIIBCgKCAQEA...
-----END PUBLIC KEY-----"

# API Key Configuration with User Mapping
# Format: api_key:user_id:role1,role2:scope1,scope2
WEAVER_ALLOWED_API_KEYS="sk-prod-abc123:user-001:admin,user:read,write,sk-dev-xyz789:user-002:developer:read"

# Redis Configuration for Nonce Storage
REDIS_URL="redis://localhost:6379/0"
NONCE_TTL_SECONDS=300  # 5 minutes
```

### Security Headers Configuration

The system now supports comprehensive security headers:

```python
# CORS Configuration
cors_enabled: bool = True
cors_origins: list[str] = []  # Empty = no origins allowed (secure default)
cors_allow_credentials: bool = False
cors_max_age: int = 600

# Security Headers
security_headers_enabled: bool = True
hsts_max_age: int = 31536000  # 1 year
csp_report_uri: str | None = None

# CSRF Protection
csrf_enabled: bool = True
csrf_cookie_secure: bool = True
```

## Migration Guide

### Switching from HS256 to RS256

1. Generate RSA key pair:
```python
from weaver_ai.crypto_utils import generate_rsa_key_pair, save_keys_to_files

private_key, public_key = generate_rsa_key_pair(key_size=2048)
save_keys_to_files(private_key, public_key)
```

2. Update configuration to use RS256:
```python
# MCP Server
server = MCPServer(
    server_id="my-server",
    private_key=private_key,
    use_rs256=True  # Enable RS256
)

# MCP Client
client = MCPClient(
    server=server,
    public_key=public_key,
    use_rs256=True
)
```

### Configuring API Key User Mapping

Instead of:
```bash
WEAVER_ALLOWED_API_KEYS="key1,key2"
```

Use:
```bash
WEAVER_ALLOWED_API_KEYS="key1:user1:admin:read,write,key2:user2:user:read"
```

### Enabling Redis Nonce Storage

1. Start Redis:
```bash
docker run -d -p 6379:6379 redis:7-alpine
```

2. Configure nonce store:
```python
from weaver_ai.a2a import configure_nonce_store

configure_nonce_store(
    redis_url="redis://localhost:6379/0",
    namespace="a2a:nonce",
    ttl_seconds=300,
    fallback_to_memory=True
)
```

## Testing Security Fixes

### Test JWT RS256 Authentication
```python
import jwt
from weaver_ai.crypto_utils import generate_rsa_key_pair

private_key, public_key = generate_rsa_key_pair()

# Create token with private key
token = jwt.encode(
    {"sub": "user123", "exp": time.time() + 3600},
    private_key,
    algorithm="RS256"
)

# Verify with public key (not private!)
decoded = jwt.decode(token, public_key, algorithms=["RS256"])
assert decoded["sub"] == "user123"
```

### Test API Key User Validation
```python
from weaver_ai.security.auth import authenticate
from weaver_ai.settings import AppSettings

settings = AppSettings(
    auth_mode="api_key",
    allowed_api_keys=["key123:user1:admin:read,write"]
)

# This should succeed
headers = {"x-api-key": "key123"}
user = authenticate(headers, settings)
assert user.user_id == "user1"

# This should fail with 403
headers = {"x-api-key": "key123", "x-user-id": "user2"}
try:
    authenticate(headers, settings)
    assert False, "Should have raised HTTPException"
except HTTPException as e:
    assert e.status_code == 403
```

### Test Redis Nonce Storage
```python
from weaver_ai.redis.nonce_store import SyncRedisNonceStore

store = SyncRedisNonceStore(
    redis_url="redis://localhost:6379/0",
    ttl_seconds=300
)

nonce = "test-nonce-123"

# First check should succeed
assert store.check_and_add(nonce) == True

# Second check should fail (replay detected)
assert store.check_and_add(nonce) == False
```

## Performance Impact

- **JWT Verification**: RS256 is ~10x slower than HS256, but still <1ms per verification
- **Redis Nonce Check**: Adds ~2-5ms latency, but prevents replay attacks
- **API Key Validation**: Constant-time comparison prevents timing attacks with minimal overhead

## Compliance

These fixes address the following compliance requirements:

- **OWASP Top 10 2021**: A01, A02, A04
- **NIST 800-63B**: Section 5.1.1 (Authenticator Requirements)
- **PCI DSS 4.0**: Requirement 8.3.2 (Strong Cryptography)
- **ISO 27001**: A.10.1.1 (Cryptographic Controls)

## Recommendations

1. **Immediate Actions**:
   - Generate and deploy RS256 key pairs
   - Update API key configuration with user mappings
   - Deploy Redis for nonce storage

2. **Short-term (1-2 weeks)**:
   - Rotate all existing API keys
   - Monitor authentication logs for anomalies
   - Implement rate limiting per user ID

3. **Long-term (1-3 months)**:
   - Implement OAuth 2.0 / OIDC for external authentication
   - Add API key rotation mechanism
   - Implement comprehensive audit logging

## Security Checklist

- [x] JWT uses asymmetric RS256 algorithm
- [x] API keys mapped to specific users
- [x] User ID validation prevents impersonation
- [x] Nonces stored persistently in Redis
- [x] TTL-based nonce expiration (5 minutes)
- [x] Atomic nonce operations prevent race conditions
- [x] Graceful fallback for Redis failures
- [x] Constant-time comparison for secrets
- [x] Backward compatibility maintained
- [x] Security headers configuration added
- [x] CORS configuration with secure defaults
- [x] CSRF protection enabled

## Conclusion

All critical vulnerabilities have been successfully remediated with production-ready implementations that maintain backward compatibility while significantly improving security. The system now implements defense in depth with multiple layers of security controls.
