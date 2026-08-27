from __future__ import annotations

from dataclasses import dataclass, field, replace

from backend.agent_runtime.application_routing import (
    UseCaseRouter,
    UseCaseRoutingContext,
    UseCaseRoutingError,
    UseCaseRoutingErrorCode,
)
from backend.agent_runtime.contracts import (
    AGENT_CONTRACT_SCHEMA_V1_0,
    AgentResultStatus,
    EffectState,
    ErrorCategory,
    ErrorEnvelope,
    ErrorSeverity,
    ErrorSource,
    RecommendedAction,
    StepKind,
    StepSpec,
    StructuredContentSecurityAssessment,
    UseCaseResult,
)
from backend.agent_runtime.gates import GateEngine, GateResolutionDisposition
from backend.agent_runtime.runtime.execution import StepExecutionResult
from backend.agent_runtime.runtime.planning import Plan
from backend.agent_runtime.runtime.routing._validation import (
    validate_gate_binding,
    validate_request_identity,
    validate_runtime_context,
)
from backend.agent_runtime.runtime.routing.agent_router import AgentStepRouter
from backend.agent_runtime.runtime.routing.model import (
    ResolvedAgentInput,
    ResolvedToolInput,
    ResolvedUseCaseInput,
    RuntimeRoutingError,
    RuntimeRoutingErrorCode,
)
from backend.agent_runtime.runtime.routing.ports import (
    RuntimeControlStepRunnerPort,
    RuntimeRoutingResolverPort,
)
from backend.agent_runtime.runtime.state import RunState, StepRuntimeStatus
from backend.agent_runtime.security import (
    security_event_from_structured_assessment,
)
from backend.agent_runtime.security.runtime_composition import (
    RuntimeSecurityFailureStage,
    RuntimeSecurityViolation,
    SecurityRuntimeGuard,
)
from backend.agent_runtime.tools import ToolRouter, ToolRoutingError, ToolRoutingErrorCode
from backend.core_contracts.outcome import ApplicationOutcome, OutcomeStatus
from backend.shared_kernel.time import Instant

_CAP_A02 = "CAP-A02"
_PRE_EXECUTION_TOOL_ERRORS = frozenset(
    {
        ToolRoutingErrorCode.TOOL_NOT_ALLOWED,
        ToolRoutingErrorCode.TOOL_NOT_BOUND,
        ToolRoutingErrorCode.SANDBOX_PROFILE_REQUIRED,
        ToolRoutingErrorCode.SANDBOX_RESOLUTION_FAILED,
        ToolRoutingErrorCode.SANDBOX_DENIED,
    }
)
_PRE_INBOUND_USE_CASE_ERRORS = frozenset(
    {
        UseCaseRoutingErrorCode.INVALID_ROUTING_CONTEXT,
        UseCaseRoutingErrorCode.UNKNOWN_USE_CASE,
        UseCaseRoutingErrorCode.USE_CASE_NOT_BOUND,
        UseCaseRoutingErrorCode.STEP_KIND_MISMATCH,
        UseCaseRoutingErrorCode.EXECUTOR_MISMATCH,
        UseCaseRoutingErrorCode.CAPABILITY_USE_CASE_MISMATCH,
        UseCaseRoutingErrorCode.NON_APPLICATION_CAPABILITY,
        UseCaseRoutingErrorCode.REQUEST_NOT_ROUTABLE,
        UseCaseRoutingErrorCode.IDEMPOTENCY_REQUIRED,
        UseCaseRoutingErrorCode.AUTHORITY_METADATA_FORBIDDEN,
    }
)


