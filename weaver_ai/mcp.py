from __future__ import annotations

import json
import uuid
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
        self.nonces: set[str] = set()

    def add_tool(self, spec: ToolSpec, func: Callable[[dict], dict]) -> None:
        self.tools[spec.name] = func

    def handle(self, request: dict) -> dict:
        nonce = request.get("nonce")
        if nonce in self.nonces:
            raise ValueError("replay")
        self.nonces.add(nonce)
        name = request["tool"]
        result = self.tools[name](request.get("args", {}))
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
        return resp["result"]
