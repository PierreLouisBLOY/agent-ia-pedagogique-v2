from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass

from backend.agent_runtime.application_routing.model import (
    UseCaseDescriptor,
    UseCaseRoutingContext,
    UseCaseRoutingError,
    UseCaseRoutingErrorCode,
)
from backend.agent_runtime.application_routing.ports import (
    UnknownUseCaseInboundBindingError,
    UseCaseInboundBindings,
)
from backend.agent_runtime.application_routing.registry import (
    UnknownUseCaseError,
    UseCaseRegistry,
)
from backend.agent_runtime.contracts import (
    ActorKind,
    AgentId,
    ContractMeta,
    ExecutorKind,
    PermissionScope,
    StepKind,
    StepSpec,
    UseCaseRequest,
    UseCaseResult,
)
from backend.agent_runtime.contracts.common import (
    freeze_agent_safe_mapping,
    require_contract_ref,
)
from backend.agent_runtime.contracts.errors import ErrorEnvelope
from backend.agent_runtime.contracts.security import (
    ContentOrigin,
    ContentRole,
    ContentTrustClass,
    ContentTrustLabel,
    LabeledContent,
    SecurityBoundary,
    StructuredContentSecurityAssessment,
)
from backend.agent_runtime.policy import (
    CapabilityAuthorizationPolicy,
    CapabilityPolicyDecision,
    PermissionOperation,
    PolicyDisposition,
    PolicyFacts,
    ScopeCheck,
)
from backend.agent_runtime.registry import (
    CapabilityClass,
    CapabilityExecutionRoute,
    UnknownCapabilityError,
)
from backend.agent_runtime.security import (
    assess_structured_boundary_content,
    contains_structural_keys,
)
from backend.core_contracts.capability import CapabilityId
from backend.core_contracts.invocation import UseCaseContext
from backend.core_contracts.outcome import (
    ApplicationFailure,
    ApplicationOutcome,
    OutcomeStatus,
)
from backend.shared_kernel.errors import BusinessError
from backend.shared_kernel.references import TypedEntityRef
from backend.shared_kernel.time import Instant

_PERMISSION_OPERATION_BY_CAPABILITY = {
    "CAP-R01": PermissionOperation.READ,
    "CAP-R02": PermissionOperation.READ,
    "CAP-R03": PermissionOperation.READ,
    "CAP-A01": PermissionOperation.REQUEST,
    "CAP-A02": PermissionOperation.REQUEST,
    "CAP-A03": PermissionOperation.REQUEST,
}
APPLICATION_PAYLOAD_FORBIDDEN_KEYS = frozenset(
    {
        "binding",
        "capability",
        "capability_id",
        "circuit_binding",
        "effect_state",
        "gate",
        "permission_scope",
        "permission",
        "gate_decision",
        "gate_approved",
        "promotion_allowed",
        "validated",
        "approved",
        "handler",
        "handler_id",
        "handler_path",
        "import_path",
        "provider",
        "provider_id",
        "credentials",
        "runtime_override",
        "executor",
        "use_case_override",
        "use_case_id",
        "use_case",
        "owner",
        "policy_facts",
        "reconciliation_status",
        "record_id",
        "retry_facts",
        "route",
        "snapshot_ref",
        "snapshot_refs",
        "target",
    }
)
APPLICATION_REQUESTED_EFFECT_FORBIDDEN_KEYS = frozenset(
    {
        *APPLICATION_PAYLOAD_FORBIDDEN_KEYS,
        "committed",
        "effect_committed",
        "effect_succeeded",
        "proof_of_effect",
        "success",
        "succeeded",
    }
)
_APPLICATION_RESULT_FORBIDDEN_KEYS = frozenset(
    {
        *APPLICATION_PAYLOAD_FORBIDDEN_KEYS,
        "gate_approval",
        "gate_approved",
        "promotion_allowed",
    }
)
_APPLICATION_REQUEST_CONTRACT_ID = "C-12"
_APPLICATION_RESULT_CONTRACT_ID = "C-13"


