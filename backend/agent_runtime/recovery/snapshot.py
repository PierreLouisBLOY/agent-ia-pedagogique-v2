from __future__ import annotations

import re
from collections.abc import Mapping
from dataclasses import dataclass
from enum import StrEnum
from hashlib import sha256
from types import MappingProxyType
from typing import Self

from backend.agent_runtime.contracts import ContractSchemaVersion
from backend.agent_runtime.recovery.budget import BudgetState
from backend.agent_runtime.recovery.circuit_breaker import CircuitBreakerState
from backend.agent_runtime.recovery.model import EffectLedgerRecord
from backend.agent_runtime.runtime.state import RunState
from backend.shared_kernel._strings import require_non_empty
from backend.shared_kernel.time import Instant

_HEX_DIGEST = re.compile(r"^[0-9a-f]{64}$")
_EFFECT_RECORD_ID = re.compile(r"^effect:v1:[0-9a-f]{64}$")
_CIRCUIT_ID = re.compile(r"^circuit:v1:[0-9a-f]{64}$")
_SNAPSHOT_ID = re.compile(r"^snapshot:v1:[0-9a-f]{64}$")
_MAX_FINGERPRINT_INPUT_BYTES = 65_536


class SnapshotStoreErrorCode(StrEnum):
    SNAPSHOT_VERSION_CONFLICT = "SNAPSHOT_VERSION_CONFLICT"
    SNAPSHOT_SEQUENCE_CONFLICT = "SNAPSHOT_SEQUENCE_CONFLICT"
    SNAPSHOT_PLAN_MISMATCH = "SNAPSHOT_PLAN_MISMATCH"
    SNAPSHOT_RUN_MISMATCH = "SNAPSHOT_RUN_MISMATCH"
    INVALID_SNAPSHOT = "INVALID_SNAPSHOT"
    UNKNOWN_SNAPSHOT = "UNKNOWN_SNAPSHOT"


_SNAPSHOT_ERROR_MESSAGES = MappingProxyType(
    {
        SnapshotStoreErrorCode.SNAPSHOT_VERSION_CONFLICT: "snapshot version conflict",
        SnapshotStoreErrorCode.SNAPSHOT_SEQUENCE_CONFLICT: "snapshot sequence conflict",
        SnapshotStoreErrorCode.SNAPSHOT_PLAN_MISMATCH: "snapshot plan mismatch",
        SnapshotStoreErrorCode.SNAPSHOT_RUN_MISMATCH: "snapshot run mismatch",
        SnapshotStoreErrorCode.INVALID_SNAPSHOT: "invalid state snapshot",
        SnapshotStoreErrorCode.UNKNOWN_SNAPSHOT: "unknown state snapshot",
    }
)


class SnapshotStoreError(ValueError):
    code: SnapshotStoreErrorCode

    def __init__(self, code: SnapshotStoreErrorCode) -> None:
        if not isinstance(code, SnapshotStoreErrorCode):
            raise TypeError("code must be a SnapshotStoreErrorCode")
        self.code = code
        super().__init__(_SNAPSHOT_ERROR_MESSAGES[code])


class SnapshotFreshnessIssue(StrEnum):
    STALE_LEDGER = "STALE_LEDGER"
    STALE_BUDGET = "STALE_BUDGET"
    PLAN_MISMATCH = "PLAN_MISMATCH"
    STALE_CIRCUIT = "STALE_CIRCUIT"


@dataclass(frozen=True, slots=True)
class SnapshotFreshnessAssessment:
    issues: tuple[SnapshotFreshnessIssue, ...] = ()

    def __post_init__(self) -> None:
        if not isinstance(self.issues, tuple):
            raise TypeError("issues must be a tuple")
        if any(not isinstance(item, SnapshotFreshnessIssue) for item in self.issues):
            raise TypeError("issues must contain SnapshotFreshnessIssue values")
        if len(set(self.issues)) != len(self.issues):
            raise ValueError("issues must not contain duplicates")

    @property
    def is_current(self) -> bool:
        return not self.issues


