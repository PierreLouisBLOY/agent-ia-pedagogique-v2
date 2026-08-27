from __future__ import annotations

import json
import math
import re
from collections.abc import Mapping
from dataclasses import dataclass, field, fields, is_dataclass
from datetime import timedelta
from decimal import Decimal
from enum import Enum, StrEnum

from backend.agent_runtime.application_routing import (
    UnknownUseCaseError,
    UseCaseRegistry,
)
from backend.agent_runtime.contracts import (
    EffectState,
    ErrorCategory,
    ErrorEnvelope,
    ErrorSeverity,
    ErrorSource,
    RecommendedAction,
    StepKind,
    StepSpec,
)
from backend.agent_runtime.recovery.budget import (
    BudgetAccountingPolicy,
    BudgetCheckDisposition,
    BudgetState,
    BudgetUsageDelta,
)
from backend.agent_runtime.recovery.budget_ports import BudgetStatePort
from backend.agent_runtime.recovery.checkpoint import RecoveryCheckpoint
from backend.agent_runtime.recovery.circuit_breaker import (
    CircuitBreakerKey,
    CircuitCheckDisposition,
    CircuitCheckRequest,
    CircuitOutcomeRecord,
    CircuitPreflightDisposition,
)
from backend.agent_runtime.recovery.circuit_breaker_engine import (
    CircuitBreakerEngine,
)
from backend.agent_runtime.recovery.idempotency import IdempotencyPolicy
from backend.agent_runtime.recovery.model import (
    EffectLedgerLifecycle,
    EffectLedgerRecord,
    EffectReservationDisposition,
    IdempotencyIdentity,
    IdempotencyKeyFingerprint,
    IntentFingerprint,
    RetryFailureFacts,
)
from backend.agent_runtime.recovery.ports import EffectLedgerPort
from backend.agent_runtime.recovery.runtime_ports import (
    RecoveryRuntimeResolverPort,
    RecoveryTechnicalBinding,
)
from backend.agent_runtime.recovery.snapshot import PlanFingerprint
from backend.agent_runtime.recovery.snapshot_ports import StateSnapshotStorePort
from backend.agent_runtime.registry import (
    CapabilityClass,
    CapabilityExecutionRoute,
    ToolEffectClass,
    ToolRegistry,
    UnknownToolError,
)
from backend.agent_runtime.runtime.execution import (
    PreLaunchDecision,
    PreLaunchDisposition,
    StepExecutionResult,
)
from backend.agent_runtime.runtime.planning import Plan
from backend.agent_runtime.runtime.routing import (
    ResolvedAgentInput,
    ResolvedToolInput,
    ResolvedUseCaseInput,
    RoutingPreLaunchGuard,
    RoutingStepRunner,
    RuntimeRoutingResolverPort,
)
from backend.agent_runtime.runtime.routing._validation import (
    validate_request_identity,
)
from backend.agent_runtime.runtime.state import RunState, StepRuntimeStatus
from backend.shared_kernel.time import Instant

_SAFE_CODE = re.compile(r"^[A-Z][A-Z0-9_.-]{0,127}$")


class RecoveryRuntimeErrorCode(StrEnum):
    RECOVERY_CONTEXT_MISMATCH = "RECOVERY_CONTEXT_MISMATCH"
    IDEMPOTENCY_REQUIRED = "IDEMPOTENCY_REQUIRED"
    IDEMPOTENCY_COLLISION = "IDEMPOTENCY_COLLISION"
    LEDGER_VERSION_CONFLICT = "LEDGER_VERSION_CONFLICT"
    LEDGER_FINALIZATION_CONFLICT = "LEDGER_FINALIZATION_CONFLICT"
    RETRY_FACTS_UNAVAILABLE = "RETRY_FACTS_UNAVAILABLE"
    RETRY_BUDGET_CONFLICT = "RETRY_BUDGET_CONFLICT"
    SNAPSHOT_CONFLICT = "SNAPSHOT_CONFLICT"
    CIRCUIT_BLOCKED = "CIRCUIT_BLOCKED"
    CIRCUIT_LEASE_MISMATCH = "CIRCUIT_LEASE_MISMATCH"
    CIRCUIT_OUTCOME_CONFLICT = "CIRCUIT_OUTCOME_CONFLICT"
    RECOVERY_CHECKPOINT_MISMATCH = "RECOVERY_CHECKPOINT_MISMATCH"
    UNSUPPORTED_RECOVERY_ROUTE = "UNSUPPORTED_RECOVERY_ROUTE"
    RESULT_RECOVERY_REQUIRED = "RESULT_RECOVERY_REQUIRED"


