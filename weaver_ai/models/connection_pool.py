"""HTTP connection pooling for LLM providers.

This module provides connection pooling to reuse HTTP connections
and dramatically improve throughput when making API calls.
"""

from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from typing import Any

import httpx


class HTTPConnectionPool:
    """Manages a pool of HTTP connections for efficient reuse.

    This class maintains a pool of httpx.AsyncClient instances to avoid
    the overhead of creating new connections for each request.
    """

    def __init__(
        self,
        max_connections: int = 100,
        max_keepalive_connections: int = 20,
        keepalive_expiry: float = 5.0,
        timeout: float = 30.0,
    ):
        """Initialize the connection pool.

        Args:
            max_connections: Maximum number of connections to maintain
            max_keepalive_connections: Max idle connections to keep alive
            keepalive_expiry: How long to keep idle connections (seconds)
            timeout: Default timeout for requests (seconds)
        """
        self.max_connections = max_connections
        self.max_keepalive_connections = max_keepalive_connections
        self.keepalive_expiry = keepalive_expiry
        self.timeout = timeout

        # Create connection limits
        self.limits = httpx.Limits(
            max_connections=max_connections,
            max_keepalive_connections=max_keepalive_connections,
            keepalive_expiry=keepalive_expiry,
        )

        # Create timeout config
        self.timeout_config = httpx.Timeout(
            timeout=timeout,
            connect=5.0,  # Connection timeout
            read=timeout,  # Read timeout
            write=10.0,  # Write timeout
        )

        # The shared client instance
        self._client: httpx.AsyncClient | None = None
        self._lock = asyncio.Lock()

    async def _ensure_client(self) -> httpx.AsyncClient:
        """Ensure we have an active client instance."""
        if self._client is None:
            async with self._lock:
                # Double-check after acquiring lock
                if self._client is None:
                    self._client = httpx.AsyncClient(
                        limits=self.limits,
                        timeout=self.timeout_config,
                        # Enable HTTP/2 for better multiplexing
                        http2=True,
                        # Keep connections alive
                        headers={"Connection": "keep-alive"},
                    )
        return self._client

    async def request(
        self,
        method: str,
        url: str,
        **kwargs: Any,
    ) -> httpx.Response:
        """Make an HTTP request using the connection pool.

        Args:
            method: HTTP method (GET, POST, etc.)
            url: URL to request
            **kwargs: Additional arguments to pass to httpx

        Returns:
            httpx.Response object
        """
        client = await self._ensure_client()

        # Merge timeout if provided
        if "timeout" in kwargs:
            kwargs["timeout"] = httpx.Timeout(kwargs["timeout"])

        return await client.request(method, url, **kwargs)

    async def get(self, url: str, **kwargs: Any) -> httpx.Response:
        """Make a GET request."""
        return await self.request("GET", url, **kwargs)

    async def post(self, url: str, **kwargs: Any) -> httpx.Response:
        """Make a POST request."""
        return await self.request("POST", url, **kwargs)

    async def close(self):
        """Close the connection pool and cleanup resources."""
        if self._client:
            await self._client.aclose()
            self._client = None

    async def __aenter__(self):
        """Async context manager entry."""
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        await self.close()

    def get_stats(self) -> dict[str, Any]:
        """Get connection pool statistics.

        Returns:
            Dictionary with pool statistics
        """
        if not self._client:
            return {
                "active": False,
                "connections": 0,
            }

        return {
            "active": True,
            "max_connections": self.max_connections,
            "max_keepalive": self.max_keepalive_connections,
            "keepalive_expiry": self.keepalive_expiry,
        }


# Global connection pool instance (singleton)
_global_pool: HTTPConnectionPool | None = None
_pool_lock = asyncio.Lock()


async def get_connection_pool() -> HTTPConnectionPool:
    """Get or create the global connection pool.

    Returns:
        The global HTTPConnectionPool instance
    """
    global _global_pool

    if _global_pool is None:
        async with _pool_lock:
            if _global_pool is None:
                _global_pool = HTTPConnectionPool()

    return _global_pool


async def close_global_pool():
    """Close the global connection pool."""
    global _global_pool

    if _global_pool:
        await _global_pool.close()
        _global_pool = None


@asynccontextmanager
async def connection_pool_context():
    """Context manager for connection pool lifecycle.

    Usage:
        async with connection_pool_context() as pool:
            response = await pool.post(url, json=data)
    """
    pool = await get_connection_pool()
    try:
        yield pool
    finally:
        # Don't close the global pool on context exit
        # It should persist across requests
        pass
