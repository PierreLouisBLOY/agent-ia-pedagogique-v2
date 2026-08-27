from __future__ import annotations

from dataclasses import dataclass

from backend.agent_runtime.contracts import (
    SpanKind,
    SpanStatus,
    StepKind,
    StepSpec,
    TraceContext,
)
from backend.agent_runtime.observability.runtime_context import (
    PendingObservationSpan,
    RuntimeObservabilityContext,
)
from backend.agent_runtime.observability.runtime_emitter import RuntimeObservationEmitter
from backend.agent_runtime.observability.span_catalog import SpanCode
from backend.agent_runtime.orchestration.coordination import CoordinationDecision
from backend.agent_runtime.recovery.controller import (
    RecoveryCycleResult,
    RecoveryRuntimeController,
)
from backend.agent_runtime.recovery.coordinator import (
    RecoveryCoordinator,
    RecoveryDecisionResult,
)
from backend.agent_runtime.runtime.execution import (
    PlanExecutor,
    PreLaunchDecision,
    PreLaunchDisposition,
    PreLaunchGuard,
    StepExecutionResult,
    StepRunner,
)
from backend.agent_runtime.runtime.planning import Plan
from backend.agent_runtime.runtime.state import RunState, StepRuntimeStatus
from backend.shared_kernel.correlation import CorrelationId
from backend.shared_kernel.time import Instant

_GATE_CAPABILITY_ID = "CAP-A02"


@dataclass(frozen=True, slots=True)
class ObservedPreLaunchGuard:
    """Observe one canonical prelaunch call without recalling its sources."""

    inner: PreLaunchGuard
    observability: RuntimeObservationEmitter
    context: RuntimeObservabilityContext

    def __post_init__(self) -> None:
        if not isinstance(self.inner, PreLaunchGuard):
            raise TypeError("inner must implement PreLaunchGuard")
        _require_observability(self.observability, self.context)

    def check(
        self,
        *,
        plan: Plan,
        step: StepSpec,
        run_state: RunState,
        now: Instant,
    ) -> PreLaunchDecision:
        parent = self.context.current
        prelaunch = self.observability.begin_span(parent)
        previous = _activate_context(self.context, prelaunch)
        gate = (
            self.observability.begin_span(self.context.current)
            if _uses_gate(step)
            else None
        )
        decision: PreLaunchDecision | None = None
        try:
            decision = self.inner.check(
                plan=plan,
                step=step,
                run_state=run_state,
                now=now,
            )
            return decision
        finally:
            status = _prelaunch_status(decision)
            attributes = {"step_kind": _step_kind_value(step)}
            if isinstance(decision, PreLaunchDecision):
                attributes["prelaunch_disposition"] = decision.disposition.value
            if gate is not None:
                self.observability.finish_span(
                    gate,
                    code=SpanCode.GATE_EVALUATION,
                    kind=SpanKind.GATE,
                    status=status,
                    correlation_id=run_state.correlation_id,
                    run_id=plan.run_id,
                    step_id=_step_id(step),
                    attributes=attributes,
                )
            self.observability.finish_span(
                prelaunch,
                code=SpanCode.ROUTING_PRELAUNCH,
                kind=SpanKind.RUNTIME,
                status=status,
                correlation_id=run_state.correlation_id,
                run_id=plan.run_id,
                step_id=_step_id(step),
                attributes=attributes,
            )
            _restore_context(self.context, previous)