class RecoveryRuntimeError(RuntimeError):
    code: RecoveryRuntimeErrorCode

    def __init__(self, code: RecoveryRuntimeErrorCode) -> None:
        if not isinstance(code, RecoveryRuntimeErrorCode):
            raise TypeError("code must be a RecoveryRuntimeErrorCode")
        self.code = code
        super().__init__(code.value)


@dataclass(frozen=True, slots=True)
class RecoveryExecutionContext:
    execution_route: CapabilityExecutionRoute
    target_id: str
    binding: RecoveryTechnicalBinding
    circuit_key: CircuitBreakerKey
    idempotency_required: bool
    identity: IdempotencyIdentity | None
    success_effect_state: EffectState

    def __post_init__(self) -> None:
        if not isinstance(self.execution_route, CapabilityExecutionRoute):
            raise TypeError("execution_route must be a CapabilityExecutionRoute")
        if type(self.target_id) is not str or not self.target_id:
            raise ValueError("target_id must be non-empty")
        if not isinstance(self.binding, RecoveryTechnicalBinding):
            raise TypeError("binding must be a RecoveryTechnicalBinding")
        if self.binding.target_id != self.target_id:
            raise ValueError("binding target must match recovery target")
        if not isinstance(self.circuit_key, CircuitBreakerKey):
            raise TypeError("circuit_key must be a CircuitBreakerKey")
        if (
            self.circuit_key.execution_route is not self.execution_route
            or self.circuit_key.target_id != self.target_id
            or self.circuit_key.binding_id != self.binding.binding_id
        ):
            raise ValueError("circuit key must match the exact technical binding")
        if type(self.idempotency_required) is not bool:
            raise TypeError("idempotency_required must be a bool")
        if self.idempotency_required != (self.identity is not None):
            raise ValueError("protected effects require one canonical identity")
        if not isinstance(self.success_effect_state, EffectState):
            raise TypeError("success_effect_state must be an EffectState")
        if self.idempotency_required:
            if self.success_effect_state is not EffectState.COMMITTED:
                raise ValueError("ledger-governed success must be COMMITTED")
            identity = self.identity
            if identity is None or (
                identity.execution_route is not self.execution_route
                or identity.target_id != self.target_id
            ):
                raise ValueError("identity must match the exact execution target")
        elif self.success_effect_state is not EffectState.NONE:
            raise ValueError("non-ledger success has no recovery effect state")

    def reservation_expires_at(self, now: Instant) -> Instant | None:
        ttl = self.binding.reservation_ttl_seconds
        if ttl is None:
            return None
        return Instant(now.value + timedelta(seconds=ttl))


