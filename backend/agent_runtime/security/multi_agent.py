from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import NoReturn

from backend.agent_runtime.contracts.common import (
    AgentId,
    ContractRef,
    ContractSchemaVersion,
)
from backend.agent_runtime.contracts.delegation import DelegationResult
from backend.agent_runtime.contracts.invocation import AgentInvocation
from backend.agent_runtime.contracts.policy import PermissionScope
from backend.agent_runtime.contracts.security import (
    ContentOrigin,
    ContentRole,
    ContentSecurityDisposition,
    ContentThreatSignalCode,
    ContentTrustClass,
    ContentTrustLabel,
    SecurityBoundary,
    SecurityEvent,
    SecurityEventType,
    SecurityReasonCode,
    SecuritySeverity,
    StructuredContentSecurityAssessment,
    ValidatedAgentHandoff,
)
from backend.agent_runtime.policy import (
    CapabilityAuthorizationPolicy,
    DelegationAuthorizationCode,
)
from backend.agent_runtime.security.tool_application import (
    assess_structured_boundary_content,
)
from backend.shared_kernel.correlation import CorrelationId
from backend.shared_kernel.time import Instant

_HANDOFF_AUTHORITY_KEYS = frozenset(
    {
        "agent_id",
        "artifact_refs",
        "capability",
        "capability_id",
        "correlation_id",
        "delegation_id",
        "domain_validated",
        "effect_state",
        "evidence_refs",
        "gate",
        "gate_decision",
        "handler",
        "owner",
        "permission",
        "permission_scope",
        "policy_facts",
        "promotion",
        "promotion_allowed",
        "provider",
        "recovery",
        "recovery_facts",
        "route",
        "run_id",
        "runtime_mode",
        "runtime_override",
        "source_agent",
        "step_id",
        "target_agent",
        "validator",
    }
)


class AgentHandoffSecurityErrorCode(StrEnum):
    DELEGATOR_NOT_AG01 = "DELEGATOR_NOT_AG01"
    DELEGATION_REQUIRED = "DELEGATION_REQUIRED"
    RESULT_DELEGATION_REQUIRED = "RESULT_DELEGATION_REQUIRED"
    DELEGATION_MISMATCH = "DELEGATION_MISMATCH"
    INVOCATION_MISMATCH = "INVOCATION_MISMATCH"
    LINEAGE_MISMATCH = "LINEAGE_MISMATCH"
    PRODUCER_MISMATCH = "PRODUCER_MISMATCH"
    SCOPE_DENIED = "SCOPE_DENIED"
    EVIDENCE_OUT_OF_SCOPE = "EVIDENCE_OUT_OF_SCOPE"
    AUTHORITY_METADATA_FORBIDDEN = "AUTHORITY_METADATA_FORBIDDEN"


class AgentHandoffSecurityError(ValueError):
    """Closed, raw-content-free refusal at an inter-agent boundary."""

    def __init__(self, code: AgentHandoffSecurityErrorCode) -> None:
        if type(code) is not AgentHandoffSecurityErrorCode:
            raise TypeError("code must be an AgentHandoffSecurityErrorCode")
        self.code = code
        super().__init__(code.value)


