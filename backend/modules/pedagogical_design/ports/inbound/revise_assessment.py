from collections.abc import Mapping
from typing import Protocol

from backend.modules.pedagogical_design.contracts.dto.assessment_bundle import AssessmentBundle
from backend.modules.pedagogical_design.contracts.dto.assessment_revision import (
    AssessmentRevisionRequest,
)


class ReviseAssessment(Protocol):
    def execute(self, request: AssessmentRevisionRequest, proposed: Mapping[str, object], *,
                version_ref: str, lineage: Mapping[str, object]) -> AssessmentBundle: ...
