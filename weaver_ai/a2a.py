from __future__ import annotations

import json
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

import jwt
from pydantic import BaseModel, Field


class Capability(BaseModel):
    name: str
    version: str
    scopes: list[str] = Field(default_factory=list)


class Budget(BaseModel):
    tokens: int
    time_ms: int
    tool_calls: int


class A2AEnvelope(BaseModel):
    request_id: str
    sender_id: str
    receiver_id: str
    created_at: datetime
    nonce: str
    capabilities: list[Capability]
    budget: Budget
    payload: dict[str, Any]
    signature: str | None = None


_NONCE_STORE: set[str] = set()


def canonical_json(obj: Any) -> bytes:
    def convert(o):
        if isinstance(o, datetime):
            return o.isoformat()
        if isinstance(o, dict):
            return {k: convert(v) for k, v in o.items()}
        if isinstance(o, list):
            return [convert(i) for i in o]
        return o
    return json.dumps(convert(obj), sort_keys=True, separators=(",", ":")).encode()


def sign(envelope: A2AEnvelope, private_key: str) -> str:
    payload = canonical_json(envelope.model_dump(exclude={"signature"}))
    return jwt.encode({"payload": payload.decode()}, private_key, algorithm="HS256")


def verify(envelope: A2AEnvelope, public_key: str) -> bool:
    if envelope.nonce in _NONCE_STORE:
        return False
    _NONCE_STORE.add(envelope.nonce)
    try:
        decoded = jwt.decode(envelope.signature or "", public_key, algorithms=["HS256"])
    except jwt.PyJWTError:
        return False
    payload = canonical_json(envelope.model_dump(exclude={"signature"})).decode()
    return decoded.get("payload") == payload


def check_timestamp(envelope: A2AEnvelope, skew_seconds: int = 30) -> bool:
    now = datetime.now(timezone.utc)
    return abs((now - envelope.created_at).total_seconds()) <= skew_seconds
