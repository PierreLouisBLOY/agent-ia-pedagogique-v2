from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from enum import StrEnum

from backend.shared_kernel._safe_data import freeze_safe_mapping
from backend.shared_kernel._strings import require_non_empty
from backend.shared_kernel._value_safety import require_safe_structured_value


class ApplicationFailureKind(StrEnum):
    AF_PORT_UNAVAILABLE = "AF_PORT_UNAVAILABLE"
    AF_TIMEOUT = "AF_TIMEOUT"
    AF_PERSISTENCE = "AF_PERSISTENCE"
    AF_CONCURRENCY = "AF_CONCURRENCY"
    AF_MAPPING_CORRUPTION = "AF_MAPPING_CORRUPTION"
    AF_COMMIT_OUTCOME_UNKNOWN = "AF_COMMIT_OUTCOME_UNKNOWN"
    AF_ROLLBACK_FAILED = "AF_ROLLBACK_FAILED"
    AF_POSTCOMMIT_SIDE_EFFECT = "AF_POSTCOMMIT_SIDE_EFFECT"
    AF_INTERNAL_UNEXPECTED = "AF_INTERNAL_UNEXPECTED"


_RECONCILIATION_REQUIRED = frozenset(
    {
        ApplicationFailureKind.AF_COMMIT_OUTCOME_UNKNOWN,
        ApplicationFailureKind.AF_ROLLBACK_FAILED,
    }
)


@dataclass(frozen=True, slots=True)
class ApplicationFailure:
    """A safe application/technical failure description for contract boundaries."""

    kind: ApplicationFailureKind
    message_key: str | None = None
    details: Mapping[str, object] | None = None
    cause_ref: str | None = None

    def __post_init__(self) -> None:
        if self.message_key is not None:
            require_non_empty(self.message_key, "message_key")
        if self.cause_ref is not None:
            require_non_empty(self.cause_ref, "cause_ref")
            require_safe_structured_value(
                self.cause_ref,
                root_location="application_failure_cause_ref",
            )
        if self.details is not None:
            object.__setattr__(self, "details", freeze_safe_mapping(self.details))

    @property
    def reconciliation_required(self) -> bool:
        return self.kind in _RECONCILIATION_REQUIRED
