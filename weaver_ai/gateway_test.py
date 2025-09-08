"""Simplified gateway for performance testing without auth."""

from __future__ import annotations

from fastapi import FastAPI

from .agent import AgentOrchestrator
from .mcp import MCPClient
from .model_router import StubModel
from .models import Citation, QueryRequest, QueryResponse
from .settings import AppSettings
from .tools import create_python_eval_server
from .verifier import Verifier

app = FastAPI()
_settings = AppSettings()


def get_agent() -> AgentOrchestrator:
    key = "secret"
    server = create_python_eval_server("srv", key)
    client = MCPClient(server, key)
    router = StubModel()
    verifier = Verifier()
    return AgentOrchestrator(_settings, router, client, verifier)


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


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