@dataclass(frozen=True, slots=True)
class RecoveryPreLaunchGuard:
    inner: RoutingPreLaunchGuard
    recovery_resolver: RecoveryRuntimeResolverPort
    circuit_engine: CircuitBreakerEngine
    snapshot_store: StateSnapshotStorePort
    tool_registry: ToolRegistry
    use_case_registry: UseCaseRegistry

    def __post_init__(self) -> None:
        if not isinstance(self.inner, RoutingPreLaunchGuard):
            raise TypeError("inner must be a RoutingPreLaunchGuard")
        if not isinstance(self.recovery_resolver, RecoveryRuntimeResolverPort):
            raise TypeError(
                "recovery_resolver must implement RecoveryRuntimeResolverPort"
            )
        if not isinstance(self.circuit_engine, CircuitBreakerEngine):
            raise TypeError("circuit_engine must be a CircuitBreakerEngine")
        if not isinstance(self.snapshot_store, StateSnapshotStorePort):
            raise TypeError("snapshot_store must implement StateSnapshotStorePort")
        if not isinstance(self.tool_registry, ToolRegistry):
            raise TypeError("tool_registry must be a ToolRegistry")
        if not isinstance(self.use_case_registry, UseCaseRegistry):
            raise TypeError("use_case_registry must be a UseCaseRegistry")

    def check(
        self,
        *,
        plan: Plan,
        step: StepSpec,
        run_state: RunState,
        now: Instant,
    ) -> PreLaunchDecision:
        canonical = self.inner.check(
            plan=plan,
            step=step,
            run_state=run_state,
            now=now,
        )
        if canonical.disposition is not PreLaunchDisposition.ALLOW:
            return canonical
        if step.kind in {StepKind.GATE, StepKind.JOIN, StepKind.DECISION}:
            return canonical
        try:
            checkpoint = _checkpoint_for_step(self.snapshot_store, plan.run_id, step)
            next_attempt = run_state.step_states[step.step_id].attempt_count + 1
            if checkpoint is not None:
                if checkpoint.next_attempt != next_attempt:
                    return PreLaunchDecision(
                        PreLaunchDisposition.DENY,
                        RecoveryRuntimeErrorCode.RECOVERY_CHECKPOINT_MISMATCH.value,
                    )
                if now.value < checkpoint.not_before.value:
                    return PreLaunchDecision(
                        PreLaunchDisposition.CONDITION_REQUIRED,
                        "RECOVERY_BACKOFF_PENDING",
                    )
            context = resolve_recovery_execution_context(
                plan=plan,
                step=step,
                run_state=run_state,
                routing_resolver=self.inner.resolver,
                recovery_resolver=self.recovery_resolver,
                tool_registry=self.tool_registry,
                use_case_registry=self.use_case_registry,
            )
            circuit = self.circuit_engine.inspect(
                request=CircuitCheckRequest(
                    key=context.circuit_key,
                    run_id=plan.run_id,
                    step_id=step.step_id,
                    attempt=next_attempt,
                ),
                now=now,
            )
            if circuit.disposition is CircuitPreflightDisposition.OPEN_BLOCKED:
                return PreLaunchDecision(
                    PreLaunchDisposition.CONDITION_REQUIRED,
                    "RECOVERY_CIRCUIT_OPEN",
                )
            if circuit.disposition is CircuitPreflightDisposition.HALF_OPEN_BUSY:
                return PreLaunchDecision(
                    PreLaunchDisposition.CONDITION_REQUIRED,
                    "RECOVERY_CIRCUIT_HALF_OPEN_BUSY",
                )
            return canonical
        except Exception:
            return PreLaunchDecision(
                PreLaunchDisposition.DENY,
                "RECOVERY_PRELAUNCH_DENIED",
            )


