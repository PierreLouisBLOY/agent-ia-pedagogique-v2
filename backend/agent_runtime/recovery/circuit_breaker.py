from __future__ import annotations

import re
from dataclasses import dataclass, replace
from datetime import timedelta
from enum import StrEnum
from hashlib import sha256
from types import MappingProxyType
from typing import Self

from backend.agent_runtime.contracts import ErrorCategory, ErrorEnvelope
from backend.agent_runtime.registry import CapabilityExecutionRoute
from backend.shared_kernel.time import Instant

_SAFE_IDENTIFIER = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,254}$")
_CIRCUIT_ID = re.compile(r"^circuit:v1:[0-9a-f]{64}$")
_LEASE_ID = re.compile(r"^circuit-lease:v1:[0-9a-f]{64}$")


class CircuitBreakerStatus(StrEnum):
    CLOSED = "CLOSED"
    OPEN = "OPEN"
    HALF_OPEN = "HALF_OPEN"


class CircuitCheckDisposition(StrEnum):
    CLOSED = "CLOSED"
    OPEN_BLOCKED = "OPEN_BLOCKED"
    HALF_OPEN_PROBE_GRANTED = "HALF_OPEN_PROBE_GRANTED"
    HALF_OPEN_BUSY = "HALF_OPEN_BUSY"


class CircuitPreflightDisposition(StrEnum):
    CLOSED = "CLOSED"
    OPEN_BLOCKED = "OPEN_BLOCKED"
    HALF_OPEN_READY = "HALF_OPEN_READY"
    HALF_OPEN_BUSY = "HALF_OPEN_BUSY"


class CircuitCheckReasonCode(StrEnum):
    CIRCUIT_STATE_ABSENT = "CIRCUIT_STATE_ABSENT"
    CIRCUIT_CLOSED = "CIRCUIT_CLOSED"
    CIRCUIT_OPEN = "CIRCUIT_OPEN"
    HALF_OPEN_LEASE_GRANTED = "HALF_OPEN_LEASE_GRANTED"
    HALF_OPEN_LEASE_ACTIVE = "HALF_OPEN_LEASE_ACTIVE"


class CircuitBreakerErrorCode(StrEnum):
    INVALID_CIRCUIT_KEY = "INVALID_CIRCUIT_KEY"
    UNSUPPORTED_ROUTE = "UNSUPPORTED_ROUTE"
    CIRCUIT_ALREADY_EXISTS = "CIRCUIT_ALREADY_EXISTS"
    UNKNOWN_CIRCUIT = "UNKNOWN_CIRCUIT"
    VERSION_CONFLICT = "VERSION_CONFLICT"
    INVALID_TRANSITION = "INVALID_TRANSITION"
    CIRCUIT_OPEN = "CIRCUIT_OPEN"
    HALF_OPEN_BUSY = "HALF_OPEN_BUSY"
    LEASE_MISMATCH = "LEASE_MISMATCH"
    LEASE_EXPIRED = "LEASE_EXPIRED"
    OUTCOME_MISMATCH = "OUTCOME_MISMATCH"
    INVALID_POLICY_CONFIG = "INVALID_POLICY_CONFIG"


_ERROR_MESSAGES = MappingProxyType(
    {
        CircuitBreakerErrorCode.INVALID_CIRCUIT_KEY: "invalid circuit key",
        CircuitBreakerErrorCode.UNSUPPORTED_ROUTE: "unsupported circuit route",
        CircuitBreakerErrorCode.CIRCUIT_ALREADY_EXISTS: "circuit already exists",
        CircuitBreakerErrorCode.UNKNOWN_CIRCUIT: "unknown circuit",
        CircuitBreakerErrorCode.VERSION_CONFLICT: "circuit version conflict",
        CircuitBreakerErrorCode.INVALID_TRANSITION: "invalid circuit transition",
        CircuitBreakerErrorCode.CIRCUIT_OPEN: "circuit is open",
        CircuitBreakerErrorCode.HALF_OPEN_BUSY: "half-open circuit is busy",
        CircuitBreakerErrorCode.LEASE_MISMATCH: "circuit probe lease mismatch",
        CircuitBreakerErrorCode.LEASE_EXPIRED: "circuit probe lease expired",
        CircuitBreakerErrorCode.OUTCOME_MISMATCH: "circuit outcome mismatch",
        CircuitBreakerErrorCode.INVALID_POLICY_CONFIG: (
            "invalid circuit policy configuration"
        ),
    }
)


