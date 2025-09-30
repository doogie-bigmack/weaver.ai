"""Simplified gateway for performance testing without auth."""

from __future__ import annotations

from fastapi import FastAPI

from weaver_ai.agent import AgentOrchestrator
from weaver_ai.mcp import MCPClient
from weaver_ai.models.api import Citation, QueryRequest, QueryResponse
from weaver_ai.pooled_stub import PooledStubModel
from weaver_ai.settings import AppSettings
from weaver_ai.tools import create_python_eval_server
from weaver_ai.verifier import Verifier

app = FastAPI()
_settings = AppSettings()

# Use the pooled stub model for better performance
_pooled_model = PooledStubModel()


def get_agent() -> AgentOrchestrator:
    key = "secret"
    server = create_python_eval_server("srv", key)
    client = MCPClient(server, key)
    # Use the pooled stub model for connection reuse simulation
    verifier = Verifier()
    return AgentOrchestrator(_settings, _pooled_model, client, verifier)


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/pool-stats")
async def pool_stats() -> dict:
    """Get connection pooling statistics."""
    return _pooled_model.get_stats()


@app.post("/ask")
async def ask(req: QueryRequest):
    """Simplified ask endpoint for testing."""
    agent = get_agent()

    # Use stub user for testing
    from .security.auth import UserContext

    user = UserContext(user_id=req.user_id or "test_user")

    # Process request
    answer, citations, metrics = agent.ask(req.query, req.user_id or "test", user)

    return QueryResponse(
        answer=answer,
        citations=[Citation(source=c) for c in citations],
        metrics=metrics,
    )
