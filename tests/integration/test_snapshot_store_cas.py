from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta

import pytest

from backend.agent_runtime.contracts import AGENT_CONTRACT_SCHEMA_V1_0, WorkflowStatus
from backend.agent_runtime.recovery import (
    BudgetState,
    EffectiveBudgetLimits,
    PlanFingerprint,
    SnapshotStoreError,
    SnapshotStoreErrorCode,
    StateSnapshot,
    StateSnapshotStorePort,
)
from backend.agent_runtime.runtime.state import RunState, StepRuntimeStatus, StepState
from backend.shared_kernel.correlation import CorrelationId
from backend.shared_kernel.time import Instant
from tests.support.snapshot_store_fakes import InMemoryStateSnapshotStore

NOW = Instant(datetime(2026, 8, 26, 12, 0, tzinfo=UTC))
LATER = Instant(NOW.value + timedelta(seconds=1))
LATEST = Instant(LATER.value + timedelta(seconds=1))
FINGERPRINT = PlanFingerprint.from_canonical("plan-v1")


def _run_state() -> RunState:
    return RunState(
        run_id="run-1",
        correlation_id=CorrelationId("corr-1"),
        workflow_kind="workflow",
        plan_id="plan-1",
        plan_version=1,
        status=WorkflowStatus.PLANNED,
        step_states={"step-1": StepState("step-1", StepRuntimeStatus.PENDING)},
    )


def _snapshot(sequence: int, captured_at: Instant) -> StateSnapshot:
    run_state = _run_state()
    return StateSnapshot.capture(
        schema_version=AGENT_CONTRACT_SCHEMA_V1_0,
        sequence=sequence,
        run_id=run_state.run_id,
        plan_id=run_state.plan_id,
        plan_version=run_state.plan_version,
        plan_fingerprint=FINGERPRINT,
        run_state=run_state,
        budget_state=BudgetState(
            run_id=run_state.run_id,
            version=sequence,
            limits=EffectiveBudgetLimits(),
            created_at=NOW,
            updated_at=NOW,
        ),
        effect_ledger_refs=(),
        captured_at=captured_at,
    )


def test_snapshot_fake_satisfies_port_and_saves_monotonic_sequence() -> None:
    store = InMemoryStateSnapshotStore()
    first = _snapshot(1, LATER)
    second = _snapshot(2, LATEST)

    assert isinstance(store, StateSnapshotStorePort)
    assert store.save(snapshot=first, expected_previous_sequence=None) == first
    assert store.save(snapshot=second, expected_previous_sequence=1) == second
    assert store.load_latest(run_id="run-1") == second


def test_snapshot_fake_requires_absence_for_sequence_one() -> None:
    store = InMemoryStateSnapshotStore()
    first = _snapshot(1, LATER)
    store.save(snapshot=first, expected_previous_sequence=None)

    with pytest.raises(SnapshotStoreError) as raised:
        store.save(snapshot=first, expected_previous_sequence=None)
    assert raised.value.code is SnapshotStoreErrorCode.SNAPSHOT_SEQUENCE_CONFLICT


def test_snapshot_fake_rejects_stale_expected_sequence() -> None:
    store = InMemoryStateSnapshotStore()
    store.save(snapshot=_snapshot(1, LATER), expected_previous_sequence=None)

    with pytest.raises(SnapshotStoreError) as raised:
        store.save(
            snapshot=_snapshot(2, LATEST),
            expected_previous_sequence=2,
        )
    assert raised.value.code is SnapshotStoreErrorCode.SNAPSHOT_SEQUENCE_CONFLICT


def test_concurrent_snapshot_save_allows_exactly_one_successor() -> None:
    store = InMemoryStateSnapshotStore()
    store.save(snapshot=_snapshot(1, LATER), expected_previous_sequence=None)
    candidates = (_snapshot(2, LATEST), _snapshot(2, LATEST))

    def save(candidate: StateSnapshot) -> str:
        try:
            store.save(snapshot=candidate, expected_previous_sequence=1)
        except SnapshotStoreError as error:
            return error.code.value
        return "SAVED"

    with ThreadPoolExecutor(max_workers=2) as executor:
        outcomes = tuple(executor.map(save, candidates))

    assert outcomes.count("SAVED") == 1
    assert outcomes.count(SnapshotStoreErrorCode.SNAPSHOT_SEQUENCE_CONFLICT.value) == 1
    assert store.load_latest(run_id="run-1") == candidates[0]
