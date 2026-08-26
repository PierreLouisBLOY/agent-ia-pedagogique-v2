from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum

from backend.agent_runtime.contracts import (
    EffectState,
    ErrorCategory,
    ErrorEnvelope,
    RecommendedAction,
)
from backend.agent_runtime.policy import (
    BASELINE_AGENT_RUNTIME_POLICY,
    AgentRuntimePolicy,
)
from backend.agent_runtime.recovery.backoff import (
    DeterministicBackoffPolicy,
    RetrySchedule,
)
from backend.agent_runtime.recovery.budget import (
    BudgetCheckDisposition,
    BudgetCheckResult,
    BudgetState,
)
from backend.agent_runtime.recovery.model import EffectLedgerRecord
from backend.agent_runtime.recovery.replay import (
    ReplayGuardDecision,
    ReplayGuardDisposition,
)
from backend.shared_kernel.time import Instant


class RetryDisposition(StrEnum):
    RETRY = "RETRY"
    NO_RETRY = "NO_RETRY"
    RECONCILE_FIRST = "RECONCILE_FIRST"
    REPLAN = "REPLAN"
    STOP = "STOP"
    ESCALATE = "ESCALATE"


class RetryReasonCode(StrEnum):
    INVALID_REPLAY_CONTEXT = "INVALID_REPLAY_CONTEXT"
    ATTEMPT_MISMATCH = "ATTEMPT_MISMATCH"
    RETRY_COUNTER_MISMATCH = "RETRY_COUNTER_MISMATCH"
    REPLAY_NOT_ELIGIBLE = "REPLAY_NOT_ELIGIBLE"
    FORBIDDEN_ERROR_CATEGORY = "FORBIDDEN_ERROR_CATEGORY"
    CATEGORY_NOT_RETRYABLE = "CATEGORY_NOT_RETRYABLE"
    EFFECT_COMMITTED = "EFFECT_COMMITTED"
    EFFECT_PARTIAL = "EFFECT_PARTIAL"
    EFFECT_UNKNOWN = "EFFECT_UNKNOWN"
    ERROR_NOT_RETRYABLE = "ERROR_NOT_RETRYABLE"
    REPLAN_RECOMMENDED = "REPLAN_RECOMMENDED"
    ESCALATION_RECOMMENDED = "ESCALATION_RECOMMENDED"
    STOP_RECOMMENDED = "STOP_RECOMMENDED"
    INSPECTION_REQUIRED = "INSPECTION_REQUIRED"
    RETRY_LIMIT_REACHED = "RETRY_LIMIT_REACHED"
    BUDGET_EXCEEDED = "BUDGET_EXCEEDED"
    BUDGET_USAGE_UNKNOWN = "BUDGET_USAGE_UNKNOWN"
    DEADLINE_EXPIRED = "DEADLINE_EXPIRED"
    BACKOFF_EXCEEDS_DEADLINE = "BACKOFF_EXCEEDS_DEADLINE"
    SAFE_RETRY = "SAFE_RETRY"


_HARD_STOP_CATEGORIES = frozenset(
    {
        ErrorCategory.DOMAIN,
        ErrorCategory.PERMISSION,
        ErrorCategory.GATE,
        ErrorCategory.BUDGET,
        ErrorCategory.CANCELLED,
    }
)
_RETRYABLE_CATEGORIES = frozenset(
    {
        ErrorCategory.TRANSIENT,
        ErrorCategory.PROVIDER,
        ErrorCategory.TOOL,
    }
)


@dataclass(frozen=True, slots=True)
class RetryPolicyRequest:
    """Immutable inputs for one retry decision; no free retry counter is accepted."""

    error: ErrorEnvelope
    record: EffectLedgerRecord
    budget_state: BudgetState
    budget_check: BudgetCheckResult
    replay_decision: ReplayGuardDecision
    now: Instant
    runtime_policy: AgentRuntimePolicy = BASELINE_AGENT_RUNTIME_POLICY

    def __post_init__(self) -> None:
        if not isinstance(self.error, ErrorEnvelope):
            raise TypeError("error must be an ErrorEnvelope")
        if not isinstance(self.record, EffectLedgerRecord):
            raise TypeError("record must be an EffectLedgerRecord")
        if not isinstance(self.budget_state, BudgetState):
            raise TypeError("budget_state must be a BudgetState")
        if not isinstance(self.budget_check, BudgetCheckResult):
            raise TypeError("budget_check must be a BudgetCheckResult")
        if not isinstance(self.replay_decision, ReplayGuardDecision):
            raise TypeError("replay_decision must be a ReplayGuardDecision")
        if not isinstance(self.now, Instant):
            raise TypeError("now must be an Instant")
        if not isinstance(self.runtime_policy, AgentRuntimePolicy):
            raise TypeError("runtime_policy must be an AgentRuntimePolicy")


