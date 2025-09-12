from __future__ import annotations

import time
from collections import defaultdict

from fastapi import HTTPException, Request

from ..settings import AppSettings


class TokenBucket:
    def __init__(self, rate: int, burst: int):
        self.rate = rate
        self.capacity = burst
        self.tokens = burst
        self.timestamp = time.time()

    def consume(self, amount: int = 1) -> bool:
        now = time.time()
        self.tokens = min(
            self.capacity, self.tokens + int((now - self.timestamp) * self.rate)
        )
        self.timestamp = now
        if self.tokens >= amount:
            self.tokens -= amount
            return True
        return False


# Separate buckets for users and IPs
_USER_BUCKETS: dict[str, TokenBucket] = defaultdict(lambda: TokenBucket(1, 1))
_IP_BUCKETS: dict[str, TokenBucket] = defaultdict(lambda: TokenBucket(1, 1))
_GLOBAL_BUCKET = TokenBucket(100, 100)  # Global rate limit


def get_client_ip(request: Request) -> str:
    """
    Get the real client IP address.
    Do NOT trust X-Forwarded-For and similar headers as they can be spoofed.
    """
    # Get the direct client IP from the connection
    if request.client:
        return request.client.host
    return "unknown"


def enforce(
    user_id: str, settings: AppSettings, request: Request | None = None
) -> None:
    """
    Enforce rate limiting with multiple layers:
    1. Per-user rate limiting (authenticated requests)
    2. Per-IP rate limiting (all requests)
    3. Global rate limiting (system-wide)
    """

    # User-based rate limiting
    user_bucket = _USER_BUCKETS[user_id]
    if (
        user_bucket.rate != settings.ratelimit_rps
        or user_bucket.capacity != settings.ratelimit_burst
    ):
        user_bucket.rate = settings.ratelimit_rps
        user_bucket.capacity = settings.ratelimit_burst
        user_bucket.tokens = settings.ratelimit_burst

    if not user_bucket.consume():
        raise HTTPException(status_code=429, detail="Rate limit exceeded for user")

    # IP-based rate limiting (if request provided)
    if request:
        client_ip = get_client_ip(request)
        ip_bucket = _IP_BUCKETS[client_ip]

        # More restrictive limits for IPs
        ip_rate = settings.ratelimit_rps // 2  # Half the user rate
        ip_burst = settings.ratelimit_burst // 2

        if ip_bucket.rate != ip_rate or ip_bucket.capacity != ip_burst:
            ip_bucket.rate = ip_rate
            ip_bucket.capacity = ip_burst
            ip_bucket.tokens = ip_burst

        if not ip_bucket.consume():
            raise HTTPException(status_code=429, detail="Rate limit exceeded for IP")

    # Global rate limiting
    if not _GLOBAL_BUCKET.consume():
        raise HTTPException(status_code=429, detail="System rate limit exceeded")


def reset_limits():
    """Reset all rate limits (for testing purposes)."""
    global _USER_BUCKETS, _IP_BUCKETS, _GLOBAL_BUCKET
    _USER_BUCKETS.clear()
    _IP_BUCKETS.clear()
    _GLOBAL_BUCKET = TokenBucket(100, 100)
