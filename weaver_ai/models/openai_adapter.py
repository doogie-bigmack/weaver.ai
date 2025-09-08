"""OpenAI adapter (optional - requires API key)."""

import os
from typing import Optional

from .base import ModelAdapter, ModelResponse


class OpenAIAdapter:
    """OpenAI API adapter.
    
    Note: Requires OPENAI_API_KEY environment variable.
    If not available, will raise an error.
    """
    
    def __init__(self, model: str = "gpt-3.5-turbo"):
        self.model = model
        self.api_key = os.getenv("OPENAI_API_KEY")
        
    async def generate(self, prompt: str, **kwargs) -> ModelResponse:
        """Generate response using OpenAI API."""
        if not self.api_key:
            # Return a helpful message instead of failing
            return ModelResponse(
                text="OpenAI adapter requires OPENAI_API_KEY environment variable",
                model=f"{self.model}-unavailable",
                tokens_used=0
            )
        
        try:
            import openai
            
            client = openai.AsyncOpenAI(api_key=self.api_key)
            response = await client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
                max_tokens=kwargs.get("max_tokens", 150),
                temperature=kwargs.get("temperature", 0.7)
            )
            
            return ModelResponse(
                text=response.choices[0].message.content,
                model=self.model,
                tokens_used=response.usage.total_tokens
            )
            
        except ImportError:
            return ModelResponse(
                text="OpenAI library not installed. Install with: pip install openai",
                model=f"{self.model}-unavailable",
                tokens_used=0
            )
        except Exception as e:
            return ModelResponse(
                text=f"OpenAI API error: {str(e)}",
                model=f"{self.model}-error",
                tokens_used=0
            )