@dataclass(frozen=True, slots=True)
class RetryDecision:
    disposition: RetryDisposition
    reason_codes: tuple[RetryReasonCode, ...]
    next_attempt: int | None = None
    schedule: RetrySchedule | None = None
    requires_circuit_check: bool = field(init=False, default=True)

    def __post_init__(self) -> None:
        if not isinstance(self.disposition, RetryDisposition):
            raise TypeError("disposition must be a RetryDisposition")
        if not isinstance(self.reason_codes, tuple):
            raise TypeError("reason_codes must be a tuple")
        if any(not isinstance(item, RetryReasonCode) for item in self.reason_codes):
            raise TypeError("reason_codes must contain RetryReasonCode values")
        if not self.reason_codes:
            raise ValueError("reason_codes must not be empty")
        if len(set(self.reason_codes)) != len(self.reason_codes):
            raise ValueError("reason_codes must not contain duplicates")
        if self.disposition is RetryDisposition.RETRY:
            if type(self.next_attempt) is not int or self.next_attempt < 2:
                raise ValueError("RETRY requires next_attempt >= 2")
            if not isinstance(self.schedule, RetrySchedule):
                raise TypeError("RETRY requires a RetrySchedule")
        elif self.next_attempt is not None or self.schedule is not None:
            raise ValueError("non-RETRY decisions cannot contain retry scheduling")

    @property
    def not_before(self) -> Instant | None:
        return self.schedule.not_before if self.schedule is not None else None


@dataclass(frozen=True, slots=True)
class RetryPolicy:
    """Pure retry classifier and scheduler; it never mutates or executes state."""

    backoff_policy: DeterministicBackoffPolicy = field(
        default_factory=DeterministicBackoffPolicy
    )

    def __post_init__(self) -> None:
        if not isinstance(self.backoff_policy, DeterministicBackoffPolicy):
            raise TypeError(
                "backoff_policy must be a DeterministicBackoffPolicy"
            )

    def decide(self, request: RetryPolicyRequest) -> RetryDecision:
        if not isinstance(request, RetryPolicyRequest):
            raise TypeError("request must be a RetryPolicyRequest")
        error = request.error
        record = request.record
        replay = request.replay_decision

        if (
            replay.record_id != record.record_id
            or replay.record_version != record.version
            or request.budget_state.run_id != record.identity.run_id
        ):
            return _no_retry(RetryReasonCode.INVALID_REPLAY_CONTEXT)
        if error.attempt != record.attempt or error.step_id != record.identity.step_id:
            return _no_retry(RetryReasonCode.ATTEMPT_MISMATCH)

        if record.effect_state is EffectState.UNKNOWN:
            return _decision(
                RetryDisposition.RECONCILE_FIRST,
                RetryReasonCode.EFFECT_UNKNOWN,
            )
        if record.effect_state is EffectState.PARTIAL:
            disposition = (
                RetryDisposition.ESCALATE
                if replay.disposition is ReplayGuardDisposition.MANUAL_REQUIRED
                else RetryDisposition.STOP
            )
            return _decision(disposition, RetryReasonCode.EFFECT_PARTIAL)
        if record.effect_state is EffectState.COMMITTED:
            return _no_retry(RetryReasonCode.EFFECT_COMMITTED)

        replay_refusal = _decision_for_replay_refusal(replay.disposition)
        if replay_refusal is not None:
            return replay_refusal
        if error.category in _HARD_STOP_CATEGORIES:
            return _decision(
                RetryDisposition.STOP,
                RetryReasonCode.FORBIDDEN_ERROR_CATEGORY,
            )
        if error.recommended_action is RecommendedAction.REPLAN:
            return _decision(
                RetryDisposition.REPLAN,
                RetryReasonCode.REPLAN_RECOMMENDED,
            )
        if error.recommended_action is RecommendedAction.ESCALATE:
            return _decision(
                RetryDisposition.ESCALATE,
                RetryReasonCode.ESCALATION_RECOMMENDED,
            )
        if error.recommended_action is RecommendedAction.STOP:
            return _decision(
                RetryDisposition.STOP,
                RetryReasonCode.STOP_RECOMMENDED,
            )
        if error.recommended_action is RecommendedAction.INSPECT:
            return _no_retry(RetryReasonCode.INSPECTION_REQUIRED)
        if error.category not in _RETRYABLE_CATEGORIES:
            return _no_retry(RetryReasonCode.CATEGORY_NOT_RETRYABLE)
        if not error.retryable:
            return _no_retry(RetryReasonCode.ERROR_NOT_RETRYABLE)

        budget_decision = _decision_for_budget(request)
        if budget_decision is not None:
            return budget_decision
        retry_count = request.budget_state.retries_by_step.get(
            record.identity.step_id,
            0,
        )
        if retry_count != record.attempt - 1:
            return _no_retry(RetryReasonCode.RETRY_COUNTER_MISMATCH)
        if _retry_limit_reached(request, retry_count):
            return _no_retry(RetryReasonCode.RETRY_LIMIT_REACHED)

        schedule = self.backoff_policy.schedule(
            retry_ordinal=retry_count + 1,
            now=request.now,
        )
        deadline = request.budget_state.limits.deadline
        if deadline is not None and schedule.not_before.value > deadline.value:
            return _no_retry(RetryReasonCode.BACKOFF_EXCEEDS_DEADLINE)
        return RetryDecision(
            disposition=RetryDisposition.RETRY,
            reason_codes=(RetryReasonCode.SAFE_RETRY,),
            next_attempt=record.attempt + 1,
            schedule=schedule,
        )