class CircuitBreakerError(ValueError):
    code: CircuitBreakerErrorCode

    def __init__(self, code: CircuitBreakerErrorCode) -> None:
        if not isinstance(code, CircuitBreakerErrorCode):
            raise TypeError("code must be a CircuitBreakerErrorCode")
        self.code = code
        super().__init__(_ERROR_MESSAGES[code])


@dataclass(frozen=True, slots=True)
class CircuitBreakerKey:
    execution_route: CapabilityExecutionRoute
    target_id: str
    binding_id: str

    def __post_init__(self) -> None:
        if not isinstance(self.execution_route, CapabilityExecutionRoute):
            raise TypeError("execution_route must be a CapabilityExecutionRoute")
        if self.execution_route is CapabilityExecutionRoute.RUNTIME:
            raise CircuitBreakerError(CircuitBreakerErrorCode.UNSUPPORTED_ROUTE)
        if self.execution_route not in {
            CapabilityExecutionRoute.UTILITY,
            CapabilityExecutionRoute.APPLICATION,
            CapabilityExecutionRoute.AGENT,
        }:
            raise CircuitBreakerError(CircuitBreakerErrorCode.UNSUPPORTED_ROUTE)
        try:
            _require_safe_identifier(self.target_id, "target_id")
            _require_safe_identifier(self.binding_id, "binding_id")
        except (TypeError, ValueError) as error:
            raise CircuitBreakerError(
                CircuitBreakerErrorCode.INVALID_CIRCUIT_KEY
            ) from error

    @property
    def circuit_id(self) -> str:
        return circuit_id_for(self)


def circuit_id_for(key: CircuitBreakerKey) -> str:
    if not isinstance(key, CircuitBreakerKey):
        raise TypeError("key must be a CircuitBreakerKey")
    digest = _digest_parts(
        "agent-runtime:circuit-breaker:v1",
        (key.execution_route.value, key.target_id, key.binding_id),
    )
    return f"circuit:v1:{digest}"


@dataclass(frozen=True, slots=True)
class CircuitBreakerPolicyConfig:
    failure_threshold: int
    failure_window_seconds: int
    open_duration_seconds: int
    half_open_lease_seconds: int
    half_open_success_threshold: int

    def __post_init__(self) -> None:
        try:
            for field_name in (
                "failure_threshold",
                "failure_window_seconds",
                "open_duration_seconds",
                "half_open_lease_seconds",
                "half_open_success_threshold",
            ):
                _require_positive_int(getattr(self, field_name), field_name)
        except (TypeError, ValueError) as error:
            raise CircuitBreakerError(
                CircuitBreakerErrorCode.INVALID_POLICY_CONFIG
            ) from error


@dataclass(frozen=True, slots=True)
class CircuitProbeLease:
    lease_id: str
    circuit_id: str
    state_version: int
    run_id: str
    step_id: str
    attempt: int
    acquired_at: Instant
    expires_at: Instant

    def __post_init__(self) -> None:
        if type(self.lease_id) is not str or not _LEASE_ID.fullmatch(self.lease_id):
            raise ValueError("lease_id must be an opaque circuit lease identifier")
        _require_circuit_id(self.circuit_id)
        _require_positive_int(self.state_version, "state_version")
        _require_safe_identifier(self.run_id, "run_id")
        _require_safe_identifier(self.step_id, "step_id")
        _require_positive_int(self.attempt, "attempt")
        _require_instant(self.acquired_at, "acquired_at")
        _require_instant(self.expires_at, "expires_at")
        if self.expires_at.value <= self.acquired_at.value:
            raise ValueError("expires_at must be > acquired_at")
        if self.lease_id != _lease_id_for(
            circuit_id=self.circuit_id,
            state_version=self.state_version,
            run_id=self.run_id,
            step_id=self.step_id,
            attempt=self.attempt,
            acquired_at=self.acquired_at,
        ):
            raise ValueError("lease_id must match circuit probe lease identity")

    @classmethod
    def create(
        cls,
        *,
        circuit_id: str,
        state_version: int,
        run_id: str,
        step_id: str,
        attempt: int,
        acquired_at: Instant,
        expires_at: Instant,
    ) -> Self:
        return cls(
            lease_id=_lease_id_for(
                circuit_id=circuit_id,
                state_version=state_version,
                run_id=run_id,
                step_id=step_id,
                attempt=attempt,
                acquired_at=acquired_at,
            ),
            circuit_id=circuit_id,
            state_version=state_version,
            run_id=run_id,
            step_id=step_id,
            attempt=attempt,
            acquired_at=acquired_at,
            expires_at=expires_at,
        )


