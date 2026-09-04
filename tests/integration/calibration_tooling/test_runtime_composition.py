from __future__ import annotations

import json
from dataclasses import dataclass
from decimal import Decimal

import pytest

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
from calibration_tooling.contracts.errors import (
    CalibrationErrorCode,
    CalibrationExecutionError,
)
from calibration_tooling.contracts.models import (
    CALIBRATION_SCHEMA_V1,
    AbsoluteObservationResult,
    AbsoluteObservationSpec,
    AbsoluteScoreStatus,
    AuthorizationRef,
    CalibrationPlan,
    CallRef,
    CriterionRef,
    ProjectionRef,
    RunRef,
    Sha256Digest,
)
from calibration_tooling.contracts.policy import DurableCalibrationPolicy
from calibration_tooling.observability.events import (
    CalibrationEventState,
    CalibrationTelemetryEvent,
)
from calibration_tooling.runtime.authorization import ExecutionAuthorization
from calibration_tooling.runtime.budget import ApprovedBudget
from calibration_tooling.runtime.cli import (
    CalibrationCliExitCode,
    CalibrationCliInvocation,
    CalibrationCliReport,
    CalibrationCliStatus,
    main,
)
from calibration_tooling.runtime.composition import (
    AnthropicRuntimeDependencies,
    compose_calibration_runtime,
)
from calibration_tooling.runtime.configuration import CalibrationRuntimeConfiguration
from calibration_tooling.runtime.ledger import InMemoryCallLedger


class SingleProjectionSource:
    payload: AnthropicProjectionPayload

    def __init__(self, payload: AnthropicProjectionPayload) -> None:
        self.payload = payload

    def load(self, call_ref: CallRef) -> AnthropicProjectionPayload:
        if call_ref != self.payload.call_ref:
            raise KeyError(call_ref.value)
        return self.payload


