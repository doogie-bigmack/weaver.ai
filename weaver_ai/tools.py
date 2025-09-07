from __future__ import annotations

import ast
import operator as op
from typing import Any, Dict

from pydantic import BaseModel

from .mcp import MCPServer, MCPClient, ToolSpec


class Tool(BaseModel):
    name: str
    description: str
    required_scopes: list[str] = []

    def schema(self) -> dict:  # pragma: no cover - simple example
        return {}

    def call(self, **kwargs: Any) -> dict:
        raise NotImplementedError


class PythonEvalTool(Tool):
    name: str = "python_eval"
    description: str = "Evaluate simple arithmetic expressions"
    required_scopes: list[str] = ["tool:python_eval"]

    _ops = {ast.Add: op.add, ast.Sub: op.sub, ast.Mult: op.mul, ast.Div: op.truediv}

    def call(self, expr: str) -> dict:
        node = ast.parse(expr, mode="eval")
        return {"result": self._eval(node.body)}

    def _eval(self, node: ast.AST) -> Any:
        if isinstance(node, ast.BinOp):
            return self._ops[type(node.op)](self._eval(node.left), self._eval(node.right))
        if isinstance(node, ast.Num):  # type: ignore[attr-defined]
            return node.n
        raise ValueError("unsupported expression")


def create_python_eval_server(server_id: str, key: str) -> MCPServer:
    server = MCPServer(server_id, key)
    tool = PythonEvalTool()
    spec = ToolSpec(
        name=tool.name,
        description=tool.description,
        input_schema={},
        output_schema={}
    )
    server.add_tool(spec, lambda args: tool.call(expr=args["expr"]))
    return server