@dataclass(frozen=True, slots=True)
class ObservedStepRunner:
    """Observe one launched step and its route without changing its invocation."""

    inner: StepRunner
    observability: RuntimeObservationEmitter
    context: RuntimeObservabilityContext

    def __post_init__(self) -> None:
        if not isinstance(self.inner, StepRunner):
            raise TypeError("inner must implement StepRunner")
        _require_observability(self.observability, self.context)

    def run(
        self,
        *,
        plan: Plan,
        step: StepSpec,
        run_state: RunState,
        attempt: int,
        now: Instant,
    ) -> StepExecutionResult:
        parent = self.context.current
        runtime_step = self.observability.begin_span(parent)
        previous = _activate_context(self.context, runtime_step)
        route = _route_span(_step_kind(step))
        route_span = (
            self.observability.begin_span(self.context.current)
            if route is not None
            else None
        )
        result: StepExecutionResult | None = None
        try:
            result = self.inner.run(
                plan=plan,
                step=step,
                run_state=run_state,
                attempt=attempt,
                now=now,
            )
            if isinstance(result, StepExecutionResult) and result.error is not None:
                self.observability.observe_error(
                    result.error,
                    correlation_id=run_state.correlation_id,
                    run_id=plan.run_id,
                    trace_context=(
                        runtime_step.trace_context
                        if runtime_step is not None
                        else self.context.current
                    ),
                )
            return result
        finally:
            status = _step_status(result)
            attributes: dict[str, object] = {
                "attempt": attempt,
                "step_kind": _step_kind_value(step),
            }
            if isinstance(result, StepExecutionResult):
                attributes["terminal_step_status"] = result.status.value
            if route is not None:
                code, kind = route
                self.observability.finish_span(
                    route_span,
                    code=code,
                    kind=kind,
                    status=status,
                    correlation_id=run_state.correlation_id,
                    run_id=plan.run_id,
                    step_id=_step_id(step),
                    attributes=attributes,
                )
            self.observability.finish_span(
                runtime_step,
                code=SpanCode.RUNTIME_STEP,
                kind=SpanKind.RUNTIME,
                status=status,
                correlation_id=run_state.correlation_id,
                run_id=plan.run_id,
                step_id=_step_id(step),
                attributes=attributes,
            )
            _restore_context(self.context, previous)


@dataclass(frozen=True, slots=True, kw_only=True)
class ObservedRecoveryCoordinator(RecoveryCoordinator):
    """RecoveryCoordinator subtype adding observation after canonical decisions."""

    observability: RuntimeObservationEmitter
    observability_context: RuntimeObservabilityContext

    def __post_init__(self) -> None:
        RecoveryCoordinator.__post_init__(self)
        _require_observability(self.observability, self.observability_context)

    @classmethod
    def from_coordinator(
        cls,
        inner: RecoveryCoordinator,
        *,
        observability: RuntimeObservationEmitter,
        context: RuntimeObservabilityContext,
    ) -> ObservedRecoveryCoordinator:
        if not isinstance(inner, RecoveryCoordinator):
            raise TypeError("inner must be a RecoveryCoordinator")
        return cls(
            authority_guard=inner.authority_guard,
            routing_resolver=inner.routing_resolver,
            recovery_resolver=inner.recovery_resolver,
            reference_resolver=inner.reference_resolver,
            ledger=inner.ledger,
            budget_port=inner.budget_port,
            snapshot_store=inner.snapshot_store,
            reconciliation_engine=inner.reconciliation_engine,
            circuit_engine=inner.circuit_engine,
            tool_registry=inner.tool_registry,
            use_case_registry=inner.use_case_registry,
            replay_guard=inner.replay_guard,
            retry_policy=inner.retry_policy,
            budget_policy=inner.budget_policy,
            idempotency_policy=inner.idempotency_policy,
            observability=observability,
            observability_context=context,
        )

    def recover(
        self,
        *,
        plan: Plan,
        coordination_decision: CoordinationDecision,
        now: Instant,
    ) -> RecoveryDecisionResult:
        parent = self.observability_context.current
        pending = self.observability.begin_span(parent)
        previous = _activate_context(self.observability_context, pending)
        result: RecoveryDecisionResult | None = None
        try:
            result = RecoveryCoordinator.recover(
                self,
                plan=plan,
                coordination_decision=coordination_decision,
                now=now,
            )
            return result
        finally:
            status = SpanStatus.OK if result is not None else SpanStatus.ERROR
            attributes: dict[str, object] = {}
            if result is not None:
                attributes["recovery_action"] = result.recovery_action.value
                trace_context = (
                    pending.trace_context if pending is not None else parent
                )
                self._observe_recovery_facts(
                    result,
                    trace_context=trace_context,
                    run_id=plan.run_id,
                    correlation_id=coordination_decision.run_state.correlation_id,
                )
            self.observability.finish_span(
                pending,
                code=SpanCode.RECOVERY_CYCLE,
                kind=SpanKind.RECOVERY,
                status=status,
                correlation_id=coordination_decision.run_state.correlation_id,
                run_id=plan.run_id,
                attributes=attributes,
            )
            _restore_context(self.observability_context, previous)

    def _observe_recovery_facts(
        self,
        result: RecoveryDecisionResult,
        *,
        trace_context: TraceContext,
        run_id: str,
        correlation_id: CorrelationId,
    ) -> None:
        try:
            self.observability.observe_recovery_decision(
                result,
                trace_context=trace_context,
            )
        except Exception:
            pass
        if result.reconciliation_result is not None:
            self._decision_span(
                SpanCode.RECOVERY_RECONCILIATION,
                "reconciliation_disposition",
                result.reconciliation_result.disposition.value,
                run_id=run_id,
                correlation_id=correlation_id,
            )
        if result.retry_decision is not None:
            self._decision_span(
                SpanCode.RECOVERY_RETRY,
                "retry_disposition",
                result.retry_decision.disposition.value,
                run_id=run_id,
                correlation_id=correlation_id,
            )

    def _decision_span(
        self,
        code: SpanCode,
        key: str,
        value: str,
        *,
        run_id: str,
        correlation_id: CorrelationId,
    ) -> None:
        pending = self.observability.begin_span(self.observability_context.current)
        self.observability.finish_span(
            pending,
            code=code,
            kind=SpanKind.RECOVERY,
            status=SpanStatus.OK,
            correlation_id=correlation_id,
            run_id=run_id,
            attributes={key: value},
        )

