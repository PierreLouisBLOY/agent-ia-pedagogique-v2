"""Deterministic value and structural safety for transport-neutral data."""

from __future__ import annotations

import re
from collections.abc import Mapping
from dataclasses import dataclass, fields, is_dataclass
from enum import StrEnum
from typing import Final


class SensitiveValueClass(StrEnum):
    SAFE_VALUE = "SAFE_VALUE"
    CREDENTIAL_LIKE = "CREDENTIAL_LIKE"
    AUTH_TOKEN_LIKE = "AUTH_TOKEN_LIKE"
    PRIVATE_KEY_LIKE = "PRIVATE_KEY_LIKE"
    CONNECTION_SECRET_LIKE = "CONNECTION_SECRET_LIKE"
    PRIVATE_PATH_LIKE = "PRIVATE_PATH_LIKE"


class StructuredDataLimitCode(StrEnum):
    MAX_DEPTH_EXCEEDED = "MAX_DEPTH_EXCEEDED"
    MAX_MAPPING_KEYS_EXCEEDED = "MAX_MAPPING_KEYS_EXCEEDED"
    MAX_SEQUENCE_ITEMS_EXCEEDED = "MAX_SEQUENCE_ITEMS_EXCEEDED"
    MAX_STRING_LENGTH_EXCEEDED = "MAX_STRING_LENGTH_EXCEEDED"
    MAX_TOTAL_NODES_EXCEEDED = "MAX_TOTAL_NODES_EXCEEDED"


@dataclass(frozen=True, slots=True)
class StructuredDataLimits:
    max_depth: int
    max_mapping_keys: int
    max_sequence_items: int
    max_string_length: int
    max_total_nodes: int

    def __post_init__(self) -> None:
        for field_name in (
            "max_depth",
            "max_mapping_keys",
            "max_sequence_items",
            "max_string_length",
            "max_total_nodes",
        ):
            value = getattr(self, field_name)
            if type(value) is not int:
                raise TypeError(f"{field_name} must be an integer")
            if value < 1:
                raise ValueError(f"{field_name} must be >= 1")


DEFAULT_STRUCTURED_DATA_LIMITS: Final = StructuredDataLimits(
    max_depth=16,
    max_mapping_keys=256,
    max_sequence_items=512,
    max_string_length=65_536,
    max_total_nodes=4_096,
)


@dataclass(frozen=True, slots=True)
class SensitiveValueLocation:
    classification: SensitiveValueClass
    logical_location: str

    def __post_init__(self) -> None:
        if self.classification is SensitiveValueClass.SAFE_VALUE:
            raise ValueError("a sensitive location requires a non-safe classification")
        _require_safe_location(self.logical_location)


class SensitiveValueRejected(ValueError):
    """Raw-value-free refusal raised by contract-safe data boundaries."""

    def __init__(self, finding: SensitiveValueLocation) -> None:
        if type(finding) is not SensitiveValueLocation:
            raise TypeError("finding must be a SensitiveValueLocation")
        self.finding = finding
        super().__init__(
            f"sensitive value rejected at {finding.logical_location}: "
            f"{finding.classification.value}"
        )


class StructuredDataLimitError(ValueError):
    """Bounded refusal that never includes the rejected value."""

    def __init__(self, code: StructuredDataLimitCode, logical_location: str) -> None:
        if type(code) is not StructuredDataLimitCode:
            raise TypeError("code must be a StructuredDataLimitCode")
        _require_safe_location(logical_location)
        self.code = code
        self.logical_location = logical_location
        super().__init__(f"structured data limit exceeded at {logical_location}: {code.value}")


_PRIVATE_KEY_MARKER = re.compile(
    r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----",
    re.IGNORECASE,
)
_BEARER_TOKEN = re.compile(r"\bbearer\s+[A-Za-z0-9._~+/-]{32,}\b", re.IGNORECASE)
_JWT = re.compile(
    r"(?<![A-Za-z0-9_-])[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{16,}\."
    r"[A-Za-z0-9_-]{16,}(?![A-Za-z0-9_-])"
)
_KNOWN_CREDENTIAL = re.compile(
    r"(?<![A-Za-z0-9])(?:"
    r"AKIA[0-9A-Z]{16}"
    r"|ghp_[A-Za-z0-9]{36,}"
    r"|xox[baprs]-[A-Za-z0-9-]{24,}"
    r"|sk-[A-Za-z0-9_-]{32,}"
    r")(?![A-Za-z0-9])"
)
_CONNECTION_SECRET = re.compile(
    r"\b(?:postgres(?:ql)?|mysql|mariadb|mongodb(?:\+srv)?|redis)://"
    r"[^\s/:@]+:[^\s/@]{8,}@[^\s]+",
    re.IGNORECASE,
)
_WINDOWS_ABSOLUTE_PATH = re.compile(r"^[A-Za-z]:[\\/]")


