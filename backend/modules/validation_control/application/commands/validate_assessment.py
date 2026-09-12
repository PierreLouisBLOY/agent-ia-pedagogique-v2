from collections.abc import Mapping

from backend.modules.pedagogical_design.contracts.dto.assessment_bundle import AssessmentBundle
from backend.modules.validation_control.contracts.dto.deterministic_validation import (
    AssessmentValidation,
)
from backend.modules.validation_control.contracts.dto.editorial_scope import (
    EditorialValidationScope,
)
from backend.modules.validation_control.domain.policies.assessment_checks import evaluate_checks


class ValidateAssessmentCommand:
    def execute(self, bundle: AssessmentBundle | None, *, production_ref: str,
                version_ref: str, subject_sha256: str, validation_ref: str, evaluated_at: str,
                references: tuple[Mapping[str, object], ...],
                parent: AssessmentBundle | None = None,
                editorial_scope: EditorialValidationScope | None = None) -> AssessmentValidation:
        if bundle is not None and (bundle.production_ref, bundle.version_ref, bundle.data["subject_sha256"]) != (production_ref, version_ref, subject_sha256):
            raise ValueError("ASSESSMENT_REFERENCE")
        return AssessmentValidation(validation_ref, production_ref, version_ref, subject_sha256,
            bundle.sha256 if bundle else None,
            evaluate_checks(bundle, parent=parent, references=references,
                            editorial_scope=editorial_scope), evaluated_at)
