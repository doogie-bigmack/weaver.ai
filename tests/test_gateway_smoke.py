from __future__ import annotations

from fastapi.testclient import TestClient
from weaver_ai import gateway
from weaver_ai.settings import AppSettings


def create_client() -> TestClient:
    gateway._settings = AppSettings(allowed_api_keys=["dev-key"])
    return TestClient(gateway.app)


def test_gateway_smoke():
    client = create_client()
    r = client.post("/ask", headers={"x-api-key": "dev-key"}, json={"user_id": "u", "query": "hi"})
    assert r.status_code == 200
    data = r.json()
    assert data["answer"]
