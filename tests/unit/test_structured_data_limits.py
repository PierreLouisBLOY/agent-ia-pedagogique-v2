from __future__ import annotations

import pytest

from backend.agent_runtime.contracts.common import (
    ERROR_SAFE_DATA_LIMITS,
    freeze_agent_safe_mapping,
)
from backend.agent_runtime.security import (
    SensitiveValuePolicy,
    StructuredDataLimitCode,
    StructuredDataLimitError,
)


def _nested(depth: int) -> dict[str, object]:
    value: dict[str, object] = {"leaf": True}
    for _ in range(depth):
        value = {"nested": value}
    return value


@pytest.mark.parametrize(
    ("value", "code"),
    (
        (_nested(17), StructuredDataLimitCode.MAX_DEPTH_EXCEEDED),
        (
            {f"field_{index}": index for index in range(257)},
            StructuredDataLimitCode.MAX_MAPPING_KEYS_EXCEEDED,
        ),
        (list(range(513)), StructuredDataLimitCode.MAX_SEQUENCE_ITEMS_EXCEEDED),
        ("x" * 65_537, StructuredDataLimitCode.MAX_STRING_LENGTH_EXCEEDED),
        (
            {f"field_{index}": list(range(16)) for index in range(256)},
            StructuredDataLimitCode.MAX_TOTAL_NODES_EXCEEDED,
        ),
    ),
    ids=("depth", "mapping-keys", "sequence", "string", "total-nodes"),
)
def test_default_structural_bombs_fail_closed(
    value: object,
    code: StructuredDataLimitCode,
) -> None:
    with pytest.raises(StructuredDataLimitError) as raised:
        SensitiveValuePolicy().require_safe(value, root_location="input")

    assert raised.value.code is code
    assert len(str(raised.value)) < 640


def test_error_details_use_tighter_depth_and_cardinality_limits() -> None:
    with pytest.raises(StructuredDataLimitError) as depth_error:
        freeze_agent_safe_mapping(_nested(9), limits=ERROR_SAFE_DATA_LIMITS)
    with pytest.raises(StructuredDataLimitError) as key_error:
        freeze_agent_safe_mapping(
            {f"field_{index}": index for index in range(65)},
            limits=ERROR_SAFE_DATA_LIMITS,
        )

    assert depth_error.value.code is StructuredDataLimitCode.MAX_DEPTH_EXCEEDED
    assert key_error.value.code is StructuredDataLimitCode.MAX_MAPPING_KEYS_EXCEEDED


def test_recursive_cycle_fails_with_bounded_deterministic_error() -> None:
    value: dict[str, object] = {}
    value["nested"] = value

    with pytest.raises(StructuredDataLimitError) as raised:
        SensitiveValuePolicy().require_safe(value, root_location="cycle")

    assert raised.value.code in {
        StructuredDataLimitCode.MAX_DEPTH_EXCEEDED,
        StructuredDataLimitCode.MAX_TOTAL_NODES_EXCEEDED,
    }
    assert len(raised.value.logical_location) <= 512
