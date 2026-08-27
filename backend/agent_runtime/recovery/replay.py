from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from enum import StrEnum

from backend.agent_runtime.contracts import EffectState
from backend.agent_runtime.recovery.budget import (
    BudgetCheckDisposition,
    BudgetCheckResult,
)
from backend.agent_runtime.recovery.model import (
    EffectLedgerLifecycle,
    EffectLedgerRecord,
    IdempotencyIdentity,
    ReconciliationStatus,
)


class AuthorityRevalidationStatus(StrEnum):
    VALID = "VALID"
    INVALID = "INVALID"
    NOT_REQUIRED = "NOT_REQUIRED"


class SnapshotRevalidationStatus(StrEnum):
    CURRENT = "CURRENT"
    STALE = "STALE"
    PLAN_MISMATCH = "PLAN_MISMATCH"
    NOT_REQUIRED = "NOT_REQUIRED"


class DeadlineRevalidationStatus(StrEnum):
    VALID = "VALID"
    EXPIRED = "EXPIRED"
    NOT_REQUIRED = "NOT_REQUIRED"


class SecurityRevalidationStatus(StrEnum):
    VALID = "VALID"
    INVALID = "INVALID"
    NOT_REQUIRED = "NOT_REQUIRED"


class ReplayGuardDisposition(StrEnum):
    ELIGIBLE = "ELIGIBLE"
    RECONCILE_FIRST = "RECONCILE_FIRST"
    REPLAN_REQUIRED = "REPLAN_REQUIRED"
    BLOCKED = "BLOCKED"
    MANUAL_REQUIRED = "MANUAL_REQUIRED"


class ReplayGuardReasonCode(StrEnum):
    IDENTITY_MISMATCH = "IDENTITY_MISMATCH"
    RECORD_RESERVED = "RECORD_RESERVED"
    RECORD_IN_PROGRESS = "RECORD_IN_PROGRESS"
    RECORD_ABANDONED = "RECORD_ABANDONED"
    EFFECT_COMMITTED = "EFFECT_COMMITTED"
    EFFECT_UNKNOWN = "EFFECT_UNKNOWN"
    EFFECT_PARTIAL = "EFFECT_PARTIAL"
    RECONCILIATION_PENDING = "RECONCILIATION_PENDING"
    MANUAL_RECONCILIATION_REQUIRED = "MANUAL_RECONCILIATION_REQUIRED"
    PERMISSION_INVALID = "PERMISSION_INVALID"
    GATE_INVALID = "GATE_INVALID"
    BUDGET_EXCEEDED = "BUDGET_EXCEEDED"
    BUDGET_USAGE_UNKNOWN = "BUDGET_USAGE_UNKNOWN"
    DEADLINE_EXPIRED = "DEADLINE_EXPIRED"
    SNAPSHOT_STALE = "SNAPSHOT_STALE"
    PLAN_MISMATCH = "PLAN_MISMATCH"
    SECURITY_INVALID = "SECURITY_INVALID"


@dataclass(frozen=True, slots=True)
class ReplayPreconditions:
    """Trusted revalidation facts supplied by future orchestration integration."""

    requested_identity: IdempotencyIdentity
    permission_status: AuthorityRevalidationStatus
    gate_status: AuthorityRevalidationStatus
    budget_check: BudgetCheckResult
    deadline_status: DeadlineRevalidationStatus
    snapshot_status: SnapshotRevalidationStatus
    security_status: SecurityRevalidationStatus = (
        SecurityRevalidationStatus.NOT_REQUIRED
    )

    def __post_init__(self) -> None:
        if not isinstance(self.requested_identity, IdempotencyIdentity):
            raise TypeError("requested_identity must be an IdempotencyIdentity")
        if not isinstance(self.permission_status, AuthorityRevalidationStatus):
            raise TypeError(
                "permission_status must be an AuthorityRevalidationStatus"
            )
        if not isinstance(self.gate_status, AuthorityRevalidationStatus):
            raise TypeError("gate_status must be an AuthorityRevalidationStatus")
        if not isinstance(self.budget_check, BudgetCheckResult):
            raise TypeError("budget_check must be a BudgetCheckResult")
        if not isinstance(self.deadline_status, DeadlineRevalidationStatus):
            raise TypeError(
                "deadline_status must be a DeadlineRevalidationStatus"
            )
        if not isinstance(self.snapshot_status, SnapshotRevalidationStatus):
            raise TypeError(
                "snapshot_status must be a SnapshotRevalidationStatus"
            )
        if not isinstance(self.security_status, SecurityRevalidationStatus):
            raise TypeError(
                "security_status must be a SecurityRevalidationStatus"
            )