@dataclass(frozen=True, slots=True)
class UseCaseRouter:
    capability_policy: CapabilityAuthorizationPolicy
    use_case_registry: UseCaseRegistry
    inbound_bindings: UseCaseInboundBindings

    def __post_init__(self) -> None:
        if not isinstance(self.capability_policy, CapabilityAuthorizationPolicy):
            raise TypeError("capability_policy must be a CapabilityAuthorizationPolicy")
        if not isinstance(self.use_case_registry, UseCaseRegistry):
            raise TypeError("use_case_registry must be a UseCaseRegistry")
        if not isinstance(self.inbound_bindings, UseCaseInboundBindings):
            raise TypeError("inbound_bindings must be UseCaseInboundBindings")
        if (
            self.use_case_registry.capability_registry
            is not self.capability_policy.capability_registry
        ):
            raise ValueError(
                "use-case registry and policy must share CapabilityRegistry"
            )

    def route(
        self,
        *,
        agent_id: AgentId,
        request: UseCaseRequest,
        context: UseCaseRoutingContext,
        evaluated_at: Instant,
    ) -> UseCaseResult[object, object]:
        if not isinstance(agent_id, AgentId) or not isinstance(evaluated_at, Instant):
            raise UseCaseRoutingError(UseCaseRoutingErrorCode.INVALID_ROUTING_CONTEXT)
        _validate_request_and_context(agent_id, request, context)

        try:
            descriptor = self.use_case_registry.get(request.use_case_id)
        except UnknownUseCaseError:
            raise UseCaseRoutingError(UseCaseRoutingErrorCode.UNKNOWN_USE_CASE) from None
        if descriptor.request_contract_id != _APPLICATION_REQUEST_CONTRACT_ID:
            raise UseCaseRoutingError(
                UseCaseRoutingErrorCode.REQUEST_CONTRACT_MISMATCH
            )
        if descriptor.result_contract_id != _APPLICATION_RESULT_CONTRACT_ID:
            raise UseCaseRoutingError(
                UseCaseRoutingErrorCode.RESULT_CONTRACT_MISMATCH
            )

        capability_id = context.step.capability_id
        if capability_id is None:
            raise UseCaseRoutingError(
                UseCaseRoutingErrorCode.NON_APPLICATION_CAPABILITY
            )
        try:
            capability = self.capability_policy.capability_registry.get(capability_id)
        except UnknownCapabilityError:
            raise UseCaseRoutingError(
                UseCaseRoutingErrorCode.NON_APPLICATION_CAPABILITY
            ) from None
        if (
            capability.execution_route is not CapabilityExecutionRoute.APPLICATION
            or capability.capability_class
            not in {CapabilityClass.READ, CapabilityClass.APPLICATION_ACTION}
            or capability.owner_agent is not None
        ):
            raise UseCaseRoutingError(
                UseCaseRoutingErrorCode.NON_APPLICATION_CAPABILITY
            )
        if descriptor.capability_id != capability_id:
            raise UseCaseRoutingError(
                UseCaseRoutingErrorCode.CAPABILITY_USE_CASE_MISMATCH
            )
        if descriptor.idempotency_required and request.idempotency_key is None:
            raise UseCaseRoutingError(UseCaseRoutingErrorCode.IDEMPOTENCY_REQUIRED)
        payload_security, requested_effect_security = (
            assess_use_case_request_security(request)
        )
        if (
            payload_security.structural_locations
            or requested_effect_security.structural_locations
        ):
            raise UseCaseRoutingError(
                UseCaseRoutingErrorCode.AUTHORITY_METADATA_FORBIDDEN
            )

        operation = _PERMISSION_OPERATION_BY_CAPABILITY.get(capability_id.value)
        if operation is None:
            raise UseCaseRoutingError(UseCaseRoutingErrorCode.REQUEST_NOT_ROUTABLE)
        scope = context.permission_scope
        scope_check = ScopeCheck(
            principal=scope.principal,
            capability_id=capability_id,
            operation=operation,
            resource_scope=scope.resource_scope,
            constraints=scope.constraints,
            requested_budget=scope.budget,
            evaluated_at=evaluated_at,
        )
        try:
            decision = self.capability_policy.evaluate(
                agent_id=agent_id,
                scope=scope,
                check=scope_check,
                facts=context.policy_facts,
            )
        except Exception:
            raise UseCaseRoutingError(
                UseCaseRoutingErrorCode.REQUEST_NOT_ROUTABLE
            ) from None
        if not _is_routable_application_request(decision, capability_id):
            raise UseCaseRoutingError(UseCaseRoutingErrorCode.REQUEST_NOT_ROUTABLE)

        try:
            inbound = self.inbound_bindings.get(request.use_case_id)
        except UnknownUseCaseInboundBindingError:
            raise UseCaseRoutingError(
                UseCaseRoutingErrorCode.USE_CASE_NOT_BOUND
            ) from None
        try:
            result = inbound.invoke(request=request)
        except Exception:
            raise UseCaseRoutingError(UseCaseRoutingErrorCode.INBOUND_FAILED) from None
        return _validate_result(request, descriptor, result)


