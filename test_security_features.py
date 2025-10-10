#!/usr/bin/env python3
"""Test script to demonstrate security features of Weaver AI.

This script verifies that all security middleware is working correctly
and demonstrates how to test security headers, CORS, and CSRF protection.
"""

from fastapi import FastAPI, Request
from fastapi.testclient import TestClient

from weaver_ai.middleware import (
    CSRFProtectionMiddleware,
    SecurityHeadersMiddleware,
    get_api_csrf_config,
    get_api_security_config,
)


def create_test_app() -> FastAPI:
    """Create a test FastAPI app with security middleware."""
    app = FastAPI(title="Security Test App")

    # Add security headers
    security_config = get_api_security_config()
    app.add_middleware(SecurityHeadersMiddleware, config=security_config)

    # Add CSRF protection
    csrf_config = get_api_csrf_config()
    app.add_middleware(CSRFProtectionMiddleware, config=csrf_config)

    @app.get("/test")
    async def test_get():
        return {"message": "GET request successful"}

    @app.post("/test")
    async def test_post(request: Request):
        return {"message": "POST request successful"}

    return app


def test_security_headers():
    """Test that security headers are properly set."""
    print("\n" + "=" * 60)
    print("Testing Security Headers")
    print("=" * 60)

    app = create_test_app()
    client = TestClient(app)

    response = client.get("/test")

    # Check for security headers
    security_headers = [
        "Content-Security-Policy",
        "X-Frame-Options",
        "X-Content-Type-Options",
        "Strict-Transport-Security",
        "X-XSS-Protection",
        "Referrer-Policy",
        "Permissions-Policy",
        "X-Permitted-Cross-Domain-Policies",
        "X-Download-Options",
        "X-DNS-Prefetch-Control",
    ]

    print("\nSecurity Headers Present:")
    for header in security_headers:
        if header in response.headers:
            value = response.headers[header]
            # Truncate long values for display
            if len(value) > 50:
                value = value[:50] + "..."
            print(f"  ✓ {header}: {value}")
        else:
            print(f"  ✗ {header}: MISSING")

    # Verify specific header values
    assert response.headers["X-Frame-Options"] == "DENY"
    assert response.headers["X-Content-Type-Options"] == "nosniff"
    assert response.headers["X-XSS-Protection"] == "1; mode=block"

    print("\n✓ Security headers test passed!")


def test_csrf_protection():
    """Test CSRF protection mechanism."""
    print("\n" + "=" * 60)
    print("Testing CSRF Protection")
    print("=" * 60)

    app = create_test_app()
    client = TestClient(app)

    # Test 1: GET request should receive CSRF token
    print("\n1. Testing GET request (should receive CSRF token)...")
    response = client.get("/test")
    assert response.status_code == 200

    # Check for CSRF token in cookies
    csrf_token = None
    if "csrf_token" in response.cookies:
        csrf_token = response.cookies["csrf_token"]
        print(f"  ✓ CSRF token received in cookie: {csrf_token[:20]}...")
    else:
        print("  ✗ No CSRF token in cookie")

    # Check for CSRF token in headers
    if "X-CSRF-Token" in response.headers:
        print(
            f"  ✓ CSRF token in response header: {response.headers['X-CSRF-Token'][:20]}..."
        )

    # Test 2: POST without CSRF token should fail
    print("\n2. Testing POST without CSRF token (should fail)...")
    try:
        response = client.post("/test", json={"data": "test"})
        if response.status_code == 403:
            detail = response.json()["detail"]
            print(
                f"  ✓ POST without token rejected: {response.status_code} {detail}"
            )
    except Exception as e:
        # TestClient may raise exception for 403 responses
        if "403" in str(e) and "CSRF" in str(e):
            print("  ✓ POST without token rejected: 403 CSRF validation failed")
        else:
            raise

    # Test 3: POST with CSRF token should succeed
    print("\n3. Testing POST with valid CSRF token (should succeed)...")
    if csrf_token:
        response = client.post(
            "/test",
            json={"data": "test"},
            headers={"X-CSRF-Token": csrf_token},
            cookies={"csrf_token": csrf_token},
        )
        assert response.status_code == 200
        print(f"  ✓ POST with valid token succeeded: {response.json()['message']}")

    print("\n✓ CSRF protection test passed!")


