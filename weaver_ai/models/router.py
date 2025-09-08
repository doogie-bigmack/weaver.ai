"""Simple model router for selecting appropriate models."""

from .base import ModelAdapter, ModelResponse
from .mock import MockAdapter


class ModelRouter:
    """Routes requests to appropriate models."""

    def __init__(self):
        self.models: dict[str, ModelAdapter] = {}
        self.default_model: str | None = None

        # Always include a mock model for testing
        self.register("mock", MockAdapter())
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