def _validate_request_and_context(
    agent_id: AgentId,
    request: UseCaseRequest,
    context: UseCaseRoutingContext,
) -> None:
    if type(request) is not UseCaseRequest or type(context) is not UseCaseRoutingContext:
        raise UseCaseRoutingError(UseCaseRoutingErrorCode.INVALID_ROUTING_CONTEXT)
    try:
        validated_meta = ContractMeta(
            schema_version=request.meta.schema_version,
            run_id=request.meta.run_id,
            step_id=request.meta.step_id,
            parent_step_id=request.meta.parent_step_id,
            correlation_id=request.meta.correlation_id,
            created_at=request.meta.created_at,
            actor=request.meta.actor,
            status=request.meta.status,
            trace_flags=request.meta.trace_flags,
        )
        actor_context = request.actor_context
        validated_actor_context = UseCaseContext(
            correlation_id=actor_context.correlation_id,
            session_ref=actor_context.session_ref,
            task_ref=actor_context.task_ref,
            pedagogical_context_ref=actor_context.pedagogical_context_ref,
            context_snapshot=actor_context.context_snapshot,
            operation_ref=actor_context.operation_ref,
            actor_ref=actor_context.actor_ref,
        )
        UseCaseRequest(
            meta=validated_meta,
            use_case_id=request.use_case_id,
            payload=request.payload,
            actor_context=validated_actor_context,
            precondition_refs=request.precondition_refs,
            idempotency_key=request.idempotency_key,
            requested_effect=request.requested_effect,
        )
        step = context.step
        validated_step = StepSpec(
            step_id=step.step_id,
            kind=step.kind,
            capability_id=step.capability_id,
            executor=step.executor,
            objective=step.objective,
            input_refs=step.input_refs,
            depends_on=step.depends_on,
            permission_scope_ref=step.permission_scope_ref,
            budget=step.budget,
            success_criteria=step.success_criteria,
            failure_policy=step.failure_policy,
            output_contract=step.output_contract,
            parallel_group=step.parallel_group,
        )
        scope = context.permission_scope
        validated_scope = PermissionScope(
            principal=scope.principal,
            capability_ids=scope.capability_ids,
            resource_scope=scope.resource_scope,
            operations=scope.operations,
            constraints=scope.constraints,
            valid_from=scope.valid_from,
            expires_at=scope.expires_at,
            budget=scope.budget,
            delegable=scope.delegable,
            gate_requirements=scope.gate_requirements,
            deny_rules=scope.deny_rules,
        )
        validated_facts = PolicyFacts(
            matrix_gate_satisfied=context.policy_facts.matrix_gate_satisfied,
            conditional_resolution=context.policy_facts.conditional_resolution,
        )
        UseCaseRoutingContext(
            step=validated_step,
            permission_scope_ref=context.permission_scope_ref,
            permission_scope=validated_scope,
            policy_facts=validated_facts,
        )
    except (AttributeError, TypeError, ValueError):
        raise UseCaseRoutingError(
            UseCaseRoutingErrorCode.INVALID_ROUTING_CONTEXT
        ) from None

    step = context.step
    if step.kind is not StepKind.USE_CASE:
        raise UseCaseRoutingError(UseCaseRoutingErrorCode.STEP_KIND_MISMATCH)
    if step.executor.kind is not ExecutorKind.APPLICATION:
        raise UseCaseRoutingError(UseCaseRoutingErrorCode.EXECUTOR_MISMATCH)
    if step.permission_scope_ref is None or (
        context.permission_scope_ref != step.permission_scope_ref
    ):
        raise UseCaseRoutingError(UseCaseRoutingErrorCode.INVALID_ROUTING_CONTEXT)
    if request.meta.step_id != step.step_id:
        raise UseCaseRoutingError(UseCaseRoutingErrorCode.INVALID_ROUTING_CONTEXT)
    if request.meta.correlation_id != request.actor_context.correlation_id:
        raise UseCaseRoutingError(UseCaseRoutingErrorCode.INVALID_ROUTING_CONTEXT)
    actor = request.meta.actor
    if (
        actor.kind is not ActorKind.AGENT
        or actor.actor_id != agent_id.value
        or context.permission_scope.principal != actor
    ):
        raise UseCaseRoutingError(UseCaseRoutingErrorCode.INVALID_ROUTING_CONTEXT)
    try:
        for precondition_ref in request.precondition_refs:
            require_contract_ref(precondition_ref, "precondition_ref")
        freeze_agent_safe_mapping(request.payload)
        freeze_agent_safe_mapping(request.requested_effect)
    except (TypeError, ValueError):
        raise UseCaseRoutingError(
            UseCaseRoutingErrorCode.INVALID_ROUTING_CONTEXT
        ) from None


