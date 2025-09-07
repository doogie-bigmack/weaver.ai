from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI, Request

from .agent import AgentOrchestrator
from .mcp import MCPClient
from .model_router import StubModel
from .models import Citation, QueryRequest, QueryResponse
from .security import auth, policy, ratelimit
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


def require_auth(request: Request):
    return auth.authenticate(request.headers, _settings)


def enforce_limit(request: Request):
    user = require_auth(request)
    ratelimit.enforce(user.user_id, _settings)
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


@app.post("/ask")
async def ask(request: Request):
    user = enforce_limit(request)
    data = await request.json() if hasattr(request, 'json') and callable(request.json) else {}
    req = QueryRequest(**data)
    policies = load_guardrails()
    policy.input_guard(req.query, policies)
    agent = get_agent()
    answer, citations, metrics = agent.ask(req.query, req.user_id, user)
    out = policy.output_guard(answer, policies, redact=_settings.pii_redact)
    return QueryResponse(
        answer=out.text,
        citations=[Citation(source=c) for c in citations],
        metrics=metrics,
    )