def classify_sensitive_text(value: str) -> SensitiveValueClass:
    if type(value) is not str:
        raise TypeError("value must be a string")
    if _PRIVATE_KEY_MARKER.search(value):
        return SensitiveValueClass.PRIVATE_KEY_LIKE
    if _CONNECTION_SECRET.search(value):
        return SensitiveValueClass.CONNECTION_SECRET_LIKE
    if _BEARER_TOKEN.search(value) or _JWT.search(value):
        return SensitiveValueClass.AUTH_TOKEN_LIKE
    if _KNOWN_CREDENTIAL.search(value):
        return SensitiveValueClass.CREDENTIAL_LIKE
    if _is_private_path(value):
        return SensitiveValueClass.PRIVATE_PATH_LIKE
    return SensitiveValueClass.SAFE_VALUE


def inspect_structured_value(
    value: object,
    *,
    limits: StructuredDataLimits = DEFAULT_STRUCTURED_DATA_LIMITS,
    root_location: str = "data",
) -> tuple[SensitiveValueLocation, ...]:
    """Inspect iteratively so nesting bombs fail before Python recursion does."""

    if type(limits) is not StructuredDataLimits:
        raise TypeError("limits must be StructuredDataLimits")
    root = _safe_segment(root_location, 0)
    stack: list[tuple[object, tuple[str, ...], int]] = [(value, (root,), 0)]
    findings: list[SensitiveValueLocation] = []
    visited = 0
    while stack:
        item, path, depth = stack.pop()
        visited += 1
        if visited > limits.max_total_nodes:
            _raise_limit(StructuredDataLimitCode.MAX_TOTAL_NODES_EXCEEDED, path)
        if depth > limits.max_depth:
            _raise_limit(StructuredDataLimitCode.MAX_DEPTH_EXCEEDED, path)
        if type(item) is str:
            if len(item) > limits.max_string_length:
                _raise_limit(StructuredDataLimitCode.MAX_STRING_LENGTH_EXCEEDED, path)
            classification = classify_sensitive_text(item)
            if classification is not SensitiveValueClass.SAFE_VALUE:
                findings.append(
                    SensitiveValueLocation(classification, _bounded_location(path))
                )
            continue
        if isinstance(item, Mapping):
            if len(item) > limits.max_mapping_keys:
                _raise_limit(StructuredDataLimitCode.MAX_MAPPING_KEYS_EXCEEDED, path)
            entries = tuple(item.items())
            for index, (key, nested) in reversed(tuple(enumerate(entries))):
                if type(key) is not str:
                    raise TypeError("structured data keys must be strings")
                if len(key) > limits.max_string_length:
                    _raise_limit(
                        StructuredDataLimitCode.MAX_STRING_LENGTH_EXCEEDED,
                        (*path, f"field_{index}"),
                    )
                stack.append((nested, (*path, _safe_segment(key, index)), depth + 1))
            continue
        if isinstance(item, (list, tuple)):
            if len(item) > limits.max_sequence_items:
                _raise_limit(StructuredDataLimitCode.MAX_SEQUENCE_ITEMS_EXCEEDED, path)
            for index in range(len(item) - 1, -1, -1):
                stack.append((item[index], (*path, str(index)), depth + 1))
            continue
        if is_dataclass(item) and not isinstance(item, type):
            dataclass_fields = fields(item)
            if len(dataclass_fields) > limits.max_mapping_keys:
                _raise_limit(StructuredDataLimitCode.MAX_MAPPING_KEYS_EXCEEDED, path)
            for index in range(len(dataclass_fields) - 1, -1, -1):
                item_field = dataclass_fields[index]
                stack.append(
                    (
                        getattr(item, item_field.name),
                        (*path, _safe_segment(item_field.name, index)),
                        depth + 1,
                    )
                )
    return tuple(findings)


def require_safe_structured_value(
    value: object,
    *,
    limits: StructuredDataLimits = DEFAULT_STRUCTURED_DATA_LIMITS,
    root_location: str = "data",
) -> None:
    findings = inspect_structured_value(
        value,
        limits=limits,
        root_location=root_location,
    )
    if findings:
        raise SensitiveValueRejected(findings[0])


def _is_private_path(value: str) -> bool:
    candidate = value.strip()
    if not candidate or any(character in candidate for character in "\r\n\t"):
        return False
    if _WINDOWS_ABSOLUTE_PATH.match(candidate) or candidate.startswith("\\\\"):
        return True
    if candidate.startswith(("~/", "~\\", "file:///")):
        return True
    return candidate.startswith("/") and " " not in candidate


def _raise_limit(code: StructuredDataLimitCode, path: tuple[str, ...]) -> None:
    raise StructuredDataLimitError(code, _bounded_location(path))


def _bounded_location(path: tuple[str, ...]) -> str:
    location = ".".join(path)
    if len(location) <= 512:
        return location
    return f"{path[0]}.depth_{len(path) - 1}.field"


def _safe_segment(value: str, index: int) -> str:
    normalized = "_".join(
        component
        for component in re.split(r"[^A-Za-z0-9]+", value.casefold())
        if component
    )
    if normalized and len(normalized) <= 64:
        return normalized
    return f"field_{index}"


def _require_safe_location(value: str) -> None:
    if type(value) is not str or not value or len(value) > 512:
        raise ValueError("logical_location must be a bounded safe location")
    if not all(character.isascii() and (character.isalnum() or character in "._-") for character in value):
        raise ValueError("logical_location must be a bounded safe location")
