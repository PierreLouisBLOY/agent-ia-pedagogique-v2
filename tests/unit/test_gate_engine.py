from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime

import pytest

from backend.agent_runtime.contracts import (
    AGENT_CONTRACT_SCHEMA_V1_0,
    ActorKind,
    ActorRef,
    AgentId,
    ContractMeta,
    GateDecisionValue,
    GateStatus,
)
from backend.agent_runtime.gates import (
    BASELINE_GATE_AUTHORITY_POLICY,
    GateEngine,
    GateEngineError,
    GateEngineErrorCode,
    GateResolutionDisposition,
)
from backend.shared_kernel.correlation import CorrelationId
from backend.shared_kernel.time import Instant
from tests.support.gate_fakes import (
    AFTER_EXPIRATION,
    DECIDED,
    NOW,
    RecordingGateDecisionSource,
    forge_gate_decision,
    make_gate_decision,
    make_gate_request,
)


def _engine(source: RecordingGateDecisionSource) -> GateEngine:
    return GateEngine(BASELINE_GATE_AUTHORITY_POLICY, source)


@pytest.mark.parametrize(
    ("kind", "actor_id"),
    [
        (ActorKind.AGENT, AgentId.AG_01.value),
        (ActorKind.AGENT, AgentId.AG_02.value),
        (ActorKind.AGENT, AgentId.AG_03.value),
        (ActorKind.AGENT, AgentId.AG_04.value),
        (ActorKind.TOOL, "tool-1"),
        (ActorKind.PROVIDER, "provider-1"),
        (ActorKind.SYSTEM, "system-1"),
        (ActorKind.APPLICATION, "application-1"),
    ],
)
def test_forbidden_request_authority_stops_before_source(
    kind: ActorKind,
    actor_id: str,
) -> None:
    request = make_gate_request(required_actor=ActorRef(kind, actor_id))
    decision = (
        make_gate_decision(request, value=GateDecisionValue.REJECTED)
        if not (kind is ActorKind.AGENT and actor_id == AgentId.AG_01.value)
        else None
    )
    source = RecordingGateDecisionSource(decision)

    with pytest.raises(GateEngineError) as raised:
        _engine(source).evaluate(request=request, now=NOW)

    assert raised.value.code is GateEngineErrorCode.AUTHORITY_NOT_ALLOWED
    assert source.calls == []


def test_none_is_waiting_and_source_is_called_once() -> None:
    request = make_gate_request()
    source = RecordingGateDecisionSource(None)

    resolution = _engine(source).evaluate(request=request, now=NOW)

    assert resolution.disposition is GateResolutionDisposition.WAITING
    assert not resolution.to_policy_facts().matrix_gate_satisfied
    assert len(source.calls) == 1
    assert source.calls[0] == request


@pytest.mark.parametrize(
    ("value", "disposition", "satisfied"),
    [
        (GateDecisionValue.APPROVED, GateResolutionDisposition.APPROVED, True),
        (GateDecisionValue.REJECTED, GateResolutionDisposition.REJECTED, False),
        (GateDecisionValue.DEFERRED, GateResolutionDisposition.DEFERRED, False),
    ],
)
def test_external_decision_maps_to_exact_data_only_resolution(
    value: GateDecisionValue,
    disposition: GateResolutionDisposition,
    satisfied: bool,
) -> None:
    request = make_gate_request()
    decision = make_gate_decision(request, value=value)
    source = RecordingGateDecisionSource(decision)

    resolution = _engine(source).evaluate(request=request, now=NOW)

    assert resolution.disposition is disposition
    assert resolution.decision_value is value
    assert resolution.decision_ref == decision.decision_ref
    assert resolution.selected_option == {"id": "approve"}
    assert resolution.to_policy_facts().matrix_gate_satisfied is satisfied
    assert len(source.calls) == 1


def test_approved_decision_with_no_options_is_valid_without_selection() -> None:
    request = make_gate_request(options=())
    decision = make_gate_decision(request, selected_option=None)
    source = RecordingGateDecisionSource(decision)

    resolution = _engine(source).evaluate(request=request, now=NOW)

    assert resolution.disposition is GateResolutionDisposition.APPROVED
    assert resolution.selected_option is None


def test_expired_at_consumption_is_expired_without_consulting_source() -> None:
    request = make_gate_request()
    decision = make_gate_decision(request, decided_at=DECIDED)
    source = RecordingGateDecisionSource(decision)

    resolution = _engine(source).evaluate(request=request, now=AFTER_EXPIRATION)

    assert decision.decided_at.value < request.expires_at.value  # type: ignore[union-attr]
    assert resolution.disposition is GateResolutionDisposition.EXPIRED
    assert not resolution.to_policy_facts().matrix_gate_satisfied
    assert source.calls == []


