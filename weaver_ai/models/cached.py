"""Cached model adapter that wraps any model with Redis caching."""

from __future__ import annotations

import time

from ..cache import CacheConfig, RedisCache
from .base import ModelAdapter, ModelResponse


class CachedModelAdapter(ModelAdapter):
    """Model adapter wrapper that adds Redis caching."""

    def __init__(
        self,
        base_adapter: ModelAdapter,
        cache_config: CacheConfig | None = None,
    ):
        """Initialize cached adapter.

        Args:
            base_adapter: The underlying model adapter to wrap
            cache_config: Redis cache configuration
        """
        self.base_adapter = base_adapter
        self.cache_config = cache_config or CacheConfig()
        self.cache = RedisCache(self.cache_config)
        self._cache_connected = False

    async def _ensure_cache_connected(self) -> None:
        """Ensure cache is connected."""
        if not self._cache_connected:
            self._cache_connected = await self.cache.connect()

    async def generate(self, prompt: str, **kwargs) -> ModelResponse:
        """Generate response with caching."""
        await self._ensure_cache_connected()

        # Get model name from base adapter
        model_name = getattr(self.base_adapter, "name", "unknown")

        # Try to get from cache
        if self._cache_connected:
            cached = await self.cache.get(prompt, model_name, **kwargs)
            if cached:
                # Return cached response
                return ModelResponse(
                    text=cached["text"],
                    model=cached.get("model", model_name),
                    tokens_used=cached.get("tokens_used", 0),
                    cached=True,
                    cache_key=self.cache._generate_key(prompt, model_name, **kwargs)[
                        :20
                    ]
                    + "...",
                    generation_time_ms=cached.get("generation_time_ms", 0.0),
                )

        # Generate new response
        start_time = time.time()
        response = await self.base_adapter.generate(prompt, **kwargs)
        generation_time_ms = (time.time() - start_time) * 1000

        # Cache the response
        if self._cache_connected:
            cache_data = {
                "text": response.text,
                "model": response.model,
                "tokens_used": response.tokens_used,
                "generation_time_ms": generation_time_ms,
            }
            await self.cache.set(prompt, model_name, cache_data, **kwargs)

        # Add cache metadata
        response.cached = False
        response.generation_time_ms = generation_time_ms

        return response

    async def get_cache_stats(self) -> dict:
        """Get cache statistics."""
        if self._cache_connected:
            return self.cache.get_stats()
        return {"error": "Cache not connected"}

    async def clear_cache(self, pattern: str | None = None) -> int:
        """Clear cache entries."""
        if self._cache_connected:
            return await self.cache.invalidate(pattern)
        return 0

    async def disconnect(self) -> None:
        """Disconnect from cache."""
        if self._cache_connected:
            await self.cache.disconnect()
            self._cache_connected = False
