from __future__ import annotations

from dataclasses import fields, replace
from datetime import UTC, datetime, timedelta

import pytest

from backend.agent_runtime.contracts import (
    AGENT_CONTRACT_SCHEMA_V1_0,
    ActorKind,
    ActorRef,
    ContractSchemaVersion,
    EffectState,
    WorkflowStatus,
)
from backend.agent_runtime.recovery import (
    BudgetState,
    EffectiveBudgetLimits,
    EffectLedgerRecord,
    EffectLedgerSnapshotRef,
    IdempotencyIdentity,
    IdempotencyKeyFingerprint,
    IdempotencyPolicy,
    IntentFingerprint,
    PlanFingerprint,
    SnapshotFreshnessIssue,
    SnapshotSequencePolicy,
    SnapshotStoreError,
    SnapshotStoreErrorCode,
    StateSnapshot,
    assess_snapshot_freshness,
    snapshot_id_for,
)
from backend.agent_runtime.registry import CapabilityExecutionRoute
from backend.agent_runtime.runtime.state import RunState, StepRuntimeStatus, StepState
from backend.core_contracts.capability import CapabilityId
from backend.shared_kernel.correlation import CorrelationId
from backend.shared_kernel.time import Instant

NOW = Instant(datetime(2026, 8, 26, 12, 0, tzinfo=UTC))
LATER = Instant(NOW.value + timedelta(minutes=1))
LATEST = Instant(LATER.value + timedelta(minutes=1))
PLAN_FINGERPRINT = PlanFingerprint.from_canonical("canonical-plan-v1")


def _run_state(**changes: object) -> RunState:
    values: dict[str, object] = {
        "run_id": "run-1",
        "correlation_id": CorrelationId("corr-1"),
        "workflow_kind": "workflow",
        "plan_id": "plan-1",
        "plan_version": 1,
        "status": WorkflowStatus.PLANNED,
        "step_states": {
            "step-1": StepState("step-1", StepRuntimeStatus.PENDING)
        },
    }
    values.update(changes)
    return RunState(**values)  # type: ignore[arg-type]


def _budget(**changes: object) -> BudgetState:
    values: dict[str, object] = {
        "run_id": "run-1",
        "version": 1,
        "limits": EffectiveBudgetLimits(),
        "created_at": NOW,
        "updated_at": NOW,
    }
    values.update(changes)
    return BudgetState(**values)  # type: ignore[arg-type]


def _snapshot(
    *,
    sequence: int = 1,
    run_state: RunState | None = None,
    budget_state: BudgetState | None = None,
    plan_fingerprint: PlanFingerprint = PLAN_FINGERPRINT,
    effect_ledger_refs: tuple[EffectLedgerSnapshotRef, ...] = (),
    captured_at: Instant = LATER,
) -> StateSnapshot:
    state = run_state or _run_state()
    return StateSnapshot.capture(
        schema_version=AGENT_CONTRACT_SCHEMA_V1_0,
        sequence=sequence,
        run_id=state.run_id,
        plan_id=state.plan_id,
        plan_version=state.plan_version,
        plan_fingerprint=plan_fingerprint,
        run_state=state,
        budget_state=budget_state or _budget(run_id=state.run_id),
        effect_ledger_refs=effect_ledger_refs,
        captured_at=captured_at,
    )


def _effect_record() -> EffectLedgerRecord:
    identity = IdempotencyIdentity(
        principal=ActorRef(ActorKind.AGENT, "AG-03"),
        run_id="run-1",
        step_id="step-1",
        capability_id=CapabilityId("CAP-T02"),
        execution_route=CapabilityExecutionRoute.UTILITY,
        target_id="tool.render",
        operation="render",
        intent_fingerprint=IntentFingerprint.from_value("intent"),
        caller_key_fingerprint=IdempotencyKeyFingerprint.from_key("key"),
    )
    return IdempotencyPolicy().new_reservation(identity=identity, now=NOW)


def test_plan_fingerprint_is_stable_domain_separated_and_bounded() -> None:
    fingerprint = PlanFingerprint.from_canonical("same")

    assert fingerprint == PlanFingerprint.from_canonical(b"same")
    assert len(fingerprint.value) == 64
    assert fingerprint.value != IntentFingerprint.from_value("same").value
    with pytest.raises(ValueError, match="must not be empty"):
        PlanFingerprint.from_canonical("")
    with pytest.raises(ValueError, match="bounded"):
        PlanFingerprint.from_canonical(b"x" * 65_537)