@dataclass(frozen=True, slots=True)
class CircuitBreakerState:
    circuit_id: str
    key: CircuitBreakerKey
    version: int
    status: CircuitBreakerStatus
    recent_failure_times: tuple[Instant, ...]
    opened_at: Instant | None
    open_until: Instant | None
    half_open_lease: CircuitProbeLease | None
    half_open_successes: int
    created_at: Instant
    updated_at: Instant

    def __post_init__(self) -> None:
        _require_circuit_id(self.circuit_id)
        if not isinstance(self.key, CircuitBreakerKey):
            raise TypeError("key must be a CircuitBreakerKey")
        if self.circuit_id != self.key.circuit_id:
            raise ValueError("circuit_id must match key")
        _require_positive_int(self.version, "version")
        if not isinstance(self.status, CircuitBreakerStatus):
            raise TypeError("status must be a CircuitBreakerStatus")
        if not isinstance(self.recent_failure_times, tuple):
            raise TypeError("recent_failure_times must be a tuple")
        if any(
            not isinstance(item, Instant) for item in self.recent_failure_times
        ):
            raise TypeError("recent_failure_times must contain Instant values")
        if tuple(item.value for item in self.recent_failure_times) != tuple(
            sorted(item.value for item in self.recent_failure_times)
        ):
            raise ValueError("recent_failure_times must be monotonic")
        _require_optional_instant(self.opened_at, "opened_at")
        _require_optional_instant(self.open_until, "open_until")
        if self.half_open_lease is not None and not isinstance(
            self.half_open_lease, CircuitProbeLease
        ):
            raise TypeError("half_open_lease must be a CircuitProbeLease or None")
        _require_non_negative_int(self.half_open_successes, "half_open_successes")
        _require_instant(self.created_at, "created_at")
        _require_instant(self.updated_at, "updated_at")
        if self.updated_at.value < self.created_at.value:
            raise ValueError("updated_at must be >= created_at")
        if any(
            item.value > self.updated_at.value for item in self.recent_failure_times
        ):
            raise ValueError("failure timestamps cannot be newer than updated_at")
        if any(
            item.value < self.created_at.value for item in self.recent_failure_times
        ):
            raise ValueError("failure timestamps cannot predate created_at")
        self._validate_status()

    def _validate_status(self) -> None:
        if self.status is CircuitBreakerStatus.CLOSED:
            if self.opened_at is not None or self.open_until is not None:
                raise ValueError("CLOSED cannot retain open timestamps")
            if self.half_open_lease is not None or self.half_open_successes != 0:
                raise ValueError("CLOSED cannot retain half-open state")
            return
        if self.opened_at is None or self.open_until is None:
            raise ValueError("OPEN and HALF_OPEN require open provenance")
        if self.open_until.value <= self.opened_at.value:
            raise ValueError("open_until must be > opened_at")
        if self.opened_at.value < self.created_at.value:
            raise ValueError("opened_at must be >= created_at")
        if self.updated_at.value < self.opened_at.value:
            raise ValueError("updated_at must be >= opened_at")
        if (
            not self.recent_failure_times
            or self.recent_failure_times[-1] != self.opened_at
        ):
            raise ValueError("open provenance must match the latest failure")
        if self.status is CircuitBreakerStatus.OPEN:
            if self.half_open_lease is not None or self.half_open_successes != 0:
                raise ValueError("OPEN cannot retain half-open state")
            return
        if self.updated_at.value < self.open_until.value:
            raise ValueError("HALF_OPEN requires elapsed open duration")
        lease = self.half_open_lease
        if lease is not None:
            if lease.circuit_id != self.circuit_id:
                raise ValueError("half-open lease must match circuit_id")
            if lease.state_version != self.version:
                raise ValueError("half-open lease must match state version")
            if lease.acquired_at != self.updated_at:
                raise ValueError("half-open lease acquisition must match updated_at")
            if lease.acquired_at.value < self.open_until.value:
                raise ValueError("half-open lease requires elapsed open duration")