@dataclass(frozen=True, slots=True)
class ObservedRecoveryRuntimeController:
    """Top-level runtime cycle wrapper; delivery and flush remain caller-owned."""

    inner: RecoveryRuntimeController
    observability: RuntimeObservationEmitter
    context: RuntimeObservabilityContext

    def __post_init__(self) -> None:
        if not isinstance(self.inner, RecoveryRuntimeController):
            raise TypeError("inner must be a RecoveryRuntimeController")
        _require_observability(self.observability, self.context)

    def execute_cycle(
        self,
        *,
        plan: Plan,
        run_state: RunState,
        now: Instant,
    ) -> RecoveryCycleResult:
        pending = self.observability.begin_span(self.context.current)
        previous = _activate_context(self.context, pending)
        result: RecoveryCycleResult | None = None
        try:
            result = self.inner.execute_cycle(plan=plan, run_state=run_state, now=now)
            trace_context = (
                pending.trace_context if pending is not None else self.context.current
            )
            for event in result.execution_cycle.security_events:
                self.observability.observe_security_event(
                    event,
                    trace_context=trace_context,
                )
            for directive in result.execution_cycle.directives:
                self.observability.observe_directive(
                    directive,
                    correlation_id=result.run_state.correlation_id,
                    run_id=plan.run_id,
                    trace_context=trace_context,
                )
            return result
        finally:
            self.observability.finish_span(
                pending,
                code=SpanCode.RUNTIME_CYCLE,
                kind=SpanKind.RUNTIME,
                status=SpanStatus.OK if result is not None else SpanStatus.ERROR,
                correlation_id=run_state.correlation_id,
                run_id=plan.run_id,
            )
            _restore_context(self.context, previous)


