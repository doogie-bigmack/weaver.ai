"""Mock model adapter with simulated connection pooling for testing."""

import asyncio
import random
import time

from .base import ModelResponse
from .connection_pool import get_connection_pool
from .mock import MockAdapter


class PooledMockAdapter(MockAdapter):
    """Mock LLM with simulated connection pooling behavior.

    This adapter simulates the behavior of a real LLM that uses
    connection pooling, including connection reuse benefits.
    """

    def __init__(self, name: str = "mock"):  # Changed to "mock" for test compatibility
        super().__init__(name)
        self.connection_count = 0
        self.request_count = 0
        self.connection_reuse_count = 0
        self._connections: dict[int, float] = {}  # Track "connections"
        self._lock = asyncio.Lock()

        # Simulate connection overhead (ms)
        self.connection_overhead_ms = 50
        self.request_overhead_ms = 2

    async def generate(self, prompt: str, **kwargs) -> ModelResponse:
        """Generate response with simulated connection pooling."""
        start_time = time.time()

        # Get the connection pool (in real adapter, this would be used for HTTP)
        _ = await get_connection_pool()  # Pool is ready for use

        # Simulate connection management
        async with self._lock:
            self.request_count += 1

            # Simulate connection reuse (80% of time with pooling)
            if self._connections and random.random() < 0.8:
                # Reuse existing connection (fast)
                self.connection_reuse_count += 1
                await asyncio.sleep(self.request_overhead_ms / 1000)
            else:
                # Create new connection (slow)
                self.connection_count += 1
                conn_id = self.connection_count
                self._connections[conn_id] = time.time()
                await asyncio.sleep(self.connection_overhead_ms / 1000)

            # Clean old connections (simulate keepalive expiry)
            current_time = time.time()
            expired = [
                cid
                for cid, created in self._connections.items()
                if current_time - created > 5.0  # 5 second keepalive
            ]
            for cid in expired:
                del self._connections[cid]

        # Generate the actual response
        response = await super().generate(prompt, **kwargs)

        # Add pooling stats to response (just track internally, don't add to response)
        elapsed_ms = (time.time() - start_time) * 1000

        # Update generation time in response
        response.generation_time_ms = elapsed_ms

        return response

    def get_stats(self) -> dict:
        """Get connection pooling statistics."""
        return {
            "total_requests": self.request_count,
            "connections_created": self.connection_count,
            "connections_reused": self.connection_reuse_count,
            "active_connections": len(self._connections),
            "reuse_rate": (
                self.connection_reuse_count / self.request_count
                if self.request_count > 0
                else 0
            ),
            "avg_connections_per_request": (
                self.connection_count / self.request_count
                if self.request_count > 0
                else 0
            ),
        }
