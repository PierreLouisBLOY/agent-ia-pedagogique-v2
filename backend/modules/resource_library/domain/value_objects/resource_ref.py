from __future__ import annotations

import re
from dataclasses import dataclass

from backend.modules.resource_library.domain.errors import InvalidResourceRefError

RESOURCE_REF_REGEX = r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$"
RESOURCE_REF_MIN_LENGTH = 1
RESOURCE_REF_MAX_LENGTH = 128

_RESOURCE_REF_PATTERN = re.compile(RESOURCE_REF_REGEX, flags=re.ASCII)


@dataclass(frozen=True, slots=True)
class ResourceRef:
    """Canonical opaque Resource identity approved by DM-02/A."""

    value: str

    def __post_init__(self) -> None:
        if type(self.value) is not str:
            raise TypeError("resource_ref must be a string")
        if _RESOURCE_REF_PATTERN.fullmatch(self.value) is None:
            raise InvalidResourceRefError(
                "resource_ref does not satisfy the canonical contract"
            )

    def __str__(self) -> str:
        return self.value
