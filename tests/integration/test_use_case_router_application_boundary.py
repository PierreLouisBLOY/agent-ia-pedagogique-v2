from __future__ import annotations

import pytest

from backend.agent_runtime.application_routing import (
    UseCaseRoutingError,
    UseCaseRoutingErrorCode,
)
from backend.agent_runtime.contracts import (
    AGENT_CONTRACT_SCHEMA_V1_0,
    AgentId,
    ContractMeta,
    UseCaseResult,
)
from backend.agent_runtime.contracts.errors import (
    EffectState,
    ErrorCategory,
    ErrorEnvelope,
    ErrorSeverity,
    ErrorSource,
)
from backend.agent_runtime.policy import PolicyFacts
from backend.core_contracts.outcome import (
    ApplicationFailure,
    ApplicationFailureKind,
    ApplicationOutcome,
    OutcomeStatus,
)
from backend.shared_kernel.correlation import CorrelationId
from backend.shared_kernel.errors import (
    BusinessError,
    BusinessErrorCategory,
    BusinessErrorCode,
    BusinessErrorDomain,
    BusinessErrorSeverity,
)
from tests.support.use_case_routing_fakes import (
    NOW,
    USE_CASE_CAPABILITIES,
    make_request,
    make_result,
    make_router,
)


def _route(router: object, request: object, context: object) -> object:
    return router.route(  # type: ignore[attr-defined]
        agent_id=AgentId.AG_01,
        request=request,
        context=context,
        evaluated_at=NOW,
    )


@pytest.mark.parametrize("use_case_id", tuple(USE_CASE_CAPABILITIES))
def test_each_baseline_application_use_case_routes_to_its_exact_inbound_once(
    use_case_id: str,
) -> None:
    mutable = use_case_id in {
        "application.request_promotion",
        "application.export_artifact",
    }
    facts = (
        PolicyFacts(matrix_gate_satisfied=True)
        if use_case_id == "application.request_promotion"
        else PolicyFacts()
    )
    request, context = make_request(
        use_case_id,
        idempotency_key=("idem-1" if mutable else None),
        policy_facts=facts,
    )
    expected = make_result(request)
    router, inbound = make_router(request, result=expected)

    result = _route(router, request, context)

    assert len(inbound.calls) == 1
    assert inbound.calls[0] is request
    assert result == expected
    assert result is not expected
    assert result.use_case_id == use_case_id
    assert result.meta.correlation_id == request.meta.correlation_id
    if use_case_id == "application.run_deterministic_validation":
        assert result.outcome.validation_result == {"valid": True}


@pytest.mark.parametrize(
    ("changes", "code"),
    [
        (
            {"use_case_id": "application.read_production"},
            UseCaseRoutingErrorCode.RESULT_USE_CASE_MISMATCH,
        ),
        ({"run_id": "other-run"}, UseCaseRoutingErrorCode.RESULT_RUN_MISMATCH),
        ({"step_id": "other-step"}, UseCaseRoutingErrorCode.RESULT_STEP_MISMATCH),
        (
            {"correlation_id": CorrelationId("other-correlation")},
            UseCaseRoutingErrorCode.RESULT_CORRELATION_MISMATCH,
        ),
    ],
)
def test_result_identity_mismatch_is_rejected_after_one_inbound_call(
    changes: dict[str, object],
    code: UseCaseRoutingErrorCode,
) -> None:
    request, context = make_request()
    result = make_result(request, **changes)  # type: ignore[arg-type]
    router, inbound = make_router(request, result=result)

    with pytest.raises(UseCaseRoutingError) as raised:
        _route(router, request, context)

    assert raised.value.code is code
    assert len(inbound.calls) == 1


def test_domain_rejection_is_preserved_without_runtime_remapping() -> None:
    request, context = make_request("application.run_deterministic_validation")
    business_error = BusinessError(
        code=BusinessErrorCode("VALIDATION_REJECTED"),
        domain=BusinessErrorDomain.VALIDATION,
        category=BusinessErrorCategory.INVALID,
        severity=BusinessErrorSeverity.ERROR,
        blocking=True,
        retryable=False,
        message_key="validation.rejected",
    )
    outcome: ApplicationOutcome[object, object] = ApplicationOutcome(
        outcome_status=OutcomeStatus.REJECTED,
        success=False,
        correlation_id=request.meta.correlation_id,
        business_errors=(business_error,),
        validation_result={"valid": False},
    )
    rejected = make_result(request, status=OutcomeStatus.REJECTED, outcome=outcome)
    router, inbound = make_router(request, result=rejected)

    result = _route(router, request, context)

    assert result.meta.status is OutcomeStatus.REJECTED
    assert result.outcome.business_errors == (business_error,)
    assert result.outcome.validation_result == {"valid": False}
    assert len(inbound.calls) == 1


