"""Flexible model router for selecting appropriate models.

Supports any LLM provider through OpenAI-compatible or Anthropic adapters.
Developers have full control over model selection.
"""

from __future__ import annotations

from typing import Any

from ..cache import CacheConfig
from .base import ModelAdapter, ModelResponse
from .cached import CachedModelAdapter
from .connection_pool import HTTPConnectionPool
from .mock import MockAdapter
from .pooled_mock import PooledMockAdapter


class ModelRouter:
    """Routes requests to appropriate models with flexible configuration.

    Examples:
        # Simple setup with mock model
        router = ModelRouter()

        # Add OpenAI GPT-4
        router.add_model(
            name="gpt4",
            adapter_type="openai-compatible",
            base_url="https://api.openai.com/v1",
            api_key=os.getenv("OPENAI_API_KEY"),
            model="gpt-4"
        )

        # Add Groq Llama
        router.add_model(
            name="llama",
            adapter_type="openai-compatible",
            base_url="https://api.groq.com/openai/v1",
            api_key=os.getenv("GROQ_API_KEY"),
            model="llama3-70b-8192"
        )

        # Add Anthropic Claude
        router.add_model(
            name="claude",
            adapter_type="anthropic",
            api_key=os.getenv("ANTHROPIC_API_KEY"),
            model="claude-3-opus-20240229"
        )

        # Use any model
        response = await router.generate("Hello", model_name="gpt4")
    """

    def __init__(
        self,
        use_connection_pooling: bool = True,
        use_caching: bool = False,
        cache_config: CacheConfig | None = None,
        load_mock: bool = True,
    ):
        self.models: dict[str, dict[str, Any]] = {}
        self.adapters: dict[str, ModelAdapter] = {}
        self.default_model: str | None = None
        self.use_connection_pooling = use_connection_pooling
        self.use_caching = use_caching
        self.cache_config = cache_config
        self.cache_stats = {}

        # Shared connection pool for all adapters
        self.connection_pool = HTTPConnectionPool() if use_connection_pooling else None

        # Load mock adapter by default for testing
        if load_mock:
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

            self.adapters["mock"] = adapter
            self.models["mock"] = {"adapter": "mock", "model": "mock"}
            self.default_model = "mock"

    def add_model(
        self,
        name: str,
        adapter_type: str,
        model: str,
        **config: Any,
    ) -> None:
        """Add a new model with flexible configuration.

        Args:
            name: Friendly name for this model configuration
            adapter_type: Type of adapter ("openai-compatible", "anthropic", "mock")
            model: Model identifier (e.g., "gpt-4", "claude-3-opus", "llama3-70b")
            **config: Additional configuration (api_key, base_url, etc.)

        Examples:
            # OpenAI
            router.add_model(
                name="gpt4",
                adapter_type="openai-compatible",
                base_url="https://api.openai.com/v1",
                api_key="sk-...",
                model="gpt-4"
            )

            # Anthropic
            router.add_model(
                name="claude",
                adapter_type="anthropic",
                api_key="sk-ant-...",
                model="claude-3-opus-20240229"
            )
        """
        # Lazy import to avoid circular dependencies
        from .anthropic_adapter import AnthropicAdapter
        from .openai_compatible import OpenAICompatibleAdapter

        # Create adapter based on type
        adapter: ModelAdapter
        if adapter_type == "openai-compatible":
            adapter = OpenAICompatibleAdapter(
                base_url=config.get("base_url", "https://api.openai.com/v1"),
                api_key=config.get("api_key"),
                default_model=model,
                connection_pool=self.connection_pool,
            )
        elif adapter_type == "anthropic":
            adapter = AnthropicAdapter(
                api_key=config.get("api_key"),
                default_model=model,
                connection_pool=self.connection_pool,
            )
        elif adapter_type == "mock":
            # Already handled in __init__
            return
        else:
            raise ValueError(f"Unknown adapter type: {adapter_type}")

        # Wrap with caching if enabled
        if self.use_caching:
            cached_adapter = CachedModelAdapter(adapter, self.cache_config)
            self.cache_stats[name] = cached_adapter
            adapter = cached_adapter

        # Store adapter and configuration
        self.adapters[name] = adapter
        self.models[name] = {
            "adapter_type": adapter_type,
            "model": model,
            **config,
        }

        # Set as default if it's the first non-mock model
        if not self.default_model or self.default_model == "mock":
            self.default_model = name

    def register(self, name: str, adapter: ModelAdapter) -> None:
        """Register a model adapter (legacy method, kept for compatibility)."""
        self.adapters[name] = adapter
        self.models[name] = {"adapter": adapter, "model": name}
        if not self.default_model:
            self.default_model = name

    async def generate(
        self,
        prompt: str,
        model_name: str | None = None,
        **kwargs: Any,
    ) -> ModelResponse:
        """Generate response using specified or default model.

        Args:
            prompt: The prompt to send
            model_name: Name of the model configuration to use
            **kwargs: Additional parameters passed to the adapter

        Returns:
            ModelResponse from the selected model
        """
        name = model_name or self.default_model

        if not name or name not in self.models:
            available = ", ".join(self.models.keys())
            raise ValueError(f"Model '{name}' not found. Available: {available}")

        # Get the adapter
        adapter = self.adapters.get(name)
        if not adapter:
            raise ValueError(f"No adapter found for model '{name}'")

        # Get the model identifier
        model_config = self.models[name]
        model_id = model_config.get("model")

        # Generate response
        if hasattr(adapter, "generate"):
            # Pass model ID if the adapter supports it
            try:
                return await adapter.generate(prompt, model=model_id, **kwargs)
            except TypeError:
                # Fallback for adapters that don't accept model parameter
                return await adapter.generate(prompt, **kwargs)
        else:
            raise ValueError(f"Adapter for '{name}' doesn't support generation")

    def list_models(self) -> list[str]:
        """List available model configurations."""
        return list(self.models.keys())

    def get_model_info(self, name: str) -> dict[str, Any]:
        """Get information about a model configuration."""
        if name not in self.models:
            raise ValueError(f"Model '{name}' not found")
        return self.models[name].copy()

    async def get_cache_statistics(self) -> dict:
        """Get cache statistics from all cached models."""
        stats = {}
        for name, adapter in self.cache_stats.items():
            if isinstance(adapter, CachedModelAdapter):
                stats[name] = await adapter.get_cache_stats()
        return stats
