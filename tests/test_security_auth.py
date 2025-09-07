from __future__ import annotations

import jwt
from fastapi.testclient import TestClient

from weaver_ai import gateway
from weaver_ai.settings import AppSettings


def client_api_key() -> TestClient:
    gateway._settings = AppSettings(
        allowed_api_keys=["k"], ratelimit_rps=100, ratelimit_burst=100
    )
    return TestClient(gateway.app)


def test_auth_api_key():
    client = client_api_key()
    assert client.get("/whoami").status_code == 401
    r = client.get("/whoami", headers={"x-api-key": "k"})
    assert r.status_code == 200


def test_auth_jwt_bad_signature():
    gateway._settings = AppSettings(
        auth_mode="jwt", jwt_public_key="secret", ratelimit_rps=100, ratelimit_burst=100
    )
    client = TestClient(gateway.app)
    token = jwt.encode({"sub": "u"}, "other", algorithm="HS256")
    r = client.get("/whoami", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 401