@dataclass(frozen=True, slots=True)
class ReplayGuardDecision:
    disposition: ReplayGuardDisposition
    reason_codes: tuple[ReplayGuardReasonCode, ...]
    record_id: str
    record_version: int
    requires_circuit_check: bool = field(init=False, default=True)

    def __post_init__(self) -> None:
        if not isinstance(self.disposition, ReplayGuardDisposition):
            raise TypeError("disposition must be a ReplayGuardDisposition")
        if not isinstance(self.reason_codes, tuple):
            raise TypeError("reason_codes must be a tuple")
        if any(
            not isinstance(item, ReplayGuardReasonCode)
            for item in self.reason_codes
        ):
            raise TypeError("reason_codes must contain ReplayGuardReasonCode values")
        if len(set(self.reason_codes)) != len(self.reason_codes):
            raise ValueError("reason_codes must not contain duplicates")
        if self.disposition is ReplayGuardDisposition.ELIGIBLE:
            if self.reason_codes:
                raise ValueError("ELIGIBLE cannot contain reason codes")
        elif not self.reason_codes:
            raise ValueError("a non-eligible decision requires a reason code")
        if type(self.record_id) is not str or not self.record_id:
            raise ValueError("record_id must be a non-empty string")
        if type(self.record_version) is not int:
            raise TypeError("record_version must be an integer")
        if self.record_version < 1:
            raise ValueError("record_version must be >= 1")


@dataclass(frozen=True, slots=True)
class ReplayGuard:
    """Pure fail-closed replay eligibility policy with no execution authority."""

    def evaluate(
        self,
        *,
        record: EffectLedgerRecord,
        preconditions: ReplayPreconditions,
    ) -> ReplayGuardDecision:
        if not isinstance(record, EffectLedgerRecord):
            raise TypeError("record must be an EffectLedgerRecord")
        if not isinstance(preconditions, ReplayPreconditions):
            raise TypeError("preconditions must be ReplayPreconditions")
        decide = _decision_factory(record)

        if preconditions.requested_identity != record.identity:
            return decide(
                ReplayGuardDisposition.REPLAN_REQUIRED,
                (ReplayGuardReasonCode.IDENTITY_MISMATCH,),
            )
        if record.lifecycle is EffectLedgerLifecycle.RESERVED:
            return decide(
                ReplayGuardDisposition.BLOCKED,
                (ReplayGuardReasonCode.RECORD_RESERVED,),
            )
        if record.lifecycle is EffectLedgerLifecycle.IN_PROGRESS:
            return decide(
                ReplayGuardDisposition.RECONCILE_FIRST,
                (
                    ReplayGuardReasonCode.RECORD_IN_PROGRESS,
                    ReplayGuardReasonCode.EFFECT_UNKNOWN,
                    ReplayGuardReasonCode.RECONCILIATION_PENDING,
                ),
            )
        if record.lifecycle is EffectLedgerLifecycle.ABANDONED:
            return decide(
                ReplayGuardDisposition.BLOCKED,
                (ReplayGuardReasonCode.RECORD_ABANDONED,),
            )
        effect_decision = _effect_decision(record, decide)
        if effect_decision is not None:
            return effect_decision

        if preconditions.snapshot_status is SnapshotRevalidationStatus.PLAN_MISMATCH:
            return decide(
                ReplayGuardDisposition.REPLAN_REQUIRED,
                (ReplayGuardReasonCode.PLAN_MISMATCH,),
            )
        reasons: list[ReplayGuardReasonCode] = []
        if preconditions.permission_status is AuthorityRevalidationStatus.INVALID:
            reasons.append(ReplayGuardReasonCode.PERMISSION_INVALID)
        if preconditions.gate_status is AuthorityRevalidationStatus.INVALID:
            reasons.append(ReplayGuardReasonCode.GATE_INVALID)
        if preconditions.security_status is SecurityRevalidationStatus.INVALID:
            reasons.append(ReplayGuardReasonCode.SECURITY_INVALID)
        if (
            preconditions.budget_check.disposition
            is BudgetCheckDisposition.LIMIT_EXCEEDED
        ):
            reasons.append(ReplayGuardReasonCode.BUDGET_EXCEEDED)
        elif (
            preconditions.budget_check.disposition
            is BudgetCheckDisposition.USAGE_UNKNOWN
        ):
            reasons.append(ReplayGuardReasonCode.BUDGET_USAGE_UNKNOWN)
        if preconditions.deadline_status is DeadlineRevalidationStatus.EXPIRED:
            reasons.append(ReplayGuardReasonCode.DEADLINE_EXPIRED)
        if preconditions.snapshot_status is SnapshotRevalidationStatus.STALE:
            reasons.append(ReplayGuardReasonCode.SNAPSHOT_STALE)
        if reasons:
            return decide(ReplayGuardDisposition.BLOCKED, tuple(reasons))
        return decide(ReplayGuardDisposition.ELIGIBLE, ())


