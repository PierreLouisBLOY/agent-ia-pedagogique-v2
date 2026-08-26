from __future__ import annotations

from threading import Lock

from backend.agent_runtime.recovery import SnapshotSequencePolicy, StateSnapshot


class InMemoryStateSnapshotStore:
    """Lock-backed monotonic snapshot fake used only by tests."""

    def __init__(self) -> None:
        self._lock = Lock()
        self._policy = SnapshotSequencePolicy()
        self._latest_by_run: dict[str, StateSnapshot] = {}

    def load_latest(self, *, run_id: str) -> StateSnapshot | None:
        with self._lock:
            return self._latest_by_run.get(run_id)

    def save(
        self,
        *,
        snapshot: StateSnapshot,
        expected_previous_sequence: int | None,
    ) -> StateSnapshot:
        with self._lock:
            previous = self._latest_by_run.get(snapshot.run_id)
            self._policy.validate_save(
                previous=previous,
                snapshot=snapshot,
                expected_previous_sequence=expected_previous_sequence,
            )
            self._latest_by_run[snapshot.run_id] = snapshot
            return snapshot
