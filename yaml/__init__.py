from __future__ import annotations

from typing import Any, Dict, TextIO


def safe_load(stream: str | TextIO) -> Dict[str, Any]:
    if hasattr(stream, "read"):
        text = stream.read()
    else:
        text = str(stream)
    data: Dict[str, Any] = {}
    key: str | None = None
    for raw in text.splitlines():
        line = raw.rstrip()
        if not line:
            continue
        if not line.startswith(" "):
            key = line.rstrip(":")
            data[key] = []
        elif key and line.strip().startswith("- "):
            item = line.strip()[2:].strip("'\"")
            data[key].append(item)
    return data
