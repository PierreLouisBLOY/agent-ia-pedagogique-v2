from __future__ import annotations

import json
from decimal import Decimal

import pytest

from calibration_tooling.application.service import CalibrationService
from calibration_tooling.contracts.errors import (
    CalibrationContractError,
    CalibrationErrorCode,
    CalibrationExecutionError,
)
from calibration_tooling.contracts.models import (
    CALIBRATION_SCHEMA_V1,
    AbsoluteObservationResult,
    AbsoluteObservationSpec,
    AbsoluteScoreStatus,
    AuthorizationRef,
    CalibrationObservationSpec,
    CalibrationPlan,
    CallExecutionState,
    CallRef,
    CriterionRef,
    PairwiseDecision,
    PairwiseObservationResult,
    PairwiseObservationSpec,
    ProjectionRef,
    RawProviderResponse,
    RunRef,
    Sha256Digest,
)
from calibration_tooling.contracts.parser import (
    ACTIVE_OUTPUT_SCHEMA_VERSION,
    CanonicalCalibrationOutputParser,
)
from calibration_tooling.contracts.policy import DurableCalibrationPolicy
from calibration_tooling.runtime.authorization import (
    ExecutionAuthorization,
    OneShotAuthorizationGuard,
)
from calibration_tooling.runtime.budget import ApprovedBudget, BudgetGuard
from calibration_tooling.runtime.ledger import InMemoryCallLedger
from calibration_tooling.runtime.runner import CanonicalCalibrationRunner

MATRIX = Sha256Digest("d" * 64)


class FakeTransport:
    def __init__(self, payloads: dict[CallRef, dict[str, object]]) -> None:
        self._payloads = payloads
        self.calls: list[CallRef] = []

    def invoke(self, spec: CalibrationObservationSpec) -> RawProviderResponse:
        self.calls.append(spec.call_ref)
        return RawProviderResponse(
            spec.call_ref,
            json.dumps(self._payloads[spec.call_ref]),
            Decimal("0.001000"),
            True,
        )


class FailingTransport:
    def __init__(self) -> None:
        self.call_count = 0

    def invoke(self, spec: CalibrationObservationSpec) -> RawProviderResponse:
        self.call_count += 1
        raise OSError(spec.call_ref.value)


def _specs() -> tuple[AbsoluteObservationSpec, PairwiseObservationSpec]:
    return (
        AbsoluteObservationSpec(
            CALIBRATION_SCHEMA_V1,
            CallRef("call.absolute"),
            CriterionRef("criterion.clarity"),
            ProjectionRef("projection.strong"),
            Decimal("0.010000"),
        ),
        PairwiseObservationSpec(
            CALIBRATION_SCHEMA_V1,
            CallRef("call.pairwise"),
            CriterionRef("criterion.clarity"),
            ProjectionRef("projection.strong"),
            ProjectionRef("projection.mixed"),
            Decimal("0.010000"),
        ),
    )


def _plan(observations: tuple[CalibrationObservationSpec, ...]) -> CalibrationPlan:
    return CalibrationPlan(
        CALIBRATION_SCHEMA_V1,
        RunRef("run.integration"),
        MATRIX,
        observations,
    )


def _authorization(plan: CalibrationPlan, ref: str) -> ExecutionAuthorization:
    calls = tuple(spec.call_ref for spec in plan.observations)
    return ExecutionAuthorization(
        CALIBRATION_SCHEMA_V1,
        AuthorizationRef(ref),
        MATRIX,
        calls,
        len(calls),
    )


def _runner(
    transport: FakeTransport | FailingTransport,
    ledger: InMemoryCallLedger,
    authorization_guard: OneShotAuthorizationGuard | None = None,
) -> CanonicalCalibrationRunner:
    service = CalibrationService(transport, CanonicalCalibrationOutputParser())
    return CanonicalCalibrationRunner(
        service,
        authorization_guard or OneShotAuthorizationGuard(),
        BudgetGuard(),
        ledger,
    )


def test_unique_runner_dispatches_absolute_and_pairwise_once_in_plan_order() -> None:
    absolute, pairwise = _specs()
    plan = _plan((absolute, pairwise))
    transport = FakeTransport(
        {
            absolute.call_ref: {
                "schema_version": ACTIVE_OUTPUT_SCHEMA_VERSION,
                "call_ref": absolute.call_ref.value,
                "kind": "ABSOLUTE",
                "status": "SCORED",
                "score_level": 4,
            },
            pairwise.call_ref: {
                "schema_version": ACTIVE_OUTPUT_SCHEMA_VERSION,
                "call_ref": pairwise.call_ref.value,
                "kind": "PAIRWISE",
                "decision": "A_BETTER",
            },
        }
    )
    ledger = InMemoryCallLedger()
    output = _runner(transport, ledger).run(
        plan,
        _authorization(plan, "auth.success"),
        ApprovedBudget(CALIBRATION_SCHEMA_V1, Decimal("0.020000"), 2),
        DurableCalibrationPolicy(),
    )
    assert transport.calls == [absolute.call_ref, pairwise.call_ref]
    assert output.results == (
        AbsoluteObservationResult(absolute.call_ref, AbsoluteScoreStatus.SCORED, 4),
        PairwiseObservationResult(pairwise.call_ref, PairwiseDecision.A_BETTER),
    )
    assert output.measured_cost_usd == Decimal("0.002000")
    assert all(record.state is CallExecutionState.COMPLETED for record in ledger.snapshot())


