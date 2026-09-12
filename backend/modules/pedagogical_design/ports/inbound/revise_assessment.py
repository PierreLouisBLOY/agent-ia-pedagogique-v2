from collections.abc import Callable, Mapping
from typing import Protocol

from backend.modules.pedagogical_design.contracts.dto.assessment_bundle import AssessmentBundle
from backend.modules.pedagogical_design.contracts.dto.assessment_revision import (
    AssessmentRevisionRequest,
    EditorialCorrectionPlan,
)


class ReviseAssessment(Protocol):
    def execute(self, request: AssessmentRevisionRequest, proposed: Mapping[str, object], *,
                version_ref: str, lineage: Mapping[str, object]) -> AssessmentBundle: ...

    def execute_editorial(
        self, plan: EditorialCorrectionPlan, parent: AssessmentBundle, *,
        version_ref: str, lineage: Mapping[str, object],
        calculate_locators: Callable[[str, str, tuple[str, ...]], tuple[dict[str, object], ...]],
    ) -> AssessmentBundle: ...
