from __future__ import annotations

from dataclasses import fields, replace
from datetime import timedelta

import pytest

from backend.agent_runtime.recovery import (
    CircuitBreakerError,
    CircuitBreakerErrorCode,
    CircuitBreakerKey,
    CircuitBreakerPolicyConfig,
    CircuitBreakerState,
    CircuitBreakerStatus,
    CircuitProbeLease,
    circuit_id_for,
)
from backend.agent_runtime.registry import CapabilityExecutionRoute
from backend.shared_kernel.time import Instant
from tests.support.circuit_breaker_fakes import NOW, make_closed_state, make_key


@pytest.mark.parametrize(
    "route",
    [
        CapabilityExecutionRoute.UTILITY,
        CapabilityExecutionRoute.APPLICATION,
        CapabilityExecutionRoute.AGENT,
    ],
)
def test_supported_routes_have_deterministic_opaque_id(
    route: CapabilityExecutionRoute,
) -> None:
    key = make_key(route=route)

    assert key.circuit_id == circuit_id_for(key)
    assert key.circuit_id == make_key(route=route).circuit_id
    assert key.circuit_id.startswith("circuit:v1:")
    assert key.target_id not in key.circuit_id
    assert key.binding_id not in key.circuit_id


def test_runtime_route_is_rejected() -> None:
    with pytest.raises(CircuitBreakerError) as raised:
        make_key(route=CapabilityExecutionRoute.RUNTIME)
    assert raised.value.code is CircuitBreakerErrorCode.UNSUPPORTED_ROUTE


def test_binding_and_target_each_change_circuit_id() -> None:
    baseline = make_key()
    other_binding = make_key(binding_id="binding.render.v2")
    other_target = make_key(target_id="tool.convert_format")

    assert len({baseline.circuit_id, other_binding.circuit_id, other_target.circuit_id}) == 3


@pytest.mark.parametrize(
    ("field_name", "value"),
    [
        ("target_id", "https://provider.example/api"),
        ("target_id", "C:/private/adapter"),
        ("binding_id", "provider/secret"),
        ("binding_id", ""),
    ],
)
def test_key_rejects_url_path_or_unsafe_binding(
    field_name: str,
    value: str,
) -> None:
    values = {
        "execution_route": CapabilityExecutionRoute.UTILITY,
        "target_id": "tool.render_document",
        "binding_id": "binding.render.v1",
        field_name: value,
    }
    with pytest.raises(CircuitBreakerError) as raised:
        CircuitBreakerKey(**values)  # type: ignore[arg-type]
    assert raised.value.code is CircuitBreakerErrorCode.INVALID_CIRCUIT_KEY


@pytest.mark.parametrize(
    "field_name",
    [
        "failure_threshold",
        "failure_window_seconds",
        "open_duration_seconds",
        "half_open_lease_seconds",
        "half_open_success_threshold",
    ],
)
def test_policy_config_values_are_strictly_positive(field_name: str) -> None:
    values = {
        "failure_threshold": 3,
        "failure_window_seconds": 60,
        "open_duration_seconds": 30,
        "half_open_lease_seconds": 10,
        "half_open_success_threshold": 2,
        field_name: 0,
    }
    with pytest.raises(CircuitBreakerError) as raised:
        CircuitBreakerPolicyConfig(**values)
    assert raised.value.code is CircuitBreakerErrorCode.INVALID_POLICY_CONFIG


def test_closed_and_open_state_invariants_are_exact() -> None:
    closed = make_closed_state()
    with pytest.raises(ValueError, match="CLOSED"):
        replace(closed, opened_at=NOW)
    with pytest.raises(ValueError, match="require open provenance"):
        replace(closed, status=CircuitBreakerStatus.OPEN)

    opened_at = NOW
    open_until = Instant(NOW.value + timedelta(seconds=30))
    opened = replace(
        closed,
        status=CircuitBreakerStatus.OPEN,
        recent_failure_times=(NOW,),
        opened_at=opened_at,
        open_until=open_until,
    )
    assert opened.status is CircuitBreakerStatus.OPEN
    with pytest.raises(ValueError, match="open_until"):
        replace(opened, open_until=opened_at)


def test_half_open_lease_is_exact_and_bound_to_state_version() -> None:
    key = make_key()
    acquired = Instant(NOW.value + timedelta(seconds=30))
    lease = CircuitProbeLease.create(
        circuit_id=key.circuit_id,
        state_version=2,
        run_id="run-circuit",
        step_id="step-circuit",
        attempt=1,
        acquired_at=acquired,
        expires_at=Instant(acquired.value + timedelta(seconds=10)),
    )
    state = CircuitBreakerState(
        circuit_id=key.circuit_id,
        key=key,
        version=2,
        status=CircuitBreakerStatus.HALF_OPEN,
        recent_failure_times=(NOW,),
        opened_at=NOW,
        open_until=acquired,
        half_open_lease=lease,
        half_open_successes=0,
        created_at=Instant(NOW.value - timedelta(minutes=1)),
        updated_at=acquired,
    )

    assert state.half_open_lease == lease
    assert lease.lease_id.startswith("circuit-lease:v1:")
    with pytest.raises(ValueError, match="state version"):
        replace(state, version=3)
    with pytest.raises(ValueError, match="identity"):
        replace(lease, lease_id="circuit-lease:v1:" + "0" * 64)


def test_state_and_lease_contain_no_payload_or_authority_field() -> None:
    state_fields = {item.name for item in fields(CircuitBreakerState)}
    lease_fields = {item.name for item in fields(CircuitProbeLease)}
    forbidden = {"payload", "permission", "gate", "credential", "provider_url"}

    assert state_fields.isdisjoint(forbidden)
    assert lease_fields.isdisjoint(forbidden)