@dataclass(frozen=True, slots=True)
class RecoveryAwareStepRunner:
    inner: RoutingStepRunner
    recovery_resolver: RecoveryRuntimeResolverPort
    ledger: EffectLedgerPort
    budget_port: BudgetStatePort
    circuit_engine: CircuitBreakerEngine
    snapshot_store: StateSnapshotStorePort
    tool_registry: ToolRegistry
    use_case_registry: UseCaseRegistry
    idempotency_policy: IdempotencyPolicy = field(default_factory=IdempotencyPolicy)
    budget_policy: BudgetAccountingPolicy = field(default_factory=BudgetAccountingPolicy)

    def __post_init__(self) -> None:
        if not isinstance(self.inner, RoutingStepRunner):
            raise TypeError("inner must be a RoutingStepRunner")
        if not isinstance(self.recovery_resolver, RecoveryRuntimeResolverPort):
            raise TypeError(
                "recovery_resolver must implement RecoveryRuntimeResolverPort"
            )
        if not isinstance(self.ledger, EffectLedgerPort):
            raise TypeError("ledger must implement EffectLedgerPort")
        if not isinstance(self.budget_port, BudgetStatePort):
            raise TypeError("budget_port must implement BudgetStatePort")
        if not isinstance(self.circuit_engine, CircuitBreakerEngine):
            raise TypeError("circuit_engine must be a CircuitBreakerEngine")
        if not isinstance(self.snapshot_store, StateSnapshotStorePort):
            raise TypeError("snapshot_store must implement StateSnapshotStorePort")
        if not isinstance(self.tool_registry, ToolRegistry):
            raise TypeError("tool_registry must be a ToolRegistry")
        if not isinstance(self.use_case_registry, UseCaseRegistry):
            raise TypeError("use_case_registry must be a UseCaseRegistry")

    def run(
        self,
        *,
        plan: Plan,
        step: StepSpec,
        run_state: RunState,
        attempt: int,
        now: Instant,
    ) -> StepExecutionResult:
        if step.kind in {StepKind.GATE, StepKind.JOIN, StepKind.DECISION}:
            return self.inner.run(
                plan=plan,
                step=step,
                run_state=run_state,
                attempt=attempt,
                now=now,
            )
        context = resolve_recovery_execution_context(
            plan=plan,
            step=step,
            run_state=run_state,
            routing_resolver=self.inner.resolver,
            recovery_resolver=self.recovery_resolver,
            tool_registry=self.tool_registry,
            use_case_registry=self.use_case_registry,
        )
        checkpoint = _checkpoint_for_step(self.snapshot_store, plan.run_id, step)
        if attempt > 1:
            _require_retry_checkpoint(
                context, checkpoint, step.step_id, attempt, now
            )
            self._consume_retry_budget(run_id=plan.run_id, step=step, attempt=attempt, now=now)

        circuit = self.circuit_engine.check(
            request=CircuitCheckRequest(
                key=context.circuit_key,
                run_id=plan.run_id,
                step_id=step.step_id,
                attempt=attempt,
            ),
            now=now,
        )
        if circuit.disposition in {
            CircuitCheckDisposition.OPEN_BLOCKED,
            CircuitCheckDisposition.HALF_OPEN_BUSY,
        }:
            return _closed_failure(
                step=step,
                attempt=attempt,
                code=RecoveryRuntimeErrorCode.CIRCUIT_BLOCKED.value,
            )

        record: EffectLedgerRecord | None = None
        if context.idempotency_required:
            identity = context.identity
            if identity is None:
                raise RecoveryRuntimeError(
                    RecoveryRuntimeErrorCode.IDEMPOTENCY_REQUIRED
                )
            record = self._reserve_for_attempt(
                identity=identity,
                context=context,
                checkpoint=checkpoint,
                attempt=attempt,
                now=now,
            )
            started = self.idempotency_policy.prepare_start(
                record=record,
                attempt=attempt,
                now=now,
            )
            try:
                record = self.ledger.compare_and_set(
                    record_id=record.record_id,
                    expected_version=record.version,
                    replacement=started,
                )
            except Exception as error:
                raise RecoveryRuntimeError(
                    RecoveryRuntimeErrorCode.LEDGER_VERSION_CONFLICT
                ) from error

        try:
            result = self.inner.run(
                plan=plan,
                step=step,
                run_state=run_state,
                attempt=attempt,
                now=now,
            )
        except Exception:
            if record is not None:
                self._finalize_after_exception(record=record, now=now)
            raise

        if type(result) is not StepExecutionResult:
            if record is not None:
                self._finalize_after_exception(record=record, now=now)
            raise RecoveryRuntimeError(
                RecoveryRuntimeErrorCode.LEDGER_FINALIZATION_CONFLICT
            )

        if record is not None:
            effect_state = _effect_state_for_result(context, result)
            facts = (
                RetryFailureFacts.from_error(result.error)
                if result.error is not None
                else None
            )
            finalized = self.idempotency_policy.prepare_finalize(
                record=record,
                effect_state=effect_state,
                now=now,
                result_refs=result.result_refs,
                error_code=(result.error.error_code if result.error is not None else None),
                retry_failure_facts=facts,
            )
            try:
                self.ledger.compare_and_set(
                    record_id=record.record_id,
                    expected_version=record.version,
                    replacement=finalized,
                )
            except Exception as error:
                raise RecoveryRuntimeError(
                    RecoveryRuntimeErrorCode.LEDGER_FINALIZATION_CONFLICT
                ) from error

        try:
            self.circuit_engine.record_outcome(
                outcome=CircuitOutcomeRecord(
                    key=context.circuit_key,
                    expected_version=circuit.state_version,
                    observed_at=now,
                    error=result.error,
                    lease=circuit.lease,
                )
            )
        except Exception as error:
            raise RecoveryRuntimeError(
                RecoveryRuntimeErrorCode.CIRCUIT_OUTCOME_CONFLICT
            ) from error
        return result

    def _reserve_for_attempt(
        self,
        *,
        identity: IdempotencyIdentity,
        context: RecoveryExecutionContext,
        checkpoint: RecoveryCheckpoint | None,
        attempt: int,
        now: Instant,
    ) -> EffectLedgerRecord:
        reservation = self.ledger.reserve(
            identity=identity,
            now=now,
            reservation_expires_at=context.reservation_expires_at(now),
        )
        record = reservation.record
        if reservation.disposition is EffectReservationDisposition.RESERVED_NEW:
            if record is None or attempt != 1:
                raise RecoveryRuntimeError(
                    RecoveryRuntimeErrorCode.RECOVERY_CONTEXT_MISMATCH
                )
            return record
        if reservation.disposition is EffectReservationDisposition.COLLISION:
            raise RecoveryRuntimeError(
                RecoveryRuntimeErrorCode.IDEMPOTENCY_COLLISION
            )
        if record is None:
            raise RecoveryRuntimeError(
                RecoveryRuntimeErrorCode.RECOVERY_CONTEXT_MISMATCH
            )
        if (
            reservation.disposition
            is EffectReservationDisposition.DUPLICATE_ACTIVE
            and record.lifecycle is EffectLedgerLifecycle.RESERVED
            and record.attempt == 0
            and attempt == 1
        ):
            return record
        if (
            reservation.disposition
            is EffectReservationDisposition.DUPLICATE_FINALIZED
            and record.effect_state is EffectState.NONE
        ):
            _require_retry_checkpoint(
                context, checkpoint, identity.step_id, attempt, now
            )
            replacement = self.idempotency_policy.prepare_retry_reservation(
                record=record,
                now=now,
                reservation_expires_at=context.reservation_expires_at(now),
            )
            return self._ledger_cas(record, replacement)
        if (
            reservation.disposition
            is EffectReservationDisposition.DUPLICATE_FINALIZED
            and record.effect_state is EffectState.COMMITTED
        ):
            raise RecoveryRuntimeError(
                RecoveryRuntimeErrorCode.RESULT_RECOVERY_REQUIRED
            )
        raise RecoveryRuntimeError(
            RecoveryRuntimeErrorCode.RECOVERY_CONTEXT_MISMATCH
        )

    def _ledger_cas(
        self,
        current: EffectLedgerRecord,
        replacement: EffectLedgerRecord,
    ) -> EffectLedgerRecord:
        try:
            return self.ledger.compare_and_set(
                record_id=current.record_id,
                expected_version=current.version,
                replacement=replacement,
            )
        except Exception as error:
            raise RecoveryRuntimeError(
                RecoveryRuntimeErrorCode.LEDGER_VERSION_CONFLICT
            ) from error

    def _finalize_after_exception(
        self,
        *,
        record: EffectLedgerRecord,
        now: Instant,
    ) -> None:
        facts = RetryFailureFacts(
            error_code="PROTECTED_CALL_EXCEPTION",
            category=ErrorCategory.UNKNOWN,
            retryable=False,
            recommended_action=RecommendedAction.INSPECT,
            source=ErrorSource.AGENT,
        )
        replacement = self.idempotency_policy.prepare_finalize(
            record=record,
            effect_state=EffectState.UNKNOWN,
            now=now,
            error_code=facts.error_code,
            retry_failure_facts=facts,
        )
        try:
            self.ledger.compare_and_set(
                record_id=record.record_id,
                expected_version=record.version,
                replacement=replacement,
            )
        except Exception as error:
            raise RecoveryRuntimeError(
                RecoveryRuntimeErrorCode.LEDGER_FINALIZATION_CONFLICT
            ) from error

    def _consume_retry_budget(
        self,
        *,
        run_id: str,
        step: StepSpec,
        attempt: int,
        now: Instant,
    ) -> BudgetState:
        current = self.budget_port.get(run_id=run_id)
        if current is None:
            raise RecoveryRuntimeError(
                RecoveryRuntimeErrorCode.RETRY_BUDGET_CONFLICT
            )
        if current.retries_by_step.get(step.step_id, 0) != attempt - 2:
            raise RecoveryRuntimeError(
                RecoveryRuntimeErrorCode.RETRY_BUDGET_CONFLICT
            )
        if (
            self.budget_policy.evaluate(state=current, now=now).disposition
            is not BudgetCheckDisposition.WITHIN_LIMIT
        ):
            raise RecoveryRuntimeError(
                RecoveryRuntimeErrorCode.RETRY_BUDGET_CONFLICT
            )
        replacement = self.budget_policy.apply_delta(
            state=current,
            delta=BudgetUsageDelta(retries_by_step={step.step_id: 1}),
            now=now,
        )
        if (
            self.budget_policy.evaluate(state=replacement, now=now).disposition
            is not BudgetCheckDisposition.WITHIN_LIMIT
        ):
            raise RecoveryRuntimeError(
                RecoveryRuntimeErrorCode.RETRY_BUDGET_CONFLICT
            )
        try:
            return self.budget_port.compare_and_set(
                run_id=run_id,
                expected_version=current.version,
                replacement=replacement,
            )
        except Exception as error:
            raise RecoveryRuntimeError(
                RecoveryRuntimeErrorCode.RETRY_BUDGET_CONFLICT
            ) from error