def assess_use_case_request_security(
    request: UseCaseRequest,
) -> tuple[
    StructuredContentSecurityAssessment,
    StructuredContentSecurityAssessment,
]:
    if type(request) is not UseCaseRequest:
        raise TypeError("request must be a UseCaseRequest")
    request_ref = f"application-request:{request.use_case_id}:{request.meta.step_id}"
    request_label = ContentTrustLabel(
        origin=ContentOrigin.AGENT_OUTPUT,
        role=ContentRole.RESULT,
        trust_class=ContentTrustClass.UNTRUSTED,
        source_ref=request_ref,
    )
    payload_security = assess_structured_boundary_content(
        request.payload,
        content_ref=f"{request_ref}:payload",
        label=request_label,
        boundary=SecurityBoundary.APPLICATION,
        forbidden_keys=APPLICATION_PAYLOAD_FORBIDDEN_KEYS,
        root_location="application_payload",
    )[1]
    requested_effect_security = assess_structured_boundary_content(
        request.requested_effect,
        content_ref=f"{request_ref}:requested_effect",
        label=request_label,
        boundary=SecurityBoundary.APPLICATION,
        forbidden_keys=APPLICATION_REQUESTED_EFFECT_FORBIDDEN_KEYS,
        root_location="requested_effect",
    )[1]
    return payload_security, requested_effect_security


def _is_routable_application_request(
    decision: object,
    capability_id: CapabilityId,
) -> bool:
    return (
        type(decision) is CapabilityPolicyDecision
        and decision.disposition is PolicyDisposition.REQUEST
        and decision.capability_id == capability_id
        and decision.route is CapabilityExecutionRoute.APPLICATION
    )


