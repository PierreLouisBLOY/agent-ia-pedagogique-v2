from backend.agent_runtime.agents.review import ReviewPort
from backend.infrastructure.composition.bindings.r3_agents import review
from backend.modules.pedagogical_design.contracts.dto.assessment_bundle import (
    AssessmentBundle,
    encoded,
    items,
)
from backend.modules.work_orchestration.contracts.dto.operation_identity import OperationIdentity


class AssessmentReviewAdapter:
    def __init__(self, port: ReviewPort) -> None:
        self._port = port

    def review(self, bundle: AssessmentBundle, dimensions: tuple[str, ...], *, identity: OperationIdentity | None = None) -> dict[str, object]:
        output = review(self._port, bundle, dimensions, identity=identity)
        if len(encoded(output)) > 32 * 1024 or len(items(output["findings"], 32)) > 32:
            raise ValueError("R3_REVIEW_SIZE")
        return output