@dataclass(frozen=True, slots=True)
class PlanFingerprint:
    value: str

    def __post_init__(self) -> None:
        if type(self.value) is not str:
            raise TypeError("plan fingerprint must be a string")
        if not _HEX_DIGEST.fullmatch(self.value):
            raise ValueError("plan fingerprint must be lowercase SHA-256 hex")

    @classmethod
    def from_canonical(cls, value: str | bytes) -> Self:
        if isinstance(value, str):
            raw = value.encode("utf-8")
        elif isinstance(value, bytes):
            raw = value
        else:
            raise TypeError("canonical plan input must be str or bytes")
        if not raw:
            raise ValueError("canonical plan input must not be empty")
        if len(raw) > _MAX_FINGERPRINT_INPUT_BYTES:
            raise ValueError("canonical plan input exceeds the bounded size")
        digest = sha256()
        digest.update(b"agent-runtime:plan-fingerprint:v1\x00")
        digest.update(raw)
        return cls(digest.hexdigest())


@dataclass(frozen=True, slots=True)
class EffectLedgerSnapshotRef:
    record_id: str
    version: int

    def __post_init__(self) -> None:
        if type(self.record_id) is not str:
            raise TypeError("record_id must be a string")
        if not _EFFECT_RECORD_ID.fullmatch(self.record_id):
            raise ValueError("record_id must be an opaque effect ledger identifier")
        if type(self.version) is not int:
            raise TypeError("version must be an integer")
        if self.version < 1:
            raise ValueError("version must be >= 1")


@dataclass(frozen=True, slots=True)
class CircuitBreakerSnapshotRef:
    circuit_id: str
    version: int

    def __post_init__(self) -> None:
        if type(self.circuit_id) is not str:
            raise TypeError("circuit_id must be a string")
        if not _CIRCUIT_ID.fullmatch(self.circuit_id):
            raise ValueError("circuit_id must be an opaque circuit identifier")
        if type(self.version) is not int:
            raise TypeError("version must be an integer")
        if self.version < 1:
            raise ValueError("version must be >= 1")


