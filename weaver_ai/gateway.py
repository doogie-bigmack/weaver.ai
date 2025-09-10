from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from pydantic import ValidationError

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
    
    # Get request data with error handling
    try:
        data = await request.json()
    except Exception as e:
        raise HTTPException(status_code=400, detail="Invalid JSON in request body")
    
    # Validate request data using Pydantic model
    try:
        req = QueryRequest(**data)
    except ValidationError as e:
        # Return user-friendly validation errors
        errors = []
        for error in e.errors():
            field = '.'.join(str(loc) for loc in error['loc'])
            msg = error['msg']
            errors.append(f"{field}: {msg}")
        raise HTTPException(status_code=422, detail=f"Validation error: {'; '.join(errors)}")
    except Exception as e:
        raise HTTPException(status_code=400, detail="Invalid request data")
    
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
