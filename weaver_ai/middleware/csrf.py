"""CSRF (Cross-Site Request Forgery) protection middleware.

This module implements CSRF protection using the double-submit cookie pattern,
which is stateless and suitable for API services.

References:
- OWASP CSRF Prevention: https://cheatsheetseries.owasp.org/cheatsheets/Cross-Site_Request_Forgery_Prevention_Cheat_Sheet.html
- OWASP Top 10: A01:2021 – Broken Access Control
"""

from __future__ import annotations

import hashlib
import hmac
import logging
import secrets
import time
from collections.abc import Callable

from fastapi import HTTPException, Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp

logger = logging.getLogger(__name__)


class CSRFConfig:
    """Configuration for CSRF protection middleware."""

    def __init__(
        self,
        # Enable/disable CSRF protection
        enabled: bool = True,
        # Token configuration
        token_name: str = "X-CSRF-Token",
        cookie_name: str = "csrf_token",
        header_name: str = "X-CSRF-Token",
        # Cookie settings
        cookie_secure: bool = True,  # HTTPS only
        cookie_httponly: bool = False,  # Must be accessible to JS for header
        cookie_samesite: str = "strict",
        cookie_path: str = "/",
        cookie_domain: str | None = None,
        cookie_max_age: int = 3600,  # 1 hour
        # Token validation
        token_length: int = 32,  # bytes
        time_limit: int = 3600,  # seconds
        # Safe methods that don't require CSRF token
        safe_methods: set[str] | None = None,
        # Paths to exclude from CSRF protection
        exclude_paths: set[str] | None = None,
        # Secret key for HMAC (should be from environment)
        secret_key: str | None = None,
        # Allow token in form data
        check_form_data: bool = False,
        form_field_name: str = "csrf_token",
        # Custom error message
        error_message: str = "CSRF validation failed",
        # Double submit cookie validation
        use_double_submit: bool = True,
        # Signed tokens for additional security
        use_signed_tokens: bool = True,
    ):
        self.enabled = enabled
        self.token_name = token_name
        self.cookie_name = cookie_name
        self.header_name = header_name
        self.cookie_secure = cookie_secure
        self.cookie_httponly = cookie_httponly
        self.cookie_samesite = cookie_samesite
        self.cookie_path = cookie_path
        self.cookie_domain = cookie_domain
        self.cookie_max_age = cookie_max_age
        self.token_length = token_length
        self.time_limit = time_limit
        self.safe_methods = safe_methods or {"GET", "HEAD", "OPTIONS", "TRACE"}
        self.exclude_paths = exclude_paths or {
            "/health",
            "/metrics",
            "/docs",
            "/redoc",
            "/openapi.json",
        }
        self.secret_key = secret_key or secrets.token_hex(32)
        self.check_form_data = check_form_data
        self.form_field_name = form_field_name
        self.error_message = error_message
        self.use_double_submit = use_double_submit
        self.use_signed_tokens = use_signed_tokens