@dataclass(frozen=True, slots=True)
class StateSnapshot:
    snapshot_id: str
    schema_version: ContractSchemaVersion
    sequence: int
    run_id: str
    plan_id: str
    plan_version: int
    plan_fingerprint: PlanFingerprint
    run_state: RunState
    budget_state: BudgetState
    effect_ledger_refs: tuple[EffectLedgerSnapshotRef, ...]
    captured_at: Instant
    circuit_breaker_refs: tuple[CircuitBreakerSnapshotRef, ...] = ()

    def __post_init__(self) -> None:
        if type(self.snapshot_id) is not str:
            raise TypeError("snapshot_id must be a string")
        if not _SNAPSHOT_ID.fullmatch(self.snapshot_id):
            raise ValueError("snapshot_id must be an opaque snapshot identifier")
        if not isinstance(self.schema_version, ContractSchemaVersion):
            raise TypeError("schema_version must be a ContractSchemaVersion")
        if type(self.sequence) is not int:
            raise TypeError("sequence must be an integer")
        if self.sequence < 1:
            raise ValueError("sequence must be >= 1")
        require_non_empty(self.run_id, "run_id")
        require_non_empty(self.plan_id, "plan_id")
        if type(self.plan_version) is not int:
            raise TypeError("plan_version must be an integer")
        if self.plan_version < 1:
            raise ValueError("plan_version must be >= 1")
        if not isinstance(self.plan_fingerprint, PlanFingerprint):
            raise TypeError("plan_fingerprint must be a PlanFingerprint")
        if not isinstance(self.run_state, RunState):
            raise TypeError("run_state must be a RunState")
        if not isinstance(self.budget_state, BudgetState):
            raise TypeError("budget_state must be a BudgetState")
        if not isinstance(self.effect_ledger_refs, tuple):
            raise TypeError("effect_ledger_refs must be a tuple")
        if any(
            not isinstance(item, EffectLedgerSnapshotRef)
            for item in self.effect_ledger_refs
        ):
            raise TypeError("effect_ledger_refs must contain EffectLedgerSnapshotRef values")
        if len({item.record_id for item in self.effect_ledger_refs}) != len(
            self.effect_ledger_refs
        ):
            raise ValueError("effect_ledger_refs must not contain duplicate records")
        if not isinstance(self.captured_at, Instant):
            raise TypeError("captured_at must be an Instant")
        if not isinstance(self.circuit_breaker_refs, tuple):
            raise TypeError("circuit_breaker_refs must be a tuple")
        if any(
            not isinstance(item, CircuitBreakerSnapshotRef)
            for item in self.circuit_breaker_refs
        ):
            raise TypeError(
                "circuit_breaker_refs must contain CircuitBreakerSnapshotRef values"
            )
        if len({item.circuit_id for item in self.circuit_breaker_refs}) != len(
            self.circuit_breaker_refs
        ):
            raise ValueError("circuit_breaker_refs must not contain duplicates")
        self._validate_cross_checks()
        expected_id = snapshot_id_for(
            run_id=self.run_id,
            plan_id=self.plan_id,
            plan_version=self.plan_version,
            plan_fingerprint=self.plan_fingerprint,
            sequence=self.sequence,
        )
        if self.snapshot_id != expected_id:
            raise ValueError("snapshot_id must match snapshot identity")

    @classmethod
    def capture(
        cls,
        *,
        schema_version: ContractSchemaVersion,
        sequence: int,
        run_id: str,
        plan_id: str,
        plan_version: int,
        plan_fingerprint: PlanFingerprint,
        run_state: RunState,
        budget_state: BudgetState,
        effect_ledger_refs: tuple[EffectLedgerSnapshotRef, ...],
        captured_at: Instant,
        circuit_breaker_refs: tuple[CircuitBreakerSnapshotRef, ...] = (),
    ) -> Self:
        return cls(
            snapshot_id=snapshot_id_for(
                run_id=run_id,
                plan_id=plan_id,
                plan_version=plan_version,
                plan_fingerprint=plan_fingerprint,
                sequence=sequence,
            ),
            schema_version=schema_version,
            sequence=sequence,
            run_id=run_id,
            plan_id=plan_id,
            plan_version=plan_version,
            plan_fingerprint=plan_fingerprint,
            run_state=run_state,
            budget_state=budget_state,
            effect_ledger_refs=effect_ledger_refs,
            captured_at=captured_at,
            circuit_breaker_refs=circuit_breaker_refs,
        )

    def _validate_cross_checks(self) -> None:
        if self.run_state.run_id != self.run_id:
            raise ValueError("run_state.run_id must match snapshot run_id")
        if self.run_state.plan_id != self.plan_id:
            raise ValueError("run_state.plan_id must match snapshot plan_id")
        if self.run_state.plan_version != self.plan_version:
            raise ValueError("run_state.plan_version must match snapshot plan_version")
        if self.budget_state.run_id != self.run_id:
            raise ValueError("budget_state.run_id must match snapshot run_id")
        if self.budget_state.updated_at.value > self.captured_at.value:
            raise ValueError("budget_state cannot be newer than captured_at")
        run_timestamps = tuple(
            item
            for item in (self.run_state.started_at, self.run_state.ended_at)
            if item is not None
        )
        step_timestamps = tuple(
            item
            for state in self.run_state.step_states.values()
            for item in (state.started_at, state.ended_at)
            if item is not None
        )
        if any(
            item.value > self.captured_at.value
            for item in (*run_timestamps, *step_timestamps)
        ):
            raise ValueError("runtime state cannot be newer than captured_at")


