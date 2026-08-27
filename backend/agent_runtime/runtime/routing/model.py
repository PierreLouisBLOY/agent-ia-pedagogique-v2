from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum

from backend.agent_runtime.contracts import (
    AgentInvocation,
    ContractRef,
    GateRequest,
    PermissionScope,
    ToolCallRequest,
    UseCaseRequest,
)
from backend.agent_runtime.contracts.common import require_contract_ref
from backend.agent_runtime.policy import PolicyFacts
from backend.agent_runtime.tools import ToolRoutingContext


class RuntimeRoutingErrorCode(StrEnum):
    INVALID_RUNTIME_CONTEXT = "INVALID_RUNTIME_CONTEXT"
    INVALID_STEP_SHAPE = "INVALID_STEP_SHAPE"
    RESOLUTION_FAILED = "RESOLUTION_FAILED"
    PERMISSION_SCOPE_MISMATCH = "PERMISSION_SCOPE_MISMATCH"
    REQUEST_IDENTITY_MISMATCH = "REQUEST_IDENTITY_MISMATCH"
    CAPABILITY_MISMATCH = "CAPABILITY_MISMATCH"
    GATE_REF_MISMATCH = "GATE_REF_MISMATCH"
    GATE_NOT_APPROVED = "GATE_NOT_APPROVED"
    AGENT_NOT_AUTHORIZED = "AGENT_NOT_AUTHORIZED"
    AGENT_NOT_BOUND = "AGENT_NOT_BOUND"
    INVALID_BOUNDARY_RESULT = "INVALID_BOUNDARY_RESULT"


@dataclass(frozen=True, slots=True)
class RuntimeRoutingError(RuntimeError):
    code: RuntimeRoutingErrorCode

    def __post_init__(self) -> None:
        if not isinstance(self.code, RuntimeRoutingErrorCode):
            raise TypeError("code must be a RuntimeRoutingErrorCode")
        RuntimeError.__init__(self, self.code.value)


@dataclass(frozen=True, slots=True)
class ResolvedUseCaseInput:
    request: UseCaseRequest
    permission_scope_ref: ContractRef
    permission_scope: PermissionScope
    policy_facts: PolicyFacts = field(default_factory=PolicyFacts)

    def __post_init__(self) -> None:
        if type(self.request) is not UseCaseRequest:
            raise TypeError("request must be a UseCaseRequest")
        require_contract_ref(self.permission_scope_ref, "permission_scope_ref")
        if type(self.permission_scope) is not PermissionScope:
            raise TypeError("permission_scope must be a PermissionScope")
        if type(self.policy_facts) is not PolicyFacts:
            raise TypeError("policy_facts must be PolicyFacts")


@dataclass(frozen=True, slots=True)
class ResolvedToolInput:
    request: ToolCallRequest
    permission_scope_ref: ContractRef
    context: ToolRoutingContext
    policy_facts: PolicyFacts = field(default_factory=PolicyFacts)
    satisfied_gate_requirements: tuple[str, ...] = ()
    scope_revoked: bool = False

    def __post_init__(self) -> None:
        if type(self.request) is not ToolCallRequest:
            raise TypeError("request must be a ToolCallRequest")
        require_contract_ref(self.permission_scope_ref, "permission_scope_ref")
        if type(self.context) is not ToolRoutingContext:
            raise TypeError("context must be a ToolRoutingContext")
        if type(self.policy_facts) is not PolicyFacts:
            raise TypeError("policy_facts must be PolicyFacts")
        if not isinstance(self.satisfied_gate_requirements, tuple) or any(
            not isinstance(value, str) or not value
            for value in self.satisfied_gate_requirements
        ):
            raise TypeError("satisfied_gate_requirements must be non-empty strings")
        if len(set(self.satisfied_gate_requirements)) != len(
            self.satisfied_gate_requirements
        ):
            raise ValueError("satisfied_gate_requirements must be unique")
        if not isinstance(self.scope_revoked, bool):
            raise TypeError("scope_revoked must be a bool")


@dataclass(frozen=True, slots=True)
class ResolvedGateInput:
    gate_ref: ContractRef
    request: GateRequest

    def __post_init__(self) -> None:
        require_contract_ref(self.gate_ref, "gate_ref")
        if type(self.request) is not GateRequest:
            raise TypeError("request must be a GateRequest")


@dataclass(frozen=True, slots=True)
class ResolvedAgentInput:
    invocation: AgentInvocation
    permission_scope_ref: ContractRef
    permission_scope: PermissionScope
    policy_facts: PolicyFacts = field(default_factory=PolicyFacts)
    satisfied_gate_requirements: tuple[str, ...] = ()
    scope_revoked: bool = False

    def __post_init__(self) -> None:
        if type(self.invocation) is not AgentInvocation:
            raise TypeError("invocation must be an AgentInvocation")
        require_contract_ref(self.permission_scope_ref, "permission_scope_ref")
        if type(self.permission_scope) is not PermissionScope:
            raise TypeError("permission_scope must be a PermissionScope")
        if type(self.policy_facts) is not PolicyFacts:
            raise TypeError("policy_facts must be PolicyFacts")
        if not isinstance(self.satisfied_gate_requirements, tuple) or any(
            not isinstance(value, str) or not value
            for value in self.satisfied_gate_requirements
        ):
            raise TypeError("satisfied_gate_requirements must be non-empty strings")
        if len(set(self.satisfied_gate_requirements)) != len(
            self.satisfied_gate_requirements
        ):
            raise ValueError("satisfied_gate_requirements must be unique")
        if not isinstance(self.scope_revoked, bool):
            raise TypeError("scope_revoked must be a bool")