def test_parser_failure_stops_before_the_next_call_and_has_no_retry() -> None:
    absolute, pairwise = _specs()
    plan = _plan((absolute, pairwise))
    transport = FakeTransport(
        {
            absolute.call_ref: {"invalid": "payload"},
            pairwise.call_ref: {
                "schema_version": ACTIVE_OUTPUT_SCHEMA_VERSION,
                "call_ref": pairwise.call_ref.value,
                "kind": "PAIRWISE",
                "decision": "A_BETTER",
            },
        }
    )
    ledger = InMemoryCallLedger()
    with pytest.raises(CalibrationContractError) as captured:
        _runner(transport, ledger).run(
            plan,
            _authorization(plan, "auth.parser-failure"),
            ApprovedBudget(CALIBRATION_SCHEMA_V1, Decimal("0.020000"), 2),
            DurableCalibrationPolicy(),
        )
    assert captured.value.code is CalibrationErrorCode.INVALID_PAYLOAD
    assert transport.calls == [absolute.call_ref]
    assert ledger.snapshot()[0].state is CallExecutionState.FAILED


def test_unknown_transport_failure_leaves_ambiguous_started_record() -> None:
    absolute, _ = _specs()
    plan = _plan((absolute,))
    transport = FailingTransport()
    ledger = InMemoryCallLedger()
    with pytest.raises(CalibrationExecutionError) as captured:
        _runner(transport, ledger).run(
            plan,
            _authorization(plan, "auth.transport-failure"),
            ApprovedBudget(CALIBRATION_SCHEMA_V1, Decimal("0.010000"), 1),
            DurableCalibrationPolicy(),
        )
    assert captured.value.code is CalibrationErrorCode.PROVIDER_UNAVAILABLE
    assert transport.call_count == 1
    assert ledger.snapshot()[0].state is CallExecutionState.STARTED

    with pytest.raises(CalibrationExecutionError) as captured:
        _runner(transport, ledger).run(
            plan,
            _authorization(plan, "auth.new-after-ambiguous"),
            ApprovedBudget(CALIBRATION_SCHEMA_V1, Decimal("0.010000"), 1),
            DurableCalibrationPolicy(),
        )
    assert captured.value.code is CalibrationErrorCode.LEDGER_AMBIGUOUS
    assert transport.call_count == 1


def test_budget_failure_occurs_before_authorization_consumption_or_transport() -> None:
    absolute, _ = _specs()
    plan = _plan((absolute,))
    transport = FakeTransport({})
    ledger = InMemoryCallLedger()
    authorization_guard = OneShotAuthorizationGuard()
    authorization = _authorization(plan, "auth.budget-failure")
    with pytest.raises(CalibrationExecutionError) as captured:
        _runner(transport, ledger, authorization_guard).run(
            plan,
            authorization,
            ApprovedBudget(CALIBRATION_SCHEMA_V1, Decimal("0.009999"), 1),
            DurableCalibrationPolicy(),
        )
    assert captured.value.code is CalibrationErrorCode.BUDGET_EXCEEDED
    assert not authorization_guard.is_consumed(authorization.authorization_ref)
    assert transport.calls == []
    assert ledger.snapshot() == ()


def test_authorization_is_one_shot_even_after_success() -> None:
    absolute, _ = _specs()
    plan = _plan((absolute,))
    transport = FakeTransport(
        {
            absolute.call_ref: {
                "schema_version": ACTIVE_OUTPUT_SCHEMA_VERSION,
                "call_ref": absolute.call_ref.value,
                "kind": "ABSOLUTE",
                "status": "SCORED",
                "score_level": 4,
            }
        }
    )
    guard = OneShotAuthorizationGuard()
    authorization = _authorization(plan, "auth.one-shot")
    runner = _runner(transport, InMemoryCallLedger(), guard)
    budget = ApprovedBudget(CALIBRATION_SCHEMA_V1, Decimal("0.010000"), 1)
    runner.run(plan, authorization, budget, DurableCalibrationPolicy())
    with pytest.raises(CalibrationExecutionError) as captured:
        runner.run(plan, authorization, budget, DurableCalibrationPolicy())
    assert captured.value.code is CalibrationErrorCode.AUTHORIZATION_CONSUMED
    assert transport.calls == [absolute.call_ref]
