from __future__ import annotations

import re
from typing import Sequence

from pydantic import BaseModel


class VerificationResult(BaseModel):
    groundedness: float
    tool_required: bool
    success: bool
    reason: str | None = None


class Verifier:
    def verify(
        self,
        query: str,
        answer: str,
        citations: Sequence[str],
        tools_used: Sequence[str],
    ) -> VerificationResult:
        need_tool = bool(re.search(r"[\d+\-*/]", query))
        used = "python_eval" in tools_used
        tool_required = need_tool and not used
        success = not tool_required
        groundedness = 1.0 if citations else 0.0
        reason = None if success else "tool required"
        return VerificationResult(
            groundedness=groundedness,
            tool_required=tool_required,
            success=success,
            reason=reason,
        )