def _validate_result(
    request: UseCaseRequest,
    descriptor: UseCaseDescriptor,
    candidate: object,
) -> UseCaseResult[object, object]:
    if type(candidate) is not UseCaseResult:
        raise UseCaseRoutingError(UseCaseRoutingErrorCode.INVALID_USE_CASE_RESULT)
    try:
        if candidate.use_case_id != request.use_case_id:
            raise UseCaseRoutingError(
                UseCaseRoutingErrorCode.RESULT_USE_CASE_MISMATCH
            )
        if candidate.meta.run_id != request.meta.run_id:
            raise UseCaseRoutingError(UseCaseRoutingErrorCode.RESULT_RUN_MISMATCH)
        if candidate.meta.step_id != request.meta.step_id:
            raise UseCaseRoutingError(UseCaseRoutingErrorCode.RESULT_STEP_MISMATCH)
        if candidate.meta.correlation_id != request.meta.correlation_id:
            raise UseCaseRoutingError(
                UseCaseRoutingErrorCode.RESULT_CORRELATION_MISMATCH
            )
        outcome = candidate.outcome
        if type(outcome) is not ApplicationOutcome:
            raise TypeError("invalid outcome")
        if outcome.correlation_id != request.meta.correlation_id:
            raise UseCaseRoutingError(
                UseCaseRoutingErrorCode.RESULT_CORRELATION_MISMATCH
            )
        if type(candidate.meta) is not ContractMeta or type(
            candidate.meta.status
        ) is not OutcomeStatus:
            raise TypeError("invalid result metadata")
        if candidate.meta.status is not outcome.outcome_status:
            raise ValueError("result status mismatch")
        if not isinstance(outcome.business_errors, tuple) or any(
            type(error) is not BusinessError for error in outcome.business_errors
        ):
            raise TypeError("invalid business errors")
        if not isinstance(outcome.warnings, tuple) or any(
            type(warning) is not BusinessError for warning in outcome.warnings
        ):
            raise TypeError("invalid warnings")
        if not isinstance(outcome.side_effects, tuple) or any(
            not isinstance(side_effect, Mapping)
            for side_effect in outcome.side_effects
        ):
            raise TypeError("invalid side effects")
        if outcome.application_failure is not None and type(
            outcome.application_failure
        ) is not ApplicationFailure:
            raise TypeError("invalid application failure")
        if not isinstance(outcome.subject_refs, tuple) or any(
            type(reference) is not TypedEntityRef
            for reference in outcome.subject_refs
        ):
            raise TypeError("invalid subject refs")
        if outcome.operation_ref is not None and type(
            outcome.operation_ref
        ) is not TypedEntityRef:
            raise TypeError("invalid operation ref")
        if outcome.task_ref is not None and type(outcome.task_ref) is not TypedEntityRef:
            raise TypeError("invalid task ref")
        if outcome.success and (
            outcome.business_errors
            or outcome.application_failure is not None
            or candidate.error is not None
        ):
            raise ValueError("successful result masks an error")
        _validate_application_result_data(candidate)

        validated_outcome: ApplicationOutcome[object, object] = ApplicationOutcome(
            outcome_status=outcome.outcome_status,
            success=outcome.success,
            correlation_id=outcome.correlation_id,
            data=outcome.data,
            business_errors=outcome.business_errors,
            validation_result=outcome.validation_result,
            application_failure=outcome.application_failure,
            warnings=outcome.warnings,
            side_effects=outcome.side_effects,
            operation_ref=outcome.operation_ref,
            task_ref=outcome.task_ref,
            subject_refs=outcome.subject_refs,
        )
        validated_meta = ContractMeta(
            schema_version=candidate.meta.schema_version,
            run_id=candidate.meta.run_id,
            step_id=candidate.meta.step_id,
            parent_step_id=candidate.meta.parent_step_id,
            correlation_id=candidate.meta.correlation_id,
            created_at=candidate.meta.created_at,
            actor=candidate.meta.actor,
            status=candidate.meta.status,
            trace_flags=candidate.meta.trace_flags,
        )
        validated_error = _validate_error(candidate.error, candidate.meta.step_id)
        if candidate.result_ref is not None:
            require_contract_ref(candidate.result_ref, "result_ref")
        if not isinstance(candidate.domain_events, tuple):
            raise TypeError("domain_events must be a tuple")
        for event in candidate.domain_events:
            if isinstance(event, Mapping):
                freeze_agent_safe_mapping(event)
            else:
                require_contract_ref(event, "domain_event")
        validated_result: UseCaseResult[object, object] = UseCaseResult(
            meta=validated_meta,
            use_case_id=candidate.use_case_id,
            outcome=validated_outcome,
            result_ref=candidate.result_ref,
            domain_events=candidate.domain_events,
            error=validated_error,
            content_label=candidate.content_label,
            labeled_content=candidate.labeled_content,
            security_assessments=candidate.security_assessments,
        )
        return _secure_application_result_content(validated_result)
    except UseCaseRoutingError:
        raise
    except (AttributeError, TypeError, ValueError):
        raise UseCaseRoutingError(
            UseCaseRoutingErrorCode.INVALID_USE_CASE_RESULT
        ) from None


