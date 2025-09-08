"""Mock model adapter for testing."""

import re

from .base import ModelAdapter, ModelResponse


class MockAdapter:
    """Mock LLM that returns simple responses for testing."""
    
    def __init__(self, name: str = "mock"):
        self.name = name
    
    async def generate(self, prompt: str, **kwargs) -> ModelResponse:
        """Generate a mock response based on the prompt."""
        # Simple pattern matching for common queries
        prompt_lower = prompt.lower()
        
        if "hello" in prompt_lower:
            text = "Hello! I'm a mock model for testing."
        elif any(op in prompt for op in ["+", "-", "*", "/"]):
            # Try to evaluate simple math
            text = self._evaluate_math(prompt)
        elif "analyze" in prompt_lower:
            text = "Analysis complete: The data shows interesting patterns."
        elif "test" in prompt_lower:
            text = "This is a test response from the mock model."
        else:
            text = f"Mock response for: {prompt[:50]}..."
        
        return ModelResponse(
            text=text,
            model=self.name,
            tokens_used=len(prompt.split())
        )
    
    def _evaluate_math(self, expr: str) -> str:
        """Evaluate simple math expressions safely."""
        # Extract numbers and operator
        match = re.search(r'(\d+)\s*([\+\-\*/])\s*(\d+)', expr)
        if match:
            a, op, b = match.groups()
            a, b = int(a), int(b)
            
            if op == '+':
                result = a + b
            elif op == '-':
                result = a - b
            elif op == '*':
                result = a * b
            elif op == '/' and b != 0:
                result = a / b
            else:
                return "Cannot evaluate this expression"
            
            return str(result)
        return "Invalid math expression"