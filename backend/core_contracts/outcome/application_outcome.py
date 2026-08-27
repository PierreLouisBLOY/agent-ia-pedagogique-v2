from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass

from backend.core_contracts.outcome.application_failure import ApplicationFailure
from backend.core_contracts.outcome.status import OutcomeStatus
from backend.shared_kernel._safe_data import freeze_safe_mapping
from backend.shared_kernel._value_safety import require_safe_structured_value
from backend.shared_kernel.correlation import CorrelationId
from backend.shared_kernel.errors import BusinessError
from backend.shared_kernel.references import TypedEntityRef

_SUCCESS_STATUSES = frozenset(
    {OutcomeStatus.SUCCESS, OutcomeStatus.SUCCESS_WITH_WARNING}
)


@dataclass(frozen=True, slots=True)
class ApplicationOutcome[TData, TValidationResult]:
    """Generic result of an application use case, independent from M09."""

    outcome_status: OutcomeStatus
    success: bool
    correlation_id: CorrelationId
    data: TData | None = None
    business_errors: tuple[BusinessError, ...] = ()
    validation_result: TValidationResult | None = None
    application_failure: ApplicationFailure | None = None
    warnings: tuple[BusinessError, ...] = ()
    side_effects: tuple[Mapping[str, object], ...] = ()
    operation_ref: TypedEntityRef | None = None
    task_ref: TypedEntityRef | None = None
    subject_refs: tuple[TypedEntityRef, ...] = ()

    def __post_init__(self) -> None:
        if not isinstance(self.correlation_id, CorrelationId):
            raise TypeError("correlation_id must be a CorrelationId")

        expected_success = self.outcome_status in _SUCCESS_STATUSES
        if self.success is not expected_success:
            raise ValueError("success is inconsistent with outcome_status")

        require_safe_structured_value(self.data, root_location="application_data")
        require_safe_structured_value(
            self.validation_result,
            root_location="application_validation_result",
        )
        if len(self.business_errors) > 128 or len(self.warnings) > 128:
            raise ValueError("business errors and warnings must contain at most 128 items")
        if len(self.side_effects) > 512:
            raise ValueError("side_effects must contain at most 512 items")
        if len(self.subject_refs) > 512:
            raise ValueError("subject_refs must contain at most 512 items")

        object.__setattr__(self, "business_errors", tuple(self.business_errors))
        object.__setattr__(self, "warnings", tuple(self.warnings))
        object.__setattr__(
            self,
            "side_effects",
            tuple(freeze_safe_mapping(side_effect) for side_effect in self.side_effects),
        )
        object.__setattr__(self, "subject_refs", tuple(self.subject_refs))