def _validate_error(error: object, step_id: str) -> ErrorEnvelope | None:
    if error is None:
        return None
    if type(error) is not ErrorEnvelope or error.step_id != step_id:
        raise TypeError("invalid result error")
    return ErrorEnvelope(
        error_code=error.error_code,
        category=error.category,
        source=error.source,
        retryable=error.retryable,
        severity=error.severity,
        message=error.message,
        step_id=error.step_id,
        attempt=error.attempt,
        effect_state=error.effect_state,
        related_refs=error.related_refs,
        recommended_action=error.recommended_action,
        details=error.details,
    )


def _validate_application_result_data(candidate: UseCaseResult[object, object]) -> None:
    outcome = candidate.outcome
    values = (
        outcome.data,
        outcome.validation_result,
        outcome.side_effects,
        candidate.domain_events,
        (
            outcome.application_failure.details
            if outcome.application_failure is not None
            else None
        ),
        candidate.error.details if candidate.error is not None else None,
        tuple(
            error.details
            for error in (*outcome.business_errors, *outcome.warnings)
            if error.details is not None
        ),
    )
    if any(
        contains_structural_keys(
            value,
            forbidden_keys=_APPLICATION_RESULT_FORBIDDEN_KEYS,
        )
        for value in values
    ):
        raise ValueError("Application result contains authority metadata")
    for value in (outcome.data, outcome.validation_result):
        if isinstance(value, Mapping):
            freeze_agent_safe_mapping(value)


def _secure_application_result_content(
    result: UseCaseResult[object, object],
) -> UseCaseResult[object, object]:
    label = result.content_label
    if label is None:
        raise UseCaseRoutingError(UseCaseRoutingErrorCode.INVALID_USE_CASE_RESULT)
    roots = (
        ("data", result.outcome.data),
        ("validation_result", result.outcome.validation_result),
        ("side_effects", result.outcome.side_effects),
        ("domain_events", result.domain_events),
        (
            "application_failure_details",
            (
                result.outcome.application_failure.details
                if result.outcome.application_failure is not None
                else None
            ),
        ),
        (
            "business_error_details",
            tuple(
                error.details
                for error in (
                    *result.outcome.business_errors,
                    *result.outcome.warnings,
                )
                if error.details is not None
            ),
        ),
        ("error_message", result.error.message if result.error is not None else None),
        ("error_details", result.error.details if result.error is not None else None),
    )
    labeled_content: list[LabeledContent] = []
    assessments: list[StructuredContentSecurityAssessment] = []
    for root, value in roots:
        labeled, assessment = assess_structured_boundary_content(
            value,
            content_ref=f"{label.source_ref}:{root}",
            label=label,
            boundary=SecurityBoundary.APPLICATION,
            forbidden_keys=_APPLICATION_RESULT_FORBIDDEN_KEYS,
            root_location=root,
        )
        labeled_content.extend(labeled)
        assessments.append(assessment)
    return UseCaseResult(
        meta=result.meta,
        use_case_id=result.use_case_id,
        outcome=result.outcome,
        result_ref=result.result_ref,
        domain_events=result.domain_events,
        error=result.error,
        content_label=label,
        labeled_content=tuple(labeled_content),
        security_assessments=tuple(assessments),
    )
