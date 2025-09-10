from __future__ import annotations

import hmac

import jwt
from fastapi import HTTPException
from pydantic import BaseModel

from ..settings import AppSettings


class UserContext(BaseModel):
    tenant_id: str | None = None
    user_id: str
    roles: list[str] = []
    scopes: list[str] = []


def authenticate(headers: dict[str, str], settings: AppSettings) -> UserContext:
    if settings.auth_mode == "api_key":
        key = headers.get("x-api-key", "")
        if not key:
            raise HTTPException(status_code=401, detail="Missing API key")

        # Use constant-time comparison to prevent timing attacks
        valid_key_found = False
        for allowed_key in settings.allowed_api_keys:
            if hmac.compare_digest(key, allowed_key):
                valid_key_found = True
                break

        if not valid_key_found:
            raise HTTPException(status_code=401, detail="unauthorized")
        return UserContext(user_id=headers.get("x-user-id", "anonymous"))

    # JWT authentication
    auth_header = headers.get("authorization", "")
    if not auth_header:
        raise HTTPException(status_code=401, detail="Missing authorization header")

    if not auth_header.startswith("Bearer "):
        raise HTTPException(
            status_code=401, detail="Invalid authorization header format"
        )

    token = auth_header[7:]  # Remove "Bearer " prefix safely
    if not token:
        raise HTTPException(status_code=401, detail="Missing token")

    # Ensure JWT key is configured
    if not settings.jwt_public_key:
        raise HTTPException(status_code=500, detail="JWT key not configured")

    try:
        data = jwt.decode(
            token,
            settings.jwt_public_key,
            algorithms=["HS256"],
            options={
                "verify_signature": True,
                "verify_exp": True,
                "require": ["sub"],  # Require subject claim
            },
        )
    except jwt.ExpiredSignatureError as exc:
        raise HTTPException(status_code=401, detail="Token expired") from exc
    except jwt.InvalidTokenError as exc:
        raise HTTPException(status_code=401, detail="Invalid token") from exc

    return UserContext(user_id=data.get("sub", "user"))
