from __future__ import annotations

from dataclasses import dataclass

from backend.modules.resource_library.application.dto.input.exact_resource_evidence import (
    ExactResourceEvidenceRequest,
)
from backend.modules.resource_library.application.dto.output.exact_resource_evidence import (
    ExactResourceEvidenceView,
)
from backend.modules.resource_library.ports.outbound.exact_resource_evidence import (
    ExactResourceEvidencePort,
    ExactResourceLookupStatus,
)

_ERRORS = {
    ExactResourceLookupStatus.RESOURCE_NOT_FOUND: "R6_RESOURCE_NOT_FOUND",
    ExactResourceLookupStatus.VERSION_NOT_FOUND: "R6_RESOURCE_VERSION_NOT_FOUND",
    ExactResourceLookupStatus.VERSION_MISMATCH: "R6_RESOURCE_VERSION_MISMATCH",
}


@dataclass(frozen=True, slots=True)
class GetExactResourceEvidenceQuery:
    """Read one exact M03 resource version without storage details or fallback."""

    source: ExactResourceEvidencePort

    def __post_init__(self) -> None:
        if not isinstance(self.source, ExactResourceEvidencePort):
            raise TypeError("source must implement ExactResourceEvidencePort")

    def execute(self, request: ExactResourceEvidenceRequest) -> ExactResourceEvidenceView:
        if not isinstance(request, ExactResourceEvidenceRequest):
            raise TypeError("request must be an ExactResourceEvidenceRequest")
        lookup = self.source.load_exact_resource(
            request.resource_ref, request.resource_version_ref
        )
        if lookup.status is not ExactResourceLookupStatus.FOUND:
            raise ValueError(_ERRORS[lookup.status])
        if lookup.record is None:
            raise ValueError("R6_RESOURCE_LOOKUP_SHAPE_INVALID")
        return ExactResourceEvidenceView.from_record(lookup.record)
