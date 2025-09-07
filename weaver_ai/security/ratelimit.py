from __future__ import annotations

import time
from collections import defaultdict

from fastapi import HTTPException

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
            self.capacity, self.tokens + (now - self.timestamp) * self.rate
        )
        self.timestamp = now
        if self.tokens >= amount:
            self.tokens -= amount
            return True
        return False


_BUCKETS: dict[str, TokenBucket] = defaultdict(lambda: TokenBucket(1, 1))


def enforce(user_id: str, settings: AppSettings) -> None:
    bucket = _BUCKETS[user_id]
    if (
        bucket.rate != settings.ratelimit_rps
        or bucket.capacity != settings.ratelimit_burst
    ):
        bucket.rate = settings.ratelimit_rps
        bucket.capacity = settings.ratelimit_burst
        bucket.tokens = settings.ratelimit_burst
    if not bucket.consume():
        raise HTTPException(status_code=429, detail="ratelimited")
