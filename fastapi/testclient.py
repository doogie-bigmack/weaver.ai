from __future__ import annotations

import asyncio
from typing import Any, Dict

from pydantic import BaseModel

from . import FastAPI, Request


class Response:
    def __init__(self, status_code: int, data: Any) -> None:
        self.status_code = status_code
        self._data = data

    def json(self) -> Any:
        return self._data


class TestClient:
    def __init__(self, app: FastAPI):
        self.app = app

    def _make_request(self, method: str, path: str, headers: Dict[str, str], json_data: Any | None):
        req = Request(headers=headers, json=json_data)
        try:
            data = asyncio.run(self.app._call(method, path, req))
            status = 200
            if isinstance(data, BaseModel):
                data = data.model_dump()
        except Exception as exc:  # noqa: BLE001
            if hasattr(exc, "status_code"):
                status = exc.status_code
                data = {"detail": exc.detail}
            else:
                raise
        return Response(status, data)

    def get(self, path: str, headers: Dict[str, str] | None = None):
        return self._make_request("GET", path, headers or {}, None)

    def post(self, path: str, headers: Dict[str, str] | None = None, json: Any | None = None):
        return self._make_request("POST", path, headers or {}, json)
