from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from backend.agent_runtime.agents.review import CorrectionHandoffSignal
from backend.agent_runtime.contracts import (
    AGENT_CONTRACT_SCHEMA_V1_0,
    ActorKind,
    ActorRef,
    AgentId,
    ContractMeta,
    CorrectionRequest,
    InvocationStatus,
    ProductionCandidate,
)
from backend.shared_kernel.correlation import CorrelationId
from backend.shared_kernel.time import Instant


@dataclass(frozen=True, slots=True)
class ValidationObservation:
    production_id: str
    accepted: bool


class RecordingApplicationValidator:
    """Test-only CAP-A01 probe; it observes and never mutates a candidate."""

    def __init__(self, *, accepted: bool = True) -> None:
        self.accepted = accepted
        self.calls: list[ProductionCandidate] = []

    def validate(self, candidate: ProductionCandidate) -> ValidationObservation:
        self.calls.append(candidate)
        return ValidationObservation(candidate.production_id, self.accepted)


class AG01Decision(StrEnum):
    NO_ACTION = "NO_ACTION"
    REQUEST_CORRECTION = "REQUEST_CORRECTION"


class RecordingAG01PostReview:
    """Test-only owner of the policy decision and canonical C-11 construction."""

    def __init__(self, decision: AG01Decision) -> None:
        self.decision = decision
        self.calls: list[CorrectionHandoffSignal] = []

    def decide(self, handoff: CorrectionHandoffSignal | None) -> AG01Decision:
        if handoff is not None:
            self.calls.append(handoff)
        return self.decision

    def build_correction_request(
        self,
        *,
        handoff: CorrectionHandoffSignal,
        run_id: str,
        step_id: str,
        correlation_id: str,
        created_at: Instant,
    ) -> CorrectionRequest:
        if self.decide(handoff) is not AG01Decision.REQUEST_CORRECTION:
            raise ValueError("AG-01 did not request a correction")
        return CorrectionRequest(
            meta=ContractMeta(
                AGENT_CONTRACT_SCHEMA_V1_0,
                run_id,
                step_id,
                None,
                CorrelationId(correlation_id),
                created_at,
                ActorRef(ActorKind.AGENT, AgentId.AG_03.value),
                InvocationStatus.PLANNED,
            ),
            target_production_ref=handoff.target_production_ref,
            review_ref=handoff.review_ref,
            finding_ids=handoff.finding_ids,
            evidence_refs=handoff.evidence_refs,
            allowed_changes={"finding_ids": handoff.finding_ids},
        )


class RecordingHumanGate:
    """Explicit human decision probe; review information never decides the gate."""

    def __init__(self, decision: bool) -> None:
        self.decision = decision
        self.calls: list[object] = []

    def decide(self, review_information: object) -> bool:
        self.calls.append(review_information)
        return self.decision


class RecordingPromotionProbe:
    """Test-only CAP-A02 probe requiring separate validation and gate decisions."""

    def __init__(self) -> None:
        self.calls: list[ProductionCandidate] = []

    def promote(
        self,
        candidate: ProductionCandidate,
        *,
        validation_accepted: bool,
        gate_accepted: bool,
    ) -> bool:
        if not validation_accepted or not gate_accepted:
            return False
        self.calls.append(candidate)
        return True
