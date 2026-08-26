from __future__ import annotations

from typing import Protocol, runtime_checkable

from backend.agent_runtime.recovery.snapshot import StateSnapshot


@runtime_checkable
class StateSnapshotStorePort(Protocol):
    """Monotonic technical checkpoint boundary without restore semantics."""

    def load_latest(self, *, run_id: str) -> StateSnapshot | None: ...

    def save(
        self,
        *,
        snapshot: StateSnapshot,
        expected_previous_sequence: int | None,
    ) -> StateSnapshot: ...
