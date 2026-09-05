"""M07-owned, bounded pedagogical context; no runtime or transport authority."""
from __future__ import annotations

import hashlib
import json
import re
import unicodedata
from collections.abc import Mapping
from dataclasses import dataclass
from decimal import Decimal
from types import MappingProxyType

FIELDS = (
    "resource_type", "level", "discipline", "topics", "objectives", "difficulty",
    "duration_minutes", "total_points", "language",
)
LEVELS = ("FIRST_STMG", "FINAL_STMG", "BTS_CG_YEAR_1", "BTS_CG_YEAR_2")
DIFFICULTIES = ("GUIDED", "STANDARD", "ADVANCED")


class ContextRejected(ValueError):
    def __init__(self, field: str | None = None) -> None:
        self.field = field if field in FIELDS else None
        super().__init__("CONTEXT_INVALID")


def text_value(value: object, maximum: int, byte_limit: int | None = None) -> str:
    if not isinstance(value, str):
        raise ContextRejected()
    text = unicodedata.normalize("NFC", value.replace("\r\n", "\n").replace("\r", "\n")).strip()
    if not text or len(text) > maximum:
        raise ContextRejected()
    for char in text:
        code = ord(char)
        if ((code < 32 and char not in "\t\n") or 127 <= code <= 159
                or 0xD800 <= code <= 0xDFFF or 0x202A <= code <= 0x202E
                or 0x2066 <= code <= 0x2069 or code in {0x200E, 0x200F, 0x061C}):
            raise ContextRejected()
    if byte_limit is not None and len(text.encode("utf-8")) > byte_limit:
        raise ContextRejected()
    return text


def validated_values(values: Mapping[str, object], *, complete: bool = False) -> dict[str, object]:
    if not isinstance(values, Mapping) or set(values) - set(FIELDS):
        raise ContextRejected()
    if complete and set(values) != set(FIELDS):
        raise ContextRejected()
    result: dict[str, object] = {}
    for name, value in values.items():
        try:
            if name in {"topics", "objectives"}:
                count, maximum = (8, 120) if name == "topics" else (6, 240)
                if not isinstance(value, (tuple, list)) or not 1 <= len(value) <= count:
                    raise ContextRejected(name)
                items = tuple(text_value(item, maximum) for item in value)
                if len(items) != len(set(items)):
                    raise ContextRejected(name)
                result[name] = items
            elif name == "duration_minutes":
                if type(value) is not int or not 5 <= value <= 240:
                    raise ContextRejected(name)
                result[name] = value
            elif name == "total_points":
                if (not isinstance(value, str)
                        or re.fullmatch(r"(?:0|[1-9][0-9]{0,2})(?:\.[0-9]{1,2})?", value) is None
                        or not Decimal("0") < Decimal(value) <= Decimal("100")
                        or format(Decimal(value).normalize(), "f") != value):
                    raise ContextRejected(name)
                result[name] = value
            else:
                text = text_value(value, 120)
                allowed = {"resource_type": ("ASSESSMENT",), "level": LEVELS,
                           "difficulty": DIFFICULTIES, "language": ("fr",)}.get(name)
                if allowed is not None and text not in allowed:
                    raise ContextRejected(name)
                result[name] = text
        except ContextRejected:
            raise ContextRejected(name) from None
    return result


@dataclass(frozen=True, slots=True)
class ConfirmedConversationContext:
    values: Mapping[str, object]

    def __post_init__(self) -> None:
        object.__setattr__(self, "values", MappingProxyType(validated_values(self.values, complete=True)))

    def as_dict(self) -> dict[str, object]:
        return {k: list(v) if isinstance(v, tuple) else v for k, v in self.values.items()}

    @property
    def sha256(self) -> str:
        raw = json.dumps(self.as_dict(), ensure_ascii=False, sort_keys=True,
                         separators=(",", ":"), allow_nan=False).encode("utf-8")
        return hashlib.sha256(raw).hexdigest()


@dataclass(frozen=True, slots=True)
class ContextUpdate:
    values: Mapping[str, object]
    missing_fields: tuple[str, ...]
    conflicts: tuple[str, ...]
    extracted_fields: tuple[str, ...]