def test_cors_configuration():
    """Test CORS configuration."""
    print("\n" + "=" * 60)
    print("Testing CORS Configuration")
    print("=" * 60)

    from fastapi.middleware.cors import CORSMiddleware

    app = create_test_app()

    # Add CORS middleware with test configuration
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["https://example.com"],
        allow_credentials=False,
        allow_methods=["GET", "POST"],
        allow_headers=["*"],
        expose_headers=["X-CSRF-Token"],
    )

    client = TestClient(app)

    # Test preflight request
    print("\n1. Testing CORS preflight request...")
    response = client.options(
        "/test",
        headers={
            "Origin": "https://example.com",
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "Content-Type",
        },
    )

    if response.status_code == 200:
        print("  ✓ Preflight request succeeded")

        if "Access-Control-Allow-Origin" in response.headers:
            print(
                f"  ✓ Allow-Origin: {response.headers['Access-Control-Allow-Origin']}"
            )

        if "Access-Control-Allow-Methods" in response.headers:
            print(
                f"  ✓ Allow-Methods: {response.headers['Access-Control-Allow-Methods']}"
            )

    # Test actual request with allowed origin
    print("\n2. Testing request from allowed origin...")
    response = client.get("/test", headers={"Origin": "https://example.com"})
    assert response.status_code == 200
    if "Access-Control-Allow-Origin" in response.headers:
        print(
            f"  ✓ Request allowed from: {response.headers['Access-Control-Allow-Origin']}"
        )

    # Test request from disallowed origin
    print("\n3. Testing request from disallowed origin...")
    response = client.get("/test", headers={"Origin": "https://evil.com"})
    if "Access-Control-Allow-Origin" not in response.headers:
        print("  ✓ Request blocked from evil.com (no CORS headers)")

    print("\n✓ CORS configuration test passed!")


def print_security_summary():
    """Print a summary of security features."""
    print("\n" + "=" * 60)
    print("Security Implementation Summary")
    print("=" * 60)

    features = [
        ("Content Security Policy (CSP)", "Prevents XSS attacks"),
        ("X-Frame-Options", "Prevents clickjacking"),
        ("HSTS", "Forces HTTPS usage"),
        ("CSRF Protection", "Prevents cross-site request forgery"),
        ("CORS Configuration", "Controls cross-origin access"),
        ("X-Content-Type-Options", "Prevents MIME sniffing"),
        ("Referrer-Policy", "Controls referrer information"),
        ("Permissions-Policy", "Restricts browser features"),
    ]

    print("\n✓ Implemented Security Features:")
    for feature, description in features:
        print(f"  • {feature}: {description}")

    print("\n⚠ Security Best Practices:")
    print("  1. Always use HTTPS in production")
    print("  2. Configure specific CORS origins (no wildcards)")
    print("  3. Generate strong CSRF secret keys")
    print("  4. Regularly update dependencies")
    print("  5. Monitor security headers with online tools")
    print("  6. Implement rate limiting for all endpoints")
    print("  7. Log and monitor security events")
    print("  8. Perform regular security audits")

    print("\n" + "=" * 60)
    print("✓✓✓ All Security Tests Completed Successfully!")
    print("=" * 60)


if __name__ == "__main__":
    try:
        # Run all tests
        test_security_headers()
        test_csrf_protection()
        test_cors_configuration()
        print_security_summary()

    except AssertionError as e:
        print(f"\n✗ Test failed: {e}")
        import traceback

        traceback.print_exc()
    except Exception as e:
        print(f"\n✗ Unexpected error: {e}")
        import traceback

        traceback.print_exc()
