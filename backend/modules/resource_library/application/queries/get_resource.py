from __future__ import annotations

from dataclasses import dataclass

from backend.core_contracts.outcome import ApplicationOutcome, OutcomeStatus
from backend.modules.resource_library.application.dto.input import GetResourceRequest
from backend.modules.resource_library.application.dto.output import ResourceView
from backend.modules.resource_library.ports.outbound import ResourceStorePort
from backend.shared_kernel.correlation import CorrelationId
from backend.shared_kernel.errors import (
    BusinessError,
    BusinessErrorCategory,
    BusinessErrorCode,
    BusinessErrorDomain,
    BusinessErrorSeverity,
)
from backend.shared_kernel.identifiers import TypedEntityId
from backend.shared_kernel.references import TypedEntityRef


@dataclass(frozen=True, slots=True)
class GetResourceQuery:
    """READ-15 implementation owned by M03 and backed only through OP-03."""

    resources: ResourceStorePort

    def __post_init__(self) -> None:
        if not isinstance(self.resources, ResourceStorePort):
            raise TypeError("resources must implement ResourceStorePort")

    def get_resource(
        self,
        *,
        request: GetResourceRequest,
        correlation_id: CorrelationId,
    ) -> ApplicationOutcome[ResourceView, object]:
        if not isinstance(request, GetResourceRequest):
            raise TypeError("request must be a GetResourceRequest")
        if not isinstance(correlation_id, CorrelationId):
            raise TypeError("correlation_id must be a CorrelationId")

        record = self.resources.load_resource(request.resource_ref)
        subject_ref = TypedEntityRef(TypedEntityId("resource", request.resource_ref))
        if record is None:
            return ApplicationOutcome(
                outcome_status=OutcomeStatus.REJECTED,
                success=False,
                correlation_id=correlation_id,
                business_errors=(
                    BusinessError(
                        code=BusinessErrorCode("RES_NOT_FOUND"),
                        domain=BusinessErrorDomain.RESOURCE,
                        category=BusinessErrorCategory.NOT_FOUND,
                        severity=BusinessErrorSeverity.ERROR,
                        blocking=True,
                        retryable=False,
                        message_key="resource.not_found",
                        subject_ref=subject_ref,
                    ),
                ),
                subject_refs=(subject_ref,),
            )

        return ApplicationOutcome(
            outcome_status=OutcomeStatus.SUCCESS,
            success=True,
            correlation_id=correlation_id,
            data=ResourceView(
                resource_ref=record.resource_ref,
                resource_type=record.resource_type.value,
                canonical_title=record.canonical_title,
                identity_status=record.identity_status.value,
            ),
            subject_refs=(subject_ref,),
        )
