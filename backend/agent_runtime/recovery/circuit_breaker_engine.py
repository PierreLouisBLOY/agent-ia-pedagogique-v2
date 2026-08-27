from __future__ import annotations

from dataclasses import dataclass, field

from backend.agent_runtime.recovery.circuit_breaker import (
    CircuitBreakerError,
    CircuitBreakerErrorCode,
    CircuitBreakerPolicy,
    CircuitBreakerPolicyConfig,
    CircuitBreakerState,
    CircuitCheckDecision,
    CircuitCheckDisposition,
    CircuitCheckReasonCode,
    CircuitCheckRequest,
    CircuitOutcomeRecord,
    CircuitPreflightDecision,
    CircuitPreflightDisposition,
)
from backend.agent_runtime.recovery.circuit_breaker_ports import (
    CircuitBreakerStorePort,
)
from backend.shared_kernel.time import Instant


@dataclass(frozen=True, slots=True)
class CircuitBreakerEngine:
    """One-read/one-write controller; it never calls the protected dependency."""

    store: CircuitBreakerStorePort
    config: CircuitBreakerPolicyConfig
    policy: CircuitBreakerPolicy = field(default_factory=CircuitBreakerPolicy)

    def __post_init__(self) -> None:
        if not isinstance(self.store, CircuitBreakerStorePort):
            raise TypeError("store must implement CircuitBreakerStorePort")
        if not isinstance(self.config, CircuitBreakerPolicyConfig):
            raise TypeError("config must be a CircuitBreakerPolicyConfig")
        if not isinstance(self.policy, CircuitBreakerPolicy):
            raise TypeError("policy must be a CircuitBreakerPolicy")

    def check(
        self,
        *,
        request: CircuitCheckRequest,
        now: Instant,
    ) -> CircuitCheckDecision:
        if not isinstance(request, CircuitCheckRequest):
            raise TypeError("request must be a CircuitCheckRequest")
        if not isinstance(now, Instant):
            raise TypeError("now must be an Instant")
        circuit_id = request.key.circuit_id
        state = self.store.get(circuit_id=circuit_id)
        if state is None:
            return CircuitCheckDecision(
                disposition=CircuitCheckDisposition.CLOSED,
                circuit_id=circuit_id,
                state_version=0,
                reason_codes=(CircuitCheckReasonCode.CIRCUIT_STATE_ABSENT,),
            )
        self._validate_loaded_state(state=state, request=request)
        disposition = self.policy.classify_check(state=state, now=now)
        if disposition is CircuitCheckDisposition.CLOSED:
            return CircuitCheckDecision(
                disposition=disposition,
                circuit_id=state.circuit_id,
                state_version=state.version,
                reason_codes=(CircuitCheckReasonCode.CIRCUIT_CLOSED,),
            )
        if disposition is CircuitCheckDisposition.OPEN_BLOCKED:
            return CircuitCheckDecision(
                disposition=disposition,
                circuit_id=state.circuit_id,
                state_version=state.version,
                reason_codes=(CircuitCheckReasonCode.CIRCUIT_OPEN,),
            )
        if disposition is CircuitCheckDisposition.HALF_OPEN_BUSY:
            return CircuitCheckDecision(
                disposition=disposition,
                circuit_id=state.circuit_id,
                state_version=state.version,
                reason_codes=(CircuitCheckReasonCode.HALF_OPEN_LEASE_ACTIVE,),
            )
        replacement = self.policy.prepare_half_open_lease(
            state=state,
            request=request,
            now=now,
            config=self.config,
        )
        stored = self.store.compare_and_set(
            circuit_id=state.circuit_id,
            expected_version=state.version,
            replacement=replacement,
        )
        if stored != replacement or stored.half_open_lease is None:
            raise CircuitBreakerError(CircuitBreakerErrorCode.INVALID_TRANSITION)
        return CircuitCheckDecision(
            disposition=CircuitCheckDisposition.HALF_OPEN_PROBE_GRANTED,
            circuit_id=stored.circuit_id,
            state_version=stored.version,
            reason_codes=(CircuitCheckReasonCode.HALF_OPEN_LEASE_GRANTED,),
            lease=stored.half_open_lease,
        )

    def inspect(
        self,
        *,
        request: CircuitCheckRequest,
        now: Instant,
    ) -> CircuitPreflightDecision:
        """Observe launchability without acquiring a half-open lease."""
        if not isinstance(request, CircuitCheckRequest):
            raise TypeError("request must be a CircuitCheckRequest")
        if not isinstance(now, Instant):
            raise TypeError("now must be an Instant")
        circuit_id = request.key.circuit_id
        state = self.store.get(circuit_id=circuit_id)
        if state is None:
            return CircuitPreflightDecision(
                CircuitPreflightDisposition.CLOSED,
                circuit_id,
                0,
            )
        self._validate_loaded_state(state=state, request=request)
        disposition = self.policy.classify_check(state=state, now=now)
        mapped = {
            CircuitCheckDisposition.CLOSED: CircuitPreflightDisposition.CLOSED,
            CircuitCheckDisposition.OPEN_BLOCKED: (
                CircuitPreflightDisposition.OPEN_BLOCKED
            ),
            CircuitCheckDisposition.HALF_OPEN_PROBE_GRANTED: (
                CircuitPreflightDisposition.HALF_OPEN_READY
            ),
            CircuitCheckDisposition.HALF_OPEN_BUSY: (
                CircuitPreflightDisposition.HALF_OPEN_BUSY
            ),
        }[disposition]
        return CircuitPreflightDecision(mapped, circuit_id, state.version)

    def record_outcome(
        self,
        *,
        outcome: CircuitOutcomeRecord,
    ) -> CircuitBreakerState | None:
        if not isinstance(outcome, CircuitOutcomeRecord):
            raise TypeError("outcome must be a CircuitOutcomeRecord")
        circuit_id = outcome.key.circuit_id
        state = self.store.get(circuit_id=circuit_id)
        if state is None:
            return self._record_absent_outcome(outcome)
        if state.key != outcome.key:
            raise CircuitBreakerError(CircuitBreakerErrorCode.INVALID_CIRCUIT_KEY)
        if state.version != outcome.expected_version:
            raise CircuitBreakerError(CircuitBreakerErrorCode.VERSION_CONFLICT)
        replacement = self._prepare_outcome(state=state, outcome=outcome)
        if replacement is state:
            return state
        stored = self.store.compare_and_set(
            circuit_id=circuit_id,
            expected_version=state.version,
            replacement=replacement,
        )
        if stored != replacement:
            raise CircuitBreakerError(CircuitBreakerErrorCode.INVALID_TRANSITION)
        return stored

    def _record_absent_outcome(
        self,
        outcome: CircuitOutcomeRecord,
    ) -> CircuitBreakerState | None:
        if outcome.expected_version != 0:
            raise CircuitBreakerError(CircuitBreakerErrorCode.UNKNOWN_CIRCUIT)
        if outcome.lease is not None:
            raise CircuitBreakerError(CircuitBreakerErrorCode.LEASE_MISMATCH)
        if outcome.error is None:
            return None
        initial = self.policy.prepare_initial_failure(
            key=outcome.key,
            error=outcome.error,
            now=outcome.observed_at,
            config=self.config,
        )
        if initial is None:
            return None
        stored = self.store.create(state=initial)
        if stored != initial:
            raise CircuitBreakerError(CircuitBreakerErrorCode.INVALID_TRANSITION)
        return stored

    def _prepare_outcome(
        self,
        *,
        state: CircuitBreakerState,
        outcome: CircuitOutcomeRecord,
    ) -> CircuitBreakerState:
        if outcome.error is None:
            return self.policy.prepare_success(
                state=state,
                now=outcome.observed_at,
                config=self.config,
                lease=outcome.lease,
            )
        return self.policy.prepare_failure(
            state=state,
            error=outcome.error,
            now=outcome.observed_at,
            config=self.config,
            lease=outcome.lease,
        )

    @staticmethod
    def _validate_loaded_state(
        *,
        state: CircuitBreakerState,
        request: CircuitCheckRequest,
    ) -> None:
        if not isinstance(state, CircuitBreakerState):
            raise CircuitBreakerError(CircuitBreakerErrorCode.INVALID_TRANSITION)
        if state.circuit_id != request.key.circuit_id or state.key != request.key:
            raise CircuitBreakerError(CircuitBreakerErrorCode.INVALID_CIRCUIT_KEY)
