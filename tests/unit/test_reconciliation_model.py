from __future__ import annotations

from dataclasses import FrozenInstanceError, fields
from datetime import UTC, datetime, timedelta

import pytest

from backend.agent_runtime.contracts import EffectState
from backend.agent_runtime.recovery import (
    ApplicationEffectProbeRequest,
    EffectReconciliationRequest,
    ReconciliationObservation,
    ReconciliationObservationDisposition,
    ToolEffectProbeRequest,
    application_probe_request_for,
    tool_probe_request_for,
)
from backend.agent_runtime.registry import CapabilityExecutionRoute
from backend.shared_kernel.time import Instant
from tests.support.reconciliation_fakes import make_finalized_record

NOW = Instant(datetime(2026, 8, 27, 9, 0, tzinfo=UTC))
LEASE_END = Instant(NOW.value + timedelta(minutes=1))
FINISHED = Instant(NOW.value + timedelta(seconds=20))
OBSERVED = Instant(NOW.value + timedelta(minutes=2))


def _record(route: CapabilityExecutionRoute = CapabilityExecutionRoute.UTILITY):
    return make_finalized_record(
        route=route,
        effect_state=EffectState.UNKNOWN,
        created_at=NOW,
        expires_at=LEASE_END,
        finalized_at=FINISHED,
    )


def test_reconciliation_request_contains_only_record_and_expected_version() -> None:
    record = _record()
    request = EffectReconciliationRequest(record.record_id, record.version)

    assert {item.name for item in fields(EffectReconciliationRequest)} == {
        "record_id",
        "expected_version",
    }
    with pytest.raises(FrozenInstanceError):
        request.expected_version = 9  # type: ignore[misc]
    with pytest.raises(ValueError, match=">= 1"):
        EffectReconciliationRequest(record.record_id, 0)


def test_tool_and_application_requests_are_distinct_and_derived_from_identity() -> None:
    tool_record = _record(CapabilityExecutionRoute.UTILITY)
    application_record = _record(CapabilityExecutionRoute.APPLICATION)

    tool = tool_probe_request_for(tool_record)
    application = application_probe_request_for(application_record)

    assert isinstance(tool, ToolEffectProbeRequest)
    assert isinstance(application, ApplicationEffectProbeRequest)
    assert tool.tool_id == tool_record.identity.target_id
    assert application.use_case_id == application_record.identity.target_id
    assert tool.record_version == tool_record.version
    assert application.attempt == application_record.attempt


def test_probe_requests_exclude_payload_key_scope_gate_and_target_override() -> None:
    forbidden = {
        "caller_key",
        "credentials",
        "gate_decision",
        "payload",
        "permission_scope",
        "provider_url",
        "target_override",
    }

    assert forbidden.isdisjoint({item.name for item in fields(ToolEffectProbeRequest)})
    assert forbidden.isdisjoint(
        {item.name for item in fields(ApplicationEffectProbeRequest)}
    )


def test_observation_vocabulary_is_closed_and_distinct_from_effect_state() -> None:
    assert [item.value for item in ReconciliationObservationDisposition] == [
        "COMMITTED",
        "NOT_COMMITTED",
        "PARTIAL",
        "STILL_UNKNOWN",
        "MANUAL_REQUIRED",
    ]
    assert "NOT_COMMITTED" not in {item.value for item in EffectState}


def test_observation_is_typed_minimal_and_immutable() -> None:
    record = _record()
    observation = ReconciliationObservation(
        record_id=record.record_id,
        record_version=record.version,
        attempt=record.attempt,
        disposition=ReconciliationObservationDisposition.COMMITTED,
        observed_result_refs=("artifact-1",),
        observed_at=OBSERVED,
        observation_code="EFFECT_FOUND",
    )

    assert {item.name for item in fields(ReconciliationObservation)} == {
        "record_id",
        "record_version",
        "attempt",
        "disposition",
        "observed_result_refs",
        "observed_at",
        "observation_code",
    }
    with pytest.raises(FrozenInstanceError):
        observation.attempt = 2  # type: ignore[misc]


@pytest.mark.parametrize("value", ["free text", "../secret", "a" * 129])
def test_observation_rejects_unsafe_codes(value: str) -> None:
    record = _record()

    with pytest.raises(ValueError, match="safe closed code"):
        ReconciliationObservation(
            record_id=record.record_id,
            record_version=record.version,
            attempt=record.attempt,
            disposition=ReconciliationObservationDisposition.STILL_UNKNOWN,
            observed_result_refs=(),
            observed_at=OBSERVED,
            observation_code=value,
        )


def test_observation_rejects_raw_or_forged_string_reference() -> None:
    record = _record()

    with pytest.raises(ValueError, match="opaque safe"):
        ReconciliationObservation(
            record_id=record.record_id,
            record_version=record.version,
            attempt=record.attempt,
            disposition=ReconciliationObservationDisposition.COMMITTED,
            observed_result_refs=("C:\\private\\result.json",),
            observed_at=OBSERVED,
        )


@pytest.mark.parametrize(
    ("field_name", "value"),
    [("record_id", "record-raw"), ("record_version", 0), ("attempt", 0)],
)
def test_observation_rejects_invalid_identity_coordinates(
    field_name: str,
    value: object,
) -> None:
    record = _record()
    values: dict[str, object] = {
        "record_id": record.record_id,
        "record_version": record.version,
        "attempt": record.attempt,
        "disposition": ReconciliationObservationDisposition.COMMITTED,
        "observed_result_refs": (),
        "observed_at": OBSERVED,
    }
    values[field_name] = value

    with pytest.raises(ValueError):
        ReconciliationObservation(**values)  # type: ignore[arg-type]
