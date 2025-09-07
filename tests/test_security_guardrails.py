from __future__ import annotations

from fastapi.testclient import TestClient
from weaver_ai import gateway
from weaver_ai.settings import AppSettings


def client() -> TestClient:
    gateway._settings = AppSettings(
        allowed_api_keys=["k"], ratelimit_rps=100, ratelimit_burst=100
    )
    return TestClient(gateway.app)


def test_deny_phrase():
    c = client()
    r = c.post(
        "/ask", headers={"x-api-key": "k"}, json={"user_id": "u", "query": "forbidden"}
    )
    assert r.status_code == 400


def test_pii_redact():
    c = client()
    r = c.post(
        "/ask",
        headers={"x-api-key": "k"},
        json={"user_id": "u", "query": "my ssn is 123-45-6789"},
    )
    assert r.status_code == 200
    assert "[redacted]" in r.json()["answer"]