@dataclass(frozen=True, slots=True)
class RoutingStepRunner:
    resolver: RuntimeRoutingResolverPort
    agent_router: AgentStepRouter
    use_case_router: UseCaseRouter
    tool_router: ToolRouter
    gate_engine: GateEngine
    runtime_control_runner: RuntimeControlStepRunnerPort
    security_guard: SecurityRuntimeGuard = field(default_factory=SecurityRuntimeGuard)

    def __post_init__(self) -> None:
        if not isinstance(self.resolver, RuntimeRoutingResolverPort):
            raise TypeError("resolver must implement RuntimeRoutingResolverPort")
        if not isinstance(self.agent_router, AgentStepRouter):
            raise TypeError("agent_router must be an AgentStepRouter")
        if not isinstance(self.use_case_router, UseCaseRouter):
            raise TypeError("use_case_router must be a UseCaseRouter")
        if not isinstance(self.tool_router, ToolRouter):
            raise TypeError("tool_router must be a ToolRouter")
        if not isinstance(self.gate_engine, GateEngine):
            raise TypeError("gate_engine must be a GateEngine")
        if not isinstance(self.runtime_control_runner, RuntimeControlStepRunnerPort):
            raise TypeError(
                "runtime_control_runner must implement RuntimeControlStepRunnerPort"
            )
        if not isinstance(self.security_guard, SecurityRuntimeGuard):
            raise TypeError("security_guard must be a SecurityRuntimeGuard")
        shared_policy = self.agent_router.capability_policy
        if self.use_case_router.capability_policy is not shared_policy or (
            self.tool_router.tool_call_policy.capability_policy is not shared_policy
        ):
            raise ValueError("all runtime routes must share CapabilityAuthorizationPolicy")

    def run(
        self,
        *,
        plan: Plan,
        step: StepSpec,
        run_state: RunState,
        attempt: int,
        now: Instant,
    ) -> StepExecutionResult:
        try:
            validate_runtime_context(
                plan=plan,
                step=step,
                run_state=run_state,
                capability_policy=self.agent_router.capability_policy,
            )
            if type(attempt) is not int or attempt < 1 or type(now) is not Instant:
                raise RuntimeRoutingError(
                    RuntimeRoutingErrorCode.INVALID_RUNTIME_CONTEXT
                )
        except (RuntimeRoutingError, TypeError, ValueError) as error:
            return _known_failure(
                step=step,
                attempt=attempt,
                code=_safe_runtime_code(error),
                category=ErrorCategory.VALIDATION,
                source=ErrorSource.AGENT,
            )

        if step.kind is StepKind.TOOL:
            return self._run_tool(plan, step, run_state, attempt, now)
        if step.kind is StepKind.USE_CASE:
            return self._run_use_case(plan, step, run_state, attempt, now)
        if step.kind is StepKind.GATE:
            return self._run_gate(plan, step, run_state, attempt, now)
        if step.kind is StepKind.AGENT:
            return self._run_agent(plan, step, run_state, attempt, now)
        if step.kind in {StepKind.JOIN, StepKind.DECISION}:
            result = self.runtime_control_runner.run(
                plan=plan,
                step=step,
                run_state=run_state,
                attempt=attempt,
                now=now,
            )
            if type(result) is not StepExecutionResult:
                raise RuntimeRoutingError(
                    RuntimeRoutingErrorCode.INVALID_BOUNDARY_RESULT
                )
            return result
        return _known_failure(
            step=step,
            attempt=attempt,
            code=RuntimeRoutingErrorCode.INVALID_STEP_SHAPE.value,
            category=ErrorCategory.VALIDATION,
            source=ErrorSource.AGENT,
        )

    def _run_tool(
        self,
        plan: Plan,
        step: StepSpec,
        run_state: RunState,
        attempt: int,
        now: Instant,
    ) -> StepExecutionResult:
        try:
            resolved = self.resolver.resolve_tool_input(
                plan=plan, step=step, run_state=run_state
            )
            if type(resolved) is not ResolvedToolInput:
                raise TypeError("invalid tool resolution")
            if resolved.permission_scope_ref != step.permission_scope_ref:
                raise RuntimeRoutingError(
                    RuntimeRoutingErrorCode.PERMISSION_SCOPE_MISMATCH
                )
            validate_request_identity(
                plan=plan, step=step, run_state=run_state, request=resolved.request
            )
            if resolved.request.capability_id != step.capability_id:
                raise RuntimeRoutingError(RuntimeRoutingErrorCode.CAPABILITY_MISMATCH)
            if resolved.context.root_ref.run_id != plan.run_id:
                raise RuntimeRoutingError(
                    RuntimeRoutingErrorCode.INVALID_RUNTIME_CONTEXT
                )
        except (RuntimeRoutingError, TypeError, ValueError) as error:
            return _known_failure(
                step=step,
                attempt=attempt,
                code=_safe_runtime_code(error),
                category=ErrorCategory.VALIDATION,
                source=ErrorSource.TOOL,
            )
        try:
            result = self.tool_router.route(
                agent_id=plan.created_by,
                request=resolved.request,
                context=resolved.context,
                evaluated_at=now,
                facts=resolved.policy_facts,
                satisfied_gate_requirements=resolved.satisfied_gate_requirements,
                scope_revoked=resolved.scope_revoked,
            )
        except ToolRoutingError as error:
            if error.code not in _PRE_EXECUTION_TOOL_ERRORS:
                raise
            return _known_failure(
                step=step,
                attempt=attempt,
                code=error.code.value,
                category=(
                    ErrorCategory.PERMISSION
                    if error.code is ToolRoutingErrorCode.TOOL_NOT_ALLOWED
                    else ErrorCategory.TOOL
                ),
                source=ErrorSource.TOOL,
            )
        status = {
            AgentResultStatus.SUCCEEDED: StepRuntimeStatus.SUCCEEDED,
            AgentResultStatus.PARTIAL: StepRuntimeStatus.PARTIAL,
            AgentResultStatus.FAILED: StepRuntimeStatus.FAILED,
        }.get(result.meta.status)
        if status is None:
            raise RuntimeRoutingError(RuntimeRoutingErrorCode.INVALID_BOUNDARY_RESULT)
        if result.error is not None and (
            result.error.step_id != step.step_id or result.error.attempt != attempt
        ):
            raise RuntimeRoutingError(RuntimeRoutingErrorCode.INVALID_BOUNDARY_RESULT)
        if result.security_assessment is None:
            raise RuntimeRoutingError(RuntimeRoutingErrorCode.INVALID_BOUNDARY_RESULT)
        self._enforce_result_security(
            (result.security_assessment,),
            plan=plan,
            step=step,
            run_state=run_state,
            attempt=attempt,
            now=now,
        )
        return StepExecutionResult(
            status=status,
            result_refs=result.artifacts,
            metrics=result.metrics,
            error=result.error,
        )

    def _run_use_case(
        self,
        plan: Plan,
        step: StepSpec,
        run_state: RunState,
        attempt: int,
        now: Instant,
    ) -> StepExecutionResult:
        try:
            resolved = self.resolver.resolve_use_case_input(
                plan=plan, step=step, run_state=run_state
            )
            if type(resolved) is not ResolvedUseCaseInput:
                raise TypeError("invalid use-case resolution")
            if resolved.permission_scope_ref != step.permission_scope_ref:
                raise RuntimeRoutingError(
                    RuntimeRoutingErrorCode.PERMISSION_SCOPE_MISMATCH
                )
            validate_request_identity(
                plan=plan, step=step, run_state=run_state, request=resolved.request
            )
            facts = resolved.policy_facts
            if step.capability_id is not None and step.capability_id.value == _CAP_A02:
                gate_input = self.resolver.resolve_gate_input(
                    plan=plan, step=step, run_state=run_state
                )
                validate_gate_binding(
                    plan=plan,
                    step=step,
                    run_state=run_state,
                    resolved=gate_input,
                )
                try:
                    gate_resolution = self.gate_engine.evaluate(
                        request=gate_input.request, now=now
                    )
                except Exception:
                    return _known_failure(
                        step=step,
                        attempt=attempt,
                        code="GATE_EVALUATION_FAILED",
                        category=ErrorCategory.GATE,
                        source=ErrorSource.APPLICATION,
                    )
                if gate_resolution.disposition is not GateResolutionDisposition.APPROVED:
                    return _known_failure(
                        step=step,
                        attempt=attempt,
                        code=RuntimeRoutingErrorCode.GATE_NOT_APPROVED.value,
                        category=ErrorCategory.GATE,
                        source=ErrorSource.APPLICATION,
                    )
                facts = gate_resolution.to_policy_facts()
        except (RuntimeRoutingError, TypeError, ValueError) as error:
            return _known_failure(
                step=step,
                attempt=attempt,
                code=_safe_runtime_code(error),
                category=ErrorCategory.VALIDATION,
                source=ErrorSource.APPLICATION,
            )
        context = UseCaseRoutingContext(
            step=step,
            permission_scope_ref=resolved.permission_scope_ref,
            permission_scope=resolved.permission_scope,
            policy_facts=facts,
        )
        try:
            result = self.use_case_router.route(
                agent_id=plan.created_by,
                request=resolved.request,
                context=context,
                evaluated_at=now,
            )
        except UseCaseRoutingError as error:
            if error.code not in _PRE_INBOUND_USE_CASE_ERRORS:
                raise
            return _known_failure(
                step=step,
                attempt=attempt,
                code=error.code.value,
                category=(
                    ErrorCategory.PERMISSION
                    if error.code is UseCaseRoutingErrorCode.REQUEST_NOT_ROUTABLE
                    else ErrorCategory.VALIDATION
                ),
                source=ErrorSource.APPLICATION,
            )
        if not result.security_assessments:
            raise RuntimeRoutingError(RuntimeRoutingErrorCode.INVALID_BOUNDARY_RESULT)
        self._enforce_result_security(
            result.security_assessments,
            plan=plan,
            step=step,
            run_state=run_state,
            attempt=attempt,
            now=now,
        )
        return _use_case_result(result, step=step, attempt=attempt)

    def _run_gate(
        self,
        plan: Plan,
        step: StepSpec,
        run_state: RunState,
        attempt: int,
        now: Instant,
    ) -> StepExecutionResult:
        try:
            resolved = self.resolver.resolve_gate_input(
                plan=plan, step=step, run_state=run_state
            )
            validate_gate_binding(
                plan=plan, step=step, run_state=run_state, resolved=resolved
            )
            resolution = self.gate_engine.evaluate(request=resolved.request, now=now)
        except Exception:
            return _known_failure(
                step=step,
                attempt=attempt,
                code="GATE_EVALUATION_FAILED",
                category=ErrorCategory.GATE,
                source=ErrorSource.AGENT,
            )
        if resolution.disposition is not GateResolutionDisposition.APPROVED:
            return _known_failure(
                step=step,
                attempt=attempt,
                code=RuntimeRoutingErrorCode.GATE_NOT_APPROVED.value,
                category=ErrorCategory.GATE,
                source=ErrorSource.AGENT,
            )
        refs = (() if resolution.decision_ref is None else (resolution.decision_ref,))
        return StepExecutionResult(
            status=StepRuntimeStatus.SUCCEEDED,
            result_refs=refs,
        )

    def _run_agent(
        self,
        plan: Plan,
        step: StepSpec,
        run_state: RunState,
        attempt: int,
        now: Instant,
    ) -> StepExecutionResult:
        try:
            resolved = self.resolver.resolve_agent_input(
                plan=plan, step=step, run_state=run_state
            )
            if type(resolved) is not ResolvedAgentInput:
                raise TypeError("invalid agent resolution")
            self.agent_router.authorize(
                plan=plan,
                step=step,
                run_state=run_state,
                resolved=resolved,
                evaluated_at=now,
            )
        except (RuntimeRoutingError, TypeError, ValueError) as error:
            return _known_failure(
                step=step,
                attempt=attempt,
                code=_safe_runtime_code(error),
                category=ErrorCategory.PERMISSION,
                source=ErrorSource.AGENT,
            )
        return self.agent_router.route(
            plan=plan,
            step=step,
            run_state=run_state,
            resolved=resolved,
            attempt=attempt,
            now=now,
        )

    def _enforce_result_security(
        self,
        source_assessments: tuple[StructuredContentSecurityAssessment, ...],
        *,
        plan: Plan,
        step: StepSpec,
        run_state: RunState,
        attempt: int,
        now: Instant,
    ) -> None:
        assessment = self.security_guard.compose(tuple(source_assessments))
        if assessment.launchable:
            return
        source = next(
            (
                item
                for item in source_assessments
                if item.structural_locations
                or item.disposition.value
                not in {"PASS_AS_DATA", "ISOLATE_AS_DATA"}
            ),
            source_assessments[0],
        )
        event = security_event_from_structured_assessment(
            source,
            schema_version=AGENT_CONTRACT_SCHEMA_V1_0,
            event_id=f"security-result:{attempt}:{step.step_id[:72]}",
            occurred_at=now,
            run_id=plan.run_id,
            correlation_id=run_state.correlation_id,
            step_id=step.step_id,
            hostile_propagation=True,
        )
        raise RuntimeSecurityViolation(
            assessment,
            stage=RuntimeSecurityFailureStage.POST_EFFECT,
            event=event,
        )