def _decision_for_replay_refusal(
    disposition: ReplayGuardDisposition,
) -> RetryDecision | None:
    if disposition is ReplayGuardDisposition.ELIGIBLE:
        return None
    if disposition is ReplayGuardDisposition.RECONCILE_FIRST:
        return _decision(
            RetryDisposition.RECONCILE_FIRST,
            RetryReasonCode.REPLAY_NOT_ELIGIBLE,
        )
    if disposition is ReplayGuardDisposition.REPLAN_REQUIRED:
        return _decision(
            RetryDisposition.REPLAN,
            RetryReasonCode.REPLAY_NOT_ELIGIBLE,
        )
    if disposition is ReplayGuardDisposition.MANUAL_REQUIRED:
        return _decision(
            RetryDisposition.ESCALATE,
            RetryReasonCode.REPLAY_NOT_ELIGIBLE,
        )
    return _no_retry(RetryReasonCode.REPLAY_NOT_ELIGIBLE)


def _decision_for_budget(request: RetryPolicyRequest) -> RetryDecision | None:
    disposition = request.replay_decision.disposition
    if disposition is not ReplayGuardDisposition.ELIGIBLE:
        return _no_retry(RetryReasonCode.REPLAY_NOT_ELIGIBLE)
    if request.budget_check.disposition is BudgetCheckDisposition.LIMIT_EXCEEDED:
        return _no_retry(RetryReasonCode.BUDGET_EXCEEDED)
    if request.budget_check.disposition is BudgetCheckDisposition.USAGE_UNKNOWN:
        return _no_retry(RetryReasonCode.BUDGET_USAGE_UNKNOWN)
    # Re-check the immutable absolute deadline; no caller-controlled budget or
    # deadline boolean is accepted by RetryPolicy.
    if request.budget_state.limits.deadline is not None and (
        request.now.value >= request.budget_state.limits.deadline.value
    ):
        return _decision(
            RetryDisposition.STOP,
            RetryReasonCode.DEADLINE_EXPIRED,
        )
    return None


def _retry_limit_reached(request: RetryPolicyRequest, step_retries: int) -> bool:
    limits = request.budget_state.limits
    envelope_limit = limits.max_retries_per_envelope
    if (
        envelope_limit is not None
        and request.budget_state.retries_total >= envelope_limit
    ):
        return True
    step_limits = tuple(
        item
        for item in (
            limits.max_retries_per_step,
            request.runtime_policy.max_retries_per_step,
        )
        if item is not None
    )
    return bool(step_limits) and step_retries >= min(step_limits)


def _no_retry(reason: RetryReasonCode) -> RetryDecision:
    return _decision(RetryDisposition.NO_RETRY, reason)


def _decision(
    disposition: RetryDisposition,
    reason: RetryReasonCode,
) -> RetryDecision:
    return RetryDecision(disposition=disposition, reason_codes=(reason,))
