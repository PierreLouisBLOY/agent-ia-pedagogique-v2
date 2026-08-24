from __future__ import annotations

from dataclasses import dataclass
from typing import Self


@dataclass(frozen=True, slots=True, order=True)
class ContractSchemaVersion:
    """Canonical MAJOR.MINOR version for agent runtime contracts."""

    major: int
    minor: int

    def __post_init__(self) -> None:
        if type(self.major) is not int:
            raise TypeError("major must be an integer")
        if type(self.minor) is not int:
            raise TypeError("minor must be an integer")
        if self.major < 1:
            raise ValueError("major must be >= 1")
        if self.minor < 0:
            raise ValueError("minor must be >= 0")

    @classmethod
    def parse(cls, value: str) -> Self:
        if not isinstance(value, str):
            raise TypeError("schema version must be a string")
        if value.count(".") != 1:
            raise ValueError("schema version must use canonical MAJOR.MINOR format")
        major_text, minor_text = value.split(".")
        if not _is_canonical_numeric_segment(major_text, allow_zero=False):
            raise ValueError("schema version must use canonical MAJOR.MINOR format")
        if not _is_canonical_numeric_segment(minor_text, allow_zero=True):
            raise ValueError("schema version must use canonical MAJOR.MINOR format")
        return cls(major=int(major_text), minor=int(minor_text))

    def __str__(self) -> str:
        return f"{self.major}.{self.minor}"


AGENT_CONTRACT_SCHEMA_V1_0 = ContractSchemaVersion(1, 0)


def _is_canonical_numeric_segment(value: str, *, allow_zero: bool) -> bool:
    if not value or any(character < "0" or character > "9" for character in value):
        return False
    if value == "0":
        return allow_zero
    return value[0] != "0"