@dataclass(frozen=True, slots=True)
class CircuitCheckRequest:
    key: CircuitBreakerKey
    run_id: str
    step_id: str
    attempt: int

    def __post_init__(self) -> None:
        if not isinstance(self.key, CircuitBreakerKey):
            raise TypeError("key must be a CircuitBreakerKey")
        _require_safe_identifier(self.run_id, "run_id")
        _require_safe_identifier(self.step_id, "step_id")
        _require_positive_int(self.attempt, "attempt")


@dataclass(frozen=True, slots=True)
class CircuitCheckDecision:
    disposition: CircuitCheckDisposition
    circuit_id: str
    state_version: int
    reason_codes: tuple[CircuitCheckReasonCode, ...]
    lease: CircuitProbeLease | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.disposition, CircuitCheckDisposition):
            raise TypeError("disposition must be a CircuitCheckDisposition")
        _require_circuit_id(self.circuit_id)
        _require_non_negative_int(self.state_version, "state_version")
        if not isinstance(self.reason_codes, tuple) or not self.reason_codes:
            raise ValueError("reason_codes must be a non-empty tuple")
        if any(
            not isinstance(item, CircuitCheckReasonCode)
            for item in self.reason_codes
        ):
            raise TypeError("reason_codes must contain CircuitCheckReasonCode values")
        if len(set(self.reason_codes)) != len(self.reason_codes):
            raise ValueError("reason_codes must not contain duplicates")
        if self.disposition is CircuitCheckDisposition.HALF_OPEN_PROBE_GRANTED:
            if not isinstance(self.lease, CircuitProbeLease):
                raise TypeError("granted half-open probe requires a lease")
            if self.lease.circuit_id != self.circuit_id:
                raise ValueError("decision lease must match circuit_id")
            if self.lease.state_version != self.state_version:
                raise ValueError("decision lease must match state version")
        elif self.lease is not None:
            raise ValueError("only a granted half-open probe can contain a lease")


@dataclass(frozen=True, slots=True)
class CircuitPreflightDecision:
    """Read-only circuit observation; HALF_OPEN_READY grants no probe lease."""

    disposition: CircuitPreflightDisposition
    circuit_id: str
    state_version: int

    def __post_init__(self) -> None:
        if not isinstance(self.disposition, CircuitPreflightDisposition):
            raise TypeError("disposition must be a CircuitPreflightDisposition")
        _require_circuit_id(self.circuit_id)
        _require_non_negative_int(self.state_version, "state_version")


@dataclass(frozen=True, slots=True)
class CircuitOutcomeRecord:
    key: CircuitBreakerKey
    expected_version: int
    observed_at: Instant
    error: ErrorEnvelope | None = None
    lease: CircuitProbeLease | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.key, CircuitBreakerKey):
            raise TypeError("key must be a CircuitBreakerKey")
        _require_non_negative_int(self.expected_version, "expected_version")
        _require_instant(self.observed_at, "observed_at")
        if self.error is not None and not isinstance(self.error, ErrorEnvelope):
            raise TypeError("error must be an ErrorEnvelope or None")
        if self.lease is not None and not isinstance(
            self.lease, CircuitProbeLease
        ):
            raise TypeError("lease must be a CircuitProbeLease or None")


_COUNTED_ERROR_CATEGORIES = frozenset(
    {
        ErrorCategory.TRANSIENT,
        ErrorCategory.PROVIDER,
        ErrorCategory.TOOL,
    }
)


