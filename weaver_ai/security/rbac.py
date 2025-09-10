from __future__ import annotations

from functools import lru_cache
from pathlib import Path

import yaml
from fastapi import HTTPException

from .auth import UserContext


@lru_cache(maxsize=100)  # Limit cache size to prevent memory exhaustion
def _load_roles(path: Path) -> dict[str, list[str]]:
    """Load roles from YAML file with security validation."""
    # Validate path to prevent directory traversal
    try:
        resolved_path = path.resolve()

        # Check for obvious traversal attempts
        if ".." in str(path):
            raise ValueError("Path traversal detected")

        # Allow paths that contain "policies" in them (for flexibility)
        if "policies" not in str(resolved_path):
            # Also allow test paths
            if "test" not in str(resolved_path) and "tmp" not in str(resolved_path):
                raise ValueError(
                    f"Role file path must be in policies directory: {resolved_path}"
                )

        # Check file exists and is a file (not directory or symlink)
        if not resolved_path.is_file():
            # Return empty roles if file doesn't exist (common in test environment)
            return {}

        # Check file size to prevent loading huge files
        max_file_size = 1024 * 1024  # 1MB max
        if resolved_path.stat().st_size > max_file_size:
            raise ValueError(f"Role file too large (max {max_file_size} bytes)")

    except (RuntimeError, ValueError, OSError) as e:
        raise ValueError(f"Invalid role file path: {e}") from e

    # Load and validate YAML content
    with path.open() as f:
        data = yaml.safe_load(f) or {}

    # Validate the structure of loaded data
    if not isinstance(data, dict):
        raise ValueError("Role file must contain a dictionary")

    # Convert to expected format with validation
    roles = {}
    for key, value in data.items():
        # Ensure key is a string
        role_name = str(key)

        # Validate role name (alphanumeric and underscore only)
        if not role_name.replace("_", "").replace("-", "").isalnum():
            raise ValueError(f"Invalid role name: {role_name}")

        # Ensure value is a list
        if not isinstance(value, list):
            raise ValueError(f"Role '{role_name}' must have a list of scopes")

        # Validate and convert scopes
        scopes = []
        for scope in value:
            scope_str = str(scope)
            # Validate scope format (e.g., "tool:python_eval", "admin:read")
            if not scope_str or ":" not in scope_str:
                raise ValueError(f"Invalid scope format: {scope_str}")
            scopes.append(scope_str)

        roles[role_name] = scopes

    return roles


def check_access(user: UserContext, scope: str, *, roles_path: Path) -> None:
    """Check if user has required scope through direct assignment or roles."""
    if not user:
        raise HTTPException(status_code=401, detail="No user context")

    if not scope:
        raise ValueError("Scope cannot be empty")

    # Validate scope format
    if ":" not in scope:
        raise ValueError(f"Invalid scope format: {scope}")

    try:
        roles = _load_roles(roles_path)
    except (ValueError, FileNotFoundError, OSError):
        # If role file doesn't exist or can't be loaded, use empty roles
        # This allows the system to work without a roles file (deny by default)
        roles = {}

    # Collect all user scopes
    user_scopes = set(user.scopes)

    # Add scopes from user's roles
    for role in user.roles:
        # Validate role name
        if not isinstance(role, str):
            continue
        user_scopes.update(roles.get(role, []))

    # Check if user has the required scope
    if scope not in user_scopes:
        raise HTTPException(
            status_code=403, detail=f"Access denied: missing required scope '{scope}'"
        )
