"""OpenAI-compatible adapter for any provider using the OpenAI API format.

This adapter works with:
- OpenAI (GPT-3.5, GPT-4, etc.)
- Groq (Llama, Mixtral, etc.)
- OpenRouter (400+ models)
- Anyscale
- Together AI
- Any other OpenAI-compatible API
"""

from __future__ import annotations

import os
from typing import Any

import httpx

from .base import ModelAdapter, ModelResponse
from .connection_pool import HTTPConnectionPool


class OpenAICompatibleAdapter(ModelAdapter):
    """Universal adapter for OpenAI-compatible APIs.

    The developer has full control over:
    - Base URL (which provider to use)
    - Model name (which specific model)
    - API key (authentication)

    Examples:
        # OpenAI GPT-4
        adapter = OpenAICompatibleAdapter(
            base_url="https://api.openai.com/v1",
            api_key=os.getenv("OPENAI_API_KEY")
        )
        response = await adapter.generate("Hello", model="gpt-4")

        # Groq Llama
        adapter = OpenAICompatibleAdapter(
            base_url="https://api.groq.com/openai/v1",
            api_key=os.getenv("GROQ_API_KEY")
        )
        response = await adapter.generate("Hello", model="llama3-70b-8192")

        # OpenRouter for any model
        adapter = OpenAICompatibleAdapter(
            base_url="https://openrouter.ai/api/v1",
            api_key=os.getenv("OPENROUTER_API_KEY")
        )
        response = await adapter.generate("Hello", model="anthropic/claude-3-opus")
    """

    def __init__(
        self,
        base_url: str = "https://api.openai.com/v1",
        api_key: str | None = None,
        default_model: str | None = None,
        connection_pool: HTTPConnectionPool | None = None,
    ):
        """Initialize the adapter.

        Args:
            base_url: API endpoint (e.g., "https://api.openai.com/v1")
            api_key: API key for authentication
            default_model: Default model to use if not specified in generate()
            connection_pool: Optional connection pool for better performance
        """
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key or os.getenv("LLM_API_KEY")
        self.default_model = default_model
        self.pool = connection_pool or HTTPConnectionPool()

    async def generate(
        self,
        prompt: str,
        model: str | None = None,
        **kwargs: Any,
    ) -> ModelResponse:
        """Generate a response using the OpenAI-compatible API.

        Args:
            prompt: The prompt to send
            model: Model to use (e.g., "gpt-4", "llama3-70b", etc.)
                   Developer has full control over this
            **kwargs: Additional parameters (temperature, max_tokens, etc.)

        Returns:
            ModelResponse with the generated text
        """
        # Use provided model or fall back to default
        model_name = model or self.default_model
        if not model_name:
            return ModelResponse(
                text="No model specified. Please provide a model name.",
                model="no-model",
                tokens_used=0,
            )

        if not self.api_key:
            return ModelResponse(
                text=f"API key not configured for {self.base_url}",
                model=f"{model_name}-no-key",
                tokens_used=0,
            )

        # Build the request
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        # Handle both simple strings and message lists
        if isinstance(prompt, str):
            messages = [{"role": "user", "content": prompt}]
        else:
            messages = prompt

        json_data = {
            "model": model_name,  # Pass through whatever model the developer wants
            "messages": messages,
            "max_tokens": kwargs.get("max_tokens", 1024),
            "temperature": kwargs.get("temperature", 0.7),
        }

        # Add any extra parameters the developer wants
        for key, value in kwargs.items():
            if key not in ["max_tokens", "temperature"]:
                json_data[key] = value

        try:
            # Use connection pool for better performance
            response = await self.pool.post(
                f"{self.base_url}/chat/completions",
                headers=headers,
                json=json_data,
                timeout=kwargs.get("timeout", 30.0),
            )

            if response.status_code != 200:
                error_text = response.text
                return ModelResponse(
                    text=f"API error ({response.status_code}): {error_text}",
                    model=f"{model_name}-error",
                    tokens_used=0,
                )

            data = response.json()

            # Extract response text
            text = data["choices"][0]["message"]["content"]

            # Get token usage if available
            tokens = data.get("usage", {}).get("total_tokens", 0)

            return ModelResponse(
                text=text,
                model=model_name,
                tokens_used=tokens,
            )

        except httpx.TimeoutException:
            return ModelResponse(
                text=f"Request timeout for {model_name}",
                model=f"{model_name}-timeout",
                tokens_used=0,
            )
        except Exception as e:
            return ModelResponse(
                text=f"Error calling {self.base_url}: {str(e)}",
                model=f"{model_name}-error",
                tokens_used=0,
            )

    async def stream(
        self,
        prompt: str,
        model: str | None = None,
        **kwargs: Any,
    ):
        """Stream responses (if needed in future)."""
        # Streaming can be added later if needed
        # For now, just yield the full response
        response = await self.generate(prompt, model, **kwargs)
        yield response.text

    def get_capabilities(self) -> dict[str, Any]:
        """Get adapter capabilities."""
        return {
            "streaming": False,  # Can be added later
            "max_tokens": 128000,  # Varies by model, developer should know
            "supports_json": True,  # Most modern models do
            "supports_tools": True,  # Most modern models do
        }
