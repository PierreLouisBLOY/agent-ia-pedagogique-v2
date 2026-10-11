"""Offline regressions for completion and exact P0 locators; no live fixture."""
import json
from dataclasses import replace

import pytest

from backend.adapters.outbound.openai import OpenAIResponsesResponse, OpenAIResponseStatus
from backend.adapters.outbound.review.p0_review import P0ReviewAdapter
from backend.agent_runtime.agents.review import ReviewPortResult, ReviewPortResultStatus
from backend.agent_runtime.agents.review.review_security_model import ReviewSecurityError
from backend.modules.work_orchestration.application.services.p0_agentic import quality_status
from tests.support.p0_generation_double import P0GenerationDouble
from tests.unit.test_openai_review_adapter import _adapter, _request, _semantic_payload
from tests.unit.test_p0_agentic_routing import TechnicalCritic, candidate
from tests.unit.test_p0_creation_contract import service


def test_complete_semantic_review_keeps_source_limit_without_false_incomplete():
    limitation = {"code": "LIMITED_SOURCE_SCOPE", "message": "Only the selected passage was used."}
    adapter, transport = _adapter(OpenAIResponsesResponse(
        OpenAIResponseStatus.COMPLETED, _semantic_payload(limitations=[limitation])))
    result = adapter.review(request=_request())
    assert result.status is ReviewPortResultStatus.SUCCEEDED
    assert result.limitations == (limitation,)
    assert result.structured_payload["overall_assessment"] == "acceptable"
    assert result.execution_metadata["response_status"] == "completed"
    assert len(transport.calls) == 1


@pytest.mark.parametrize("mutation", ["incomplete", "missing_dimension", "warning", "uncertainty"])
def test_technical_incompleteness_is_never_upgraded(mutation):
    payload = json.loads(_semantic_payload(limitations=[{"code": "LIMITED", "message": "Scope limited."}]))
    if mutation == "missing_dimension":
        payload["structured_payload"]["coverage"] = ["REV-ACC"]
    if mutation in {"warning", "uncertainty"}:
        payload["warnings" if mutation == "warning" else "uncertainties"] = [
            {"code": "REMAINING", "message": "Coverage not established."}]
    response = OpenAIResponsesResponse(
        OpenAIResponseStatus.INCOMPLETE if mutation == "incomplete" else OpenAIResponseStatus.COMPLETED,
        json.dumps(payload))
    adapter, transport = _adapter(response)
    result = adapter.review(request=_request())
    assert result.status is ReviewPortResultStatus.PARTIAL
    assert result.limitations and len(transport.calls) == 1


class WholeTargetCritic(TechnicalCritic):
    def __init__(self, locator, *, authority=False):
        super().__init__()
        self.locator, self.authority = locator, authority

    def review(self, *, request):
        result = super().review(request=request)
        finding = {
            "finding_id": "scope-gap", "dimension": "REV-SRC", "severity": "minor",
            "description": "Selected passage gives limited method detail.",
            "rationale": "Human source judgement remains necessary.",
            "target_locator": self.locator, "correction_required": False,
            "evidence_refs": request.evidence_refs, "confidence": {}, "suggested_action": {},
        }
        if self.authority:
            finding["suggested_action"] = {"promotion_allowed": True}
        return replace(result, technical_findings=(finding,))


def review_request():
    app = service(P0GenerationDouble())
    view, prepared = candidate(app)
    saved = app.saved_source(view["production_ref"], view["version_ref"])
    return {"production": saved.data["bundle"], "bundle_sha256": view["bundle_sha256"],
        "evidence_pack": prepared["agentic"]["evidence_pack"],
        "plan": prepared["agentic"]["plan"], "validation": saved.data["validations"][0]}


def test_p0_whole_target_is_exact_descriptive_and_does_not_grant_authority():
    critic = WholeTargetCritic({"kind": "whole_target"})
    request = review_request()
    report = P0ReviewAdapter(critic, authorize=lambda request: False).review(request=request)
    assert report["findings"][0]["target_locator"] == {"kind": "whole_target"}
    assert report["version_ref"] == request["production"]["version_ref"]
    assert report["bundle_sha256"] == request["bundle_sha256"]
    assert report["promotion"] == "NOT_PERFORMED" and len(critic.requests) == 1
    assert critic.requests[0].target_content is None


@pytest.mark.parametrize("mutation", ["extra_locator_key", "outside_path", "authority"])
def test_p0_locator_or_authority_mutation_still_refuses(mutation):
    locator = {"kind": "whole_target", "path": "/outside"} if mutation == "extra_locator_key" else (
        {"kind": "json_path", "path": "/outside"} if mutation == "outside_path" else {"kind": "whole_target"})
    critic = WholeTargetCritic(locator, authority=mutation == "authority")
    with pytest.raises((ReviewSecurityError, ValueError)):
        P0ReviewAdapter(critic, authorize=lambda request: False).review(request=review_request())
    assert len(critic.requests) == 1


def test_source_limit_still_prevents_review_quality_ok():
    status = quality_status({"quantitative_review_required": False}, review={
        "status": "completed", "overall_assessment": "acceptable", "instruction_coverage": "FULL",
        "limitations": [{"code": "LIMITED_SOURCE_SCOPE"}]})
    assert status["review"] == "RESERVE" and status["human_review"] == "HUMAN_REVIEW_REQUIRED"


def test_negative_authority_metadata_is_still_rejected_pending_policy_decision():
    critic = WholeTargetCritic({"kind": "whole_target"})
    original = critic.review

    def negative_metadata(*, request):
        result: ReviewPortResult = original(request=request)
        return replace(result, uncertainties=({"code": "NO_AUTHORITATIVE_ORACLE"},))

    critic.review = negative_metadata
    with pytest.raises(ReviewSecurityError):
        P0ReviewAdapter(critic, authorize=lambda request: False).review(request=review_request())
    assert len(critic.requests) == 1