def test_snapshot_sequence_one_and_id_are_stable() -> None:
    snapshot = _snapshot()

    assert snapshot.sequence == 1
    assert snapshot.snapshot_id == snapshot_id_for(
        run_id="run-1",
        plan_id="plan-1",
        plan_version=1,
        plan_fingerprint=PLAN_FINGERPRINT,
        sequence=1,
    )
    assert snapshot.snapshot_id == _snapshot().snapshot_id


def test_snapshot_contains_only_typed_technical_state() -> None:
    names = {item.name for item in fields(StateSnapshot)}

    assert names == {
        "snapshot_id",
        "schema_version",
        "sequence",
        "run_id",
        "plan_id",
        "plan_version",
        "plan_fingerprint",
        "run_state",
        "budget_state",
        "effect_ledger_refs",
        "captured_at",
    }
    assert "payload" not in repr(_snapshot()).lower()


@pytest.mark.parametrize(
    ("run_changes", "budget_changes", "message"),
    [
        ({"run_id": "run-2"}, {}, "run_state.run_id"),
        ({"plan_id": "plan-2"}, {}, "run_state.plan_id"),
        ({"plan_version": 2}, {}, "run_state.plan_version"),
        ({}, {"run_id": "run-2"}, "budget_state.run_id"),
    ],
)
def test_snapshot_rejects_run_plan_and_budget_mismatches(
    run_changes: dict[str, object],
    budget_changes: dict[str, object],
    message: str,
) -> None:
    run_state = _run_state(**run_changes)
    budget_state = _budget(**budget_changes)
    with pytest.raises(ValueError, match=message):
        StateSnapshot.capture(
            schema_version=AGENT_CONTRACT_SCHEMA_V1_0,
            sequence=1,
            run_id="run-1",
            plan_id="plan-1",
            plan_version=1,
            plan_fingerprint=PLAN_FINGERPRINT,
            run_state=run_state,
            budget_state=budget_state,
            effect_ledger_refs=(),
            captured_at=LATER,
        )


def test_snapshot_rejects_duplicate_or_invalid_ledger_refs() -> None:
    ref = EffectLedgerSnapshotRef("effect:v1:" + "a" * 64, 1)
    with pytest.raises(ValueError, match="duplicate"):
        _snapshot(effect_ledger_refs=(ref, ref))
    with pytest.raises(ValueError, match=">= 1"):
        EffectLedgerSnapshotRef(ref.record_id, 0)
    with pytest.raises(ValueError, match="opaque"):
        EffectLedgerSnapshotRef("raw-ledger-key", 1)


def test_snapshot_rejects_forged_id_and_future_state_timestamp() -> None:
    snapshot = _snapshot()
    with pytest.raises(ValueError, match="identity"):
        replace(snapshot, snapshot_id="snapshot:v1:" + "0" * 64)
    with pytest.raises(ValueError, match="newer"):
        _snapshot(budget_state=_budget(updated_at=LATEST), captured_at=LATER)


def test_sequence_policy_accepts_initial_and_exact_successor() -> None:
    first = _snapshot(sequence=1)
    second = _snapshot(sequence=2, captured_at=LATEST)
    policy = SnapshotSequencePolicy()

    policy.validate_save(
        previous=None,
        snapshot=first,
        expected_previous_sequence=None,
    )
    policy.validate_save(
        previous=first,
        snapshot=second,
        expected_previous_sequence=1,
    )


@pytest.mark.parametrize("sequence", [1, 3])
def test_sequence_policy_rejects_stale_or_skipped_sequence(sequence: int) -> None:
    first = _snapshot(sequence=1)
    candidate = _snapshot(sequence=sequence, captured_at=LATEST)

    with pytest.raises(SnapshotStoreError) as raised:
        SnapshotSequencePolicy().validate_save(
            previous=first,
            snapshot=candidate,
            expected_previous_sequence=1,
        )
    assert raised.value.code is SnapshotStoreErrorCode.SNAPSHOT_SEQUENCE_CONFLICT


