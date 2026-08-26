from __future__ import annotations

from typing import Protocol, runtime_checkable

from backend.agent_runtime.recovery.budget import BudgetState


@runtime_checkable
class BudgetStatePort(Protocol):
    """Versioned technical accounting persistence boundary."""

    def get(self, *, run_id: str) -> BudgetState | None: ...

    def compare_and_set(
        self,
        *,
        run_id: str,
        expected_version: int,
        replacement: BudgetState,
    ) -> BudgetState: ...
