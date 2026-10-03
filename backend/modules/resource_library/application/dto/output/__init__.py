"""Typed resource-library Application outputs."""

from backend.modules.resource_library.application.dto.output.exact_resource_evidence import (
    EXACT_RESOURCE_EVIDENCE_CONTRACT,
    EXACT_RESOURCE_PROVENANCE_LABEL,
    ExactResourceEvidenceView,
    ExactResourceQuestionView,
)
from backend.modules.resource_library.application.dto.output.resource_view import (
    ResourceView,
)

__all__ = [
    "EXACT_RESOURCE_EVIDENCE_CONTRACT",
    "EXACT_RESOURCE_PROVENANCE_LABEL",
    "ExactResourceEvidenceView",
    "ExactResourceQuestionView",
    "ResourceView",
]
