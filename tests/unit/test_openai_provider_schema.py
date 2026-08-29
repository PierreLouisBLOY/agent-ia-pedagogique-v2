from __future__ import annotations

from copy import deepcopy

import pytest

from backend.adapters.outbound.openai.schema import (
    OpenAIProviderSchemaError,
    OpenAIProviderSchemaErrorCode,
    lower_openai_strict_schema,
    validate_openai_strict_schema,
)


def _source_schema() -> dict[str, object]:
    return {
        "type": "object",
        "properties": {
            "items": {
                "type": "array",
                "items": {"type": "string", "minLength": 1},
                "minItems": 0,
                "maxItems": 2,
                "uniqueItems": True,
            }
        },
        "required": ["items"],
        "additionalProperties": False,
    }


def test_openai_schema_lowering_is_deterministic_and_non_mutating() -> None:
    source = _source_schema()
    snapshot = deepcopy(source)
    first = lower_openai_strict_schema(source)
    second = lower_openai_strict_schema(source)
    assert first == second
    assert source == snapshot
    assert "uniqueItems" in str(source)
    assert "uniqueItems" not in str(first)
    validate_openai_strict_schema(first)


@pytest.mark.parametrize(
    "keyword",
    (
        "allOf",
        "not",
        "dependentRequired",
        "dependentSchemas",
        "if",
        "then",
        "else",
        "unknownKeyword",
    ),
)
def test_openai_schema_validator_rejects_every_unsupported_keyword(
    keyword: str,
) -> None:
    schema = _source_schema()
    array_schema = schema["properties"]
    assert type(array_schema) is dict
    array_schema["items"][keyword] = {}  # type: ignore[index]
    with pytest.raises(OpenAIProviderSchemaError) as raised:
        lower_openai_strict_schema(schema)
    assert raised.value.code is OpenAIProviderSchemaErrorCode.UNSUPPORTED_KEYWORD
