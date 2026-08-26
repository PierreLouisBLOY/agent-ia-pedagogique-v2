from __future__ import annotations

from typing import Protocol, runtime_checkable

from backend.agent_runtime.recovery.circuit_breaker import CircuitBreakerState


@runtime_checkable
class CircuitBreakerStorePort(Protocol):
    """Atomic technical health persistence without execution authority."""

    def get(self, *, circuit_id: str) -> CircuitBreakerState | None: ...

    def create(self, *, state: CircuitBreakerState) -> CircuitBreakerState: ...

    def compare_and_set(
        self,
        *,
        circuit_id: str,
        expected_version: int,
        replacement: CircuitBreakerState,
    ) -> CircuitBreakerState: ...
