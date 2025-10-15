from __future__ import annotations

import pytest

from weaver_ai.agent import AgentOrchestrator
from weaver_ai.mcp import MCPClient
from weaver_ai.model_router import StubModel
from weaver_ai.security.auth import UserContext
from weaver_ai.settings import AppSettings
from weaver_ai.tools import create_python_eval_server
from weaver_ai.verifier import Verifier


def _agent() -> AgentOrchestrator:
    settings = AppSettings()
    key = "k"
    server = create_python_eval_server("srv", key)
    # Use HS256 (symmetric key) to match server, not RS256
    client = MCPClient(server, key, use_rs256=False)
    router = StubModel()
    return AgentOrchestrator(settings, router, client, Verifier())


def test_agent_math_success():
    agent = _agent()
    user = UserContext(user_id="u", roles=["user"])
    ans, cites, _ = agent.ask("2+3", "u", user)
    assert ans == "5"
    assert cites == ["python_eval"]


def test_agent_math_forbidden():
    agent = _agent()
    user = UserContext(user_id="u", roles=[])
    with pytest.raises(Exception):  # noqa: B017
        agent.ask("2+3", "u", user)
