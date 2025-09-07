from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import yaml
from fastapi import HTTPException
from pydantic import BaseModel


class GuardrailDecision(BaseModel):
    text: str


def load_policies(path: Path) -> dict[str, Any]:
    with path.open() as f:
        return yaml.safe_load(f) or {}


def input_guard(text: str, policies: dict[str, Any]) -> None:
    for pattern in policies.get("deny_patterns", []):
        if pattern in text:
            raise HTTPException(status_code=400, detail="blocked")


def output_guard(text: str, policies: dict[str, Any], *, redact: bool = True) -> GuardrailDecision:
    if redact:
        for regex in policies.get("pii_regexes", []):
            text = re.sub(regex, "[redacted]", text)
    return GuardrailDecision(text=text)
