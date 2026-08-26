from __future__ import annotations

from datetime import UTC, datetime
from typing import cast

from backend.agent_runtime.contracts import (
    AGENT_CONTRACT_SCHEMA_V1_0,
    ActorKind,
    ActorRef,
    AgentId,
    ContractMeta,
    GateDecision,
    GateDecisionValue,
    GateRequest,
    GateStatus,
)
from backend.agent_runtime.gates import GateDecisionSourcePort
from backend.shared_kernel.correlation import CorrelationId
from backend.shared_kernel.time import Instant

CREATED = Instant(datetime(2026, 8, 26, 16, 0, tzinfo=UTC))
DECIDED = Instant(datetime(2026, 8, 26, 16, 5, tzinfo=UTC))
NOW = Instant(datetime(2026, 8, 26, 16, 6, tzinfo=UTC))
EXPIRES = Instant(datetime(2026, 8, 26, 16, 10, tzinfo=UTC))
AFTER_EXPIRATION = Instant(datetime(2026, 8, 26, 16, 11, tzinfo=UTC))


class RecordingGateDecisionSource(GateDecisionSourcePort):
    def __init__(self, decision: object, *, error: Exception | None = None) -> None:
        self.decision = decision
        self.error = error
        self.calls: list[GateRequest] = []

    def receive(self, *, request: GateRequest) -> GateDecision | None:
        self.calls.append(request)
        if self.error is not None:
            raise self.error
        return cast(GateDecision | None, self.decision)


def make_gate_request(
    *,
    required_actor: ActorRef | None = None,
    gate_id: str = "gate-promotion-1",
    run_id: str = "run-gate",
    step_id: str = "step-gate",
    correlation_id: str = "corr-gate",
    options: tuple[dict[str, object], ...] = (
        {"id": "approve"},
        {"id": "reject"},
    ),
    context_summary: dict[str, object] | None = None,
    expires_at: Instant | None = EXPIRES,
) -> GateRequest:
    caller = ActorRef(ActorKind.AGENT, AgentId.AG_01.value)
    return GateRequest(
        meta=ContractMeta(
            AGENT_CONTRACT_SCHEMA_V1_0,
            run_id,
            step_id,
            None,
            CorrelationId(correlation_id),
            CREATED,
            caller,
            GateStatus.PENDING,
        ),
        gate_id=gate_id,
        gate_type="human_promotion_approval",
        reason="Promotion requires an external human decision",
        options=options,
        required_actor=required_actor or ActorRef(ActorKind.USER, "user-1"),
        context_summary=(
            {"production_ref": "production-1"}
            if context_summary is None
            else context_summary
        ),
        expires_at=expires_at,
    )


def make_gate_decision(
    request: GateRequest,
    *,
    value: GateDecisionValue = GateDecisionValue.APPROVED,
    decided_at: Instant = DECIDED,
    selected_option: dict[str, object] | None = None,
    decision_ref: str = "gate-decision-1",
) -> GateDecision:
    status = {
        GateDecisionValue.APPROVED: GateStatus.APPROVED,
        GateDecisionValue.REJECTED: GateStatus.REJECTED,
        GateDecisionValue.DEFERRED: GateStatus.DEFERRED,
    }[value]
    return GateDecision(
        meta=ContractMeta(
            AGENT_CONTRACT_SCHEMA_V1_0,
            request.meta.run_id,
            request.meta.step_id,
            request.meta.parent_step_id,
            request.meta.correlation_id,
            decided_at,
            request.required_actor,
            status,
        ),
        gate_id=request.gate_id,
        decision=value,
        actor=request.required_actor,
        decided_at=decided_at,
        decision_ref=decision_ref,
        request=request,
        selected_option=(
            ({"id": "approve"} if request.options else None)
            if selected_option is None
            else selected_option
        ),
        comment="External decision recorded",
    )


def forge_gate_decision(
    source: GateDecision,
    **overrides: object,
) -> GateDecision:
    forged = object.__new__(GateDecision)
    values = {
        "meta": source.meta,
        "gate_id": source.gate_id,
        "decision": source.decision,
        "actor": source.actor,
        "decided_at": source.decided_at,
        "decision_ref": source.decision_ref,
        "request": source.request,
        "selected_option": source.selected_option,
        "comment": source.comment,
    }
    values.update(overrides)
    for field_name, value in values.items():
        object.__setattr__(forged, field_name, value)
    return forged
