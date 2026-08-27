from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum

from backend.agent_runtime.contracts import PermissionScope, StepSpec
from backend.agent_runtime.contracts.common import ContractRef, require_contract_ref
from backend.agent_runtime.policy import PolicyFacts
from backend.core_contracts.capability import CapabilityId
from backend.shared_kernel._strings import require_non_empty


@dataclass(frozen=True, slots=True)
class UseCaseDescriptor:
    """Static metadata for one Application inbound route."""

    use_case_id: str
    canonical_name: str
    capability_id: CapabilityId
    request_contract_id: str
    result_contract_id: str
    idempotency_required: bool

    def __post_init__(self) -> None:
        require_non_empty(self.use_case_id, "use_case_id")
        require_non_empty(self.canonical_name, "canonical_name")
        if not isinstance(self.capability_id, CapabilityId):
            raise TypeError("capability_id must be a CapabilityId")
        require_non_empty(self.request_contract_id, "request_contract_id")
        require_non_empty(self.result_contract_id, "result_contract_id")
        if not isinstance(self.idempotency_required, bool):
            raise TypeError("idempotency_required must be a bool")


@dataclass(frozen=True, slots=True)
class UseCaseRoutingContext:
    """Trusted routing inputs resolved by the caller, never from request payload data."""

    step: StepSpec
    permission_scope_ref: ContractRef
    permission_scope: PermissionScope
    policy_facts: PolicyFacts = field(default_factory=PolicyFacts)

    def __post_init__(self) -> None:
        if not isinstance(self.step, StepSpec):
            raise TypeError("step must be a StepSpec")
        require_contract_ref(self.permission_scope_ref, "permission_scope_ref")
        if not isinstance(self.permission_scope, PermissionScope):
            raise TypeError("permission_scope must be a PermissionScope")
        if not isinstance(self.policy_facts, PolicyFacts):
            raise TypeError("policy_facts must be PolicyFacts")


class UseCaseRoutingErrorCode(StrEnum):
    INVALID_ROUTING_CONTEXT = "INVALID_ROUTING_CONTEXT"
    UNKNOWN_USE_CASE = "UNKNOWN_USE_CASE"
    USE_CASE_NOT_BOUND = "USE_CASE_NOT_BOUND"
    STEP_KIND_MISMATCH = "STEP_KIND_MISMATCH"
    EXECUTOR_MISMATCH = "EXECUTOR_MISMATCH"
    CAPABILITY_USE_CASE_MISMATCH = "CAPABILITY_USE_CASE_MISMATCH"
    NON_APPLICATION_CAPABILITY = "NON_APPLICATION_CAPABILITY"
    REQUEST_NOT_ROUTABLE = "REQUEST_NOT_ROUTABLE"
    IDEMPOTENCY_REQUIRED = "IDEMPOTENCY_REQUIRED"
    AUTHORITY_METADATA_FORBIDDEN = "AUTHORITY_METADATA_FORBIDDEN"
    REQUEST_CONTRACT_MISMATCH = "REQUEST_CONTRACT_MISMATCH"
    INBOUND_FAILED = "INBOUND_FAILED"
    RESULT_USE_CASE_MISMATCH = "RESULT_USE_CASE_MISMATCH"
    RESULT_RUN_MISMATCH = "RESULT_RUN_MISMATCH"
    RESULT_STEP_MISMATCH = "RESULT_STEP_MISMATCH"
    RESULT_CORRELATION_MISMATCH = "RESULT_CORRELATION_MISMATCH"
    INVALID_USE_CASE_RESULT = "INVALID_USE_CASE_RESULT"
    RESULT_CONTRACT_MISMATCH = "RESULT_CONTRACT_MISMATCH"


_SAFE_REASONS = {
    UseCaseRoutingErrorCode.INVALID_ROUTING_CONTEXT: "use-case routing context is invalid",
    UseCaseRoutingErrorCode.UNKNOWN_USE_CASE: "use case is not registered",
    UseCaseRoutingErrorCode.USE_CASE_NOT_BOUND: "use case has no exact inbound binding",
    UseCaseRoutingErrorCode.STEP_KIND_MISMATCH: "step is not a use-case step",
    UseCaseRoutingErrorCode.EXECUTOR_MISMATCH: "step is not assigned to Application",
    UseCaseRoutingErrorCode.CAPABILITY_USE_CASE_MISMATCH: (
        "use-case capability does not match the step"
    ),
    UseCaseRoutingErrorCode.NON_APPLICATION_CAPABILITY: (
        "capability is not an Application capability"
    ),
    UseCaseRoutingErrorCode.REQUEST_NOT_ROUTABLE: (
        "policy did not authorize an Application request handoff"
    ),
    UseCaseRoutingErrorCode.IDEMPOTENCY_REQUIRED: "use case requires an idempotency key",
    UseCaseRoutingErrorCode.AUTHORITY_METADATA_FORBIDDEN: (
        "request data contains forbidden authority metadata"
    ),
    UseCaseRoutingErrorCode.REQUEST_CONTRACT_MISMATCH: (
        "use-case request contract does not match its descriptor"
    ),
    UseCaseRoutingErrorCode.INBOUND_FAILED: "Application inbound invocation failed",
    UseCaseRoutingErrorCode.RESULT_USE_CASE_MISMATCH: "use-case result identity mismatch",
    UseCaseRoutingErrorCode.RESULT_RUN_MISMATCH: "use-case result run mismatch",
    UseCaseRoutingErrorCode.RESULT_STEP_MISMATCH: "use-case result step mismatch",
    UseCaseRoutingErrorCode.RESULT_CORRELATION_MISMATCH: (
        "use-case result correlation mismatch"
    ),
    UseCaseRoutingErrorCode.INVALID_USE_CASE_RESULT: "Application returned an invalid result",
    UseCaseRoutingErrorCode.RESULT_CONTRACT_MISMATCH: (
        "use-case result contract does not match its descriptor"
    ),
}


class UseCaseRoutingError(RuntimeError):
    code: UseCaseRoutingErrorCode
    safe_reason: str

    def __init__(self, code: UseCaseRoutingErrorCode) -> None:
        if not isinstance(code, UseCaseRoutingErrorCode):
            raise TypeError("code must be a UseCaseRoutingErrorCode")
        self.code = code
        self.safe_reason = _SAFE_REASONS[code]
        super().__init__(self.safe_reason)