@dataclass(frozen=True, slots=True)
class AgentHandoffSecurityPolicy:
    """Validate lineage and classify content without granting authority."""

    authorization_policy: CapabilityAuthorizationPolicy = field(
        default_factory=CapabilityAuthorizationPolicy
    )

    def __post_init__(self) -> None:
        if type(self.authorization_policy) is not CapabilityAuthorizationPolicy:
            raise TypeError(
                "authorization_policy must be a CapabilityAuthorizationPolicy"
            )

    def secure[TPayload](
        self,
        *,
        delegator: AgentId,
        parent_scope: PermissionScope,
        invocation: AgentInvocation,
        result: DelegationResult[TPayload],
        evaluated_at: Instant,
        parent_revoked: bool = False,
    ) -> ValidatedAgentHandoff[TPayload]:
        if delegator is not AgentId.AG_01:
            _refuse(AgentHandoffSecurityErrorCode.DELEGATOR_NOT_AG01)
        if type(parent_scope) is not PermissionScope:
            raise TypeError("parent_scope must be a PermissionScope")
        if type(invocation) is not AgentInvocation:
            raise TypeError("invocation must be an AgentInvocation")
        if not isinstance(result, DelegationResult):
            raise TypeError("result must be a DelegationResult")
        if type(evaluated_at) is not Instant:
            raise TypeError("evaluated_at must be an Instant")
        if type(parent_revoked) is not bool:
            raise TypeError("parent_revoked must be a bool")
        delegation = invocation.delegation
        if delegation is None:
            _refuse(AgentHandoffSecurityErrorCode.DELEGATION_REQUIRED)
        if result.delegation is None:
            _refuse(AgentHandoffSecurityErrorCode.RESULT_DELEGATION_REQUIRED)
        if result.delegation != delegation or result.delegation_id != delegation.delegation_id:
            _refuse(AgentHandoffSecurityErrorCode.DELEGATION_MISMATCH)
        if result.source_agent is not invocation.agent_id:
            _refuse(AgentHandoffSecurityErrorCode.PRODUCER_MISMATCH)
        if result.agent_result.producer_agent is not invocation.agent_id:
            _refuse(AgentHandoffSecurityErrorCode.PRODUCER_MISMATCH)
        if result.agent_result.invocation_id != invocation.invocation_id:
            _refuse(AgentHandoffSecurityErrorCode.INVOCATION_MISMATCH)
        if not _same_lineage(invocation, result):
            _refuse(AgentHandoffSecurityErrorCode.LINEAGE_MISMATCH)

        capability_id = delegation.source_step.capability_id
        if capability_id is None:
            _refuse(AgentHandoffSecurityErrorCode.DELEGATION_MISMATCH)
        authorization = self.authorization_policy.evaluate_delegation(
            parent_scope=parent_scope,
            child_scope=delegation.permission_scope,
            capability_id=capability_id,
            target_agent=delegation.target_agent,
            evaluated_at=evaluated_at,
            parent_revoked=parent_revoked,
        )
        if authorization.code is not DelegationAuthorizationCode.ALLOW:
            _refuse(AgentHandoffSecurityErrorCode.SCOPE_DENIED)
        if result.source_agent in {AgentId.AG_03, AgentId.AG_04} and not set(
            result.agent_result.evidence_refs
        ).issubset(delegation.evidence_refs):
            _refuse(AgentHandoffSecurityErrorCode.EVIDENCE_OUT_OF_SCOPE)

        context_label = ContentTrustLabel(
            ContentOrigin.AGENT_OUTPUT,
            ContentRole.RESULT,
            ContentTrustClass.STRUCTURALLY_VALIDATED,
            f"delegation:{delegation.delegation_id}",
        )
        context_content, context_assessment = assess_structured_boundary_content(
            delegation.context_slice,
            content_ref=f"delegation-context:{delegation.delegation_id}",
            label=context_label,
            boundary=SecurityBoundary.AGENT,
            forbidden_keys=_HANDOFF_AUTHORITY_KEYS,
            root_location="delegation.context_slice",
        )
        output_label = ContentTrustLabel(
            _output_origin(result.source_agent, capability_id.value),
            ContentRole.RESULT,
            ContentTrustClass.STRUCTURALLY_VALIDATED,
            f"agent-result:{result.agent_result.invocation_id}",
        )
        output_content, output_assessment = assess_structured_boundary_content(
            _result_content(result),
            content_ref=f"agent-result-content:{result.agent_result.invocation_id}",
            label=output_label,
            boundary=SecurityBoundary.AGENT,
            forbidden_keys=_HANDOFF_AUTHORITY_KEYS,
            root_location="agent_result",
        )
        if context_assessment.structural_locations or output_assessment.structural_locations:
            _refuse(AgentHandoffSecurityErrorCode.AUTHORITY_METADATA_FORBIDDEN)
        return ValidatedAgentHandoff(
            invocation=invocation,
            result=result,
            output_label=output_label,
            context_content=context_content,
            output_content=output_content,
            context_assessment=context_assessment,
            output_assessment=output_assessment,
        )