def resolve_recovery_execution_context(
    *,
    plan: Plan,
    step: StepSpec,
    run_state: RunState,
    routing_resolver: RuntimeRoutingResolverPort,
    recovery_resolver: RecoveryRuntimeResolverPort,
    tool_registry: ToolRegistry,
    use_case_registry: UseCaseRegistry,
) -> RecoveryExecutionContext:
    if step.kind is StepKind.TOOL:
        tool_resolved = routing_resolver.resolve_tool_input(
            plan=plan, step=step, run_state=run_state
        )
        if type(tool_resolved) is not ResolvedToolInput:
            raise RecoveryRuntimeError(
                RecoveryRuntimeErrorCode.RECOVERY_CONTEXT_MISMATCH
            )
        validate_request_identity(
            plan=plan, step=step, run_state=run_state, request=tool_resolved.request
        )
        try:
            tool_descriptor = tool_registry.get(tool_resolved.request.tool_id)
        except UnknownToolError as error:
            raise RecoveryRuntimeError(
                RecoveryRuntimeErrorCode.RECOVERY_CONTEXT_MISMATCH
            ) from error
        binding = recovery_resolver.resolve_tool_recovery(
            plan=plan,
            step=step,
            run_state=run_state,
            request=tool_resolved.request,
        )
        _require_binding_target(binding, tool_resolved.request.tool_id)
        identity = _identity(
            plan=plan,
            step=step,
            principal=tool_resolved.request.permission_scope.principal,
            route=CapabilityExecutionRoute.UTILITY,
            target_id=tool_resolved.request.tool_id,
            operation=tool_descriptor.canonical_name,
            idempotency_key=tool_resolved.request.idempotency_key,
            intent={
                "route": "UTILITY",
                "target_id": tool_resolved.request.tool_id,
                "capability_id": tool_resolved.request.capability_id.value,
                "operation": tool_descriptor.canonical_name,
                "arguments": tool_resolved.request.arguments,
            },
            required=tool_descriptor.idempotency_required,
        )
        if tool_descriptor.effect_class not in {
            ToolEffectClass.LOCAL_FILE_TRANSFORM,
            ToolEffectClass.EXTERNAL_MUTATION,
        } and tool_descriptor.idempotency_required:
            raise RecoveryRuntimeError(
                RecoveryRuntimeErrorCode.RECOVERY_CONTEXT_MISMATCH
            )
        return _context(
            route=CapabilityExecutionRoute.UTILITY,
            target_id=tool_resolved.request.tool_id,
            binding=binding,
            identity=identity,
        )
    if step.kind is StepKind.USE_CASE:
        application_resolved = routing_resolver.resolve_use_case_input(
            plan=plan, step=step, run_state=run_state
        )
        if type(application_resolved) is not ResolvedUseCaseInput:
            raise RecoveryRuntimeError(
                RecoveryRuntimeErrorCode.RECOVERY_CONTEXT_MISMATCH
            )
        validate_request_identity(
            plan=plan,
            step=step,
            run_state=run_state,
            request=application_resolved.request,
        )
        try:
            use_case_descriptor = use_case_registry.get(
                application_resolved.request.use_case_id
            )
            capability = use_case_registry.capability_registry.get(
                use_case_descriptor.capability_id
            )
        except (UnknownUseCaseError, LookupError) as error:
            raise RecoveryRuntimeError(
                RecoveryRuntimeErrorCode.RECOVERY_CONTEXT_MISMATCH
            ) from error
        binding = recovery_resolver.resolve_application_recovery(
            plan=plan,
            step=step,
            run_state=run_state,
            request=application_resolved.request,
        )
        _require_binding_target(binding, application_resolved.request.use_case_id)
        if use_case_descriptor.idempotency_required and (
            capability.capability_class is not CapabilityClass.APPLICATION_ACTION
        ):
            raise RecoveryRuntimeError(
                RecoveryRuntimeErrorCode.RECOVERY_CONTEXT_MISMATCH
            )
        identity = _identity(
            plan=plan,
            step=step,
            principal=application_resolved.permission_scope.principal,
            route=CapabilityExecutionRoute.APPLICATION,
            target_id=application_resolved.request.use_case_id,
            operation=use_case_descriptor.canonical_name,
            idempotency_key=application_resolved.request.idempotency_key,
            intent={
                "route": "APPLICATION",
                "target_id": application_resolved.request.use_case_id,
                "capability_id": use_case_descriptor.capability_id.value,
                "operation": use_case_descriptor.canonical_name,
                "payload": application_resolved.request.payload,
                "requested_effect": application_resolved.request.requested_effect,
            },
            required=use_case_descriptor.idempotency_required,
        )
        return _context(
            route=CapabilityExecutionRoute.APPLICATION,
            target_id=application_resolved.request.use_case_id,
            binding=binding,
            identity=identity,
        )
    if step.kind is StepKind.AGENT:
        agent_resolved = routing_resolver.resolve_agent_input(
            plan=plan, step=step, run_state=run_state
        )
        if (
            type(agent_resolved) is not ResolvedAgentInput
            or step.executor.agent_id is None
        ):
            raise RecoveryRuntimeError(
                RecoveryRuntimeErrorCode.RECOVERY_CONTEXT_MISMATCH
            )
        binding = recovery_resolver.resolve_agent_recovery(
            plan=plan, step=step, run_state=run_state
        )
        target_id = step.executor.agent_id.value
        _require_binding_target(binding, target_id)
        return _context(
            route=CapabilityExecutionRoute.AGENT,
            target_id=target_id,
            binding=binding,
            identity=None,
        )
    raise RecoveryRuntimeError(RecoveryRuntimeErrorCode.UNSUPPORTED_RECOVERY_ROUTE)


