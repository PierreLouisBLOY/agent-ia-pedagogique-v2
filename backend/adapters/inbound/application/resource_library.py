from __future__ import annotations

from collections.abc import Mapping

from backend.agent_runtime.contracts import ContractMeta, UseCaseRequest, UseCaseResult
from backend.core_contracts.outcome import ApplicationOutcome
from backend.modules.resource_library.application.dto.input import GetResourceRequest
from backend.modules.resource_library.application.dto.output import ResourceView
from backend.modules.resource_library.ports.inbound import ResourceLibraryInbound

RESOURCE_READ_USE_CASE_ID = "application.read_canonical_resource"


class ResourceLibraryUseCaseInbound:
    """C-12/C-13 bridge to canonical IP-03 getResource."""

    def __init__(self, resource_library: ResourceLibraryInbound) -> None:
        if not isinstance(resource_library, ResourceLibraryInbound):
            raise TypeError("resource_library must implement ResourceLibraryInbound")
        self._resource_library = resource_library

    def invoke(
        self,
        *,
        request: UseCaseRequest,
    ) -> UseCaseResult[object, object]:
        if type(request) is not UseCaseRequest:
            raise TypeError("request must be a UseCaseRequest")
        if request.use_case_id != RESOURCE_READ_USE_CASE_ID:
            raise ValueError("unsupported use case")
        resource_ref = request.payload.get("resource_ref")
        if type(resource_ref) is not str or not resource_ref:
            raise ValueError("resource_ref must be a non-empty string")
        if set(request.payload) != {"resource_ref"}:
            raise ValueError("getResource payload contains unsupported fields")

        typed_outcome = self._resource_library.get_resource(
            request=GetResourceRequest(resource_ref),
            correlation_id=request.meta.correlation_id,
        )
        outcome: ApplicationOutcome[object, object] = ApplicationOutcome(
            outcome_status=typed_outcome.outcome_status,
            success=typed_outcome.success,
            correlation_id=typed_outcome.correlation_id,
            data=_resource_data(typed_outcome.data),
            business_errors=typed_outcome.business_errors,
            validation_result=typed_outcome.validation_result,
            application_failure=typed_outcome.application_failure,
            warnings=typed_outcome.warnings,
            side_effects=typed_outcome.side_effects,
            operation_ref=typed_outcome.operation_ref,
            task_ref=typed_outcome.task_ref,
            subject_refs=typed_outcome.subject_refs,
        )
        return UseCaseResult(
            meta=ContractMeta(
                schema_version=request.meta.schema_version,
                run_id=request.meta.run_id,
                step_id=request.meta.step_id,
                parent_step_id=request.meta.parent_step_id,
                correlation_id=request.meta.correlation_id,
                created_at=request.meta.created_at,
                actor=request.meta.actor,
                status=outcome.outcome_status,
                trace_flags=request.meta.trace_flags,
            ),
            use_case_id=request.use_case_id,
            outcome=outcome,
        )


def _resource_data(view: ResourceView | None) -> Mapping[str, object] | None:
    if view is None:
        return None
    return {
        "resource_ref": view.resource_ref,
        "resource_type": view.resource_type,
        "canonical_title": view.canonical_title,
        "identity_status": view.identity_status,
    }