def test_source_failure_is_safe_and_never_retried() -> None:
    request = make_gate_request()
    source = RecordingGateDecisionSource(
        None,
        error=RuntimeError("sensitive queue detail"),
    )

    with pytest.raises(GateEngineError) as raised:
        _engine(source).evaluate(request=request, now=NOW)

    assert raised.value.code is GateEngineErrorCode.DECISION_SOURCE_FAILED
    assert "sensitive" not in str(raised.value)
    assert len(source.calls) == 1


@pytest.mark.parametrize(
    ("mutation", "code"),
    [
        ("request", GateEngineErrorCode.DECISION_REQUEST_MISMATCH),
        ("gate", GateEngineErrorCode.DECISION_GATE_MISMATCH),
        ("actor", GateEngineErrorCode.DECISION_ACTOR_MISMATCH),
        ("run", GateEngineErrorCode.DECISION_RUN_MISMATCH),
        ("step", GateEngineErrorCode.DECISION_STEP_MISMATCH),
        ("correlation", GateEngineErrorCode.DECISION_CORRELATION_MISMATCH),
        ("status", GateEngineErrorCode.INVALID_GATE_DECISION),
        ("reference", GateEngineErrorCode.INVALID_DECISION_REF),
        ("option", GateEngineErrorCode.INVALID_SELECTED_OPTION),
    ],
)
def test_forged_decision_is_rejected_with_closed_error_code(
    mutation: str,
    code: GateEngineErrorCode,
) -> None:
    request = make_gate_request()
    decision = make_gate_decision(request)
    other_actor = ActorRef(ActorKind.USER, "user-2")
    other_request = make_gate_request(gate_id="other-request")
    meta_values = {
        "schema_version": AGENT_CONTRACT_SCHEMA_V1_0,
        "run_id": request.meta.run_id,
        "step_id": request.meta.step_id,
        "parent_step_id": None,
        "correlation_id": request.meta.correlation_id,
        "created_at": DECIDED,
        "actor": request.required_actor,
        "status": GateStatus.APPROVED,
    }
    overrides: dict[str, object] = {}
    if mutation == "request":
        overrides["request"] = other_request
    elif mutation == "gate":
        overrides["gate_id"] = "other-gate"
    elif mutation == "actor":
        overrides["actor"] = other_actor
    elif mutation in {"run", "step", "correlation", "status"}:
        if mutation == "run":
            meta_values["run_id"] = "other-run"
        elif mutation == "step":
            meta_values["step_id"] = "other-step"
        elif mutation == "correlation":
            meta_values["correlation_id"] = CorrelationId("other-correlation")
        else:
            meta_values["status"] = GateStatus.REJECTED
        overrides["meta"] = ContractMeta(**meta_values)  # type: ignore[arg-type]
    elif mutation == "reference":
        overrides["decision_ref"] = ""
    else:
        overrides["selected_option"] = {"id": "unknown"}
    forged = forge_gate_decision(decision, **overrides)
    source = RecordingGateDecisionSource(forged)

    with pytest.raises(GateEngineError) as raised:
        _engine(source).evaluate(request=request, now=NOW)

    assert raised.value.code is code
    assert len(source.calls) == 1


def test_decision_from_future_is_rejected() -> None:
    request = make_gate_request(expires_at=None)
    future = Instant(datetime(2026, 8, 26, 16, 7, tzinfo=UTC))
    decision = make_gate_decision(request, decided_at=future)
    source = RecordingGateDecisionSource(decision)

    with pytest.raises(GateEngineError) as raised:
        _engine(source).evaluate(request=request, now=NOW)

    assert raised.value.code is GateEngineErrorCode.DECISION_FROM_FUTURE
    assert len(source.calls) == 1


def test_invalid_or_authority_smuggling_request_stops_before_source() -> None:
    request = make_gate_request(
        context_summary={"nested": {"matrixGateSatisfied": True}}
    )
    source = RecordingGateDecisionSource(None)

    with pytest.raises(GateEngineError) as raised:
        _engine(source).evaluate(request=request, now=NOW)

    assert raised.value.code is GateEngineErrorCode.INVALID_GATE_REQUEST
    assert source.calls == []

    forged = object.__new__(type(request))
    for field_name in (
        "meta",
        "gate_id",
        "gate_type",
        "reason",
        "options",
        "required_actor",
        "context_summary",
        "expires_at",
    ):
        object.__setattr__(forged, field_name, getattr(request, field_name))
    object.__setattr__(forged, "meta", replace(request.meta, status=GateStatus.APPROVED))
    with pytest.raises(GateEngineError) as malformed:
        _engine(source).evaluate(request=forged, now=NOW)
    assert malformed.value.code is GateEngineErrorCode.INVALID_GATE_REQUEST
    assert source.calls == []