def plan_fingerprint(plan: Plan) -> PlanFingerprint:
    if not isinstance(plan, Plan):
        raise TypeError("plan must be a Plan")
    return PlanFingerprint.from_canonical(_canonical_bytes(plan))


def _context(
    *,
    route: CapabilityExecutionRoute,
    target_id: str,
    binding: RecoveryTechnicalBinding,
    identity: IdempotencyIdentity | None,
) -> RecoveryExecutionContext:
    return RecoveryExecutionContext(
        execution_route=route,
        target_id=target_id,
        binding=binding,
        circuit_key=CircuitBreakerKey(route, target_id, binding.binding_id),
        idempotency_required=identity is not None,
        identity=identity,
        success_effect_state=(
            EffectState.COMMITTED if identity is not None else EffectState.NONE
        ),
    )


def _identity(
    *,
    plan: Plan,
    step: StepSpec,
    principal: object,
    route: CapabilityExecutionRoute,
    target_id: str,
    operation: str,
    idempotency_key: str | None,
    intent: Mapping[str, object],
    required: bool,
) -> IdempotencyIdentity | None:
    if not required:
        return None
    if idempotency_key is None:
        raise RecoveryRuntimeError(RecoveryRuntimeErrorCode.IDEMPOTENCY_REQUIRED)
    capability_id = step.capability_id
    if capability_id is None:
        raise RecoveryRuntimeError(
            RecoveryRuntimeErrorCode.RECOVERY_CONTEXT_MISMATCH
        )
    from backend.agent_runtime.contracts import ActorRef

    if not isinstance(principal, ActorRef):
        raise RecoveryRuntimeError(
            RecoveryRuntimeErrorCode.RECOVERY_CONTEXT_MISMATCH
        )
    return IdempotencyIdentity(
        principal=principal,
        run_id=plan.run_id,
        step_id=step.step_id,
        capability_id=capability_id,
        execution_route=route,
        target_id=target_id,
        operation=operation,
        intent_fingerprint=IntentFingerprint.from_value(_canonical_bytes(intent)),
        caller_key_fingerprint=IdempotencyKeyFingerprint.from_key(idempotency_key),
    )