def snapshot_id_for(
    *,
    run_id: str,
    plan_id: str,
    plan_version: int,
    plan_fingerprint: PlanFingerprint,
    sequence: int,
) -> str:
    require_non_empty(run_id, "run_id")
    require_non_empty(plan_id, "plan_id")
    if type(plan_version) is not int:
        raise TypeError("plan_version must be an integer")
    if plan_version < 1:
        raise ValueError("plan_version must be >= 1")
    if not isinstance(plan_fingerprint, PlanFingerprint):
        raise TypeError("plan_fingerprint must be a PlanFingerprint")
    if type(sequence) is not int:
        raise TypeError("sequence must be an integer")
    if sequence < 1:
        raise ValueError("sequence must be >= 1")
    digest = sha256()
    digest.update(b"agent-runtime:state-snapshot:v1\x00")
    for part in (
        run_id,
        plan_id,
        str(plan_version),
        plan_fingerprint.value,
        str(sequence),
    ):
        encoded = part.encode("utf-8")
        digest.update(len(encoded).to_bytes(8, "big"))
        digest.update(encoded)
    return f"snapshot:v1:{digest.hexdigest()}"


@dataclass(frozen=True, slots=True)
class SnapshotSequencePolicy:
    """Pure monotonicity checks for snapshot-store compare-and-set operations."""

    def validate_save(
        self,
        *,
        previous: StateSnapshot | None,
        snapshot: StateSnapshot,
        expected_previous_sequence: int | None,
    ) -> None:
        if previous is not None and not isinstance(previous, StateSnapshot):
            raise TypeError("previous must be a StateSnapshot or None")
        if not isinstance(snapshot, StateSnapshot):
            raise TypeError("snapshot must be a StateSnapshot")
        if expected_previous_sequence is not None and (
            type(expected_previous_sequence) is not int
            or expected_previous_sequence < 1
        ):
            raise ValueError("expected_previous_sequence must be >= 1 or None")
        if previous is None:
            if expected_previous_sequence is not None or snapshot.sequence != 1:
                raise SnapshotStoreError(
                    SnapshotStoreErrorCode.SNAPSHOT_SEQUENCE_CONFLICT
                )
            return
        if previous.run_id != snapshot.run_id:
            raise SnapshotStoreError(SnapshotStoreErrorCode.SNAPSHOT_RUN_MISMATCH)
        if expected_previous_sequence != previous.sequence:
            raise SnapshotStoreError(
                SnapshotStoreErrorCode.SNAPSHOT_SEQUENCE_CONFLICT
            )
        if snapshot.sequence != previous.sequence + 1:
            raise SnapshotStoreError(
                SnapshotStoreErrorCode.SNAPSHOT_SEQUENCE_CONFLICT
            )
        if snapshot.captured_at.value < previous.captured_at.value:
            raise SnapshotStoreError(SnapshotStoreErrorCode.INVALID_SNAPSHOT)
        if snapshot.schema_version < previous.schema_version:
            raise SnapshotStoreError(
                SnapshotStoreErrorCode.SNAPSHOT_VERSION_CONFLICT
            )
        self._validate_plan_progression(previous, snapshot)
        self._validate_state_progression(previous, snapshot)

    @staticmethod
    def _validate_plan_progression(
        previous: StateSnapshot,
        snapshot: StateSnapshot,
    ) -> None:
        if snapshot.plan_id != previous.plan_id:
            raise SnapshotStoreError(SnapshotStoreErrorCode.SNAPSHOT_PLAN_MISMATCH)
        if snapshot.plan_version < previous.plan_version:
            raise SnapshotStoreError(SnapshotStoreErrorCode.SNAPSHOT_PLAN_MISMATCH)
        fingerprint_changed = snapshot.plan_fingerprint != previous.plan_fingerprint
        version_changed = snapshot.plan_version != previous.plan_version
        if fingerprint_changed != version_changed:
            raise SnapshotStoreError(SnapshotStoreErrorCode.SNAPSHOT_PLAN_MISMATCH)

    @staticmethod
    def _validate_state_progression(
        previous: StateSnapshot,
        snapshot: StateSnapshot,
    ) -> None:
        if snapshot.budget_state.version < previous.budget_state.version:
            raise SnapshotStoreError(
                SnapshotStoreErrorCode.SNAPSHOT_VERSION_CONFLICT
            )
        current_refs = {item.record_id: item.version for item in snapshot.effect_ledger_refs}
        for item in previous.effect_ledger_refs:
            if current_refs.get(item.record_id, 0) < item.version:
                raise SnapshotStoreError(
                    SnapshotStoreErrorCode.SNAPSHOT_VERSION_CONFLICT
                )
        current_circuit_refs = {
            item.circuit_id: item.version for item in snapshot.circuit_breaker_refs
        }
        for circuit_ref in previous.circuit_breaker_refs:
            current_version = current_circuit_refs.get(circuit_ref.circuit_id)
            if (
                current_version is not None
                and current_version < circuit_ref.version
            ):
                raise SnapshotStoreError(
                    SnapshotStoreErrorCode.SNAPSHOT_VERSION_CONFLICT
                )


