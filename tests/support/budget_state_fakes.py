from __future__ import annotations

from threading import Lock

from backend.agent_runtime.recovery import (
    BudgetAccountingPolicy,
    BudgetState,
    BudgetStateError,
    BudgetStateErrorCode,
)


class InMemoryBudgetStatePort:
    """Lock-backed CAS fake used only by tests."""

    def __init__(self, *initial_states: BudgetState) -> None:
        self._lock = Lock()
        self._policy = BudgetAccountingPolicy()
        self._states: dict[str, BudgetState] = {}
        for state in initial_states:
            if not isinstance(state, BudgetState):
                raise TypeError("initial states must be BudgetState values")
            if state.run_id in self._states:
                raise ValueError("initial states must have distinct run IDs")
            self._states[state.run_id] = state

    def get(self, *, run_id: str) -> BudgetState | None:
        with self._lock:
            return self._states.get(run_id)

    def compare_and_set(
        self,
        *,
        run_id: str,
        expected_version: int,
        replacement: BudgetState,
    ) -> BudgetState:
        with self._lock:
            current = self._states.get(run_id)
            if current is None:
                raise BudgetStateError(BudgetStateErrorCode.INVALID_STATE)
            self._policy.validate_compare_and_set(
                current=current,
                expected_version=expected_version,
                replacement=replacement,
            )
            self._states[run_id] = replacement
            return replacement
