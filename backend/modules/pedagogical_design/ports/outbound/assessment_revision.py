from collections.abc import Mapping
from typing import Protocol

from backend.modules.pedagogical_design.contracts.dto.assessment_revision import (
    AssessmentRevisionRequest,
)


class AssessmentRevisionPort(Protocol):
    def propose(self, request: AssessmentRevisionRequest) -> Mapping[str, object]: ...
