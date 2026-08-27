from __future__ import annotations

import re
from dataclasses import dataclass
from enum import StrEnum

from backend.shared_kernel.time import Instant

_EFFECT_RECORD_ID = re.compile(r"^effect:v1:[0-9a-f]{64}$")
_SAFE_IDENTIFIER = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,254}$")
_SAFE_REASON_CODE = re.compile(r"^[A-Z][A-Z0-9_.-]{0,127}$")


class RecoveryCheckpointAction(StrEnum):
    RETRY_SCHEDULED = "RETRY_SCHEDULED"


@dataclass(frozen=True, slots=True)
class RecoveryCheckpoint:
    """Minimal crash-safe state for one decisive pending recovery action."""

    action: RecoveryCheckpointAction
    step_id: str
    record_id: str
    record_version: int
    next_attempt: int
    retry_ordinal: int
    not_before: Instant
    reason_codes: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not isinstance(self.action, RecoveryCheckpointAction):
            raise TypeError("action must be a RecoveryCheckpointAction")
        if type(self.step_id) is not str or not _SAFE_IDENTIFIER.fullmatch(
            self.step_id
        ):
            raise ValueError("step_id must be a safe identifier")
        if type(self.record_id) is not str or not _EFFECT_RECORD_ID.fullmatch(
            self.record_id
        ):
            raise ValueError("record_id must be an opaque effect record identifier")
        if type(self.record_version) is not int or self.record_version < 1:
            raise ValueError("record_version must be >= 1")
        if type(self.next_attempt) is not int or self.next_attempt < 2:
            raise ValueError("next_attempt must be >= 2")
        if type(self.retry_ordinal) is not int or self.retry_ordinal < 1:
            raise ValueError("retry_ordinal must be >= 1")
        if self.retry_ordinal != self.next_attempt - 1:
            raise ValueError("retry_ordinal must equal next_attempt - 1")
        if not isinstance(self.not_before, Instant):
            raise TypeError("not_before must be an Instant")
        if not isinstance(self.reason_codes, tuple):
            raise TypeError("reason_codes must be a tuple")
        if any(
            type(item) is not str or not _SAFE_REASON_CODE.fullmatch(item)
            for item in self.reason_codes
        ):
            raise ValueError("reason_codes must contain safe closed codes")
        if len(set(self.reason_codes)) != len(self.reason_codes):
            raise ValueError("reason_codes must not contain duplicates")
