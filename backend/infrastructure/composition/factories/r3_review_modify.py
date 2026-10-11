"""Explicit R3 composition: synthetic injection only; no automatic provider binding."""
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import uuid4

from backend.adapters.inbound.api.r3_review_modify import R3Endpoint
from backend.adapters.inbound.application.r3_review_modify import R3ApplicationInbound
from backend.adapters.outbound.generation.assessment_revision import AssessmentRevisionAdapter
from backend.adapters.outbound.review.assessment_review import AssessmentReviewAdapter
from backend.adapters.outbound.system.r3_job import UnapprovedR3Job
from backend.infrastructure.composition.factories.conversation import ConversationComposition
from backend.modules.pedagogical_design.contracts.dto.assessment_revision import (
    EditorialCorrectionPlan,
)
from backend.modules.validation_control.contracts.dto.editorial_scope import (
    EditorialAuthorizationEvidence,
)
from backend.modules.work_orchestration.application.services.r3_review_modify import (
    R3ReviewModifyService,
)
from backend.modules.work_orchestration.contracts.dto.r3_review_modify import R3JobRequest
from backend.modules.work_orchestration.ports.outbound.r3_job import R3JobPort


@dataclass(frozen=True, slots=True)
class R3AgentDispatcher:
    generation: AssessmentRevisionAdapter
    reviewer: AssessmentReviewAdapter

    def __call__(self, request: R3JobRequest) -> Mapping[str, object]:
        if request.operation == "reviews" and request.bundle is not None:
            return self.reviewer.review(request.bundle, request.dimensions, identity=request.identity)
        if request.revision is not None:
            return self.generation.propose(request.revision, identity=request.identity)
        raise ValueError("R3_JOB_REQUEST")


@dataclass(frozen=True, slots=True)
class R3Composition:
    service: R3ReviewModifyService
    endpoint: R3Endpoint


def build_r3(conversation: ConversationComposition, jobs: R3JobPort | None = None, *,
             editorial_plan: EditorialCorrectionPlan | None = None,
             editorial_evidence: EditorialAuthorizationEvidence | None = None,
             editorial_authenticate: Callable[[EditorialAuthorizationEvidence], bool] | None = None,
             editorial_baseline: str | None = None,
             editorial_contract_sha256: str | None = None) -> R3Composition:
    from backend.adapters.outbound.generation.openai.locator_materialization import (
        calculation_locators,
    )

    state = conversation.service.snapshot()
    service = R3ReviewModifyService(conversation_id=str(state["conversation_id"]),
        store=conversation.store, jobs=jobs if jobs is not None else UnapprovedR3Job(),
        ensure_session=conversation.service.snapshot, clock=lambda: datetime.now(UTC),
        new_id=lambda prefix: prefix + ":" + uuid4().hex,
        editorial_plan=editorial_plan, editorial_evidence=editorial_evidence,
        editorial_authenticate=editorial_authenticate, editorial_baseline=editorial_baseline,
        editorial_contract_sha256=editorial_contract_sha256,
        calculate_locators=calculation_locators if editorial_plan is not None else None)
    return R3Composition(service, R3Endpoint(R3ApplicationInbound(service)))