def security_event_from_agent_handoff_error(
    error: AgentHandoffSecurityError,
    *,
    schema_version: ContractSchemaVersion,
    event_id: str,
    occurred_at: Instant,
    run_id: str,
    correlation_id: CorrelationId,
    step_id: str,
    refs: tuple[ContractRef, ...] = (),
) -> SecurityEvent:
    if type(error) is not AgentHandoffSecurityError:
        raise TypeError("error must be an AgentHandoffSecurityError")
    event_type = (
        SecurityEventType.AUTHORITY_SMUGGLING
        if error.code is AgentHandoffSecurityErrorCode.AUTHORITY_METADATA_FORBIDDEN
        else SecurityEventType.TRUST_BOUNDARY_VIOLATION
        if error.code
        in {
            AgentHandoffSecurityErrorCode.PRODUCER_MISMATCH,
            AgentHandoffSecurityErrorCode.SCOPE_DENIED,
            AgentHandoffSecurityErrorCode.EVIDENCE_OUT_OF_SCOPE,
        }
        else SecurityEventType.AGENT_HANDOFF_VIOLATION
    )
    return SecurityEvent(
        schema_version=schema_version,
        event_id=event_id,
        event_type=event_type,
        severity=SecuritySeverity.HIGH,
        boundary=SecurityBoundary.AGENT,
        reason_code=SecurityReasonCode(f"AGENT_HANDOFF.{error.code.value}"),
        occurred_at=occurred_at,
        run_id=run_id,
        correlation_id=correlation_id,
        step_id=step_id,
        refs=refs,
        metadata={"violation_code": error.code.value},
    )


def security_event_from_agent_content_assessment(
    assessment: StructuredContentSecurityAssessment,
    *,
    schema_version: ContractSchemaVersion,
    event_id: str,
    occurred_at: Instant,
    run_id: str,
    correlation_id: CorrelationId,
    step_id: str,
    hostile_propagation: bool = False,
) -> SecurityEvent | None:
    if type(assessment) is not StructuredContentSecurityAssessment:
        raise TypeError("assessment must be a StructuredContentSecurityAssessment")
    if type(hostile_propagation) is not bool:
        raise TypeError("hostile_propagation must be a bool")
    signal_codes = {
        signal.code
        for nested in assessment.content_assessments
        for signal in nested.signals
    }
    if assessment.structural_locations:
        event_type = SecurityEventType.AUTHORITY_SMUGGLING
    elif hostile_propagation and signal_codes:
        event_type = SecurityEventType.HOSTILE_CONTENT_PROPAGATION
    elif ContentThreatSignalCode.ROLE_CONFUSION in signal_codes:
        event_type = SecurityEventType.TRUST_BOUNDARY_VIOLATION
    elif signal_codes:
        event_type = SecurityEventType.INDIRECT_CONTENT_INJECTION
    else:
        return None
    return SecurityEvent(
        schema_version=schema_version,
        event_id=event_id,
        event_type=event_type,
        severity=(
            SecuritySeverity.HIGH
            if assessment.disposition
            in {
                ContentSecurityDisposition.QUARANTINE,
                ContentSecurityDisposition.REJECT_CONTENT,
            }
            else SecuritySeverity.MEDIUM
        ),
        boundary=SecurityBoundary.AGENT,
        reason_code=assessment.reason_codes[0],
        occurred_at=occurred_at,
        run_id=run_id,
        correlation_id=correlation_id,
        step_id=step_id,
        refs=(assessment.content_ref,),
        content_label=assessment.label,
        metadata={"signal_count": len(signal_codes)},
    )


def _same_lineage(
    invocation: AgentInvocation, result: DelegationResult[object]
) -> bool:
    result_meta = result.agent_result.meta
    invocation_meta = invocation.meta
    return bool(
        result_meta.schema_version == invocation_meta.schema_version
        and result_meta.run_id == invocation_meta.run_id
        and result_meta.step_id == invocation_meta.step_id
        and result_meta.parent_step_id == invocation_meta.parent_step_id
        and result_meta.correlation_id == invocation_meta.correlation_id
    )


def _result_content(result: DelegationResult[object]) -> dict[str, object]:
    agent_result = result.agent_result
    return {
        "result": agent_result.payload,
        "warnings": agent_result.warnings,
        "metrics": agent_result.metrics,
        "error_message": agent_result.error.message if agent_result.error else None,
        "error_details": agent_result.error.details if agent_result.error else {},
        "stop_reason": agent_result.stop_reason,
    }


def _output_origin(source_agent: AgentId, capability_id: str) -> ContentOrigin:
    if source_agent is AgentId.AG_04:
        return ContentOrigin.REVIEW_OUTPUT
    if source_agent is AgentId.AG_03 and capability_id == "CAP-G03":
        return ContentOrigin.CORRECTION_OUTPUT
    return ContentOrigin.AGENT_OUTPUT


def _refuse(code: AgentHandoffSecurityErrorCode) -> NoReturn:
    raise AgentHandoffSecurityError(code)
