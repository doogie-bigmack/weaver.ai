from __future__ import annotations

import base64
import hmac
import hashlib
import json
from typing import Any, Dict


class PyJWTError(Exception):
    pass


def _b64(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode().rstrip("=")


def _b64d(data: str) -> bytes:
    padding = "=" * (-len(data) % 4)
    return base64.urlsafe_b64decode(data + padding)


def encode(payload: Dict[str, Any], key: str, algorithm: str = "HS256") -> str:
    header = {"alg": algorithm, "typ": "JWT"}
    head = _b64(json.dumps(header, separators=(",", ":")).encode())
    body = _b64(json.dumps(payload, separators=(",", ":")).encode())
    signing = f"{head}.{body}".encode()
    sig = _b64(hmac.new(key.encode(), signing, hashlib.sha256).digest())
    return f"{head}.{body}.{sig}"


def decode(token: str, key: str, algorithms: list[str] | None = None) -> Dict[str, Any]:
    try:
        head_b64, body_b64, sig_b64 = token.split(".")
    except ValueError as exc:
        raise PyJWTError("malformed") from exc
    signing = f"{head_b64}.{body_b64}".encode()
    expected = hmac.new(key.encode(), signing, hashlib.sha256).digest()
    if not hmac.compare_digest(_b64d(sig_b64), expected):
        raise PyJWTError("bad signature")
    return json.loads(_b64d(body_b64))

