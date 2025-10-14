from __future__ import annotations

import hmac
import logging
from typing import Any

import jwt
from fastapi import HTTPException
from pydantic import BaseModel

from ..settings import AppSettings

logger = logging.getLogger(__name__)


class UserContext(BaseModel):
    tenant_id: str | None = None
    user_id: str
    roles: list[str] = []
    scopes: list[str] = []


class APIKeyMapping:
    """Secure API key to user mapping."""

    def __init__(self, mappings: dict[str, dict[str, Any]] | None = None):
        """
        Initialize API key mappings.

        Args:
            mappings: Dictionary mapping API keys to user info
                     Format: {"api_key": {"user_id": "user123", "roles": [...], "scopes": [...]}}
        """
        self.mappings = mappings or {}

    def get_user_info(self, api_key: str) -> dict[str, Any] | None:
        """
        Get user information for an API key using constant-time comparison.

        Args:
            api_key: The API key to lookup

        Returns:
            User information dict or None if not found
        """
        for stored_key, user_info in self.mappings.items():
            if hmac.compare_digest(api_key, stored_key):
                return user_info
        return None


def parse_api_key_mappings(api_keys: list[str]) -> dict[str, dict[str, Any]]:
    """
    Parse API key configuration into mappings.

    Expected format: "api_key:user_id:role1,role2:scope1,scope2"
    Simple format: "api_key" (maps to anonymous user)

    Args:
        api_keys: List of API key configuration strings

    Returns:
        Dictionary mapping API keys to user information
    """
    mappings = {}

    for key_config in api_keys:
        if not key_config:
            continue

        parts = key_config.split(":", 3)

        if len(parts) == 1:
            # Simple API key format - map to anonymous user
            mappings[parts[0]] = {"user_id": "anonymous", "roles": [], "scopes": []}
        elif len(parts) >= 2:
            # Extended format with user_id
            api_key = parts[0]
            user_id = parts[1] if parts[1] else "anonymous"
            roles = parts[2].split(",") if len(parts) > 2 and parts[2] else []
            scopes = parts[3].split(",") if len(parts) > 3 and parts[3] else []

            mappings[api_key] = {"user_id": user_id, "roles": roles, "scopes": scopes}
        else:
            logger.warning(f"Invalid API key configuration format: {key_config}")

    return mappings


def authenticate(headers: dict[str, str], settings: AppSettings) -> UserContext:
    """
    Authenticate a request using API key or JWT.

    Args:
        headers: Request headers
        settings: Application settings

    Returns:
        UserContext with authenticated user information

    Raises:
        HTTPException: If authentication fails
    """
    if settings.auth_mode == "api_key":
        key = headers.get("x-api-key", "")
        if not key:
            raise HTTPException(status_code=401, detail="Missing API key")

        # Parse API key mappings from settings
        api_key_mappings = parse_api_key_mappings(settings.allowed_api_keys)
        key_mapper = APIKeyMapping(api_key_mappings)

        # Get user info for the provided API key
        user_info = key_mapper.get_user_info(key)

        if not user_info:
            raise HTTPException(status_code=401, detail="Invalid API key")

        # Check if x-user-id header is provided
        header_user_id = headers.get("x-user-id")

        # If x-user-id is provided, validate it matches the API key's user
        if header_user_id and header_user_id != user_info["user_id"]:
            logger.warning(
                f"User ID mismatch: API key belongs to '{user_info['user_id']}' "
                f"but x-user-id header specifies '{header_user_id}'"
            )
            raise HTTPException(
                status_code=403, detail="User ID does not match API key authorization"
            )

        return UserContext(
            user_id=user_info["user_id"],
            roles=user_info.get("roles", []),
            scopes=user_info.get("scopes", []),
        )

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

    # Determine algorithm based on key type
    # Check if it's an RSA public key
    is_rsa_key = (
        "BEGIN PUBLIC KEY" in settings.jwt_public_key
        or "BEGIN RSA PUBLIC KEY" in settings.jwt_public_key
    )

    algorithm = "RS256" if is_rsa_key else "HS256"

    try:
        data = jwt.decode(
            token,
            settings.jwt_public_key,
            algorithms=[algorithm],
            options={
                "verify_signature": True,
                "verify_exp": True,
                "require": ["sub"],  # Require subject claim
            },
        )
    except jwt.ExpiredSignatureError as exc:
        raise HTTPException(status_code=401, detail="Token expired") from exc
    except jwt.InvalidTokenError as exc:
        logger.error(f"JWT validation failed: {exc}")
        raise HTTPException(status_code=401, detail="Invalid token") from exc

    return UserContext(
        user_id=data.get("sub", "user"),
        roles=data.get("roles", []),
        scopes=data.get("scopes", []),
    )
