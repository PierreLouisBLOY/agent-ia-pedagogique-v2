from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass
from enum import StrEnum

from backend.shared_kernel._strings import require_non_empty

MAX_AUDIT_PAYLOAD_BYTES = 4096


class AuditEventType(StrEnum):
    RUNTIME_PORT_CONTRACT = "RUNTIME_PORT_CONTRACT"


@dataclass(frozen=True, slots=True)
class AuditActorRef:
    """Technical actor identity kept at the Application boundary."""

    value: str

    def __post_init__(self) -> None:
        require_non_empty(self.value, "value")
        if len(self.value) > 256:
            raise ValueError("value must contain at most 256 characters")


@dataclass(frozen=True, slots=True)
class AuditPayload:
    """Canonical, bounded JSON object ready for adapter persistence."""

    serialized_json: str

    def __post_init__(self) -> None:
        if not isinstance(self.serialized_json, str):
            raise TypeError("serialized_json must be a string")
        if len(self.serialized_json.encode("utf-8")) > MAX_AUDIT_PAYLOAD_BYTES:
            raise ValueError("serialized_json exceeds the audit payload limit")
        try:
            decoded = json.loads(self.serialized_json)
        except json.JSONDecodeError as error:
            raise ValueError("serialized_json must be valid JSON") from error
        if type(decoded) is not dict:
            raise ValueError("serialized_json must contain a JSON object")
        canonical = json.dumps(decoded, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        if canonical != self.serialized_json:
            raise ValueError("serialized_json must use canonical JSON encoding")

    @classmethod
    def from_mapping(cls, value: Mapping[str, object]) -> AuditPayload:
        if not isinstance(value, Mapping):
            raise TypeError("value must be a mapping")
        try:
            serialized = json.dumps(
                dict(value), ensure_ascii=False, sort_keys=True, separators=(",", ":")
            )
        except (TypeError, ValueError) as error:
            raise ValueError("value must be JSON serializable") from error
        return cls(serialized)


@dataclass(frozen=True, slots=True)
class AuditPersistenceValues:
    event_type: AuditEventType
    actor_ref: AuditActorRef
    payload: AuditPayload

    def __post_init__(self) -> None:
        if not isinstance(self.event_type, AuditEventType):
            raise TypeError("event_type must be an AuditEventType")
        if not isinstance(self.actor_ref, AuditActorRef):
            raise TypeError("actor_ref must be an AuditActorRef")
        if not isinstance(self.payload, AuditPayload):
            raise TypeError("payload must be an AuditPayload")
