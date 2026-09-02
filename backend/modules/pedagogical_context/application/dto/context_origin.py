from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class ContextOriginCode(StrEnum):
    RUNTIME = "runtime"


@dataclass(frozen=True, slots=True)
class ContextOrigin:
    """Technical Application metadata, never pedagogical notes."""

    value: ContextOriginCode

    def __post_init__(self) -> None:
        if not isinstance(self.value, ContextOriginCode):
            raise TypeError("value must be a ContextOriginCode")
