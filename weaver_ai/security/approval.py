from __future__ import annotations

from collections import deque
from typing import Deque, Dict

from pydantic import BaseModel


class PendingTool(BaseModel):
    tool: str
    args: dict
    user_id: str


_QUEUE: Deque[PendingTool] = deque()


def submit(tool: str, args: dict, user_id: str) -> None:
    _QUEUE.append(PendingTool(tool=tool, args=args, user_id=user_id))


def approve() -> PendingTool | None:
    return _QUEUE.popleft() if _QUEUE else None
