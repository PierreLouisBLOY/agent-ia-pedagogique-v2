"""OpenAI-specific lowering and validation for strict JSON schemas."""

from __future__ import annotations

from copy import deepcopy
from enum import StrEnum
from typing import NoReturn, cast


class OpenAIProviderSchemaErrorCode(StrEnum):
    INVALID_SCHEMA = "INVALID_SCHEMA"
    UNSUPPORTED_KEYWORD = "UNSUPPORTED_KEYWORD"


class OpenAIProviderSchemaError(RuntimeError):
    """Closed compatibility failure raised before an OpenAI request is sent."""

    code: OpenAIProviderSchemaErrorCode

    def __init__(self, code: OpenAIProviderSchemaErrorCode) -> None:
        self.code = code
        super().__init__(code.value)


_SUPPORTED_KEYWORDS = frozenset(
    {
        "$defs",
        "$ref",
        "additionalProperties",
        "anyOf",
        "const",
        "description",
        "enum",
        "exclusiveMaximum",
        "exclusiveMinimum",
        "format",
        "items",
        "maxItems",
        "maxLength",
        "maximum",
        "minItems",
        "minLength",
        "minimum",
        "multipleOf",
        "pattern",
        "patternProperties",
        "properties",
        "required",
        "type",
    }
)
_LOWERED_KEYWORDS = frozenset({"uniqueItems"})
_EXPLICITLY_UNSUPPORTED_KEYWORDS = frozenset(
    {
        "allOf",
        "dependentRequired",
        "dependentSchemas",
        "else",
        "if",
        "not",
        "then",
        "uniqueItems",
    }
)
_MAX_NESTING_DEPTH = 10
_MAX_OBJECT_PROPERTIES = 5_000


def lower_openai_strict_schema(schema: dict[str, object]) -> dict[str, object]:
    """Copy a V2 schema, lower deliberate keywords, then validate the result."""

    if type(schema) is not dict:
        _schema_error(OpenAIProviderSchemaErrorCode.INVALID_SCHEMA)
    lowered = _lower_node(deepcopy(schema))
    validate_openai_strict_schema(lowered)
    return lowered


def validate_openai_strict_schema(schema: dict[str, object]) -> None:
    """Fail closed when a schema falls outside the supported strict subset."""

    if type(schema) is not dict or schema.get("type") != "object" or "anyOf" in schema:
        _schema_error(OpenAIProviderSchemaErrorCode.INVALID_SCHEMA)
    property_count = [0]
    _validate_node(schema, depth=1, property_count=property_count)


def _lower_node(node: dict[str, object]) -> dict[str, object]:
    lowered: dict[str, object] = {}
    for key, value in node.items():
        if key in _LOWERED_KEYWORDS:
            continue
        if key in {"properties", "patternProperties", "$defs"}:
            if type(value) is not dict:
                _schema_error(OpenAIProviderSchemaErrorCode.INVALID_SCHEMA)
            lowered[key] = {
                name: _lower_node(_require_schema(child))
                for name, child in cast(dict[str, object], value).items()
            }
        elif key == "items":
            lowered[key] = _lower_node(_require_schema(value))
        elif key == "anyOf":
            if type(value) is not list:
                _schema_error(OpenAIProviderSchemaErrorCode.INVALID_SCHEMA)
            lowered[key] = [_lower_node(_require_schema(child)) for child in value]
        else:
            lowered[key] = value
    return lowered


def _validate_node(
    node: dict[str, object],
    *,
    depth: int,
    property_count: list[int],
) -> None:
    if depth > _MAX_NESTING_DEPTH:
        _schema_error(OpenAIProviderSchemaErrorCode.INVALID_SCHEMA)
    for key in node:
        if key in _EXPLICITLY_UNSUPPORTED_KEYWORDS or key not in _SUPPORTED_KEYWORDS:
            _schema_error(OpenAIProviderSchemaErrorCode.UNSUPPORTED_KEYWORD)

    node_type = node.get("type")
    if node_type == "object":
        properties = node.get("properties")
        required = node.get("required")
        if (
            type(properties) is not dict
            or type(required) is not list
            or any(type(item) is not str for item in required)
            or set(required) != set(properties)
            or node.get("additionalProperties") is not False
        ):
            _schema_error(OpenAIProviderSchemaErrorCode.INVALID_SCHEMA)
        property_count[0] += len(properties)
        if property_count[0] > _MAX_OBJECT_PROPERTIES:
            _schema_error(OpenAIProviderSchemaErrorCode.INVALID_SCHEMA)
        for child in properties.values():
            _validate_node(
                _require_schema(child),
                depth=depth + 1,
                property_count=property_count,
            )

    for container_key in ("patternProperties", "$defs"):
        container = node.get(container_key)
        if container is not None:
            if type(container) is not dict:
                _schema_error(OpenAIProviderSchemaErrorCode.INVALID_SCHEMA)
            for child in container.values():
                _validate_node(
                    _require_schema(child),
                    depth=depth + 1,
                    property_count=property_count,
                )

    items = node.get("items")
    if items is not None:
        _validate_node(
            _require_schema(items),
            depth=depth + 1,
            property_count=property_count,
        )
    alternatives = node.get("anyOf")
    if alternatives is not None:
        if type(alternatives) is not list or not alternatives:
            _schema_error(OpenAIProviderSchemaErrorCode.INVALID_SCHEMA)
        for child in alternatives:
            _validate_node(
                _require_schema(child),
                depth=depth + 1,
                property_count=property_count,
            )


def _require_schema(value: object) -> dict[str, object]:
    if type(value) is not dict:
        _schema_error(OpenAIProviderSchemaErrorCode.INVALID_SCHEMA)
    return cast(dict[str, object], value)


def _schema_error(code: OpenAIProviderSchemaErrorCode) -> NoReturn:
    raise OpenAIProviderSchemaError(code) from None
