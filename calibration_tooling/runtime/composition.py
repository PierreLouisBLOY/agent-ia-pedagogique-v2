"""The sole explicit assembly point for the active calibration provider."""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal

from backend.infrastructure.config.secrets.provider import ProviderSecretValue
from calibration_tooling.adapters.anthropic.contracts import (
    AnthropicMessagesClient,
    AnthropicProjectionSource,
)
from calibration_tooling.adapters.anthropic.scorer import AnthropicCalibrationScorer
from calibration_tooling.adapters.anthropic.transport import AnthropicMessagesTransport
from calibration_tooling.application.ports import CallLedgerPort, MonotonicClockPort
from calibration_tooling.application.service import CalibrationService
from calibration_tooling.contracts.errors import (
    CalibrationError,
    CalibrationErrorCode,
    fail_execution,
)
from calibration_tooling.contracts.models import CalibrationPlan, CalibrationRunOutput
from calibration_tooling.contracts.parser import CanonicalCalibrationOutputParser
from calibration_tooling.contracts.policy import DurableCalibrationPolicy
from calibration_tooling.observability.events import (
    CalibrationEventState,
    CalibrationTelemetryEvent,
    CalibrationTelemetrySink,
    NullCalibrationTelemetrySink,
)
from calibration_tooling.runtime.authorization import (
    ExecutionAuthorization,
    OneShotAuthorizationGuard,
)
from calibration_tooling.runtime.budget import ApprovedBudget, BudgetGuard
from calibration_tooling.runtime.configuration import (
    CalibrationRuntimeConfiguration,
    require_enabled_anthropic_configuration,
)
from calibration_tooling.runtime.runner import CanonicalCalibrationRunner


@dataclass(frozen=True, slots=True)
class AnthropicRuntimeDependencies:
    client: AnthropicMessagesClient = field(repr=False)
    secret: ProviderSecretValue | None = field(repr=False)
    projection_source: AnthropicProjectionSource = field(repr=False)
    ledger: CallLedgerPort = field(repr=False)
    clock: MonotonicClockPort = field(repr=False)


class CalibrationRuntime:
    """Fail-closed runtime wrapper around the one active calibration runner."""

    __slots__ = ("_clock", "_configuration", "_runner", "_telemetry")

    def __init__(
        self,
        *,
        configuration: CalibrationRuntimeConfiguration,
        runner: CanonicalCalibrationRunner | None,
        clock: MonotonicClockPort | None,
        telemetry: CalibrationTelemetrySink,
    ) -> None:
        if type(configuration) is not CalibrationRuntimeConfiguration:
            raise TypeError("configuration must be CalibrationRuntimeConfiguration")
        self._configuration = configuration
        self._runner = runner
        self._clock = clock
        self._telemetry = telemetry

    def __repr__(self) -> str:
        return (
            "CalibrationRuntime("
            f"provider_code={self._configuration.provider_code.value!r}, "
            f"live_provider_enabled={self._configuration.live_provider_enabled!r})"
        )

    def run(
        self,
        plan: CalibrationPlan,
        authorization: ExecutionAuthorization,
        budget: ApprovedBudget,
        policy: DurableCalibrationPolicy,
    ) -> CalibrationRunOutput:
        if not self._configuration.live_provider_enabled:
            self._emit(
                _event(
                    configuration=self._configuration,
                    plan=plan,
                    state=CalibrationEventState.BLOCKED,
                    duration_milliseconds=0,
                    error_code=CalibrationErrorCode.PROVIDER_DISABLED,
                )
            )
            fail_execution(CalibrationErrorCode.PROVIDER_DISABLED)
        if self._runner is None or self._clock is None:
            fail_execution(CalibrationErrorCode.CONFIGURATION_INVALID)
        started = _required_clock_value(self._clock)
        self._emit(
            _event(
                configuration=self._configuration,
                plan=plan,
                state=CalibrationEventState.STARTED,
                duration_milliseconds=0,
            )
        )
        try:
            output = self._runner.run(plan, authorization, budget, policy)
        except CalibrationError as error:
            self._emit(
                _event(
                    configuration=self._configuration,
                    plan=plan,
                    state=CalibrationEventState.FAILED,
                    duration_milliseconds=_duration(self._clock, started),
                    error_code=error.code,
                )
            )
            raise
        except Exception:
            self._emit(
                _event(
                    configuration=self._configuration,
                    plan=plan,
                    state=CalibrationEventState.FAILED,
                    duration_milliseconds=_duration(self._clock, started),
                    error_code=CalibrationErrorCode.PROVIDER_UNAVAILABLE,
                )
            )
            fail_execution(CalibrationErrorCode.PROVIDER_UNAVAILABLE)
        self._emit(
            _event(
                configuration=self._configuration,
                plan=plan,
                state=CalibrationEventState.COMPLETED,
                duration_milliseconds=_duration(self._clock, started),
                measured_cost_usd=output.measured_cost_usd,
            )
        )
        return output

    def _emit(self, event: CalibrationTelemetryEvent) -> None:
        try:
            self._telemetry.emit(event)
        except Exception:
            return


