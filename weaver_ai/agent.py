from __future__ import annotations

import re
import time
from typing import List, Sequence


from .model_router import ModelRouter, StubModel
from .mcp import MCPClient
from .reward import compute_reward
from .security import rbac
from .settings import AppSettings
from .verifier import Verifier


class AgentOrchestrator:
    def __init__(
        self,
        settings: AppSettings,
        router: ModelRouter,
        mcp: MCPClient,
        verifier: Verifier,
    ) -> None:
        self.settings = settings
        self.router = router
        self.mcp = mcp
        self.verifier = verifier

    def ask(self, query: str, user_id: str, ctx) -> tuple[str, List[str], dict]:
        start = time.time()
        citations: List[str] = []
        tools_used: List[str] = []
        if re.fullmatch(r"\s*\d+\s*[\+\-\*\/]\s*\d+\s*", query):
            rbac.check_access(ctx, "tool:python_eval", roles_path=self.settings_roles())
            result = self.mcp.call("python_eval", {"expr": query})
            answer = str(result["result"])
            citations.append("python_eval")
            tools_used.append("python_eval")
        else:
            answer = self.router.generate(query)
        latency_ms = (time.time() - start) * 1000
        verification = self.verifier.verify(query, answer, citations, tools_used)
        reward = compute_reward(verification, latency_ms)
        metrics = {
            "latency_ms": latency_ms,
            "groundedness": verification.groundedness,
            "tool_required": verification.tool_required,
            "verification_success": verification.success,
            "reward": reward,
        }
        return answer, citations, metrics

    def settings_roles(self):
        from pathlib import Path

        return Path("weaver_ai/policies/roles.yaml")