@dataclass(frozen=True, slots=True)
class CircuitBreakerPolicy:
    """Pure technical health policy; it grants no execution authority."""

    def classify_error(self, error: ErrorEnvelope) -> bool:
        if not isinstance(error, ErrorEnvelope):
            raise TypeError("error must be an ErrorEnvelope")
        return error.category in _COUNTED_ERROR_CATEGORIES

    def classify_check(
        self,
        *,
        state: CircuitBreakerState,
        now: Instant,
    ) -> CircuitCheckDisposition:
        _require_state(state)
        _require_now(state, now)
        if state.status is CircuitBreakerStatus.CLOSED:
            return CircuitCheckDisposition.CLOSED
        if state.status is CircuitBreakerStatus.OPEN:
            if now.value < _required_instant(state.open_until).value:
                return CircuitCheckDisposition.OPEN_BLOCKED
            return CircuitCheckDisposition.HALF_OPEN_PROBE_GRANTED
        lease = state.half_open_lease
        if lease is not None and now.value < lease.expires_at.value:
            return CircuitCheckDisposition.HALF_OPEN_BUSY
        return CircuitCheckDisposition.HALF_OPEN_PROBE_GRANTED

    def prepare_initial_failure(
        self,
        *,
        key: CircuitBreakerKey,
        error: ErrorEnvelope,
        now: Instant,
        config: CircuitBreakerPolicyConfig,
    ) -> CircuitBreakerState | None:
        _require_key(key)
        _require_config(config)
        _require_instant(now, "now")
        if not self.classify_error(error):
            return None
        status = (
            CircuitBreakerStatus.OPEN
            if config.failure_threshold == 1
            else CircuitBreakerStatus.CLOSED
        )
        return CircuitBreakerState(
            circuit_id=key.circuit_id,
            key=key,
            version=1,
            status=status,
            recent_failure_times=(now,),
            opened_at=now if status is CircuitBreakerStatus.OPEN else None,
            open_until=(
                Instant(now.value + timedelta(seconds=config.open_duration_seconds))
                if status is CircuitBreakerStatus.OPEN
                else None
            ),
            half_open_lease=None,
            half_open_successes=0,
            created_at=now,
            updated_at=now,
        )

    def prepare_half_open_lease(
        self,
        *,
        state: CircuitBreakerState,
        request: CircuitCheckRequest,
        now: Instant,
        config: CircuitBreakerPolicyConfig,
    ) -> CircuitBreakerState:
        _require_state(state)
        _require_config(config)
        _require_now(state, now)
        if request.key != state.key:
            raise CircuitBreakerError(CircuitBreakerErrorCode.INVALID_CIRCUIT_KEY)
        disposition = self.classify_check(state=state, now=now)
        if disposition is CircuitCheckDisposition.OPEN_BLOCKED:
            raise CircuitBreakerError(CircuitBreakerErrorCode.CIRCUIT_OPEN)
        if disposition is CircuitCheckDisposition.HALF_OPEN_BUSY:
            raise CircuitBreakerError(CircuitBreakerErrorCode.HALF_OPEN_BUSY)
        if disposition is CircuitCheckDisposition.CLOSED:
            raise CircuitBreakerError(CircuitBreakerErrorCode.INVALID_TRANSITION)
        next_version = state.version + 1
        lease = CircuitProbeLease.create(
            circuit_id=state.circuit_id,
            state_version=next_version,
            run_id=request.run_id,
            step_id=request.step_id,
            attempt=request.attempt,
            acquired_at=now,
            expires_at=Instant(
                now.value + timedelta(seconds=config.half_open_lease_seconds)
            ),
        )
        replacement = replace(
            state,
            version=next_version,
            status=CircuitBreakerStatus.HALF_OPEN,
            half_open_lease=lease,
            updated_at=now,
        )
        self.validate_transition(current=state, replacement=replacement)
        return replacement

    def prepare_lease_expiry(
        self,
        *,
        state: CircuitBreakerState,
        request: CircuitCheckRequest,
        now: Instant,
        config: CircuitBreakerPolicyConfig,
    ) -> CircuitBreakerState:
        return self.prepare_half_open_lease(
            state=state,
            request=request,
            now=now,
            config=config,
        )

    def prepare_success(
        self,
        *,
        state: CircuitBreakerState,
        now: Instant,
        config: CircuitBreakerPolicyConfig,
        lease: CircuitProbeLease | None = None,
    ) -> CircuitBreakerState:
        _require_state(state)
        _require_config(config)
        _require_now(state, now)
        if state.status is CircuitBreakerStatus.OPEN:
            raise CircuitBreakerError(CircuitBreakerErrorCode.INVALID_TRANSITION)
        if state.status is CircuitBreakerStatus.CLOSED:
            if lease is not None:
                raise CircuitBreakerError(CircuitBreakerErrorCode.LEASE_MISMATCH)
            failures = _windowed_failures(state, now, config)
            if failures == state.recent_failure_times:
                return state
            replacement = replace(
                state,
                version=state.version + 1,
                recent_failure_times=failures,
                updated_at=now,
            )
            self.validate_transition(current=state, replacement=replacement)
            return replacement
        self._require_active_lease(state=state, lease=lease, observed_at=now)
        successes = state.half_open_successes + 1
        if successes >= config.half_open_success_threshold:
            replacement = replace(
                state,
                version=state.version + 1,
                status=CircuitBreakerStatus.CLOSED,
                recent_failure_times=(),
                opened_at=None,
                open_until=None,
                half_open_lease=None,
                half_open_successes=0,
                updated_at=now,
            )
        else:
            replacement = replace(
                state,
                version=state.version + 1,
                half_open_lease=None,
                half_open_successes=successes,
                updated_at=now,
            )
        self.validate_transition(current=state, replacement=replacement)
        return replacement

    def prepare_failure(
        self,
        *,
        state: CircuitBreakerState,
        error: ErrorEnvelope,
        now: Instant,
        config: CircuitBreakerPolicyConfig,
        lease: CircuitProbeLease | None = None,
    ) -> CircuitBreakerState:
        _require_state(state)
        _require_config(config)
        _require_now(state, now)
        counted = self.classify_error(error)
        if state.status is CircuitBreakerStatus.OPEN:
            raise CircuitBreakerError(CircuitBreakerErrorCode.INVALID_TRANSITION)
        if state.status is CircuitBreakerStatus.HALF_OPEN:
            active_lease = self._require_active_lease(
                state=state,
                lease=lease,
                observed_at=now,
            )
            if error.step_id != active_lease.step_id or (
                error.attempt != active_lease.attempt
            ):
                raise CircuitBreakerError(CircuitBreakerErrorCode.OUTCOME_MISMATCH)
            if counted:
                replacement = replace(
                    state,
                    version=state.version + 1,
                    status=CircuitBreakerStatus.OPEN,
                    recent_failure_times=(now,),
                    opened_at=now,
                    open_until=Instant(
                        now.value
                        + timedelta(seconds=config.open_duration_seconds)
                    ),
                    half_open_lease=None,
                    half_open_successes=0,
                    updated_at=now,
                )
            else:
                replacement = replace(
                    state,
                    version=state.version + 1,
                    half_open_lease=None,
                    updated_at=now,
                )
            self.validate_transition(current=state, replacement=replacement)
            return replacement
        if lease is not None:
            raise CircuitBreakerError(CircuitBreakerErrorCode.LEASE_MISMATCH)
        failures = _windowed_failures(state, now, config)
        if counted:
            failures = (*failures, now)[-config.failure_threshold :]
        if failures == state.recent_failure_times:
            return state
        opens = counted and len(failures) >= config.failure_threshold
        replacement = replace(
            state,
            version=state.version + 1,
            status=(
                CircuitBreakerStatus.OPEN if opens else CircuitBreakerStatus.CLOSED
            ),
            recent_failure_times=failures,
            opened_at=now if opens else None,
            open_until=(
                Instant(now.value + timedelta(seconds=config.open_duration_seconds))
                if opens
                else None
            ),
            updated_at=now,
        )
        self.validate_transition(current=state, replacement=replacement)
        return replacement

    def validate_transition(
        self,
        *,
        current: CircuitBreakerState,
        replacement: CircuitBreakerState,
    ) -> None:
        _require_state(current)
        _require_state(replacement)
        if replacement.version != current.version + 1:
            raise CircuitBreakerError(CircuitBreakerErrorCode.VERSION_CONFLICT)
        if (
            replacement.circuit_id != current.circuit_id
            or replacement.key != current.key
            or replacement.created_at != current.created_at
            or replacement.updated_at.value < current.updated_at.value
        ):
            raise CircuitBreakerError(CircuitBreakerErrorCode.INVALID_TRANSITION)
        allowed = {
            CircuitBreakerStatus.CLOSED: {
                CircuitBreakerStatus.CLOSED,
                CircuitBreakerStatus.OPEN,
            },
            CircuitBreakerStatus.OPEN: {CircuitBreakerStatus.HALF_OPEN},
            CircuitBreakerStatus.HALF_OPEN: {
                CircuitBreakerStatus.HALF_OPEN,
                CircuitBreakerStatus.OPEN,
                CircuitBreakerStatus.CLOSED,
            },
        }
        if replacement.status not in allowed[current.status]:
            raise CircuitBreakerError(CircuitBreakerErrorCode.INVALID_TRANSITION)
        if current.status is CircuitBreakerStatus.HALF_OPEN and (
            replacement.status is CircuitBreakerStatus.HALF_OPEN
            and current.half_open_lease is not None
            and replacement.half_open_lease == current.half_open_lease
        ):
            raise CircuitBreakerError(CircuitBreakerErrorCode.INVALID_TRANSITION)

    @staticmethod
    def _require_active_lease(
        *,
        state: CircuitBreakerState,
        lease: CircuitProbeLease | None,
        observed_at: Instant,
    ) -> CircuitProbeLease:
        current = state.half_open_lease
        if current is None or lease is None or current != lease:
            raise CircuitBreakerError(CircuitBreakerErrorCode.LEASE_MISMATCH)
        if observed_at.value < current.acquired_at.value:
            raise CircuitBreakerError(CircuitBreakerErrorCode.OUTCOME_MISMATCH)
        if observed_at.value >= current.expires_at.value:
            raise CircuitBreakerError(CircuitBreakerErrorCode.LEASE_EXPIRED)
        return current


