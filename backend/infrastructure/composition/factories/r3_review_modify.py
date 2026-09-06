"""Explicit R3 composition: synthetic injection only; no automatic provider binding."""
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import uuid4

from backend.adapters.inbound.api.r3_review_modify import R3Endpoint
from backend.adapters.inbound.application.r3_review_modify import R3ApplicationInbound
from backend.adapters.outbound.generation.assessment_revision import AssessmentRevisionAdapter
from backend.adapters.outbound.review.assessment_review import AssessmentReviewAdapter
from backend.adapters.outbound.system.r3_job import UnapprovedR3Job
from backend.infrastructure.composition.factories.conversation import ConversationComposition
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
            return self.reviewer.review(request.bundle, request.dimensions)
        if request.revision is not None:
            return self.generation.propose(request.revision)
        raise ValueError("R3_JOB_REQUEST")


@dataclass(frozen=True, slots=True)
class R3Composition:
    service: R3ReviewModifyService
    endpoint: R3Endpoint


def build_r3(conversation: ConversationComposition, jobs: R3JobPort | None = None) -> R3Composition:
    state = conversation.service.snapshot()
    service = R3ReviewModifyService(conversation_id=str(state["conversation_id"]),
        store=conversation.store, jobs=jobs if jobs is not None else UnapprovedR3Job(),
        ensure_session=conversation.service.snapshot, clock=lambda: datetime.now(UTC),
        new_id=lambda prefix: prefix + ":" + uuid4().hex)
    return R3Composition(service, R3Endpoint(R3ApplicationInbound(service)))