def _canonical_bytes(value: object) -> bytes:
    normalized = _canonical_value(value)
    return json.dumps(
        normalized,
        ensure_ascii=False,
        allow_nan=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")


def _canonical_value(value: object) -> object:
    if value is None or type(value) in {bool, int, str}:
        return value
    if isinstance(value, Decimal):
        if not value.is_finite():
            raise ValueError("non-finite Decimal is not canonical")
        return {"$decimal": format(value, "f")}
    if type(value) is float:
        if not math.isfinite(value):
            raise ValueError("non-finite float is not canonical")
        return {"$float": format(value, ".17g")}
    if isinstance(value, Enum):
        return {
            "$enum": f"{type(value).__module__}.{type(value).__qualname__}",
            "value": _canonical_value(value.value),
        }
    if isinstance(value, Instant):
        return {"$instant": value.value.isoformat(timespec="microseconds")}
    if isinstance(value, Mapping):
        if any(type(key) is not str for key in value):
            raise TypeError("canonical mappings require string keys")
        return {key: _canonical_value(value[key]) for key in sorted(value)}
    if isinstance(value, (tuple, list)):
        return [_canonical_value(item) for item in value]
    if is_dataclass(value) and not isinstance(value, type):
        return {
            "$type": f"{type(value).__module__}.{type(value).__qualname__}",
            "fields": {
                item.name: _canonical_value(getattr(value, item.name))
                for item in fields(value)
            },
        }
    raise TypeError(f"unsupported canonical value type: {type(value).__name__}")


def _checkpoint_for_step(
    store: StateSnapshotStorePort,
    run_id: str,
    step: StepSpec,
) -> RecoveryCheckpoint | None:
    snapshot = store.load_latest(run_id=run_id)
    if snapshot is None or snapshot.recovery_checkpoint is None:
        return None
    checkpoint = snapshot.recovery_checkpoint
    return checkpoint if checkpoint.step_id == step.step_id else None


def _require_retry_checkpoint(
    context: RecoveryExecutionContext,
    checkpoint: RecoveryCheckpoint | None,
    step_id: str,
    attempt: int,
    now: Instant,
) -> None:
    identity = context.identity
    if (
        identity is None
        or checkpoint is None
        or checkpoint.step_id != step_id
        or checkpoint.record_id != identity.record_id
        or checkpoint.next_attempt != attempt
        or checkpoint.retry_ordinal != attempt - 1
        or now.value < checkpoint.not_before.value
    ):
        raise RecoveryRuntimeError(
            RecoveryRuntimeErrorCode.RECOVERY_CHECKPOINT_MISMATCH
        )


def _require_binding_target(
    binding: RecoveryTechnicalBinding,
    target_id: str,
) -> None:
    if not isinstance(binding, RecoveryTechnicalBinding) or (
        binding.target_id != target_id
    ):
        raise RecoveryRuntimeError(
            RecoveryRuntimeErrorCode.RECOVERY_CONTEXT_MISMATCH
        )


def _effect_state_for_result(
    context: RecoveryExecutionContext,
    result: StepExecutionResult,
) -> EffectState:
    if result.error is not None:
        return result.error.effect_state
    if result.status is StepRuntimeStatus.PARTIAL:
        return EffectState.PARTIAL
    if result.status is StepRuntimeStatus.SUCCEEDED:
        return context.success_effect_state
    return EffectState.UNKNOWN


def _closed_failure(
    *,
    step: StepSpec,
    attempt: int,
    code: str,
) -> StepExecutionResult:
    if not _SAFE_CODE.fullmatch(code):
        raise ValueError("code must be a safe closed code")
    return StepExecutionResult(
        status=StepRuntimeStatus.FAILED,
        error=ErrorEnvelope(
            error_code=code,
            category=ErrorCategory.TRANSIENT,
            source=ErrorSource.AGENT,
            retryable=False,
            severity=ErrorSeverity.ERROR,
            message="recovery runtime blocked the protected call",
            step_id=step.step_id,
            attempt=attempt,
            effect_state=EffectState.NONE,
            recommended_action=RecommendedAction.INSPECT,
        ),
    )
