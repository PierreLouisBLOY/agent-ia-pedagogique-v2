"""Synthetic doubles through actual AG03/AG04 ports, never imported by production."""
import json
from dataclasses import replace
from uuid import uuid4

from backend.adapters.outbound.generation.assessment_revision import AssessmentRevisionAdapter
from backend.adapters.outbound.review.assessment_review import AssessmentReviewAdapter
from backend.agent_runtime.agents.generation import GenerationPortResult, GenerationPortResultStatus
from backend.agent_runtime.agents.review import ReviewPortResult, ReviewPortResultStatus
from backend.infrastructure.composition.factories.conversation import build_conversation
from backend.infrastructure.composition.factories.r3_review_modify import (
    R3AgentDispatcher,
    build_r3,
)
from backend.modules.pedagogical_design.contracts.dto.assessment_bundle import as_plain, object_data
from backend.modules.pedagogical_design.contracts.dto.assessment_revision import HARDEN
from backend.modules.work_orchestration.contracts.dto.r3_review_modify import R3Command, R3JobResult
from tests.support.r3_synthetic import harden_delta, production, supplements


class FakeR3Generation:
    def __init__(self, invalid=False):
        self.invalid = invalid
        self.calls = []

    def generate(self, *, request):
        self.calls.append(request)
        result = harden_delta() if request.objective == HARDEN else supplements()
        section = "{broken" if self.invalid else json.dumps(result)
        return GenerationPortResult(request.source_step_id, request.operation,
            GenerationPortResultStatus.SUCCEEDED, structured_payload={"sections": {"R3_RESULT_JSON": section}},
            evidence_refs_used=request.evidence_refs)


class FakeR3Review:
    def __init__(self):
        self.calls = []

    def review(self, *, request):
        self.calls.append(request)
        return ReviewPortResult(request.source_step_id, request.operation, ReviewPortResultStatus.SUCCEEDED,
            structured_payload={"overall_assessment": "acceptable", "correction_required": False,
                                "coverage": [d.value for d in request.review_dimensions], "confidence": {}},
            technical_findings=(), evidence_refs_used=request.evidence_refs)


class ImmediateJobs:
    def __init__(self):
        self.generation, self.reviewer = FakeR3Generation(), FakeR3Review()
        self.dispatch = R3AgentDispatcher(AssessmentRevisionAdapter(self.generation),
                                          AssessmentReviewAdapter(self.reviewer))
        self.requests, self.result, self.closed = [], None, False

    def authorize(self, request):
        if self.closed:
            raise ValueError("JOB_UNAVAILABLE")

    def start(self, request):
        self.requests.append(request)
        try:
            self.result = R3JobResult(request.operation_ref, "SUCCEEDED", self.dispatch(request))
        except Exception:
            self.result = R3JobResult(request.operation_ref, "FAILED_OUTPUT")

    def poll(self):
        result, self.result = self.result, None
        return result

    def close(self):
        self.closed = True


def seed(conversation):
    state = conversation.service.snapshot()
    prod = production(conversation_id=state["conversation_id"])
    old = conversation.store.read(state["conversation_id"])
    data = object_data(as_plain(old.view))
    data.update(revision=old.revision + 1,
                current_candidate={"production_ref": prod.production_ref, "version_ref": prod.version_ref},
                confirmed_context_sha256=prod.data["context_sha256"])
    conversation.store.publish(replace(old, revision=old.revision + 1, view=data),
                                expected_revision=old.revision, production=prod)
    return prod


def harness():
    conversation = build_conversation()
    prod = seed(conversation)
    jobs = ImmediateJobs()
    component = build_r3(conversation, jobs)
    return conversation, component, jobs, prod


def command(conversation, component, operation, prod, *, command_id=None, **overrides):
    state = conversation.service.snapshot()
    bundle = conversation.store.r3_bundle(prod.production_ref, prod.version_ref)
    body = {"conversation_id": state["conversation_id"], "command_id": command_id or str(uuid4()),
            "expected_revision": state["revision"], "production_ref": prod.production_ref}
    if operation == "modifications":
        body.update(base_version_ref=prod.version_ref, base_bundle_sha256=bundle.sha256,
                    operation=HARDEN, instruction="Rends le dossier 3 plus difficile.")
    else:
        body["version_ref"] = prod.version_ref
        if operation == "assessment-preparations":
            from backend.modules.pedagogical_design.contracts.dto.assessment_bundle import (
                fingerprint,
            )
            body["subject_sha256"] = fingerprint({"content": prod.data["content"], "sections": prod.data["sections"]})
        else:
            body["bundle_sha256"] = bundle.sha256 if bundle else None
            if operation == "reviews":
                body["dimensions"] = ["REV-ACC", "REV-CON", "REV-PED"]
    body.update(overrides)
    return R3Command(operation, body)


def run(conversation, component, operation, prod, **overrides):
    cmd = command(conversation, component, operation, prod, **overrides)
    result = component.service.execute(cmd)
    component.service.poll()
    return component.service.report(result["operation_ref"]), cmd


def sleeping_worker(request):
    import time
    time.sleep(10)
    return {}


def echo_worker(request):
    return {"synthetic": True, "operation_ref": request.operation_ref}


def failing_worker(request):
    raise ValueError("SYNTHETIC_PRIVATE_MARKER")


def oversized_worker(request):
    return {"value": "x" * (300 * 1024)}
