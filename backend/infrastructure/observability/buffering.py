from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from threading import Lock

from backend.agent_runtime.observability.delivery_model import (
    DeliveryBufferSnapshot,
    DeliveryDropReason,
    DeliveryOverflowPolicy,
    ObservationChannel,
)
from backend.agent_runtime.observability.delivery_policy import (
    ObservabilityDeliveryPolicy,
)
from backend.infrastructure.observability.serialization import SerializedObservation


@dataclass(frozen=True, slots=True)
class BufferEnqueueResult:
    accepted: bool
    displaced_count: int = 0
    reason: DeliveryDropReason | None = None

    def __post_init__(self) -> None:
        if type(self.accepted) is not bool:
            raise TypeError("accepted must be a bool")
        if type(self.displaced_count) is not int or self.displaced_count < 0:
            raise ValueError("displaced_count must be a non-negative integer")
        if self.reason is not None and not isinstance(
            self.reason, DeliveryDropReason
        ):
            raise TypeError("reason must be a DeliveryDropReason or None")
        if self.accepted and self.reason is not None:
            raise ValueError("accepted enqueue must not have a reason")
        if not self.accepted and self.reason is None:
            raise ValueError("rejected enqueue requires a reason")
        if not self.accepted and self.displaced_count:
            raise ValueError("rejected enqueue cannot displace buffered items")


class BoundedDeliveryBuffer:
    """Thread-safe bounded FIFO with non-blocking overflow semantics."""

    def __init__(
        self,
        channel: ObservationChannel,
        policy: ObservabilityDeliveryPolicy,
    ) -> None:
        if not isinstance(channel, ObservationChannel):
            raise TypeError("channel must be an ObservationChannel")
        if not isinstance(policy, ObservabilityDeliveryPolicy):
            raise TypeError("policy must be an ObservabilityDeliveryPolicy")
        self._channel = channel
        self._policy = policy
        self._items: deque[SerializedObservation] = deque()
        self._occupancy_bytes = 0
        self._lock = Lock()

    def enqueue(self, item: SerializedObservation) -> BufferEnqueueResult:
        if not isinstance(item, SerializedObservation):
            raise TypeError("item must be a SerializedObservation")
        if item.channel is not self._channel:
            raise ValueError("serialized observation channel must match buffer")
        if item.size_bytes > self._policy.max_bytes:
            return BufferEnqueueResult(
                False,
                reason=DeliveryDropReason.RECORD_TOO_LARGE,
            )
        with self._lock:
            if self._fits(item):
                self._append(item)
                return BufferEnqueueResult(True)
            if (
                self._policy.overflow_policy
                is DeliveryOverflowPolicy.DROP_NEWEST
            ):
                return BufferEnqueueResult(
                    False,
                    reason=DeliveryDropReason.BUFFER_FULL,
                )
            displaced = 0
            while self._items and not self._fits(item):
                removed = self._items.popleft()
                self._occupancy_bytes -= removed.size_bytes
                displaced += 1
            self._append(item)
            return BufferEnqueueResult(True, displaced_count=displaced)

    def pop_oldest(self) -> SerializedObservation | None:
        with self._lock:
            if not self._items:
                return None
            item = self._items.popleft()
            self._occupancy_bytes -= item.size_bytes
            return item

    def snapshot(self) -> DeliveryBufferSnapshot:
        with self._lock:
            return DeliveryBufferSnapshot(
                occupancy_items=len(self._items),
                occupancy_bytes=self._occupancy_bytes,
                capacity_items=self._policy.max_items,
                capacity_bytes=self._policy.max_bytes,
            )

    def _fits(self, item: SerializedObservation) -> bool:
        return (
            len(self._items) < self._policy.max_items
            and self._occupancy_bytes + item.size_bytes <= self._policy.max_bytes
        )

    def _append(self, item: SerializedObservation) -> None:
        self._items.append(item)
        self._occupancy_bytes += item.size_bytes
