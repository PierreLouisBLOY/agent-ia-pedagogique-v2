from dataclasses import FrozenInstanceError

import pytest

from backend.core_contracts.capability import CapabilityId
from backend.core_contracts.invocation import UseCaseContext
from backend.core_contracts.outcome import (
    ApplicationFailure,
    ApplicationFailureKind,
    ApplicationOutcome,
    OutcomeStatus,
)
from backend.shared_kernel.correlation import CorrelationId


class FakeValidationResult:
    def __init__(self, valid: bool) -> None:
        self.valid = valid


def test_outcome_status_has_exact_canonical_values() -> None:
    assert [item.value for item in OutcomeStatus] == [
        "SUCCESS",
        "SUCCESS_WITH_WARNING",
        "REJECTED",
        "FAILED",
        "INDETERMINATE",
    ]


def test_application_failure_kind_has_exact_canonical_values() -> None:
    assert [item.value for item in ApplicationFailureKind] == [
        "AF_PORT_UNAVAILABLE",
        "AF_TIMEOUT",
        "AF_PERSISTENCE",
        "AF_CONCURRENCY",
        "AF_MAPPING_CORRUPTION",
        "AF_COMMIT_OUTCOME_UNKNOWN",
        "AF_ROLLBACK_FAILED",
        "AF_POSTCOMMIT_SIDE_EFFECT",
        "AF_INTERNAL_UNEXPECTED",
    ]


@pytest.mark.parametrize(
    "kind",
    [
        ApplicationFailureKind.AF_COMMIT_OUTCOME_UNKNOWN,
        ApplicationFailureKind.AF_ROLLBACK_FAILED,
    ],
)
def test_uncertain_transaction_failures_require_reconciliation(
    kind: ApplicationFailureKind,
) -> None:
    assert ApplicationFailure(kind).reconciliation_required is True


def test_other_application_failures_do_not_require_reconciliation() -> None:
    other_kinds = set(ApplicationFailureKind) - {
        ApplicationFailureKind.AF_COMMIT_OUTCOME_UNKNOWN,
        ApplicationFailureKind.AF_ROLLBACK_FAILED,
    }

    assert all(not ApplicationFailure(kind).reconciliation_required for kind in other_kinds)


@pytest.mark.parametrize(
    ("status", "success"),
    [
        (OutcomeStatus.SUCCESS, True),
        (OutcomeStatus.SUCCESS_WITH_WARNING, True),
        (OutcomeStatus.REJECTED, False),
        (OutcomeStatus.FAILED, False),
        (OutcomeStatus.INDETERMINATE, False),
    ],
)
def test_application_outcome_accepts_canonical_success_mapping(
    status: OutcomeStatus, success: bool
) -> None:
    outcome: ApplicationOutcome[str, FakeValidationResult] = ApplicationOutcome(
        outcome_status=status,
        success=success,
        correlation_id=CorrelationId("corr-1"),
    )

    assert outcome.success is success


@pytest.mark.parametrize("status", list(OutcomeStatus))
def test_application_outcome_rejects_incoherent_success(status: OutcomeStatus) -> None:
    canonical_success = status in {
        OutcomeStatus.SUCCESS,
        OutcomeStatus.SUCCESS_WITH_WARNING,
    }

    with pytest.raises(ValueError):
        ApplicationOutcome[object, object](
            outcome_status=status,
            success=not canonical_success,
            correlation_id=CorrelationId("corr-1"),
        )


def test_application_outcome_is_generic_over_m09_validation_result() -> None:
    validation = FakeValidationResult(valid=True)
    outcome: ApplicationOutcome[str, FakeValidationResult] = ApplicationOutcome(
        outcome_status=OutcomeStatus.SUCCESS,
        success=True,
        correlation_id=CorrelationId("corr-1"),
        data="created",
        validation_result=validation,
    )

    assert outcome.validation_result is validation
    assert outcome.data == "created"


def test_application_outcome_requires_correlation_argument() -> None:
    with pytest.raises(TypeError):
        ApplicationOutcome[object, object](  # type: ignore[call-arg]
            outcome_status=OutcomeStatus.SUCCESS,
            success=True,
        )


@pytest.mark.parametrize("invalid_correlation", [None, "corr-1"])
def test_application_outcome_rejects_invalid_correlation(
    invalid_correlation: object,
) -> None:
    with pytest.raises(TypeError):
        ApplicationOutcome[object, object](
            outcome_status=OutcomeStatus.SUCCESS,
            success=True,
            correlation_id=invalid_correlation,  # type: ignore[arg-type]
        )


def test_application_failure_rejects_raw_exceptions() -> None:
    with pytest.raises(TypeError):
        ApplicationFailure(
            kind=ApplicationFailureKind.AF_INTERNAL_UNEXPECTED,
            details={"exception": RuntimeError("raw")},
        )

    with pytest.raises(TypeError):
        ApplicationFailure(
            kind=ApplicationFailureKind.AF_INTERNAL_UNEXPECTED,
            cause_ref=RuntimeError("raw"),  # type: ignore[arg-type]
        )


def test_use_case_context_requires_correlation_and_freezes_snapshot() -> None:
    context = UseCaseContext(
        correlation_id=CorrelationId("corr-1"),
        context_snapshot={"locale": "fr-FR", "levels": ["college"]},
    )

    assert context.context_snapshot is not None
    assert context.context_snapshot["levels"] == ("college",)
    with pytest.raises(TypeError):
        context.context_snapshot["locale"] = "en"  # type: ignore[index]
    with pytest.raises(TypeError):
        UseCaseContext(correlation_id=None)  # type: ignore[arg-type]


def test_application_outcome_accepts_and_freezes_safe_side_effects() -> None:
    outcome: ApplicationOutcome[object, object] = ApplicationOutcome(
        outcome_status=OutcomeStatus.SUCCESS,
        success=True,
        correlation_id=CorrelationId("corr-1"),
        side_effects=({"kind": "audit", "subjects": ["course-1"]},),
    )

    assert outcome.side_effects[0]["subjects"] == ("course-1",)
    with pytest.raises(TypeError):
        outcome.side_effects[0]["kind"] = "other"  # type: ignore[index]


@pytest.mark.parametrize(
    "side_effect",
    [RuntimeError("raw"), {"auth_token": "secret"}],
)
def test_application_outcome_rejects_unsafe_side_effects(side_effect: object) -> None:
    with pytest.raises((TypeError, ValueError)):
        ApplicationOutcome[object, object](
            outcome_status=OutcomeStatus.SUCCESS,
            success=True,
            correlation_id=CorrelationId("corr-1"),
            side_effects=(side_effect,),  # type: ignore[arg-type]
        )


def test_core_contract_value_objects_are_immutable_and_non_empty() -> None:
    capability_id = CapabilityId("course.generate")

    with pytest.raises(FrozenInstanceError):
        capability_id.value = "course.read"  # type: ignore[misc]
    with pytest.raises(ValueError):
        CapabilityId(" ")