def _use_case_result(
    result: UseCaseResult[object, object], *, step: StepSpec, attempt: int
) -> StepExecutionResult:
    outcome = result.outcome
    status = outcome.outcome_status
    result_ref = result.result_ref
    error = result.error
    refs = (() if result_ref is None else (result_ref,))
    if status is OutcomeStatus.SUCCESS:
        if error is not None:
            raise RuntimeRoutingError(RuntimeRoutingErrorCode.INVALID_BOUNDARY_RESULT)
        return StepExecutionResult(
            status=StepRuntimeStatus.SUCCEEDED,
            result_refs=refs,
        )
    if status is OutcomeStatus.SUCCESS_WITH_WARNING:
        return StepExecutionResult(
            status=StepRuntimeStatus.PARTIAL,
            result_refs=refs,
            error=error,
        )
    if status not in {
        OutcomeStatus.REJECTED,
        OutcomeStatus.FAILED,
        OutcomeStatus.INDETERMINATE,
    }:
        raise RuntimeRoutingError(RuntimeRoutingErrorCode.INVALID_BOUNDARY_RESULT)
    if error is not None:
        if error.step_id != step.step_id or error.attempt != attempt:
            raise RuntimeRoutingError(RuntimeRoutingErrorCode.INVALID_BOUNDARY_RESULT)
        effect_state = _application_effect_state(outcome, status)
        runtime_error = (
            replace(error, effect_state=effect_state)
            if effect_state is EffectState.UNKNOWN
            or (
                effect_state in {EffectState.PARTIAL, EffectState.COMMITTED}
                and error.effect_state is EffectState.NONE
            )
            else error
        )
    else:
        effect_state = _application_effect_state(outcome, status)
        runtime_error = _error_envelope(
            step=step,
            attempt=attempt,
            code=f"APPLICATION_{status.value}",
            category=(
                ErrorCategory.DOMAIN
                if status is OutcomeStatus.REJECTED
                else ErrorCategory.UNKNOWN
            ),
            source=ErrorSource.APPLICATION,
            effect_state=effect_state,
        )
    return StepExecutionResult(
        status=StepRuntimeStatus.FAILED,
        result_refs=refs,
        error=runtime_error,
    )


