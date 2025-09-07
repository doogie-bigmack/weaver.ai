from __future__ import annotations

from fastapi.testclient import TestClient

from weaver_ai import gateway
from weaver_ai.settings import AppSettings


def client() -> TestClient:
    gateway._settings = AppSettings(allowed_api_keys=["k"], ratelimit_rps=100, ratelimit_burst=100)
    return TestClient(gateway.app)


def test_rbac_forbidden():
    c = client()
    r = c.post("/ask", headers={"x-api-key": "k"}, json={"user_id": "u", "query": "2+2"})
    assert r.status_code == 403
