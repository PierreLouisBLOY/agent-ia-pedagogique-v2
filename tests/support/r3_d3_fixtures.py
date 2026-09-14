"""Invented D3 fixtures only; no historical export, key, database or network."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Callable, Mapping
from dataclasses import dataclass, replace
from datetime import UTC, datetime, timedelta
from typing import Any, cast
from uuid import uuid4

from backend.adapters.outbound.generation.assessment_revision import AssessmentRevisionAdapter
from backend.adapters.outbound.generation.openai.adapter import OpenAIGenerationAdapter
from backend.adapters.outbound.openai.contracts import (
    OpenAIResponsesRequest,
    OpenAIResponsesResponse,
    OpenAIResponseStatus,
    OpenAIResponsesTransport,
    OpenAIResponseUsage,
)
from backend.adapters.outbound.review.assessment_review import AssessmentReviewAdapter
from backend.agent_runtime.agents.generation import (
    GenerationPort,
    GenerationPortRequest,
    GenerationPortResult,
    GenerationPortResultStatus,
)
from backend.agent_runtime.agents.review import ReviewPortRequest, ReviewPortResult
from backend.infrastructure.composition.bindings.r3_agents import transform
from backend.infrastructure.composition.factories.r3_d3_recovery import (
    RestoredR3Session,
    build_restored_r3,
)
from backend.infrastructure.composition.factories.r3_harden_profile import load_harden_profile
from backend.infrastructure.composition.factories.r3_review_modify import R3AgentDispatcher
from backend.infrastructure.config.secrets.provider import (
    ProviderCredentialRef,
    ProviderSecretValue,
)
from backend.modules.pedagogical_design.contracts.dto.assessment_bundle import (
    AssessmentBundle,
    encoded,
    object_data,
)
from backend.modules.pedagogical_design.contracts.dto.assessment_revision import (
    HARDEN,
    AssessmentRevisionRequest,
    EditorialCorrectionPlan,
)
from backend.modules.work_orchestration.application.services.conversation import (
    initial_conversation,
)
from backend.modules.work_orchestration.contracts.dto.production_read_view import ProductionReadView
from backend.modules.work_orchestration.contracts.dto.r3_review_modify import (
    R3JobRequest,
    R3JobResult,
)
from tests.support import r3_synthetic
from tests.unit import test_r3_editorial_corrections as editorial

NOW = datetime(2026, 1, 1, tzinfo=UTC)
BASELINE = "6e43ca5a58cb50a71de87d099812ec340e8be686"


@dataclass
class RestorationFixture:
    sources: dict[str, bytes]
    grant: dict[str, Any]
    parent: AssessmentBundle
    child: AssessmentBundle
    views: tuple[ProductionReadView, ProductionReadView]

    def build(
        self, *, clock: Callable[[], datetime] = lambda: NOW, jobs: SyntheticJobs | None = None
    ) -> RestoredR3Session:
        raw = encoded(self.grant)
        return build_restored_r3(
            sources=self.sources,
            grant_raw=raw,
            expected_grant_sha256=hashlib.sha256(raw).hexdigest(),
            baseline_commit=BASELINE,
            clock=clock,
            jobs=jobs,
        )

    def command(
        self, session: RestoredR3Session, operation: str = "validations"
    ) -> dict[str, object]:
        state = session.store.read(self.views[1].conversation_id)
        assert state is not None
        body: dict[str, object] = {
            "conversation_id": state.conversation_id,
            "command_id": str(uuid4()),
            "expected_revision": state.revision,
            "production_ref": self.child.production_ref,
        }
        if operation == "modifications":
            body.update(
                base_version_ref=self.child.version_ref,
                base_bundle_sha256=self.child.sha256,
                operation=HARDEN,
                instruction="Rends le dossier 3 plus difficile.",
            )
        else:
            body.update(version_ref=self.child.version_ref, bundle_sha256=self.child.sha256)
        return body


def synthetic_restoration() -> RestorationFixture:
    # Typed bridges to unchanged, deliberately artificial historical test helpers.
    parent = cast(Callable[[], AssessmentBundle], r3_synthetic.bundle)()
    review = cast(Callable[[AssessmentBundle], dict[str, Any]], editorial.review_for)(parent)
    plan = EditorialCorrectionPlan(
        encoded(cast(Callable[..., dict[str, Any]], editorial.plan_data)(parent, review))
    )
    child, command_id, operation_ref = cast(
        Callable[..., tuple[AssessmentBundle, str, str]], editorial.child_for
    )(parent, plan)
    v1 = cast(Callable[[], ProductionReadView], r3_synthetic.production)()
    v2 = replace(
        v1, version_ref=child.version_ref, data={**v1.data, "version_ref": child.version_ref}
    )
    state = initial_conversation(v1.conversation_id, NOW + timedelta(hours=1))
    view = {
        **state.view,
        "current_candidate": {
            "production_ref": child.production_ref,
            "version_ref": child.version_ref,
        },
        "confirmed_context_sha256": v1.data["context_sha256"],
    }
    receipt = {
        "operation_ref": operation_ref,
        "command_id": command_id,
        "state": "SUCCEEDED",
        "production_ref": child.production_ref,
        "version_ref": child.version_ref,
        "revision": 7,
        "review_ref": None,
        "bundle_sha256": child.sha256,
        "review_status": "REVIEW_NOT_RUN",
        "validation_status": "WARNING",
    }
    sources = {
        "state": encoded(
            {"conversation_id": state.conversation_id, "revision": state.revision, "view": view}
        ),
        "parent_view": encoded(v1.data),
        "child_view": encoded(v2.data),
        "parent_bundle": encoded(parent.data),
        "child_bundle": encoded(child.data),
        "review": encoded(review),
        "receipt": encoded(receipt),
        "plan": plan.raw,
        "owner_decision": b"SYNTHETIC-INDEPENDENT-RESTORATION-DECISION",
    }
    grant = {
        "contract": "R3-RESTORE-EXISTING-1.0",
        "purpose": "RESTORE_EXISTING",
        "baseline_commit": BASELINE,
        "source_hashes": {k: hashlib.sha256(v).hexdigest() for k, v in sources.items()},
        "conversation_id": state.conversation_id,
        "production_ref": child.production_ref,
        "parent_version_ref": parent.version_ref,
        "child_version_ref": child.version_ref,
        "child_bundle_sha256": child.sha256,
        "issued_at": NOW.isoformat(),
        "expires_at": (NOW + timedelta(hours=1)).isoformat(),
        "max_validations": 4,
    }
    return RestorationFixture(sources, grant, parent, child, (v1, v2))


def wire_output() -> dict[str, Any]:
    delta = cast(Callable[[], dict[str, Any]], r3_synthetic.harden_delta)()
    for question in delta["questions_d3"]:
        question["locator"] = {
            k: v for k, v in question["locator"].items() if k in {"section_id", "exact_text"}
        }
    for answer in delta["answers_d3"]:
        for calculation in answer["calculations"]:
            del calculation["locator"]
    return delta


class CapturePort:
    request: GenerationPortRequest | None = None

    def generate(self, *, request: GenerationPortRequest) -> GenerationPortResult:
        self.request = request
        return GenerationPortResult(
            request.source_step_id,
            request.operation,
            GenerationPortResultStatus.SUCCEEDED,
            structured_payload={"sections": {"R3_RESULT_JSON": "{}"}},
        )


def synthetic_harden_request() -> GenerationPortRequest:
    fixture = synthetic_restoration()
    request = AssessmentRevisionRequest(
        HARDEN,
        fixture.child.production_ref,
        fixture.child.version_ref,
        object_data(fixture.child.data["subject"]),
        object_data(fixture.child.data["pedagogical_context"]),
        tuple(cast(tuple[Mapping[str, object], ...], fixture.child.data["references"])),
        fixture.child,
    )
    port = CapturePort()
    transform(port, request)
    assert port.request is not None
    return port.request


class SyntheticResolver:
    def __init__(self, events: list[str]) -> None:
        self.events = events

    def resolve(self, credential_ref: ProviderCredentialRef) -> ProviderSecretValue:
        assert credential_ref.value == "openai.r3.harden.private"
        self.events.append("SYNTHETIC_RESOLVE")
        return ProviderSecretValue("SYNTHETIC_NOT_A_CREDENTIAL")


class SyntheticTransport:
    r2_destination = True

    def __init__(
        self,
        events: list[str],
        output: str | None = None,
        status: OpenAIResponseStatus = OpenAIResponseStatus.COMPLETED,
    ) -> None:
        self.events, self.output, self.status = events, output, status

    def build(
        self, *, secret: ProviderSecretValue, timeout_seconds: float
    ) -> OpenAIResponsesTransport:
        assert timeout_seconds == 90.0
        self.events.append("SYNTHETIC_BUILD")
        return self

    def create(self, *, request: OpenAIResponsesRequest) -> OpenAIResponsesResponse:
        self.events.append("SYNTHETIC_CREATE")
        return OpenAIResponsesResponse(
            self.status,
            self.output if self.output is not None else json.dumps(wire_output()),
            usage=OpenAIResponseUsage(input_tokens=1000, output_tokens=500, total_tokens=1500),
            service_tier="default",
        )


def synthetic_adapter(events: list[str], **kwargs: Any) -> OpenAIGenerationAdapter:
    provider, model = load_harden_profile()
    return OpenAIGenerationAdapter(
        provider_profile=provider,
        model_profile=model,
        secret_resolver=SyntheticResolver(events),
        transport_factory=SyntheticTransport(events, **kwargs),
    )


class NoReview:
    def review(self, *, request: ReviewPortRequest) -> ReviewPortResult:
        raise AssertionError("SYNTHETIC_REVIEW_NOT_ALLOWED")


class SyntheticJobs:
    def __init__(self, port: GenerationPort) -> None:
        self.dispatch = R3AgentDispatcher(
            AssessmentRevisionAdapter(port), AssessmentReviewAdapter(NoReview())
        )
        self.result: R3JobResult | None = None
        self.closed = False
        self.calls = 0

    def authorize(self, request: R3JobRequest) -> None:
        if (
            self.closed
            or self.calls
            or request.revision is None
            or request.revision.operation != HARDEN
        ):
            raise ValueError("R3_NOT_AUTHORIZED")

    def start(self, request: R3JobRequest) -> None:
        self.calls += 1
        self.result = R3JobResult(request.operation_ref, "SUCCEEDED", self.dispatch(request))

    def poll(self) -> R3JobResult | None:
        result, self.result = self.result, None
        return result

    def close(self) -> None:
        self.closed = True


def synthetic_dependency_failure(kind: str) -> dict[str, Any]:
    delta = cast(Callable[[], dict[str, Any]], r3_synthetic.harden_delta)()
    if kind == "duration":
        delta["marking_d3"]["duration_minutes"] = 21
    elif kind == "points":
        delta["marking_d3"]["questions"][0]["points"] = "7.00"
    elif kind == "dossier":
        delta["marking_d3"]["dossier_id"] = "DOSSIER_2"
    else:
        raise ValueError(kind)
    return delta
