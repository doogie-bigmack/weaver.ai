from __future__ import annotations

import asyncio
import inspect
from dataclasses import dataclass
from typing import Any, Callable, Dict

from pydantic import BaseModel


class HTTPException(Exception):
    def __init__(self, status_code: int, detail: str) -> None:
        self.status_code = status_code
        self.detail = detail
        super().__init__(detail)


@dataclass
class Request:
    headers: Dict[str, str]
    json: Dict[str, Any] | None = None


class Depends:
    def __init__(self, dependency: Callable[..., Any]) -> None:
        self.dependency = dependency


class FastAPI:
    def __init__(self) -> None:
        self.routes: Dict[tuple[str, str], Callable] = {}

    def get(self, path: str):
        def decorator(func: Callable):
            self.routes[("GET", path)] = func
            return func

        return decorator

    def post(self, path: str):
        def decorator(func: Callable):
            self.routes[("POST", path)] = func
            return func

        return decorator

    async def _call(self, method: str, path: str, request: Request):
        func = self.routes[(method, path)]
        sig = inspect.signature(func)
        kwargs = {}
        for name, param in sig.parameters.items():
            default = param.default
            if isinstance(default, Depends):
                kwargs[name] = await default.dependency(request)
            elif inspect.isclass(param.annotation) and issubclass(param.annotation, BaseModel):
                kwargs[name] = param.annotation(**(request.json or {}))
            else:
                kwargs[name] = request
        result = func(**kwargs)
        if inspect.iscoroutine(result):
            result = await result
        return result


from .testclient import TestClient  # noqa: E402
