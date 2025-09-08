"""Stub model with simulated connection pooling for performance testing."""

import random
import time

from .model_router import StubModel


class PooledStubModel(StubModel):
    model_config = {"extra": "allow"}  # Allow extra attributes for Pydantic
    """Stub model with simulated connection pooling benefits.

    This model simulates the performance improvements from connection
    pooling without actually making network calls.
    """

    def __init__(self):
        super().__init__()
        self.connection_count = 0
        self.request_count = 0
        self.connection_reuse_count = 0
        self._connections: dict[int, float] = {}

        # Simulate connection overhead (ms)
        # With pooling, most requests reuse connections
        self.connection_overhead_ms = 2  # Time to establish new connection (reduced)
        self.request_overhead_ms = 0.1  # Time for pooled request (minimal)

    def generate(self, prompt: str, **kwargs) -> str:
        """Generate response with simulated connection pooling benefits."""
        self.request_count += 1

        # Simulate connection reuse (90% of time with pooling after warmup)
        if self._connections and random.random() < 0.9:
            # Reuse existing connection (fast)
            self.connection_reuse_count += 1
            # Simulate minimal overhead for pooled connection
            time.sleep(self.request_overhead_ms / 1000)
        else:
            # Create new connection (slower)
            self.connection_count += 1
            conn_id = self.connection_count
            self._connections[conn_id] = time.time()
            # Simulate connection establishment overhead
            time.sleep(self.connection_overhead_ms / 1000)

            # Keep pool size reasonable (simulate connection limit)
            if len(self._connections) > 100:
                # Remove oldest connection
                oldest = min(self._connections.keys())
                del self._connections[oldest]

        # Clean old connections (simulate keepalive expiry)
        current_time = time.time()
        expired = [
            cid
            for cid, created in self._connections.items()
            if current_time - created > 60.0  # 60 second keepalive
        ]
        for cid in expired:
            del self._connections[cid]

        # Return the standard stub response
        return f"[MODEL RESPONSE] {prompt}"

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
        }