class CSRFProtectionMiddleware(BaseHTTPMiddleware):
    """Middleware for CSRF protection using double-submit cookie pattern.

    This implementation follows OWASP recommendations:
    1. Uses cryptographically secure random tokens
    2. Implements double-submit cookie pattern (stateless)
    3. Validates token presence and equality
    4. Supports signed tokens for additional security
    5. Exempts safe HTTP methods (GET, HEAD, OPTIONS)
    """

    def __init__(self, app: ASGIApp, config: CSRFConfig | None = None):
        super().__init__(app)
        self.config = config or CSRFConfig()
        logger.info("CSRFProtectionMiddleware initialized")

    def generate_token(self) -> str:
        """Generate a cryptographically secure CSRF token."""
        # Generate random token
        token = secrets.token_urlsafe(self.config.token_length)

        if self.config.use_signed_tokens:
            # Add timestamp and sign the token
            timestamp = str(int(time.time()))
            message = f"{token}.{timestamp}"
            signature = self._sign_token(message)
            return f"{message}.{signature}"

        return token

    def _sign_token(self, message: str) -> str:
        """Sign a token using HMAC-SHA256."""
        return hmac.new(
            self.config.secret_key.encode(), message.encode(), hashlib.sha256
        ).hexdigest()

    def validate_token(self, token: str) -> bool:
        """Validate a CSRF token including signature and timestamp."""
        if not token:
            return False

        if not self.config.use_signed_tokens:
            # Simple token validation - just check it exists and has correct length
            return len(token) >= self.config.token_length

        # Validate signed token
        try:
            parts = token.split(".")
            if len(parts) != 3:
                logger.debug("Invalid token format: wrong number of parts")
                return False

            token_value, timestamp_str, signature = parts

            # Verify signature
            message = f"{token_value}.{timestamp_str}"
            expected_signature = self._sign_token(message)

            if not hmac.compare_digest(signature, expected_signature):
                logger.debug("Invalid token: signature mismatch")
                return False

            # Verify timestamp
            timestamp = int(timestamp_str)
            current_time = int(time.time())

            if current_time - timestamp > self.config.time_limit:
                logger.debug("Token expired")
                return False

            return True

        except (ValueError, AttributeError) as e:
            logger.debug(f"Token validation error: {e}")
            return False

    def get_token_from_request(self, request: Request) -> str | None:
        """Extract CSRF token from request headers or form data."""
        # Check header first (most common for APIs)
        token = request.headers.get(self.config.header_name)
        if token:
            return token

        # Check custom header alternatives
        token = request.headers.get(self.config.token_name)
        if token:
            return token

        # Check form data if configured (for form submissions)
        if self.config.check_form_data and request.method == "POST":
            # Note: This would need to be async and parse form data
            # For API-focused implementation, we'll skip form data checking
            pass

        return None

    def should_check_csrf(self, request: Request) -> bool:
        """Determine if CSRF check should be performed for this request."""
        # Skip if disabled
        if not self.config.enabled:
            return False

        # Skip for safe methods
        if request.method in self.config.safe_methods:
            return False

        # Skip for excluded paths
        if request.url.path in self.config.exclude_paths:
            return False

        # Skip for preflight requests
        if request.method == "OPTIONS":
            return False

        return True

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Process request and validate CSRF token for state-changing operations."""

        # Generate new token for GET requests (to be included in forms/AJAX)
        if request.method == "GET" and self.config.enabled:
            response = await call_next(request)

            # Set CSRF cookie if not present
            csrf_cookie = request.cookies.get(self.config.cookie_name)
            if not csrf_cookie:
                new_token = self.generate_token()
                response.set_cookie(
                    key=self.config.cookie_name,
                    value=new_token,
                    secure=self.config.cookie_secure,
                    httponly=self.config.cookie_httponly,
                    samesite=self.config.cookie_samesite,
                    path=self.config.cookie_path,
                    domain=self.config.cookie_domain,
                    max_age=self.config.cookie_max_age,
                )
                # Also add token to response header for easy access
                response.headers[self.config.header_name] = new_token

            return response

        # Check CSRF for state-changing operations
        if self.should_check_csrf(request):
            # Get token from cookie (double-submit pattern)
            cookie_token = request.cookies.get(self.config.cookie_name)
            if not cookie_token:
                logger.warning(
                    f"CSRF validation failed: no cookie token for {request.url.path}"
                )
                raise HTTPException(
                    status_code=403,
                    detail=self.config.error_message,
                    headers={"X-CSRF-Failure": "missing-cookie"},
                )

            # Get token from request (header or form)
            request_token = self.get_token_from_request(request)
            if not request_token:
                logger.warning(
                    f"CSRF validation failed: no request token for {request.url.path}"
                )
                raise HTTPException(
                    status_code=403,
                    detail=self.config.error_message,
                    headers={"X-CSRF-Failure": "missing-token"},
                )

            # Validate tokens match (double-submit check)
            if self.config.use_double_submit:
                if not hmac.compare_digest(cookie_token, request_token):
                    logger.warning(
                        f"CSRF validation failed: token mismatch for {request.url.path}"
                    )
                    raise HTTPException(
                        status_code=403,
                        detail=self.config.error_message,
                        headers={"X-CSRF-Failure": "token-mismatch"},
                    )

            # Validate token signature and timestamp
            if self.config.use_signed_tokens:
                if not self.validate_token(cookie_token):
                    logger.warning(
                        f"CSRF validation failed: invalid token for {request.url.path}"
                    )
                    raise HTTPException(
                        status_code=403,
                        detail=self.config.error_message,
                        headers={"X-CSRF-Failure": "invalid-token"},
                    )

        # Process request
        response = await call_next(request)

        # Rotate token on successful state-changing operation (optional)
        if self.should_check_csrf(request) and response.status_code < 400:
            # Generate new token for next request
            new_token = self.generate_token()
            response.set_cookie(
                key=self.config.cookie_name,
                value=new_token,
                secure=self.config.cookie_secure,
                httponly=self.config.cookie_httponly,
                samesite=self.config.cookie_samesite,
                path=self.config.cookie_path,
                domain=self.config.cookie_domain,
                max_age=self.config.cookie_max_age,
            )
            # Add to header for client convenience
            response.headers[self.config.header_name] = new_token

        return response


def get_api_csrf_config(secret_key: str | None = None) -> CSRFConfig:
    """Get CSRF configuration optimized for API services.

    This configuration:
    - Uses double-submit cookie pattern (stateless)
    - Requires CSRF token in headers for state-changing operations
    - Exempts safe methods and health check endpoints
    - Uses signed tokens with timestamp validation

    Args:
        secret_key: Secret key for signing tokens (should be from environment)

    Returns:
        CSRFConfig instance for API use
    """
    import os

    return CSRFConfig(
        enabled=True,
        # Use environment variable for secret key in production
        secret_key=secret_key or os.getenv("CSRF_SECRET_KEY"),
        # API-specific settings
        cookie_secure=os.getenv("CSRF_COOKIE_SECURE", "true").lower() == "true",
        cookie_httponly=False,  # Must be readable by JavaScript for API calls
        cookie_samesite="strict",
        # Exempt common API endpoints
        exclude_paths={
            "/health",
            "/metrics",
            "/docs",
            "/redoc",
            "/openapi.json",
            "/a2a/card",  # A2A discovery endpoint
            "/ask",  # Main query endpoint (uses API key auth)
            "/whoami",  # Auth info endpoint
            "/a2a/message",  # A2A message handling endpoint
        },
        # Use signed tokens with 1 hour expiry
        use_signed_tokens=True,
        time_limit=3600,
        # API-focused: only check headers, not form data
        check_form_data=False,
        # Clear error message for API consumers
        error_message=(
            "CSRF token validation failed. Please include a valid CSRF token "
            "in the X-CSRF-Token header."
        ),
    )
