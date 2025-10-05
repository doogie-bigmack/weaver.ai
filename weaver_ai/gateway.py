from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException, Request
from pydantic import ValidationError

from .agent import AgentOrchestrator
from .mcp import MCPClient
from .middleware import CacheConfig, ResponseCacheMiddleware
from .model_router import StubModel
from .models import Citation, QueryRequest, QueryResponse
from .redis.connection_pool import (
    RedisPoolConfig,
    close_redis_pool,
    get_pool_stats,
    init_redis_pool,
)
from .security import auth, policy, ratelimit
from .settings import AppSettings
from .tools import create_python_eval_server
from .verifier import Verifier

logger = logging.getLogger(__name__)

_settings = AppSettings()
_cache_middleware: ResponseCacheMiddleware | None = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage application lifespan: startup and shutdown."""
    # Startup: Initialize Redis connection pool
    try:
        redis_config = RedisPoolConfig(
            host="localhost",
            port=6379,
            max_connections=100,  # Shared across all components
        )
        await init_redis_pool(redis_config)
        logger.info("Redis connection pool initialized successfully")
    except Exception as e:
        logger.error(f"Failed to initialize Redis pool: {e}", exc_info=True)

    yield

    # Shutdown: Close Redis connection pool
    try:
        await close_redis_pool()
        logger.info("Redis connection pool closed successfully")
    except Exception as e:
        logger.error(f"Error closing Redis pool: {e}", exc_info=True)


app = FastAPI(lifespan=lifespan)

# Add response caching middleware
cache_config = CacheConfig(
    enabled=True,
    cache_patterns={
        "/health": 60,  # Cache health checks for 1 minute
        "/whoami": 30,  # Cache auth info for 30 seconds
        "/metrics": 10,  # Cache metrics for 10 seconds
    },
)
_cache_middleware = ResponseCacheMiddleware(app, cache_config)
app.add_middleware(ResponseCacheMiddleware, config=cache_config)


def get_agent() -> AgentOrchestrator:
    key = "secret"
    server = create_python_eval_server("srv", key)
    client = MCPClient(server, key)
    router = StubModel()
    verifier = Verifier()
    return AgentOrchestrator(_settings, router, client, verifier)


def require_auth(request: Request):
    return auth.authenticate(request.headers, _settings)


def enforce_limit(request: Request):
    user = require_auth(request)
    ratelimit.enforce(user.user_id, _settings, request)
    return user


def load_guardrails() -> dict:
    return policy.load_policies(Path("weaver_ai/policies/guardrails.yaml"))


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/whoami")
async def whoami(request: Request):
    user = enforce_limit(request)
    return user


@app.get("/metrics")
async def metrics() -> dict[str, Any]:
    """Get performance metrics including cache stats and Redis pool stats.

    Returns:
        Dictionary with comprehensive performance metrics
    """
    metrics_data: dict[str, Any] = {
        "service": "weaver-ai",
        "status": "healthy",
    }

    # Get cache middleware stats
    if _cache_middleware:
        try:
            cache_stats = _cache_middleware.get_stats()
            metrics_data["http_cache"] = cache_stats
        except Exception as e:
            logger.error(f"Failed to get cache stats: {e}")
            metrics_data["http_cache"] = {"error": str(e)}

    # Get Redis pool stats
    try:
        pool_stats = get_pool_stats()
        metrics_data["redis_pool"] = pool_stats
    except Exception as e:
        logger.error(f"Failed to get pool stats: {e}")
        metrics_data["redis_pool"] = {"error": str(e)}

    return metrics_data


@app.post("/ask")
async def ask(request: Request):
    user = enforce_limit(request)

    # Get request data with error handling
    try:
        data = await request.json()
    except Exception:
        raise HTTPException(
            status_code=400, detail="Invalid JSON in request body"
        ) from None

    # Validate request data using Pydantic model
    try:
        req = QueryRequest(**data)
    except ValidationError as e:
        # Return user-friendly validation errors
        errors = []
        for error in e.errors():
            field = ".".join(str(loc) for loc in error["loc"])
            msg = error["msg"]
            errors.append(f"{field}: {msg}")
        raise HTTPException(
            status_code=422, detail=f"Validation error: {'; '.join(errors)}"
        ) from e
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid request data") from None

    # Apply input guards
    policies = load_guardrails()
    policy.input_guard(req.query, policies)

    # Process request
    agent = get_agent()
    answer, citations, metrics = agent.ask(req.query, req.user_id, user)

    # Apply output guards
    out = policy.output_guard(answer, policies, redact=_settings.pii_redact)

    # Return response
    return QueryResponse(
        answer=out.text,
        citations=[Citation(source=c) for c in citations],
        metrics=metrics,
    )
