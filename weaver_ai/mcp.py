from __future__ import annotations

import json
import time
import uuid
from collections import OrderedDict
from collections.abc import Callable

import jwt
from pydantic import BaseModel, Field


class ToolSpec(BaseModel):
    name: str
    description: str
    input_schema: dict
    output_schema: dict
    required_scopes: list[str] = Field(default_factory=list)


class MCPServer:
    def __init__(self, server_id: str, private_key: str):
        self.server_id = server_id
        self.private_key = private_key
        self.tools: dict[str, Callable[[dict], dict]] = {}
        # Use OrderedDict to maintain insertion order for LRU-like behavior
        self.nonces: OrderedDict[str, float] = OrderedDict()
        # Nonce TTL in seconds (5 minutes)
        self.nonce_ttl = 300
        # Maximum number of nonces to store
        self.max_nonces = 10000

    def _cleanup_expired_nonces(self) -> None:
        """Remove expired nonces from storage."""
        current_time = time.time()
        expired_nonces = []

        # Find expired nonces
        for nonce, timestamp in self.nonces.items():
            if current_time - timestamp > self.nonce_ttl:
                expired_nonces.append(nonce)
            else:
                # Since OrderedDict maintains order, once we find a non-expired nonce,
                # all subsequent ones are also non-expired
                break

        # Remove expired nonces
        for nonce in expired_nonces:
            del self.nonces[nonce]

    def add_tool(self, spec: ToolSpec, func: Callable[[dict], dict]) -> None:
        self.tools[spec.name] = func

    def handle(self, request: dict) -> dict:
        # Clean up expired nonces first
        self._cleanup_expired_nonces()

        nonce = request.get("nonce")
        if not nonce:
            raise ValueError("Missing nonce")

        # Check for replay attack
        if nonce in self.nonces:
            raise ValueError("Nonce replay detected")

        # Add new nonce with timestamp
        self.nonces[nonce] = time.time()

        # Enforce maximum nonce storage limit (LRU eviction)
        if len(self.nonces) > self.max_nonces:
            # Remove oldest nonce (first item in OrderedDict)
            self.nonces.popitem(last=False)

        # Validate tool name
        name = request.get("tool")
        if not name:
            raise ValueError("Missing tool name")

        if name not in self.tools:
            raise ValueError(f"Unknown tool: {name}")

        # Execute tool
        result = self.tools[name](request.get("args", {}))

        # Create signed response
        payload = json.dumps({"result": result, "nonce": nonce}).encode()
        sig = jwt.encode(
            {"payload": payload.decode()}, self.private_key, algorithm="HS256"
        )
        return {"result": result, "nonce": nonce, "signature": sig}


class MCPClient:
    def __init__(self, server: MCPServer, public_key: str):
        self.server = server
        self.public_key = public_key

    def call(self, tool: str, args: dict | None = None) -> dict:
        nonce = str(uuid.uuid4())
        resp = self.server.handle({"tool": tool, "args": args or {}, "nonce": nonce})
        try:
            decoded = jwt.decode(
                resp["signature"], self.public_key, algorithms=["HS256"]
            )
        except jwt.PyJWTError as exc:
            raise ValueError("bad signature") from exc
        payload = (
            json.dumps({"result": resp["result"], "nonce": nonce}).encode().decode()
        )
        if decoded.get("payload") != payload:
            raise ValueError("payload mismatch")
        return resp["result"]  # type: ignore[no-any-return]