def test_application_failure_and_indeterminate_status_are_preserved() -> None:
    request, context = make_request(
        "application.export_artifact",
        idempotency_key="export-1",
    )
    failure = ApplicationFailure(
        kind=ApplicationFailureKind.AF_COMMIT_OUTCOME_UNKNOWN,
        message_key="export.commit.unknown",
    )
    outcome: ApplicationOutcome[object, object] = ApplicationOutcome(
        outcome_status=OutcomeStatus.INDETERMINATE,
        success=False,
        correlation_id=request.meta.correlation_id,
        application_failure=failure,
    )
    indeterminate = make_result(
        request,
        status=OutcomeStatus.INDETERMINATE,
        outcome=outcome,
    )
    router, inbound = make_router(request, result=indeterminate)

    result = _route(router, request, context)

    assert result.meta.status is OutcomeStatus.INDETERMINATE
    assert result.outcome.application_failure == failure
    assert result.outcome.application_failure.reconciliation_required
    assert len(inbound.calls) == 1


def test_success_that_masks_domain_error_is_rejected_without_retry() -> None:
    request, context = make_request()
    business_error = BusinessError(
        code=BusinessErrorCode("MASKED"),
        domain=BusinessErrorDomain.CORE,
        category=BusinessErrorCategory.INVARIANT,
        severity=BusinessErrorSeverity.ERROR,
        blocking=True,
        retryable=False,
        message_key="masked.error",
    )
    outcome: ApplicationOutcome[object, object] = ApplicationOutcome(
        outcome_status=OutcomeStatus.SUCCESS,
        success=True,
        correlation_id=request.meta.correlation_id,
        business_errors=(business_error,),
    )
    masked = make_result(request, outcome=outcome)
    router, inbound = make_router(request, result=masked)

    with pytest.raises(UseCaseRoutingError) as raised:
        _route(router, request, context)

    assert raised.value.code is UseCaseRoutingErrorCode.INVALID_USE_CASE_RESULT
    assert len(inbound.calls) == 1


def test_forged_status_outcome_and_error_mismatch_are_fail_closed() -> None:
    request, context = make_request()
    valid = make_result(request)
    failed_meta = ContractMeta(
        AGENT_CONTRACT_SCHEMA_V1_0,
        request.meta.run_id,
        request.meta.step_id,
        None,
        request.meta.correlation_id,
        NOW,
        request.meta.actor,
        OutcomeStatus.FAILED,
    )
    wrong_error = ErrorEnvelope(
        error_code="application.failed",
        category=ErrorCategory.DOMAIN,
        source=ErrorSource.APPLICATION,
        retryable=False,
        severity=ErrorSeverity.ERROR,
        message="application failed",
        step_id="other-step",
        attempt=1,
        effect_state=EffectState.NONE,
    )
    forged_values = (
        _forge_result(valid, meta=failed_meta),
        _forge_result(valid, error=wrong_error),
        object(),
    )

    for forged in forged_values:
        router, inbound = make_router(request, result=forged)
        with pytest.raises(UseCaseRoutingError) as raised:
            _route(router, request, context)
        assert raised.value.code is UseCaseRoutingErrorCode.INVALID_USE_CASE_RESULT
        assert len(inbound.calls) == 1


def _forge_result(
    source: UseCaseResult[object, object],
    **overrides: object,
) -> UseCaseResult[object, object]:
    forged = object.__new__(UseCaseResult)
    values = {
        "meta": source.meta,
        "use_case_id": source.use_case_id,
        "outcome": source.outcome,
        "result_ref": source.result_ref,
        "domain_events": source.domain_events,
        "error": source.error,
    }
    values.update(overrides)
    for field_name, value in values.items():
        object.__setattr__(forged, field_name, value)
    return forged
