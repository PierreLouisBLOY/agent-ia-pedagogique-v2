from __future__ import annotations

import json
from decimal import Decimal

from calibration_tooling.application.service import CalibrationService
from calibration_tooling.contracts.models import (
    CALIBRATION_SCHEMA_V1,
    AbsoluteObservationResult,
    AbsoluteObservationSpec,
    AbsoluteScoreStatus,
    AuthorizationRef,
    CalibrationObservationSpec,
    CalibrationPlan,
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


class ApprovedSnapshotTransport:
    calls: list[CallRef]

    def __init__(self) -> None:
        self.calls = []

    def invoke(self, spec: CalibrationObservationSpec) -> RawProviderResponse:
        self.calls.append(spec.call_ref)
        if type(spec) is AbsoluteObservationSpec:
            payload: dict[str, object] = {
                "schema_version": ACTIVE_OUTPUT_SCHEMA_VERSION,
                "call_ref": spec.call_ref.value,
                "kind": "ABSOLUTE",
                "status": "SCORED",
                "score_level": 4,
            }
        else:
            payload = {
                "schema_version": ACTIVE_OUTPUT_SCHEMA_VERSION,
                "call_ref": spec.call_ref.value,
                "kind": "PAIRWISE",
                "decision": "A_BETTER",
            }
        return RawProviderResponse(
            spec.call_ref,
            json.dumps(payload),
            Decimal("0.001000"),
            True,
        )


def test_active_runner_preserves_approved_absolute_pairwise_parity() -> None:
    matrix = Sha256Digest("e" * 64)
    absolute = AbsoluteObservationSpec(
        CALIBRATION_SCHEMA_V1,
        CallRef("call.parity.absolute"),
        CriterionRef("criterion.clarity"),
        ProjectionRef("projection.strong"),
        Decimal("0.010000"),
    )
    pairwise = PairwiseObservationSpec(
        CALIBRATION_SCHEMA_V1,
        CallRef("call.parity.pairwise"),
        CriterionRef("criterion.clarity"),
        ProjectionRef("projection.strong"),
        ProjectionRef("projection.mixed"),
        Decimal("0.010000"),
    )
    plan = CalibrationPlan(
        CALIBRATION_SCHEMA_V1,
        RunRef("run.parity"),
        matrix,
        (absolute, pairwise),
    )
    transport = ApprovedSnapshotTransport()
    runner = CanonicalCalibrationRunner(
        CalibrationService(transport, CanonicalCalibrationOutputParser()),
        OneShotAuthorizationGuard(),
        BudgetGuard(),
        InMemoryCallLedger(),
    )

    output = runner.run(
        plan,
        ExecutionAuthorization(
            CALIBRATION_SCHEMA_V1,
            AuthorizationRef("auth.parity"),
            matrix,
            (absolute.call_ref, pairwise.call_ref),
            2,
        ),
        ApprovedBudget(CALIBRATION_SCHEMA_V1, Decimal("0.020000"), 2),
        DurableCalibrationPolicy(),
    )

    assert transport.calls == [absolute.call_ref, pairwise.call_ref]
    assert output.results == (
        AbsoluteObservationResult(
            absolute.call_ref, AbsoluteScoreStatus.SCORED, 4
        ),
        PairwiseObservationResult(pairwise.call_ref, PairwiseDecision.A_BETTER),
    )
    assert output.measured_cost_usd == Decimal("0.002000")