def _windowed_failures(
    state: CircuitBreakerState,
    now: Instant,
    config: CircuitBreakerPolicyConfig,
) -> tuple[Instant, ...]:
    cutoff = now.value - timedelta(seconds=config.failure_window_seconds)
    return tuple(
        item for item in state.recent_failure_times if item.value >= cutoff
    )[-config.failure_threshold :]


def _lease_id_for(
    *,
    circuit_id: str,
    state_version: int,
    run_id: str,
    step_id: str,
    attempt: int,
    acquired_at: Instant,
) -> str:
    _require_circuit_id(circuit_id)
    _require_positive_int(state_version, "state_version")
    _require_safe_identifier(run_id, "run_id")
    _require_safe_identifier(step_id, "step_id")
    _require_positive_int(attempt, "attempt")
    _require_instant(acquired_at, "acquired_at")
    digest = _digest_parts(
        "agent-runtime:circuit-probe-lease:v1",
        (
            circuit_id,
            str(state_version),
            run_id,
            step_id,
            str(attempt),
            acquired_at.value.isoformat(timespec="microseconds"),
        ),
    )
    return f"circuit-lease:v1:{digest}"


def _digest_parts(domain: str, parts: tuple[str, ...]) -> str:
    digest = sha256()
    digest.update(domain.encode("ascii"))
    digest.update(b"\x00")
    for part in parts:
        raw = part.encode("utf-8")
        digest.update(len(raw).to_bytes(8, "big"))
        digest.update(raw)
    return digest.hexdigest()


