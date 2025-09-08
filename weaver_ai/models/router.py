"""Simple model router for selecting appropriate models."""

from typing import Optional

from ..cache import CacheConfig
from .base import ModelAdapter, ModelResponse
from .cached import CachedModelAdapter
from .mock import MockAdapter
from .pooled_mock import PooledMockAdapter


class ModelRouter:
    """Routes requests to appropriate models."""

    def __init__(
        self,
        use_connection_pooling: bool = True,
        use_caching: bool = False,
        cache_config: Optional[CacheConfig] = None,
    ):
        self.models: dict[str, ModelAdapter] = {}
        self.default_model: str | None = None
        self.use_connection_pooling = use_connection_pooling
        self.use_caching = use_caching
        self.cache_config = cache_config
        self.cache_stats = {}

        # Use pooled mock adapter when connection pooling is enabled
        if use_connection_pooling:
            base_adapter: ModelAdapter = PooledMockAdapter()
        else:
            base_adapter = MockAdapter()

        # Wrap with caching if enabled
        if use_caching:
            adapter: ModelAdapter = CachedModelAdapter(base_adapter, cache_config)
            self.cache_stats["mock"] = adapter
        else:
            adapter = base_adapter

        self.register("mock", adapter)
        self.default_model = "mock"

    def register(self, name: str, adapter: ModelAdapter) -> None:
        """Register a model adapter."""
        self.models[name] = adapter
        if not self.default_model:
            self.default_model = name

    async def generate(
        self, prompt: str, model: str | None = None, **kwargs
    ) -> ModelResponse:
        """Generate response using specified or default model."""
        model_name = model or self.default_model

        if not model_name or model_name not in self.models:
            raise ValueError(f"Model '{model_name}' not found")

        adapter = self.models[model_name]
        return await adapter.generate(prompt, **kwargs)

    def list_models(self) -> list[str]:
        """List available models."""
        return list(self.models.keys())

    async def get_cache_statistics(self) -> dict:
        """Get cache statistics from all cached models."""
        stats = {}
        for name, adapter in self.cache_stats.items():
            if isinstance(adapter, CachedModelAdapter):
                stats[name] = await adapter.get_cache_stats()
        return stats
