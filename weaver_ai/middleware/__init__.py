"""FastAPI middleware for performance optimization."""

from .cache import CacheConfig, ResponseCacheMiddleware

__all__ = ["ResponseCacheMiddleware", "CacheConfig"]
