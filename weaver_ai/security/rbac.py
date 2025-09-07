from __future__ import annotations

from functools import lru_cache
from pathlib import Path

import yaml
from fastapi import HTTPException

from .auth import UserContext


@lru_cache
def _load_roles(path: Path) -> dict[str, list[str]]:
    with path.open() as f:
        data = yaml.safe_load(f) or {}
    return {str(k): list(v) for k, v in data.items()}


def check_access(user: UserContext, scope: str, *, roles_path: Path) -> None:
    roles = _load_roles(roles_path)
    user_scopes = set(user.scopes)
    for role in user.roles:
        user_scopes.update(roles.get(role, []))
    if scope not in user_scopes:
        raise HTTPException(status_code=403, detail="forbidden")
