from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from threading import Lock

from backend.agent_runtime.contracts import (
    EffectState,
    ErrorCategory,
    ErrorEnvelope,
    ErrorSeverity,
    ErrorSource,
    RecommendedAction,
)
from backend.agent_runtime.recovery import (
    CircuitBreakerError,
    CircuitBreakerErrorCode,
    CircuitBreakerKey,
    CircuitBreakerPolicy,
    CircuitBreakerPolicyConfig,
    CircuitBreakerState,
    CircuitBreakerStatus,
)
from backend.agent_runtime.registry import CapabilityExecutionRoute
from backend.shared_kernel.time import Instant

NOW = Instant(datetime(2026, 8, 27, 12, 0, tzinfo=UTC))
CONFIG = CircuitBreakerPolicyConfig(
    failure_threshold=3,
    failure_window_seconds=60,
    open_duration_seconds=30,
    half_open_lease_seconds=10,
    half_open_success_threshold=2,
)


class InMemoryCircuitBreakerStore:
    """Lock-based test fake; Phase F provides no production store."""

    def __init__(
        self,
        *,
        initial_states: tuple[CircuitBreakerState, ...] = (),
        policy: CircuitBreakerPolicy | None = None,
        on_get: Callable[[], None] | None = None,
    ) -> None:
        self._policy = policy or CircuitBreakerPolicy()
        self._lock = Lock()
        self._states: dict[str, CircuitBreakerState] = {}
        self._on_get = on_get
        self.get_calls = 0
        self.create_calls = 0
        self.cas_calls = 0
        for state in initial_states:
            if not isinstance(state, CircuitBreakerState):
                raise TypeError("initial_states must contain CircuitBreakerState values")
            if state.circuit_id in self._states:
                raise ValueError("initial_states must have distinct circuit IDs")
            self._states[state.circuit_id] = state

    def get(self, *, circuit_id: str) -> CircuitBreakerState | None:
        with self._lock:
            self.get_calls += 1
            state = self._states.get(circuit_id)
        if self._on_get is not None:
            self._on_get()
        return state

    def create(self, *, state: CircuitBreakerState) -> CircuitBreakerState:
        with self._lock:
            self.create_calls += 1
            if state.circuit_id in self._states:
                raise CircuitBreakerError(
                    CircuitBreakerErrorCode.CIRCUIT_ALREADY_EXISTS
                )
            self._states[state.circuit_id] = state
            return state

    def compare_and_set(
        self,
        *,
        circuit_id: str,
        expected_version: int,
        replacement: CircuitBreakerState,
    ) -> CircuitBreakerState:
        with self._lock:
            self.cas_calls += 1
            current = self._states.get(circuit_id)
            if current is None:
                raise CircuitBreakerError(CircuitBreakerErrorCode.UNKNOWN_CIRCUIT)
            if current.version != expected_version:
                raise CircuitBreakerError(CircuitBreakerErrorCode.VERSION_CONFLICT)
            self._policy.validate_transition(
                current=current,
                replacement=replacement,
            )
            self._states[circuit_id] = replacement
            return replacement


def make_key(
    *,
    route: CapabilityExecutionRoute = CapabilityExecutionRoute.UTILITY,
    target_id: str = "tool.render_document",
    binding_id: str = "binding.render.v1",
) -> CircuitBreakerKey:
    return CircuitBreakerKey(
        execution_route=route,
        target_id=target_id,
        binding_id=binding_id,
    )


def make_error(
    category: ErrorCategory = ErrorCategory.TRANSIENT,
    *,
    step_id: str = "step-circuit",
    attempt: int = 1,
) -> ErrorEnvelope:
    return ErrorEnvelope(
        error_code="DEPENDENCY_FAILURE",
        category=category,
        source=ErrorSource.PROVIDER,
        retryable=True,
        severity=ErrorSeverity.ERROR,
        message="dependency failed",
        step_id=step_id,
        attempt=attempt,
        effect_state=EffectState.NONE,
        recommended_action=RecommendedAction.RETRY,
    )


def make_closed_state(
    *,
    key: CircuitBreakerKey | None = None,
    version: int = 1,
    failures: tuple[Instant, ...] = (),
    updated_at: Instant = NOW,
) -> CircuitBreakerState:
    target = key or make_key()
    return CircuitBreakerState(
        circuit_id=target.circuit_id,
        key=target,
        version=version,
        status=CircuitBreakerStatus.CLOSED,
        recent_failure_times=failures,
        opened_at=None,
        open_until=None,
        half_open_lease=None,
        half_open_successes=0,
        created_at=Instant(NOW.value - timedelta(minutes=2)),
        updated_at=updated_at,
    )


def make_open_state(
    *,
    key: CircuitBreakerKey | None = None,
    version: int = 1,
    opened_at: Instant = NOW,
    open_until: Instant | None = None,
) -> CircuitBreakerState:
    target = key or make_key()
    return CircuitBreakerState(
        circuit_id=target.circuit_id,
        key=target,
        version=version,
        status=CircuitBreakerStatus.OPEN,
        recent_failure_times=(opened_at,),
        opened_at=opened_at,
        open_until=open_until
        or Instant(opened_at.value + timedelta(seconds=CONFIG.open_duration_seconds)),
        half_open_lease=None,
        half_open_successes=0,
        created_at=Instant(opened_at.value - timedelta(minutes=2)),
        updated_at=opened_at,
    )