def assess_snapshot_freshness(
    *,
    snapshot: StateSnapshot,
    current_budget: BudgetState,
    current_ledger_records: Mapping[str, EffectLedgerRecord],
    current_plan_fingerprint: PlanFingerprint,
    current_circuit_states: Mapping[str, CircuitBreakerState] | None = None,
) -> SnapshotFreshnessAssessment:
    """Identify stale technical references without restoring or mutating runtime state."""
    if not isinstance(snapshot, StateSnapshot):
        raise TypeError("snapshot must be a StateSnapshot")
    if not isinstance(current_budget, BudgetState):
        raise TypeError("current_budget must be a BudgetState")
    if current_budget.run_id != snapshot.run_id:
        raise SnapshotStoreError(SnapshotStoreErrorCode.SNAPSHOT_RUN_MISMATCH)
    if not isinstance(current_ledger_records, Mapping):
        raise TypeError("current_ledger_records must be a mapping")
    if not isinstance(current_plan_fingerprint, PlanFingerprint):
        raise TypeError("current_plan_fingerprint must be a PlanFingerprint")
    issues: list[SnapshotFreshnessIssue] = []
    if snapshot.plan_fingerprint != current_plan_fingerprint:
        issues.append(SnapshotFreshnessIssue.PLAN_MISMATCH)
    if snapshot.budget_state.version < current_budget.version:
        issues.append(SnapshotFreshnessIssue.STALE_BUDGET)
    for record_id, record in current_ledger_records.items():
        require_non_empty(record_id, "current_ledger_records key")
        if not isinstance(record, EffectLedgerRecord):
            raise TypeError("current_ledger_records values must be EffectLedgerRecord values")
        if record.record_id != record_id:
            raise ValueError("current_ledger_records key must match record_id")
    snapshot_versions = {
        item.record_id: item.version for item in snapshot.effect_ledger_refs
    }
    if any(
        record_id in snapshot_versions
        and snapshot_versions[record_id] < record.version
        for record_id, record in current_ledger_records.items()
    ):
        issues.append(SnapshotFreshnessIssue.STALE_LEDGER)
    if current_circuit_states is not None:
        if not isinstance(current_circuit_states, Mapping):
            raise TypeError("current_circuit_states must be a mapping or None")
        for circuit_id, state in current_circuit_states.items():
            require_non_empty(circuit_id, "current_circuit_states key")
            if not isinstance(state, CircuitBreakerState):
                raise TypeError(
                    "current_circuit_states values must be CircuitBreakerState values"
                )
            if state.circuit_id != circuit_id:
                raise ValueError("current_circuit_states key must match circuit_id")
        snapshot_circuit_versions = {
            item.circuit_id: item.version for item in snapshot.circuit_breaker_refs
        }
        if any(
            circuit_id in snapshot_circuit_versions
            and snapshot_circuit_versions[circuit_id] < state.version
            for circuit_id, state in current_circuit_states.items()
        ):
            issues.append(SnapshotFreshnessIssue.STALE_CIRCUIT)
    return SnapshotFreshnessAssessment(tuple(issues))
