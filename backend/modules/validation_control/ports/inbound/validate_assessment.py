from collections.abc import Mapping
from typing import Protocol

from backend.modules.pedagogical_design.contracts.dto.assessment_bundle import AssessmentBundle
from backend.modules.validation_control.contracts.dto.deterministic_validation import (
    AssessmentValidation,
)


class ValidateAssessment(Protocol):
    def execute(self, bundle: AssessmentBundle | None, *, production_ref: str,
                version_ref: str, subject_sha256: str, validation_ref: str, evaluated_at: str,
                references: tuple[Mapping[str, object], ...],
                parent: AssessmentBundle | None = None) -> AssessmentValidation: ...
