"""Security headers middleware for enhanced application security.

This module implements comprehensive security headers following OWASP recommendations
to protect against common web vulnerabilities including XSS, clickjacking, MIME sniffing,
and other security threats.

References:
- OWASP Secure Headers Project: https://owasp.org/www-project-secure-headers/
- MDN Web Security: https://developer.mozilla.org/en-US/docs/Web/Security
"""

from __future__ import annotations

import json
import logging
from typing import Callable, Literal

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp

logger = logging.getLogger(__name__)


class SecurityHeadersConfig:
    """Configuration for security headers middleware.

    All headers follow OWASP recommendations with secure defaults.
    """

    def __init__(
        self,
        # Content Security Policy - Defense against XSS
        csp_enabled: bool = True,
        csp_directives: dict[str, str | list[str]] | None = None,
        csp_report_uri: str | None = None,
        csp_report_only: bool = False,
        # Frame Options - Clickjacking protection
        frame_options: Literal["DENY", "SAMEORIGIN"] = "DENY",
        # Content Type Options - MIME sniffing protection
        content_type_options: bool = True,
        # HSTS - Force HTTPS
        hsts_enabled: bool = True,
        hsts_max_age: int = 31536000,  # 1 year
        hsts_include_subdomains: bool = True,
        hsts_preload: bool = True,
        # XSS Protection - Legacy but still useful for older browsers
        xss_protection: bool = True,
        # Referrer Policy - Control referrer information
        referrer_policy: Literal[
            "no-referrer",
            "no-referrer-when-downgrade",
            "origin",
            "origin-when-cross-origin",
            "same-origin",
            "strict-origin",
            "strict-origin-when-cross-origin",
            "unsafe-url",
        ] = "strict-origin-when-cross-origin",
        # Permissions Policy (formerly Feature Policy)
        permissions_policy_enabled: bool = True,
        permissions_policy: dict[str, str | list[str]] | None = None,
        # Additional security headers
        x_permitted_cross_domain_policies: Literal[
            "none", "master-only", "by-content-type", "all"
        ] = "none",
        x_download_options: bool = True,  # IE8+ only
        x_dns_prefetch_control: Literal["on", "off"] = "off",
    ):
        self.csp_enabled = csp_enabled
        self.csp_report_uri = csp_report_uri
        self.csp_report_only = csp_report_only

        # Default CSP directives - very restrictive by default
        self.csp_directives = csp_directives or {
            "default-src": "'self'",
            "script-src": [
                "'self'",
                "'unsafe-inline'",
            ],  # Allow inline scripts for API responses
            "style-src": ["'self'", "'unsafe-inline'"],
            "img-src": ["'self'", "data:", "https:"],
            "font-src": ["'self'"],
            "connect-src": ["'self'"],
            "media-src": "'none'",
            "object-src": "'none'",
            "frame-src": "'none'",
            "frame-ancestors": "'none'",
            "form-action": "'self'",
            "base-uri": "'self'",
            "upgrade-insecure-requests": "",
        }

        self.frame_options = frame_options
        self.content_type_options = content_type_options
        self.hsts_enabled = hsts_enabled
        self.hsts_max_age = hsts_max_age
        self.hsts_include_subdomains = hsts_include_subdomains
        self.hsts_preload = hsts_preload
        self.xss_protection = xss_protection
        self.referrer_policy = referrer_policy
        self.permissions_policy_enabled = permissions_policy_enabled

        # Default Permissions Policy - restrictive by default
        self.permissions_policy = permissions_policy or {
            "accelerometer": "()",
            "ambient-light-sensor": "()",
            "autoplay": "()",
            "battery": "()",
            "camera": "()",
            "display-capture": "()",
            "document-domain": "()",
            "encrypted-media": "()",
            "execution-while-not-rendered": "()",
            "execution-while-out-of-viewport": "()",
            "fullscreen": "(self)",
            "gamepad": "()",
            "geolocation": "()",
            "gyroscope": "()",
            "magnetometer": "()",
            "microphone": "()",
            "midi": "()",
            "navigation-override": "()",
            "payment": "()",
            "picture-in-picture": "()",
            "publickey-credentials-get": "()",
            "speaker-selection": "()",
            "sync-xhr": "()",
            "usb": "()",
            "web-share": "()",
            "xr-spatial-tracking": "()",
        }

        self.x_permitted_cross_domain_policies = x_permitted_cross_domain_policies
        self.x_download_options = x_download_options
        self.x_dns_prefetch_control = x_dns_prefetch_control

    def build_csp_header(self) -> str:
        """Build Content-Security-Policy header value from directives."""
        if not self.csp_directives:
            return ""

        csp_parts = []
        for directive, value in self.csp_directives.items():
            if isinstance(value, list):
                csp_parts.append(f"{directive} {' '.join(value)}")
            elif value:  # Non-empty string
                csp_parts.append(f"{directive} {value}")
            else:  # Empty string for directives without values
                csp_parts.append(directive)

        csp_header = "; ".join(csp_parts)

        # Add report-uri if configured
        if self.csp_report_uri:
            csp_header += f"; report-uri {self.csp_report_uri}"

        return csp_header

    def build_permissions_policy_header(self) -> str:
        """Build Permissions-Policy header value from policy dict."""
        if not self.permissions_policy:
            return ""

        policy_parts = []
        for feature, allowlist in self.permissions_policy.items():
            if isinstance(allowlist, list):
                policy_parts.append(f'{feature}=({" ".join(allowlist)})')
            else:
                policy_parts.append(f"{feature}={allowlist}")

        return ", ".join(policy_parts)

    def build_hsts_header(self) -> str:
        """Build Strict-Transport-Security header value."""
        hsts_parts = [f"max-age={self.hsts_max_age}"]

        if self.hsts_include_subdomains:
            hsts_parts.append("includeSubDomains")

        if self.hsts_preload:
            hsts_parts.append("preload")

        return "; ".join(hsts_parts)


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Middleware to add comprehensive security headers to all responses.

    This middleware adds security headers following OWASP best practices
    to protect against common web vulnerabilities.
    """

    def __init__(self, app: ASGIApp, config: SecurityHeadersConfig | None = None):
        super().__init__(app)
        self.config = config or SecurityHeadersConfig()
        logger.info("SecurityHeadersMiddleware initialized with config")

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Add security headers to the response."""
        # Process the request
        response = await call_next(request)

        # Add Content-Security-Policy
        if self.config.csp_enabled:
            csp_header = self.config.build_csp_header()
            if csp_header:
                header_name = (
                    "Content-Security-Policy-Report-Only"
                    if self.config.csp_report_only
                    else "Content-Security-Policy"
                )
                response.headers[header_name] = csp_header

        # Add X-Frame-Options
        if self.config.frame_options:
            response.headers["X-Frame-Options"] = self.config.frame_options

        # Add X-Content-Type-Options
        if self.config.content_type_options:
            response.headers["X-Content-Type-Options"] = "nosniff"

        # Add Strict-Transport-Security (only for HTTPS)
        # Note: In production, check if request is HTTPS
        if self.config.hsts_enabled:
            response.headers["Strict-Transport-Security"] = (
                self.config.build_hsts_header()
            )

        # Add X-XSS-Protection (legacy but still useful)
        if self.config.xss_protection:
            response.headers["X-XSS-Protection"] = "1; mode=block"

        # Add Referrer-Policy
        if self.config.referrer_policy:
            response.headers["Referrer-Policy"] = self.config.referrer_policy

        # Add Permissions-Policy
        if self.config.permissions_policy_enabled:
            permissions_header = self.config.build_permissions_policy_header()
            if permissions_header:
                response.headers["Permissions-Policy"] = permissions_header

        # Add X-Permitted-Cross-Domain-Policies (Adobe products)
        if self.config.x_permitted_cross_domain_policies:
            response.headers["X-Permitted-Cross-Domain-Policies"] = (
                self.config.x_permitted_cross_domain_policies
            )

        # Add X-Download-Options (IE8+)
        if self.config.x_download_options:
            response.headers["X-Download-Options"] = "noopen"

        # Add X-DNS-Prefetch-Control
        if self.config.x_dns_prefetch_control:
            response.headers["X-DNS-Prefetch-Control"] = (
                self.config.x_dns_prefetch_control
            )

        return response


def get_api_security_config() -> SecurityHeadersConfig:
    """Get security configuration optimized for API services.

    This configuration is more permissive for API endpoints while
    still maintaining strong security.
    """
    return SecurityHeadersConfig(
        # CSP for API - allow data URIs and external connections
        csp_directives={
            "default-src": "'none'",
            "script-src": "'none'",
            "style-src": "'none'",
            "img-src": "'none'",
            "font-src": "'none'",
            "connect-src": "'self'",
            "media-src": "'none'",
            "object-src": "'none'",
            "frame-src": "'none'",
            "frame-ancestors": "'none'",
            "form-action": "'none'",
            "base-uri": "'none'",
        },
        # API doesn't need frame embedding
        frame_options="DENY",
        # Force HTTPS in production
        hsts_enabled=True,
        # API-specific referrer policy
        referrer_policy="strict-origin-when-cross-origin",
        # Disable features not needed for API
        permissions_policy={
            "accelerometer": "()",
            "camera": "()",
            "geolocation": "()",
            "gyroscope": "()",
            "magnetometer": "()",
            "microphone": "()",
            "payment": "()",
            "usb": "()",
        },
    )