def _require_key(value: CircuitBreakerKey) -> None:
    if not isinstance(value, CircuitBreakerKey):
        raise TypeError("key must be a CircuitBreakerKey")


def _require_state(value: CircuitBreakerState) -> None:
    if not isinstance(value, CircuitBreakerState):
        raise TypeError("state must be a CircuitBreakerState")


def _require_config(value: CircuitBreakerPolicyConfig) -> None:
    if not isinstance(value, CircuitBreakerPolicyConfig):
        raise TypeError("config must be a CircuitBreakerPolicyConfig")


def _require_now(state: CircuitBreakerState, now: Instant) -> None:
    _require_instant(now, "now")
    if now.value < state.updated_at.value:
        raise CircuitBreakerError(CircuitBreakerErrorCode.INVALID_TRANSITION)


def _require_safe_identifier(value: str, field_name: str) -> None:
    if type(value) is not str:
        raise TypeError(f"{field_name} must be a string")
    if not _SAFE_IDENTIFIER.fullmatch(value):
        raise ValueError(f"{field_name} must be a safe identifier")


def _require_circuit_id(value: str) -> None:
    if type(value) is not str:
        raise TypeError("circuit_id must be a string")
    if not _CIRCUIT_ID.fullmatch(value):
        raise ValueError("circuit_id must be an opaque circuit identifier")


def _require_positive_int(value: int, field_name: str) -> None:
    if type(value) is not int:
        raise TypeError(f"{field_name} must be an integer")
    if value < 1:
        raise ValueError(f"{field_name} must be >= 1")


def _require_non_negative_int(value: int, field_name: str) -> None:
    if type(value) is not int:
        raise TypeError(f"{field_name} must be an integer")
    if value < 0:
        raise ValueError(f"{field_name} must be >= 0")


def _require_instant(value: Instant, field_name: str) -> None:
    if not isinstance(value, Instant):
        raise TypeError(f"{field_name} must be an Instant")


def _require_optional_instant(value: Instant | None, field_name: str) -> None:
    if value is not None:
        _require_instant(value, field_name)


def _required_instant(value: Instant | None) -> Instant:
    if value is None:
        raise CircuitBreakerError(CircuitBreakerErrorCode.INVALID_TRANSITION)
    return value
