"""Simple test gateway with Redis caching for performance testing."""

import logging
import time
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from weaver_ai.cache import CacheConfig
from weaver_ai.models.router import ModelRouter

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class QueryRequest(BaseModel):
    """Request model for queries."""

    query: str
    model: str | None = None


class QueryResponse(BaseModel):
    """Response model for queries."""

    response: str
    model: str | None = None
    cached: bool = False
    latency_ms: float | None = None


# Global model router
model_router: ModelRouter | None = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage application lifecycle."""
    global model_router

    # Initialize with caching enabled
    cache_config = CacheConfig(
        host="redis",  # Use container name when running in Docker
        port=6379,
        enabled=True,
        track_stats=True,
    )

    model_router = ModelRouter(
        use_connection_pooling=True,
        use_caching=True,
        cache_config=cache_config,
    )

    logger.info("Gateway started with Redis caching enabled")

    yield

    # Cleanup
    logger.info("Gateway shutting down")


# Create FastAPI app
app = FastAPI(
    title="Weaver AI Cached Gateway",
    description="Test gateway with Redis caching for performance testing",
    version="0.1.0",
    lifespan=lifespan,
)


@app.get("/health")
async def health():
    """Health check endpoint."""
    return {"status": "healthy", "caching": "enabled"}


@app.post("/ask")
async def ask(request: QueryRequest):
    """Process a query with caching."""
    if not model_router:
        raise HTTPException(status_code=503, detail="Service not initialized")

    try:
        start = time.time()
        response = await model_router.generate(request.query, model=request.model)
        latency_ms = (time.time() - start) * 1000

        # Check if response was cached
        cached = response.cached

        return QueryResponse(
            response=response.text,
            model=response.model,
            cached=cached,
            latency_ms=latency_ms,
        )
    except Exception as e:
        logger.error(f"Error processing query: {e}")
        raise HTTPException(status_code=500, detail=str(e)) from e


@app.get("/cache/stats")
async def cache_stats():
    """Get cache statistics."""
    if not model_router:
        raise HTTPException(status_code=503, detail="Service not initialized")

    try:
        stats = await model_router.get_cache_statistics()
        return {"cache_stats": stats}
    except Exception as e:
        logger.error(f"Error getting cache stats: {e}")
        raise HTTPException(status_code=500, detail=str(e)) from e


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