def instrument_plan_executor(
    executor: PlanExecutor,
    *,
    observability: RuntimeObservationEmitter,
    context: RuntimeObservabilityContext,
) -> PlanExecutor:
    if not isinstance(executor, PlanExecutor):
        raise TypeError("executor must be a PlanExecutor")
    return PlanExecutor(
        scheduler=executor.scheduler,
        prelaunch_guard=ObservedPreLaunchGuard(
            executor.prelaunch_guard,
            observability,
            context,
        ),
        runner=ObservedStepRunner(executor.runner, observability, context),
    )


def instrument_recovery_runtime_controller(
    controller: RecoveryRuntimeController,
    *,
    observability: RuntimeObservationEmitter,
    context: RuntimeObservabilityContext,
) -> ObservedRecoveryRuntimeController:
    if not isinstance(controller, RecoveryRuntimeController):
        raise TypeError("controller must be a RecoveryRuntimeController")
    recovery = ObservedRecoveryCoordinator.from_coordinator(
        controller.recovery_coordinator,
        observability=observability,
        context=context,
    )
    inner = RecoveryRuntimeController(
        executor=instrument_plan_executor(
            controller.executor,
            observability=observability,
            context=context,
        ),
        orchestration_coordinator=controller.orchestration_coordinator,
        recovery_coordinator=recovery,
    )
    return ObservedRecoveryRuntimeController(inner, observability, context)


def _route_span(kind: StepKind) -> tuple[SpanCode, SpanKind] | None:
    return {
        StepKind.TOOL: (SpanCode.TOOL_CALL, SpanKind.TOOL),
        StepKind.USE_CASE: (SpanCode.APPLICATION_CALL, SpanKind.APPLICATION),
        StepKind.AGENT: (SpanCode.AGENT_INVOCATION, SpanKind.AGENT),
        StepKind.GATE: (SpanCode.GATE_EVALUATION, SpanKind.GATE),
    }.get(kind)


def _prelaunch_status(decision: object) -> SpanStatus:
    if not isinstance(decision, PreLaunchDecision):
        return SpanStatus.ERROR
    if decision.disposition is PreLaunchDisposition.ALLOW:
        return SpanStatus.OK
    if decision.disposition is PreLaunchDisposition.DENY:
        return SpanStatus.CANCELLED
    return SpanStatus.UNSET


def _step_status(result: object) -> SpanStatus:
    if not isinstance(result, StepExecutionResult):
        return SpanStatus.ERROR
    if result.status is StepRuntimeStatus.SUCCEEDED:
        return SpanStatus.OK
    if result.status is StepRuntimeStatus.CANCELLED:
        return SpanStatus.CANCELLED
    if result.status is StepRuntimeStatus.PARTIAL:
        return SpanStatus.UNSET
    return SpanStatus.ERROR


def _uses_gate(step: StepSpec) -> bool:
    kind = _step_kind(step)
    if kind is StepKind.GATE:
        return True
    if kind is not StepKind.USE_CASE:
        return False
    capability = getattr(step, "capability_id", None)
    return getattr(capability, "value", None) == _GATE_CAPABILITY_ID


def _step_kind(step: StepSpec) -> StepKind:
    return step.kind


def _step_kind_value(step: StepSpec) -> str:
    return step.kind.value


def _step_id(step: StepSpec) -> str:
    return step.step_id


def _require_observability(
    observability: RuntimeObservationEmitter,
    context: RuntimeObservabilityContext,
) -> None:
    if not isinstance(observability, RuntimeObservationEmitter):
        raise TypeError("observability must be a RuntimeObservationEmitter")
    if not isinstance(context, RuntimeObservabilityContext):
        raise TypeError("context must be a RuntimeObservabilityContext")


def _activate_context(
    context: RuntimeObservabilityContext,
    pending: PendingObservationSpan | None,
) -> TraceContext | None:
    if pending is None:
        return None
    try:
        return context.activate(pending.trace_context)
    except Exception:
        return None


def _restore_context(
    context: RuntimeObservabilityContext,
    previous: TraceContext | None,
) -> None:
    if previous is None:
        return
    try:
        context.restore(previous)
    except Exception:
        return
