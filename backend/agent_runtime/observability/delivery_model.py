from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class ObservationChannel(StrEnum):
    LOG = "log"
    SPAN = "span"
    METRIC = "metric"


class DeliveryDisposition(StrEnum):
    BUFFERED = "BUFFERED"
    DROPPED = "DROPPED"
    REJECTED = "REJECTED"


class DeliveryDropReason(StrEnum):
    BUFFER_FULL = "BUFFER_FULL"
    SERIALIZATION_REJECTED = "SERIALIZATION_REJECTED"
    SINK_FAILURE = "SINK_FAILURE"
    RECORD_TOO_LARGE = "RECORD_TOO_LARGE"
    CHANNEL_DISABLED = "CHANNEL_DISABLED"


class DeliveryOverflowPolicy(StrEnum):
    DROP_NEWEST = "DROP_NEWEST"
    DROP_OLDEST = "DROP_OLDEST"


class DeliveryHealthStatus(StrEnum):
    HEALTHY = "HEALTHY"
    DEGRADED = "DEGRADED"
    DISABLED = "DISABLED"


@dataclass(frozen=True, slots=True)
class DeliveryAttempt:
    disposition: DeliveryDisposition
    reason: DeliveryDropReason | None = None
    displaced_count: int = 0

    def __post_init__(self) -> None:
        if not isinstance(self.disposition, DeliveryDisposition):
            raise TypeError("disposition must be a DeliveryDisposition")
        if self.reason is not None and not isinstance(
            self.reason, DeliveryDropReason
        ):
            raise TypeError("reason must be a DeliveryDropReason or None")
        _require_non_negative_int(self.displaced_count, "displaced_count")
        if self.disposition is DeliveryDisposition.BUFFERED:
            if self.reason is not None:
                raise ValueError("BUFFERED must not have a reason")
            return
        if self.reason is None:
            raise ValueError("DROPPED and REJECTED require a reason")
        if self.displaced_count:
            raise ValueError("only BUFFERED can report displaced items")


@dataclass(frozen=True, slots=True)
class DeliveryStatsSnapshot:
    delivered_count: int = 0
    buffered_count: int = 0
    dropped_count: int = 0
    failed_count: int = 0
    rejected_count: int = 0

    def __post_init__(self) -> None:
        for field_name in (
            "delivered_count",
            "buffered_count",
            "dropped_count",
            "failed_count",
            "rejected_count",
        ):
            _require_non_negative_int(getattr(self, field_name), field_name)


@dataclass(frozen=True, slots=True)
class DeliveryBufferSnapshot:
    occupancy_items: int
    occupancy_bytes: int
    capacity_items: int
    capacity_bytes: int

    def __post_init__(self) -> None:
        for field_name in (
            "occupancy_items",
            "occupancy_bytes",
            "capacity_items",
            "capacity_bytes",
        ):
            _require_non_negative_int(getattr(self, field_name), field_name)
        if self.capacity_items < 1 or self.capacity_bytes < 1:
            raise ValueError("buffer capacity must be positive")
        if self.occupancy_items > self.capacity_items:
            raise ValueError("buffer item occupancy exceeds capacity")
        if self.occupancy_bytes > self.capacity_bytes:
            raise ValueError("buffer byte occupancy exceeds capacity")


@dataclass(frozen=True, slots=True)
class DeliveryHealthSnapshot:
    channel: ObservationChannel
    status: DeliveryHealthStatus
    stats: DeliveryStatsSnapshot
    buffer: DeliveryBufferSnapshot
    last_failure_reason: DeliveryDropReason | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.channel, ObservationChannel):
            raise TypeError("channel must be an ObservationChannel")
        if not isinstance(self.status, DeliveryHealthStatus):
            raise TypeError("status must be a DeliveryHealthStatus")
        if not isinstance(self.stats, DeliveryStatsSnapshot):
            raise TypeError("stats must be a DeliveryStatsSnapshot")
        if not isinstance(self.buffer, DeliveryBufferSnapshot):
            raise TypeError("buffer must be a DeliveryBufferSnapshot")
        if self.last_failure_reason is not None and not isinstance(
            self.last_failure_reason, DeliveryDropReason
        ):
            raise TypeError(
                "last_failure_reason must be a DeliveryDropReason or None"
            )
        if self.status is DeliveryHealthStatus.HEALTHY and (
            self.last_failure_reason is not None
        ):
            raise ValueError("HEALTHY must not contain a failure reason")
        if self.status is DeliveryHealthStatus.DEGRADED and (
            self.last_failure_reason is None
        ):
            raise ValueError("DEGRADED requires a failure reason")


@dataclass(frozen=True, slots=True)
class DeliveryFlushResult:
    channel: ObservationChannel
    attempted_count: int
    delivered_count: int
    failed_count: int
    remaining_items: int
    busy: bool = False
    limit_reached: bool = False
    stopped_reason: DeliveryDropReason | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.channel, ObservationChannel):
            raise TypeError("channel must be an ObservationChannel")
        for field_name in (
            "attempted_count",
            "delivered_count",
            "failed_count",
            "remaining_items",
        ):
            _require_non_negative_int(getattr(self, field_name), field_name)
        if type(self.busy) is not bool or type(self.limit_reached) is not bool:
            raise TypeError("busy and limit_reached must be booleans")
        if self.attempted_count != self.delivered_count + self.failed_count:
            raise ValueError("attempted count must equal delivered plus failed")
        if self.failed_count > 1:
            raise ValueError("a flush stops after its first failure")
        if self.busy and self.attempted_count:
            raise ValueError("a busy flush cannot attempt delivery")
        if self.stopped_reason is not None and not isinstance(
            self.stopped_reason, DeliveryDropReason
        ):
            raise TypeError("stopped_reason must be a DeliveryDropReason or None")
        if self.failed_count:
            if self.stopped_reason is not DeliveryDropReason.SINK_FAILURE:
                raise ValueError("failed flush must stop for SINK_FAILURE")
        elif self.stopped_reason is not None:
            raise ValueError("successful flush must not have a stopped reason")


def _require_non_negative_int(value: int, field_name: str) -> None:
    if type(value) is not int:
        raise TypeError(f"{field_name} must be an integer")
    if value < 0:
        raise ValueError(f"{field_name} must be non-negative")
