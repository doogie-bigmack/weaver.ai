from __future__ import annotations

from typing import Any, Dict


class _Unset:
    pass


UNSET = _Unset()


class FieldInfo:
    def __init__(self, default: Any = UNSET, default_factory: Any | None = None) -> None:
        self.default = default
        self.default_factory = default_factory


def Field(*, default: Any = UNSET, default_factory: Any | None = None, **kwargs: Any) -> Any:
    return FieldInfo(default, default_factory)


class BaseModel:
    def __init__(self, **data: Any) -> None:
        for name in getattr(self.__class__, "__annotations__", {}):
            if name in data:
                value = data[name]
            else:
                default = getattr(self.__class__, name, UNSET)
                if isinstance(default, FieldInfo):
                    if default.default is not UNSET:
                        value = default.default
                    elif default.default_factory is not None:
                        value = default.default_factory()
                    else:
                        value = None
                elif default is not UNSET:
                    value = default() if callable(default) and name.endswith("_factory") else default
                else:
                    value = None
            if isinstance(value, (list, dict, set)):
                value = value.copy()
            setattr(self, name, value)

    def model_dump(self, *, exclude: set[str] | None = None) -> Dict[str, Any]:
        exclude = exclude or set()
        result = {}
        for k in getattr(self.__class__, "__annotations__", {}):
            if k in exclude:
                continue
            v = getattr(self, k)
            if isinstance(v, BaseModel):
                result[k] = v.model_dump()
            elif isinstance(v, list):
                result[k] = [i.model_dump() if isinstance(i, BaseModel) else i for i in v]
            else:
                result[k] = v
        return result


class BaseSettings(BaseModel):
    pass