def compose_calibration_runtime(
    *,
    configuration: CalibrationRuntimeConfiguration,
    dependencies: AnthropicRuntimeDependencies | None = None,
    telemetry: CalibrationTelemetrySink | None = None,
) -> CalibrationRuntime:
    if type(configuration) is not CalibrationRuntimeConfiguration:
        fail_execution(CalibrationErrorCode.CONFIGURATION_INVALID)
    selected_telemetry = (
        telemetry if telemetry is not None else NullCalibrationTelemetrySink()
    )
    if not configuration.live_provider_enabled:
        return CalibrationRuntime(
            configuration=configuration,
            runner=None,
            clock=None,
            telemetry=selected_telemetry,
        )
    anthropic = require_enabled_anthropic_configuration(configuration)
    if dependencies is None:
        fail_execution(CalibrationErrorCode.CONFIGURATION_INVALID)
    if dependencies.secret is None:
        fail_execution(CalibrationErrorCode.CREDENTIAL_UNAVAILABLE)
    transport = AnthropicMessagesTransport(
        client=dependencies.client,
        secret=dependencies.secret,
        timeout_milliseconds=anthropic.timeout_milliseconds,
    )
    scorer = AnthropicCalibrationScorer(
        configuration=anthropic,
        projection_source=dependencies.projection_source,
        transport=transport,
    )
    service = CalibrationService(scorer, CanonicalCalibrationOutputParser())
    runner = CanonicalCalibrationRunner(
        service,
        OneShotAuthorizationGuard(),
        BudgetGuard(),
        dependencies.ledger,
    )
    return CalibrationRuntime(
        configuration=configuration,
        runner=runner,
        clock=dependencies.clock,
        telemetry=selected_telemetry,
    )


def _event(
    *,
    configuration: CalibrationRuntimeConfiguration,
    plan: CalibrationPlan,
    state: CalibrationEventState,
    duration_milliseconds: int,
    measured_cost_usd: Decimal | None = None,
    error_code: CalibrationErrorCode | None = None,
) -> CalibrationTelemetryEvent:
    if measured_cost_usd is not None and type(measured_cost_usd) is not Decimal:
        fail_execution(CalibrationErrorCode.CONFIGURATION_INVALID)
    model = (
        configuration.anthropic.model
        if configuration.anthropic is not None
        else "unconfigured"
    )
    return CalibrationTelemetryEvent(
        run_ref=plan.run_ref,
        provider_code=configuration.provider_code.value,
        model_code=model,
        state=state,
        duration_milliseconds=duration_milliseconds,
        measured_cost_usd=measured_cost_usd,
        error_code=error_code,
    )


def _required_clock_value(clock: MonotonicClockPort) -> int:
    try:
        value = clock.now_milliseconds()
    except Exception:
        fail_execution(CalibrationErrorCode.CONFIGURATION_INVALID)
    if type(value) is not int or value < 0:
        fail_execution(CalibrationErrorCode.CONFIGURATION_INVALID)
    return value


def _duration(clock: MonotonicClockPort, started: int) -> int:
    try:
        ended = clock.now_milliseconds()
    except Exception:
        return 0
    if type(ended) is not int or ended < started:
        return 0
    return min(ended - started, 604_800_000)
