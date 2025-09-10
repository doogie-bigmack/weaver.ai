"""Anthropic Claude adapter for direct API access.

Anthropic uses a different API format than OpenAI, so it needs its own adapter.
"""

from __future__ import annotations

import os
from typing import Any

import httpx

from .base import ModelAdapter, ModelResponse
from .connection_pool import HTTPConnectionPool


class AnthropicAdapter(ModelAdapter):
    """Adapter for Anthropic's Claude API.

    Handles the different API format that Anthropic uses:
    - Different headers (x-api-key instead of Authorization)
    - Different endpoint (/v1/messages instead of /v1/chat/completions)
    - Requires anthropic-version header

    Examples:
        # Claude 3 Opus
        adapter = AnthropicAdapter(api_key=os.getenv("ANTHROPIC_API_KEY"))
        response = await adapter.generate("Hello", model="claude-3-opus-20240229")

        # Claude 3 Sonnet
        response = await adapter.generate("Hello", model="claude-3-sonnet-20240229")

        # Future models work without code changes
        response = await adapter.generate("Hello", model="claude-4-opus-20250101")
    """

    def __init__(
        self,
        api_key: str | None = None,
        default_model: str | None = None,
        connection_pool: HTTPConnectionPool | None = None,
        anthropic_version: str = "2023-06-01",
    ):
        """Initialize the Anthropic adapter.

        Args:
            api_key: Anthropic API key
            default_model: Default model if not specified in generate()
            connection_pool: Optional connection pool for better performance
            anthropic_version: API version (default: "2023-06-01")
        """
        self.base_url = "https://api.anthropic.com/v1"
        self.api_key = api_key or os.getenv("ANTHROPIC_API_KEY")
        self.default_model = default_model or "claude-3-sonnet-20240229"
        self.anthropic_version = anthropic_version
        self.pool = connection_pool or HTTPConnectionPool()

    async def generate(
        self,
        prompt: str,
        model: str | None = None,
        **kwargs: Any,
    ) -> ModelResponse:
        """Generate a response using Anthropic's Claude API.

        Args:
            prompt: The prompt to send
            model: Claude model to use (developer's choice)
            **kwargs: Additional parameters

        Returns:
            ModelResponse with the generated text
        """
        # Use provided model or fall back to default
        model_name = model or self.default_model

        if not self.api_key:
            return ModelResponse(
                text="Anthropic API key not configured",
                model=f"{model_name}-no-key",
                tokens_used=0,
            )

        # Build Anthropic-specific headers
        headers = {
            "x-api-key": self.api_key,
            "anthropic-version": self.anthropic_version,
            "content-type": "application/json",
        }

        # Handle both simple strings and message lists
        if isinstance(prompt, str):
            messages = [{"role": "user", "content": prompt}]
        else:
            messages = prompt

        # Build request with Anthropic's format
        json_data = {
            "model": model_name,  # Pass through developer's model choice
            "messages": messages,
            "max_tokens": kwargs.get("max_tokens", 1024),
        }

        # Add optional parameters
        if "temperature" in kwargs:
            json_data["temperature"] = kwargs["temperature"]
        if "system" in kwargs:
            json_data["system"] = kwargs["system"]
        if "stop_sequences" in kwargs:
            json_data["stop_sequences"] = kwargs["stop_sequences"]

        # Add any extra parameters
        for key, value in kwargs.items():
            if key not in ["max_tokens", "temperature", "system", "stop_sequences"]:
                json_data[key] = value

        try:
            # Use connection pool for better performance
            response = await self.pool.post(
                f"{self.base_url}/messages",  # Different endpoint than OpenAI
                headers=headers,
                json=json_data,
                timeout=kwargs.get("timeout", 30.0),
            )

            if response.status_code != 200:
                error_data = response.json() if response.text else {}
                error_msg = error_data.get("error", {}).get("message", response.text)
                return ModelResponse(
                    text=f"Anthropic API error ({response.status_code}): {error_msg}",
                    model=f"{model_name}-error",
                    tokens_used=0,
                )

            data = response.json()

            # Extract response text from Anthropic's format
            text = ""
            if "content" in data:
                # Handle different content types
                for content_item in data["content"]:
                    if content_item.get("type") == "text":
                        text += content_item.get("text", "")

            # Get token usage if available
            usage = data.get("usage", {})
            tokens = usage.get("input_tokens", 0) + usage.get("output_tokens", 0)

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
                text=f"Error calling Anthropic API: {str(e)}",
                model=f"{model_name}-error",
                tokens_used=0,
            )

    async def stream(
        self,
        prompt: str,
        model: str | None = None,
        **kwargs: Any,
    ):
        """Stream responses (if needed in future).

        Anthropic supports streaming, but for now we just yield the full response.
        """
        response = await self.generate(prompt, model, **kwargs)
        yield response.text

    def get_capabilities(self) -> dict[str, Any]:
        """Get adapter capabilities."""
        return {
            "streaming": True,  # Anthropic supports streaming
            "max_tokens": 200000,  # Claude 3 supports up to 200k
            "supports_json": True,
            "supports_tools": True,
            "supports_vision": True,  # Claude 3 supports images
            "supports_system": True,  # Supports system prompts
        }
