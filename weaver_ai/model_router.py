from __future__ import annotations

from pydantic import BaseModel


class ModelRouter(BaseModel):
    def generate(
        self,
        prompt: str,
        *,
        stop: list[str] | None = None,
        max_tokens: int = 256,
        temperature: float = 0.2,
    ) -> str:
        raise NotImplementedError


class StubModel(ModelRouter):
    def generate(self, prompt: str, **kwargs) -> str:  # type: ignore[override]
        return f"[MODEL RESPONSE] {prompt}"


class OpenAIAdapter(ModelRouter):
    def generate(self, prompt: str, **kwargs) -> str:  # type: ignore[override]
        raise NotImplementedError("OpenAI adapter not implemented in tests")


class VLLMAdapter(ModelRouter):
    def generate(self, prompt: str, **kwargs) -> str:  # type: ignore[override]
        return f"vllm:{prompt}"


class TGIAdapter(ModelRouter):
    def generate(self, prompt: str, **kwargs) -> str:  # type: ignore[override]
        return f"tgi:{prompt}"
