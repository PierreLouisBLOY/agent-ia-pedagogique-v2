from __future__ import annotations

from dataclasses import replace

import pytest

from backend.adapters.inbound.api.read15 import (
    Read15Endpoint,
    Read15ValidationRejected,
    public_error,
)
from backend.adapters.inbound.application.resource_library import ResourceLibraryUseCaseInbound
from backend.agent_runtime.contracts import ContractMeta, UseCaseRequest, UseCaseResult
from backend.core_contracts.outcome import (
    ApplicationFailure,
    ApplicationFailureKind,
    ApplicationOutcome,
    OutcomeStatus,
)
from backend.modules.resource_library.application.queries import GetResourceQuery
from backend.modules.resource_library.domain.value_objects import ResourceRef
from backend.modules.resource_library.ports.outbound import ResourceRecord
from backend.shared_kernel.correlation import CorrelationId
from tests.support.use_case_routing_fakes import make_request

CORRELATION = "corr-use-case"
DATA = {
    "resource_ref": "resource:1", "resource_type": "COURSE",
    "canonical_title": "Titre synthétique", "availability_status": "ACTIVE",
}


def make_result(outcome: ApplicationOutcome[object, object]) -> UseCaseResult[object, object]:
    request, _ = make_request(payload={"resource_ref": "resource:1"})
    meta = request.meta
    return UseCaseResult(
        meta=ContractMeta(
            meta.schema_version, meta.run_id, meta.step_id, meta.parent_step_id,
            outcome.correlation_id, meta.created_at, meta.actor, outcome.outcome_status,
        ),
        use_case_id=request.use_case_id, outcome=outcome,
    )


def success(data: object = DATA) -> UseCaseResult[object, object]:
    return make_result(ApplicationOutcome(
        OutcomeStatus.SUCCESS, True, CorrelationId(CORRELATION), data=data,
    ))


def test_success_is_the_exact_public_projection_and_no_canonicality() -> None:
    endpoint = Read15Endpoint(lambda reference, correlation: success())
    projection = endpoint.get("resource:1", CORRELATION)
    assert projection.status == 200
    assert projection.payload == {"data": DATA, "meta": {"correlation_id": CORRELATION}}


@pytest.mark.parametrize("data", [
    None, [], {}, {**DATA, "identity_status": "CANONICAL"},
    {**DATA, "availability_status": None}, {**DATA, "resource_ref": "another"},
    {**DATA, "canonical_title": ""},
])
def test_malformed_success_is_not_an_empty_success(data: object) -> None:
    endpoint = Read15Endpoint(lambda reference, correlation: success(data))
    assert endpoint.get("resource:1", CORRELATION) == public_error("INTERNAL_ERROR", CORRELATION)


def test_application_validation_and_technical_exception_are_distinct() -> None:
    def invalid(reference: str, correlation: str) -> UseCaseResult[object, object]:
        raise Read15ValidationRejected("PRIVATE_SENTINEL")
    def failure(reference: str, correlation: str) -> UseCaseResult[object, object]:
        raise RuntimeError("PRIVATE_SENTINEL")
    assert Read15Endpoint(invalid).get("resource:1", CORRELATION) == public_error(
        "READ15_REQUEST_REJECTED", CORRELATION
    )
    assert Read15Endpoint(failure).get("resource:1", CORRELATION) == public_error(
        "INTERNAL_ERROR", CORRELATION
    )


class MissingStore:
    def load_resource(self, resource_ref: ResourceRef) -> ResourceRecord | None:
        return None


def test_real_application_business_not_found_is_preserved() -> None:
    request, _ = make_request(payload={"resource_ref": "resource:1"})
    inbound = ResourceLibraryUseCaseInbound(GetResourceQuery(MissingStore()))
    def invoke(reference: str, correlation: str) -> UseCaseResult[object, object]:
        actual: UseCaseRequest = request
        return inbound.invoke(request=actual)
    assert Read15Endpoint(invoke).get("resource:1", CORRELATION) == public_error(
        "RES_NOT_FOUND", CORRELATION
    )


@pytest.mark.parametrize("technical", [False, True])
def test_validation_result_and_application_failure_compartments(technical: bool) -> None:
    outcome: ApplicationOutcome[object, object] = ApplicationOutcome(
        OutcomeStatus.FAILED if technical else OutcomeStatus.REJECTED,
        False, CorrelationId(CORRELATION),
        application_failure=ApplicationFailure(ApplicationFailureKind.AF_PERSISTENCE)
        if technical else None,
        validation_result=None if technical else {"valid": False},
    )
    endpoint = Read15Endpoint(lambda reference, correlation: make_result(outcome))
    assert endpoint.get("resource:1", CORRELATION).status == (500 if technical else 400)


def test_wrong_correlation_and_side_effects_fail_closed() -> None:
    valid = success()
    for outcome in (
        replace(valid.outcome, correlation_id=CorrelationId("corr-other")),
        replace(valid.outcome, side_effects=({"effect": "unexpected"},)),
    ):
        endpoint = Read15Endpoint(lambda reference, correlation, value=outcome: make_result(value))
        assert endpoint.get("resource:1", CORRELATION).status == 500


def test_unknown_error_is_minimized() -> None:
    assert public_error("PRIVATE_SENTINEL", CORRELATION) == public_error(
        "INTERNAL_ERROR", CORRELATION
    )
