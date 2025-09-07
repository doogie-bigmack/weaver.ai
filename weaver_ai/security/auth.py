from __future__ import annotations

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
        key = headers.get("x-api-key")
        if key in settings.allowed_api_keys:
            return UserContext(user_id=headers.get("x-user-id", "anonymous"))
        raise HTTPException(status_code=401, detail="unauthorized")
    token = headers.get("authorization", "").split("Bearer ")[-1]
    try:
        data = jwt.decode(token, settings.jwt_public_key or "", algorithms=["HS256"])
    except jwt.PyJWTError as exc:
        raise HTTPException(status_code=401, detail="bad token") from exc
    return UserContext(user_id=data.get("sub", "user"))
