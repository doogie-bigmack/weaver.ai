from __future__ import annotations

import pytest

from weaver_ai.mcp import MCPClient
from weaver_ai.tools import create_python_eval_server


def test_mcp_roundtrip():
    key = "k"
    server = create_python_eval_server("srv", key)
    client = MCPClient(server, key)
    result = client.call("python_eval", {"expr": "1+1"})
    assert result["result"] == 2


def test_mcp_replay():
    key = "k"
    server = create_python_eval_server("srv", key)
    nonce_req = {"tool": "python_eval", "args": {"expr": "1"}, "nonce": "n"}
    server.handle(nonce_req)
    with pytest.raises(ValueError):
        server.handle(nonce_req)
