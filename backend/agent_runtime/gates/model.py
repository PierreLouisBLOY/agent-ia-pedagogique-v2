from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from enum import StrEnum

from backend.agent_runtime.contracts import (
    ActorRef,
    GateDecisionValue,
    GateRequest,
)
from backend.agent_runtime.contracts.common import (
    ContractRef,
    freeze_agent_safe_mapping,
    require_contract_ref,
)
from backend.agent_runtime.policy import PolicyFacts
from backend.shared_kernel.time import Instant


class GateResolutionDisposition(StrEnum):
    WAITING = "WAITING"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    DEFERRED = "DEFERRED"
    EXPIRED = "EXPIRED"


_DECISION_BY_DISPOSITION = {
    GateResolutionDisposition.APPROVED: GateDecisionValue.APPROVED,
    GateResolutionDisposition.REJECTED: GateDecisionValue.REJECTED,
    GateResolutionDisposition.DEFERRED: GateDecisionValue.DEFERRED,
}


@dataclass(frozen=True, slots=True)
class GateResolution:
    """Data-only result of validating one externally supplied gate decision."""

    disposition: GateResolutionDisposition
    gate_id: str
    gate_type: str
    request: GateRequest
    required_actor: ActorRef
    decision_ref: ContractRef | None = None
    decision_value: GateDecisionValue | None = None
    decided_at: Instant | None = None
    selected_option: Mapping[str, object] | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.disposition, GateResolutionDisposition):
            raise TypeError("disposition must be a GateResolutionDisposition")
        if not isinstance(self.request, GateRequest):
            raise TypeError("request must be a GateRequest")
        if self.gate_id != self.request.gate_id:
            raise ValueError("gate_id must match request")
        if self.gate_type != self.request.gate_type:
            raise ValueError("gate_type must match request")
        if self.required_actor != self.request.required_actor:
            raise ValueError("required_actor must match request")
        expected_decision = _DECISION_BY_DISPOSITION.get(self.disposition)
        if expected_decision is None:
            if any(
                value is not None
                for value in (
                    self.decision_ref,
                    self.decision_value,
                    self.decided_at,
                    self.selected_option,
                )
            ):
                raise ValueError("non-decision resolutions cannot carry decision data")
            return
        if self.decision_value is not expected_decision:
            raise ValueError("decision_value must match disposition")
        if self.decision_ref is None or self.decided_at is None:
            raise ValueError("decision resolutions require reference and time")
        require_contract_ref(self.decision_ref, "decision_ref")
        if not isinstance(self.decided_at, Instant):
            raise TypeError("decided_at must be an Instant")
        if self.selected_option is not None:
            object.__setattr__(
                self,
                "selected_option",
                freeze_agent_safe_mapping(self.selected_option),
            )

    def to_policy_facts(self) -> PolicyFacts:
        return PolicyFacts(
            matrix_gate_satisfied=(
                self.disposition is GateResolutionDisposition.APPROVED
            )
        )


class GateEngineErrorCode(StrEnum):
    INVALID_GATE_REQUEST = "INVALID_GATE_REQUEST"
    AUTHORITY_NOT_ALLOWED = "AUTHORITY_NOT_ALLOWED"
    DECISION_SOURCE_FAILED = "DECISION_SOURCE_FAILED"
    INVALID_GATE_DECISION = "INVALID_GATE_DECISION"
    DECISION_REQUEST_MISMATCH = "DECISION_REQUEST_MISMATCH"
    DECISION_GATE_MISMATCH = "DECISION_GATE_MISMATCH"
    DECISION_ACTOR_MISMATCH = "DECISION_ACTOR_MISMATCH"
    DECISION_RUN_MISMATCH = "DECISION_RUN_MISMATCH"
    DECISION_STEP_MISMATCH = "DECISION_STEP_MISMATCH"
    DECISION_CORRELATION_MISMATCH = "DECISION_CORRELATION_MISMATCH"
    DECISION_FROM_FUTURE = "DECISION_FROM_FUTURE"
    INVALID_DECISION_REF = "INVALID_DECISION_REF"
    INVALID_SELECTED_OPTION = "INVALID_SELECTED_OPTION"


_SAFE_REASONS = {
    GateEngineErrorCode.INVALID_GATE_REQUEST: "gate request is invalid",
    GateEngineErrorCode.AUTHORITY_NOT_ALLOWED: "gate authority is not allowed",
    GateEngineErrorCode.DECISION_SOURCE_FAILED: "gate decision source failed",
    GateEngineErrorCode.INVALID_GATE_DECISION: "gate decision is invalid",
    GateEngineErrorCode.DECISION_REQUEST_MISMATCH: "gate decision request mismatch",
    GateEngineErrorCode.DECISION_GATE_MISMATCH: "gate decision identity mismatch",
    GateEngineErrorCode.DECISION_ACTOR_MISMATCH: "gate decision actor mismatch",
    GateEngineErrorCode.DECISION_RUN_MISMATCH: "gate decision run mismatch",
    GateEngineErrorCode.DECISION_STEP_MISMATCH: "gate decision step mismatch",
    GateEngineErrorCode.DECISION_CORRELATION_MISMATCH: (
        "gate decision correlation mismatch"
    ),
    GateEngineErrorCode.DECISION_FROM_FUTURE: "gate decision is from the future",
    GateEngineErrorCode.INVALID_DECISION_REF: "gate decision reference is invalid",
    GateEngineErrorCode.INVALID_SELECTED_OPTION: "selected gate option is invalid",
}


class GateEngineError(RuntimeError):
    code: GateEngineErrorCode
    safe_reason: str

    def __init__(self, code: GateEngineErrorCode) -> None:
        if not isinstance(code, GateEngineErrorCode):
            raise TypeError("code must be a GateEngineErrorCode")
        self.code = code
        self.safe_reason = _SAFE_REASONS[code]
        super().__init__(self.safe_reason)
