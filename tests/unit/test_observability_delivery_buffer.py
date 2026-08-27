from __future__ import annotations

import pytest

from backend.agent_runtime.observability import (
    DeliveryDropReason,
    DeliveryOverflowPolicy,
    ObservabilityDeliveryPolicy,
    ObservationChannel,
)
from backend.infrastructure.observability import (
    BoundedDeliveryBuffer,
    SerializedObservation,
)


def _item(value: str) -> SerializedObservation:
    payload = f'{{"value":"{value}"}}\n'
    return SerializedObservation(
        ObservationChannel.LOG,
        payload,
        len(payload.encode("utf-8")),
    )


def test_drop_newest_preserves_existing_fifo_history() -> None:
    policy = ObservabilityDeliveryPolicy(max_items=2, max_bytes=1_024)
    buffer = BoundedDeliveryBuffer(ObservationChannel.LOG, policy)
    first = _item("first")
    second = _item("second")
    newest = _item("newest")

    assert buffer.enqueue(first).accepted
    assert buffer.enqueue(second).accepted
    rejected = buffer.enqueue(newest)

    assert rejected.accepted is False
    assert rejected.reason is DeliveryDropReason.BUFFER_FULL
    assert buffer.pop_oldest() == first
    assert buffer.pop_oldest() == second
    assert buffer.pop_oldest() is None


def test_drop_oldest_removes_minimum_without_reordering_survivors() -> None:
    policy = ObservabilityDeliveryPolicy(
        max_items=2,
        max_bytes=1_024,
        overflow_policy=DeliveryOverflowPolicy.DROP_OLDEST,
    )
    buffer = BoundedDeliveryBuffer(ObservationChannel.LOG, policy)
    first = _item("first")
    second = _item("second")
    newest = _item("newest")
    buffer.enqueue(first)
    buffer.enqueue(second)

    accepted = buffer.enqueue(newest)

    assert accepted.accepted is True
    assert accepted.displaced_count == 1
    assert buffer.pop_oldest() == second
    assert buffer.pop_oldest() == newest


def test_buffer_enforces_byte_bound_independently_from_item_bound() -> None:
    item = _item("larger-record")
    policy = ObservabilityDeliveryPolicy(
        max_items=10,
        max_bytes=item.size_bytes - 1,
    )
    buffer = BoundedDeliveryBuffer(ObservationChannel.LOG, policy)

    result = buffer.enqueue(item)

    assert result.accepted is False
    assert result.reason is DeliveryDropReason.RECORD_TOO_LARGE
    assert buffer.snapshot().occupancy_items == 0
    assert buffer.snapshot().occupancy_bytes == 0


@pytest.mark.parametrize(
    ("field_name", "value"),
    [
        ("max_items", 0),
        ("max_items", 4_097),
        ("max_bytes", 0),
        ("max_bytes", 64 * 1_024 * 1_024 + 1),
        ("max_flush_items", 0),
        ("max_flush_items", 1_025),
    ],
)
def test_delivery_policy_rejects_unbounded_or_invalid_configuration(
    field_name: str,
    value: int,
) -> None:
    with pytest.raises(ValueError):
        ObservabilityDeliveryPolicy(**{field_name: value})


def test_buffer_rejects_cross_channel_items() -> None:
    buffer = BoundedDeliveryBuffer(
        ObservationChannel.METRIC,
        ObservabilityDeliveryPolicy(),
    )

    with pytest.raises(ValueError, match="channel"):
        buffer.enqueue(_item("log"))
