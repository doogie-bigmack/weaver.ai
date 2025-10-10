from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException, Request
from pydantic import ValidationError

from .a2a import A2AEnvelope, check_timestamp, verify
from .a2a_router import A2ARouter, A2ARoutingError
from .agent import AgentOrchestrator
from .mcp import MCPClient
from .middleware import CacheConfig, ResponseCacheMiddleware
from .model_router import StubModel
from .models import Citation, QueryRequest, QueryResponse
from .redis import RedisEventMesh
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
        import os

        redis_config = RedisPoolConfig(
            host=os.getenv("REDIS_HOST", "localhost"),
            port=int(os.getenv("REDIS_PORT", "6379")),
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

    # Note: HTTP cache stats are currently not exposed in /metrics
    # The middleware instance is not directly accessible after app.add_middleware()
    # Consider using a global stats collector or Redis-based stats in the future

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


# ============================================================================
# A2A (Agent-to-Agent) Protocol Endpoints
# ============================================================================

# Initialize A2A router (will be done in lifespan in future)
_a2a_router: A2ARouter | None = None
_a2a_mesh: RedisEventMesh | None = None


async def get_a2a_router() -> A2ARouter:
    """Get or create A2A router instance."""
    global _a2a_router, _a2a_mesh

    if _a2a_router is None:
        # Initialize Redis event mesh for A2A using configured host/port
        import os

        redis_host = os.getenv("REDIS_HOST", "localhost")
        redis_port = os.getenv("REDIS_PORT", "6379")
        redis_url = f"redis://{redis_host}:{redis_port}"

        _a2a_mesh = RedisEventMesh(redis_url)
        await _a2a_mesh.connect()

        # Initialize router
        _a2a_router = A2ARouter(_a2a_mesh)
        await _a2a_router.start()

    return _a2a_router


@app.post("/a2a/message")
async def receive_a2a_message(envelope: A2AEnvelope):
    """Receive and route A2A messages from external agents.

    This endpoint:
    1. Verifies message signature
    2. Checks timestamp validity
    3. Routes message to appropriate local agent via Redis
    4. Waits for agent response
    5. Returns signed response

    Args:
        envelope: A2A message envelope

    Returns:
        Result dictionary or error
    """
    try:
        # 1. Verify timestamp (30 second window)
        if not check_timestamp(envelope, skew_seconds=30):
            raise HTTPException(
                status_code=400,
                detail="Message timestamp outside acceptable window",
            )

        # 2. Verify signature
        # Get sender's public key from settings
        sender_public_key = _settings.mcp_server_public_keys.get(envelope.sender_id)

        if not sender_public_key:
            logger.error(f"Unknown sender: {envelope.sender_id}")
            logger.error(
                f"Available senders: {list(_settings.mcp_server_public_keys.keys())}"
            )
            raise HTTPException(
                status_code=401,
                detail=f"Unknown sender: {envelope.sender_id}",
            )

        logger.info(f"Verifying signature for sender: {envelope.sender_id}")
        logger.debug(f"Public key (first 50 chars): {sender_public_key[:50]}")
        sig_preview = envelope.signature[:50] if envelope.signature else "None"
        logger.debug(f"Signature (first 50 chars): {sig_preview}")

        verification_result = verify(envelope, sender_public_key)
        logger.info(f"Verification result: {verification_result}")

        if not verification_result:
            logger.error("Signature verification failed")
            raise HTTPException(
                status_code=401,
                detail="Invalid message signature",
            )

        # 3. Get router and route message
        router = await get_a2a_router()

        try:
            result = await router.route_message(envelope)
        except A2ARoutingError as e:
            raise HTTPException(
                status_code=500,
                detail=f"Routing failed: {str(e)}",
            ) from e

        # 4. Return result data directly (A2A client expects just the data)
        return result

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"A2A message processing failed: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail="Internal server error",
        ) from None


@app.get("/a2a/card")
async def get_agent_card():
    """Return agent card describing this agent's capabilities.

    Agent cards enable discovery and capability negotiation.

    Returns:
        Agent card dictionary
    """
    return {
        "agent_id": "weaver-ai-agent",
        "name": "Weaver AI Agent",
        "version": "1.0.0",
        "description": "Multi-agent orchestration framework with A2A support",
        "capabilities": [
            {
                "name": "translation:en-es",
                "version": "1.0.0",
                "description": "English to Spanish translation",
                "scopes": ["execute"],
            },
            {
                "name": "data:processing",
                "version": "1.0.0",
                "description": "Data processing and analysis",
                "scopes": ["execute"],
            },
        ],
        "endpoints": {
            "a2a": "/a2a/message",
            "card": "/a2a/card",
        },
        "authentication": {
            "type": "signature",
            "algorithm": "RS256",
            "public_key": _settings.a2a_signing_public_key_pem,
        },
        "protocols": ["a2a-v1", "json-rpc-2.0"],
    }