def _application_effect_state(
    outcome: ApplicationOutcome[object, object], status: OutcomeStatus
) -> EffectState:
    application_failure = outcome.application_failure
    if status is OutcomeStatus.INDETERMINATE or (
        application_failure is not None
        and application_failure.reconciliation_required
    ):
        return EffectState.UNKNOWN
    if (
        application_failure is not None
        and application_failure.kind.value == "AF_POSTCOMMIT_SIDE_EFFECT"
    ):
        return EffectState.COMMITTED
    if outcome.side_effects:
        return EffectState.PARTIAL
    return EffectState.NONE


def _known_failure(
    *,
    step: StepSpec,
    attempt: int,
    code: str,
    category: ErrorCategory,
    source: ErrorSource,
) -> StepExecutionResult:
    return StepExecutionResult(
        status=StepRuntimeStatus.FAILED,
        error=_error_envelope(
            step=step,
            attempt=max(attempt, 1),
            code=code,
            category=category,
            source=source,
            effect_state=EffectState.NONE,
        ),
    )


def _error_envelope(
    *,
    step: StepSpec,
    attempt: int,
    code: str,
    category: ErrorCategory,
    source: ErrorSource,
    effect_state: EffectState,
) -> ErrorEnvelope:
    return ErrorEnvelope(
        error_code=code,
        category=category,
        source=source,
        retryable=False,
        severity=ErrorSeverity.ERROR,
        message="runtime routing failed closed",
        step_id=step.step_id,
        attempt=attempt,
        effect_state=effect_state,
        recommended_action=RecommendedAction.STOP,
    )


def _safe_runtime_code(error: Exception) -> str:
    if isinstance(error, RuntimeRoutingError):
        return error.code.value
    return RuntimeRoutingErrorCode.RESOLUTION_FAILED.value