def _effect_decision(
    record: EffectLedgerRecord,
    decide: Callable[
        [ReplayGuardDisposition, tuple[ReplayGuardReasonCode, ...]],
        ReplayGuardDecision,
    ],
) -> ReplayGuardDecision | None:
    if record.effect_state is EffectState.COMMITTED:
        return decide(
            ReplayGuardDisposition.BLOCKED,
            (ReplayGuardReasonCode.EFFECT_COMMITTED,),
        )
    if record.effect_state is EffectState.UNKNOWN:
        if record.reconciliation_status is ReconciliationStatus.MANUAL_REQUIRED:
            return decide(
                ReplayGuardDisposition.MANUAL_REQUIRED,
                (
                    ReplayGuardReasonCode.EFFECT_UNKNOWN,
                    ReplayGuardReasonCode.MANUAL_RECONCILIATION_REQUIRED,
                ),
            )
        return decide(
            ReplayGuardDisposition.RECONCILE_FIRST,
            (
                ReplayGuardReasonCode.EFFECT_UNKNOWN,
                ReplayGuardReasonCode.RECONCILIATION_PENDING,
            ),
        )
    if record.effect_state is EffectState.PARTIAL:
        if record.reconciliation_status is ReconciliationStatus.PENDING:
            return decide(
                ReplayGuardDisposition.RECONCILE_FIRST,
                (
                    ReplayGuardReasonCode.EFFECT_PARTIAL,
                    ReplayGuardReasonCode.RECONCILIATION_PENDING,
                ),
            )
        if record.reconciliation_status is ReconciliationStatus.MANUAL_REQUIRED:
            return decide(
                ReplayGuardDisposition.MANUAL_REQUIRED,
                (
                    ReplayGuardReasonCode.EFFECT_PARTIAL,
                    ReplayGuardReasonCode.MANUAL_RECONCILIATION_REQUIRED,
                ),
            )
        return decide(
            ReplayGuardDisposition.BLOCKED,
            (ReplayGuardReasonCode.EFFECT_PARTIAL,),
        )
    return None


def _decision_factory(
    record: EffectLedgerRecord,
) -> Callable[
    [ReplayGuardDisposition, tuple[ReplayGuardReasonCode, ...]],
    ReplayGuardDecision,
]:
    def decide(
        disposition: ReplayGuardDisposition,
        reason_codes: tuple[ReplayGuardReasonCode, ...],
    ) -> ReplayGuardDecision:
        return ReplayGuardDecision(
            disposition=disposition,
            reason_codes=reason_codes,
            record_id=record.record_id,
            record_version=record.version,
        )

    return decide