def test_sequence_policy_requires_plan_version_and_fingerprint_to_move_together() -> None:
    first = _snapshot(sequence=1)
    changed_fingerprint = PlanFingerprint.from_canonical("canonical-plan-v2")
    same_version = _snapshot(
        sequence=2,
        plan_fingerprint=changed_fingerprint,
        captured_at=LATEST,
    )
    with pytest.raises(SnapshotStoreError) as raised:
        SnapshotSequencePolicy().validate_save(
            previous=first,
            snapshot=same_version,
            expected_previous_sequence=1,
        )
    assert raised.value.code is SnapshotStoreErrorCode.SNAPSHOT_PLAN_MISMATCH

    replan_state = _run_state(plan_version=2)
    valid_replan = _snapshot(
        sequence=2,
        run_state=replan_state,
        budget_state=_budget(),
        plan_fingerprint=changed_fingerprint,
        captured_at=LATEST,
    )
    SnapshotSequencePolicy().validate_save(
        previous=first,
        snapshot=valid_replan,
        expected_previous_sequence=1,
    )


def test_sequence_policy_rejects_budget_or_ledger_version_regression() -> None:
    record_id = "effect:v1:" + "a" * 64
    first = _snapshot(
        budget_state=_budget(version=2),
        effect_ledger_refs=(EffectLedgerSnapshotRef(record_id, 2),),
    )
    lower_budget = _snapshot(
        sequence=2,
        budget_state=_budget(version=1),
        effect_ledger_refs=(EffectLedgerSnapshotRef(record_id, 2),),
        captured_at=LATEST,
    )
    lower_ledger = _snapshot(
        sequence=2,
        budget_state=_budget(version=2),
        effect_ledger_refs=(EffectLedgerSnapshotRef(record_id, 1),),
        captured_at=LATEST,
    )
    for candidate in (lower_budget, lower_ledger):
        with pytest.raises(SnapshotStoreError) as raised:
            SnapshotSequencePolicy().validate_save(
                previous=first,
                snapshot=candidate,
                expected_previous_sequence=1,
            )
        assert raised.value.code is SnapshotStoreErrorCode.SNAPSHOT_VERSION_CONFLICT


def test_sequence_policy_rejects_schema_version_regression() -> None:
    first = replace(_snapshot(sequence=1), schema_version=ContractSchemaVersion(2, 0))
    second = _snapshot(sequence=2, captured_at=LATEST)

    with pytest.raises(SnapshotStoreError) as raised:
        SnapshotSequencePolicy().validate_save(
            previous=first,
            snapshot=second,
            expected_previous_sequence=1,
        )
    assert raised.value.code is SnapshotStoreErrorCode.SNAPSHOT_VERSION_CONFLICT


def test_freshness_reports_newer_budget_and_ledger_without_restoring() -> None:
    record = _effect_record()
    snapshot = _snapshot(
        effect_ledger_refs=(EffectLedgerSnapshotRef(record.record_id, 1),)
    )
    current_record = replace(record, version=2, updated_at=LATER)
    current_budget = _budget(version=2, updated_at=LATER)

    assessment = assess_snapshot_freshness(
        snapshot=snapshot,
        current_budget=current_budget,
        current_ledger_records={record.record_id: current_record},
        current_plan_fingerprint=PLAN_FINGERPRINT,
    )

    assert assessment.issues == (
        SnapshotFreshnessIssue.STALE_BUDGET,
        SnapshotFreshnessIssue.STALE_LEDGER,
    )
    assert not assessment.is_current


def test_freshness_reports_plan_mismatch_and_current_state() -> None:
    snapshot = _snapshot()
    current = assess_snapshot_freshness(
        snapshot=snapshot,
        current_budget=snapshot.budget_state,
        current_ledger_records={},
        current_plan_fingerprint=PLAN_FINGERPRINT,
    )
    mismatch = assess_snapshot_freshness(
        snapshot=snapshot,
        current_budget=snapshot.budget_state,
        current_ledger_records={},
        current_plan_fingerprint=PlanFingerprint.from_canonical("other-plan"),
    )

    assert current.is_current
    assert mismatch.issues == (SnapshotFreshnessIssue.PLAN_MISMATCH,)


def test_snapshot_does_not_copy_effect_state_from_ledger() -> None:
    record = _effect_record()
    ref = EffectLedgerSnapshotRef(record.record_id, record.version)
    snapshot = _snapshot(effect_ledger_refs=(ref,))

    assert record.effect_state is EffectState.NONE
    assert not hasattr(snapshot.effect_ledger_refs[0], "effect_state")
