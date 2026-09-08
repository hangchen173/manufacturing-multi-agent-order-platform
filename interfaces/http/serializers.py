from dataclasses import asdict, is_dataclass
from enum import Enum
from typing import Any

from pydantic import BaseModel


def to_jsonable(data: Any) -> Any:
    if isinstance(data, BaseModel):
        return data.model_dump(mode="json")

    if isinstance(data, Enum):
        return data.value

    if is_dataclass(data):
        return to_jsonable(asdict(data))

    if isinstance(data, dict):
        return {key: to_jsonable(value) for key, value in data.items()}

    if isinstance(data, (list, tuple, set)):
        return [to_jsonable(item) for item in data]

    return data
