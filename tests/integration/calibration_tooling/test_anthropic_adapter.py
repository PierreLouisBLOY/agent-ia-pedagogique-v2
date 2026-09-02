from __future__ import annotations

import json
from decimal import Decimal

from backend.infrastructure.config.secrets.provider import ProviderSecretValue
from calibration_tooling.adapters.anthropic.contracts import (
    AnthropicEffort,
    AnthropicMessageResponse,
    AnthropicProjectionPayload,
    AnthropicScoringRequest,
    AnthropicStopReason,
    AnthropicThinkingMode,
    AnthropicTokenPricing,
    AnthropicUsage,
    ResolvedAnthropicConfiguration,
)
from calibration_tooling.adapters.anthropic.scorer import AnthropicCalibrationScorer
from calibration_tooling.adapters.anthropic.transport import AnthropicMessagesTransport
from calibration_tooling.application.service import CalibrationService
from calibration_tooling.contracts.models import (
    CALIBRATION_SCHEMA_V1,
    AbsoluteObservationResult,
    AbsoluteObservationSpec,
    AbsoluteScoreStatus,
    AuthorizationRef,
    CalibrationPlan,
    CallExecutionState,
    CallRef,
    CriterionRef,
    ProjectionRef,
    RunRef,
    Sha256Digest,
)
from calibration_tooling.contracts.parser import CanonicalCalibrationOutputParser
from calibration_tooling.contracts.policy import DurableCalibrationPolicy
from calibration_tooling.runtime.authorization import (
    ExecutionAuthorization,
    OneShotAuthorizationGuard,
)
from calibration_tooling.runtime.budget import ApprovedBudget, BudgetGuard
from calibration_tooling.runtime.ledger import InMemoryCallLedger
from calibration_tooling.runtime.runner import CanonicalCalibrationRunner


class SingleProjectionSource:
    def __init__(self, payload: AnthropicProjectionPayload) -> None:
        self.payload = payload

    def load(self, call_ref: CallRef) -> AnthropicProjectionPayload:
        if call_ref != self.payload.call_ref:
            raise KeyError(call_ref.value)
        return self.payload


class SuccessfulInjectedClient:
    def __init__(self, call_ref: CallRef) -> None:
        self.call_ref = call_ref
        self.call_count = 0

    def create(
        self,
        *,
        api_key: str,
        timeout_seconds: float,
        request: AnthropicScoringRequest,
    ) -> AnthropicMessageResponse:
        self.call_count += 1
        assert api_key == "synthetic-test-secret"
        assert timeout_seconds == 30.0
        assert request.max_tokens == 2_048
        return AnthropicMessageResponse(
            (
                json.dumps(
                    {
                        "schema_version": "calibration-output.v1",
                        "call_ref": self.call_ref.value,
                        "kind": "ABSOLUTE",
                        "status": "SCORED",
                        "score_level": 4,
                    }
                ),
            ),
            AnthropicStopReason.END_TURN,
            AnthropicUsage(100, 0, 0, 20),
            thinking_block_count=1,
        )


def test_b02_runner_reaches_active_anthropic_adapter_once_with_injected_client() -> None:
    matrix = Sha256Digest("b" * 64)
    call_ref = CallRef("call.anthropic.absolute")
    spec = AbsoluteObservationSpec(
        CALIBRATION_SCHEMA_V1,
        call_ref,
        CriterionRef("criterion.clarity"),
        ProjectionRef("projection.strong"),
        Decimal("0.055600"),
    )
    plan = CalibrationPlan(
        CALIBRATION_SCHEMA_V1,
        RunRef("run.anthropic.offline"),
        matrix,
        (spec,),
    )
    configuration = ResolvedAnthropicConfiguration(
        model="claude-sonnet-5",
        max_tokens=2_048,
        timeout_milliseconds=30_000,
        pricing=AnthropicTokenPricing(
            Decimal("3"), Decimal("3.75"), Decimal("0.30"), Decimal("15")
        ),
        thinking_mode=AnthropicThinkingMode.ADAPTIVE,
        effort=AnthropicEffort.LOW,
    )
    client = SuccessfulInjectedClient(call_ref)
    transport = AnthropicMessagesTransport(
        client=client,
        secret=ProviderSecretValue("synthetic-test-secret"),
        timeout_milliseconds=configuration.timeout_milliseconds,
    )
    service = CalibrationService(
        AnthropicCalibrationScorer(
            configuration=configuration,
            projection_source=SingleProjectionSource(
                AnthropicProjectionPayload(call_ref, '{"content":"synthetic strong"}')
            ),
            transport=transport,
        ),
        CanonicalCalibrationOutputParser(),
    )
    ledger = InMemoryCallLedger()
    output = CanonicalCalibrationRunner(
        service,
        OneShotAuthorizationGuard(),
        BudgetGuard(),
        ledger,
    ).run(
        plan,
        ExecutionAuthorization(
            CALIBRATION_SCHEMA_V1,
            AuthorizationRef("auth.anthropic.offline"),
            matrix,
            (call_ref,),
            1,
        ),
        ApprovedBudget(CALIBRATION_SCHEMA_V1, Decimal("0.055600"), 1),
        DurableCalibrationPolicy(),
    )
    assert output.results == (
        AbsoluteObservationResult(call_ref, AbsoluteScoreStatus.SCORED, 4),
    )
    assert output.measured_cost_usd == Decimal("0.000600")
    assert client.call_count == 1
    assert ledger.snapshot()[0].state is CallExecutionState.COMPLETED