class SuccessfulClient:
    call_ref: CallRef
    call_count: int

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
        assert request.model == "claude-sonnet-5"
        return AnthropicMessageResponse(
            text_blocks=(
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
            stop_reason=AnthropicStopReason.END_TURN,
            usage=AnthropicUsage(100, 0, 0, 20),
            thinking_block_count=1,
        )


class IncrementingClock:
    current: int

    def __init__(self) -> None:
        self.current = 100

    def now_milliseconds(self) -> int:
        self.current += 7
        return self.current


class RecordingTelemetrySink:
    events: list[CalibrationTelemetryEvent]

    def __init__(self) -> None:
        self.events = []

    def emit(self, event: CalibrationTelemetryEvent) -> None:
        self.events.append(event)


class RaisingTelemetrySink:
    def emit(self, event: CalibrationTelemetryEvent) -> None:
        del event
        raise RuntimeError("synthetic telemetry outage")


class ReportSink:
    reports: list[CalibrationCliReport]

    def __init__(self) -> None:
        self.reports = []

    def write(self, report: CalibrationCliReport) -> None:
        self.reports.append(report)


@dataclass(frozen=True, slots=True)
class Scenario:
    configuration: CalibrationRuntimeConfiguration
    dependencies: AnthropicRuntimeDependencies
    plan: CalibrationPlan
    authorization: ExecutionAuthorization
    budget: ApprovedBudget
    policy: DurableCalibrationPolicy
    client: SuccessfulClient
    ledger: InMemoryCallLedger
    telemetry: RecordingTelemetrySink


def _scenario() -> Scenario:
    matrix = Sha256Digest("b" * 64)
    call_ref = CallRef("call.composition.absolute")
    plan = CalibrationPlan(
        CALIBRATION_SCHEMA_V1,
        RunRef("run.composition.offline"),
        matrix,
        (
            AbsoluteObservationSpec(
                CALIBRATION_SCHEMA_V1,
                call_ref,
                CriterionRef("criterion.clarity"),
                ProjectionRef("projection.strong"),
                Decimal("0.055600"),
            ),
        ),
    )
    resolved = ResolvedAnthropicConfiguration(
        model="claude-sonnet-5",
        max_tokens=2_048,
        timeout_milliseconds=30_000,
        pricing=AnthropicTokenPricing(
            Decimal("3"), Decimal("3.75"), Decimal("0.30"), Decimal("15")
        ),
        thinking_mode=AnthropicThinkingMode.ADAPTIVE,
        effort=AnthropicEffort.LOW,
    )
    client = SuccessfulClient(call_ref)
    ledger = InMemoryCallLedger()
    telemetry = RecordingTelemetrySink()
    dependencies = AnthropicRuntimeDependencies(
        client=client,
        secret=ProviderSecretValue("synthetic-test-secret"),
        projection_source=SingleProjectionSource(
            AnthropicProjectionPayload(call_ref, '{"content":"synthetic strong"}')
        ),
        ledger=ledger,
        clock=IncrementingClock(),
    )
    return Scenario(
        configuration=CalibrationRuntimeConfiguration(
            live_provider_enabled=True,
            anthropic=resolved,
        ),
        dependencies=dependencies,
        plan=plan,
        authorization=ExecutionAuthorization(
            CALIBRATION_SCHEMA_V1,
            AuthorizationRef("auth.composition.offline"),
            matrix,
            (call_ref,),
            1,
        ),
        budget=ApprovedBudget(CALIBRATION_SCHEMA_V1, Decimal("0.055600"), 1),
        policy=DurableCalibrationPolicy(),
        client=client,
        ledger=ledger,
        telemetry=telemetry,
    )


def test_composed_runtime_reaches_injected_fake_client_once() -> None:
    scenario = _scenario()
    runtime = compose_calibration_runtime(
        configuration=scenario.configuration,
        dependencies=scenario.dependencies,
        telemetry=scenario.telemetry,
    )

    output = runtime.run(
        scenario.plan,
        scenario.authorization,
        scenario.budget,
        scenario.policy,
    )

    assert output.results == (
        AbsoluteObservationResult(
            scenario.plan.observations[0].call_ref,
            AbsoluteScoreStatus.SCORED,
            4,
        ),
    )
    assert output.measured_cost_usd == Decimal("0.000600")
    assert scenario.client.call_count == 1
    assert [event.state for event in scenario.telemetry.events] == [
        CalibrationEventState.STARTED,
        CalibrationEventState.STARTED,
        CalibrationEventState.COMPLETED,
        CalibrationEventState.COMPLETED,
    ]
    assert scenario.telemetry.events[-1].measured_cost_usd == Decimal("0.000600")
    call_events = [
        event for event in scenario.telemetry.events if event.call_ref is not None
    ]
    assert call_events[-1].input_tokens == 100
    assert call_events[-1].cached_input_tokens == 0
    assert call_events[-1].output_tokens == 20


def test_allowlist_and_budget_block_before_the_fake_client() -> None:
    allowlist_scenario = _scenario()
    wrong_authorization = ExecutionAuthorization(
        CALIBRATION_SCHEMA_V1,
        AuthorizationRef("auth.wrong-allowlist"),
        allowlist_scenario.plan.matrix_sha256,
        (CallRef("call.not-allowed"),),
        1,
    )
    runtime = compose_calibration_runtime(
        configuration=allowlist_scenario.configuration,
        dependencies=allowlist_scenario.dependencies,
        telemetry=allowlist_scenario.telemetry,
    )
    with pytest.raises(CalibrationExecutionError) as captured:
        runtime.run(
            allowlist_scenario.plan,
            wrong_authorization,
            allowlist_scenario.budget,
            allowlist_scenario.policy,
        )
    assert captured.value.code is CalibrationErrorCode.ALLOWLIST_MISMATCH
    assert allowlist_scenario.client.call_count == 0
    assert allowlist_scenario.ledger.snapshot() == ()

    budget_scenario = _scenario()
    runtime = compose_calibration_runtime(
        configuration=budget_scenario.configuration,
        dependencies=budget_scenario.dependencies,
        telemetry=budget_scenario.telemetry,
    )
    with pytest.raises(CalibrationExecutionError) as captured:
        runtime.run(
            budget_scenario.plan,
            budget_scenario.authorization,
            ApprovedBudget(CALIBRATION_SCHEMA_V1, Decimal("0.010000"), 1),
            budget_scenario.policy,
        )
    assert captured.value.code is CalibrationErrorCode.BUDGET_EXCEEDED
    assert budget_scenario.client.call_count == 0
    assert budget_scenario.ledger.snapshot() == ()


def test_ambiguous_ledger_blocks_before_the_fake_client() -> None:
    scenario = _scenario()
    scenario.ledger.reserve(scenario.plan.observations[0].call_ref)
    runtime = compose_calibration_runtime(
        configuration=scenario.configuration,
        dependencies=scenario.dependencies,
        telemetry=scenario.telemetry,
    )

    with pytest.raises(CalibrationExecutionError) as captured:
        runtime.run(
            scenario.plan,
            scenario.authorization,
            scenario.budget,
            scenario.policy,
        )

    assert captured.value.code is CalibrationErrorCode.LEDGER_AMBIGUOUS
    assert scenario.client.call_count == 0
    assert scenario.telemetry.events[-1].error_code is CalibrationErrorCode.LEDGER_AMBIGUOUS


def test_enabled_composition_requires_injected_dependencies_and_secret() -> None:
    scenario = _scenario()
    with pytest.raises(CalibrationExecutionError) as captured:
        compose_calibration_runtime(configuration=scenario.configuration)
    assert captured.value.code is CalibrationErrorCode.CONFIGURATION_INVALID

    without_secret = AnthropicRuntimeDependencies(
        client=scenario.dependencies.client,
        secret=None,
        projection_source=scenario.dependencies.projection_source,
        ledger=scenario.dependencies.ledger,
        clock=scenario.dependencies.clock,
    )
    with pytest.raises(CalibrationExecutionError) as captured:
        compose_calibration_runtime(
            configuration=scenario.configuration,
            dependencies=without_secret,
        )
    assert captured.value.code is CalibrationErrorCode.CREDENTIAL_UNAVAILABLE
    assert scenario.client.call_count == 0


def test_telemetry_failure_cannot_change_provider_outcome_or_retry() -> None:
    scenario = _scenario()
    runtime = compose_calibration_runtime(
        configuration=scenario.configuration,
        dependencies=scenario.dependencies,
        telemetry=RaisingTelemetrySink(),
    )

    output = runtime.run(
        scenario.plan,
        scenario.authorization,
        scenario.budget,
        scenario.policy,
    )

    assert output.measured_cost_usd == Decimal("0.000600")
    assert scenario.client.call_count == 1


def test_unique_cli_drives_the_composed_runtime_with_injected_state() -> None:
    scenario = _scenario()
    output = ReportSink()
    runtime = compose_calibration_runtime(
        configuration=scenario.configuration,
        dependencies=scenario.dependencies,
        telemetry=scenario.telemetry,
    )

    exit_code = main(
        ("run",),
        runtime=runtime,
        invocation=CalibrationCliInvocation(
            scenario.plan,
            scenario.authorization,
            scenario.budget,
            scenario.policy,
        ),
        output=output,
    )

    assert exit_code == int(CalibrationCliExitCode.SUCCESS)
    assert output.reports == [
        CalibrationCliReport(
            status=CalibrationCliStatus.COMPLETED,
            run_ref=scenario.plan.run_ref,
            measured_cost_usd=Decimal("0.000600"),
        )
    ]
    assert scenario.client.call_count == 1
