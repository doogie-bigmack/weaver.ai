from __future__ import annotations

from fastapi.testclient import TestClient

from weaver_ai import gateway
from weaver_ai.settings import AppSettings


def client() -> TestClient:
    gateway._settings = AppSettings(allowed_api_keys=["k"], ratelimit_rps=0, ratelimit_burst=2)
    return TestClient(gateway.app)


def test_ratelimit():
    c = client()
    h = {"x-api-key": "k"}
    assert c.get("/whoami", headers=h).status_code == 200
    assert c.get("/whoami", headers=h).status_code == 200
    assert c.get("/whoami", headers=h).status_code == 429
