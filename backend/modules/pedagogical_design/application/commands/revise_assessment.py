from collections.abc import Callable, Mapping

from backend.modules.pedagogical_design.contracts.dto.assessment_bundle import AssessmentBundle
from backend.modules.pedagogical_design.contracts.dto.assessment_revision import (
    AssessmentRevisionRequest,
    EditorialCorrectionPlan,
)
from backend.modules.pedagogical_design.domain.policies.assessment_revision import (
    assemble_editorial_corrections,
    assemble_revision,
)


class ReviseAssessmentCommand:
    def execute(self, request: AssessmentRevisionRequest, proposed: Mapping[str, object], *,
                version_ref: str, lineage: Mapping[str, object],
                observe: Callable[[str], None] | None = None) -> AssessmentBundle:
        return assemble_revision(request, proposed, version_ref=version_ref, lineage=lineage,
                                 observe=observe)

    def execute_editorial(
        self, plan: EditorialCorrectionPlan, parent: AssessmentBundle, *,
        version_ref: str, lineage: Mapping[str, object],
        calculate_locators: Callable[[str, str, tuple[str, ...]], tuple[dict[str, object], ...]],
    ) -> AssessmentBundle:
        return assemble_editorial_corrections(plan, parent, version_ref=version_ref,
            lineage=lineage, calculate_locators=calculate_locators)
