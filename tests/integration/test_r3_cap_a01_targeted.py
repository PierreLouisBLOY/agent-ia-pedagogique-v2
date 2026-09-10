"""Actual in-memory Application flow: diagnostics before close, no I/O."""

import json

import pytest

from backend.adapters.outbound.generation.assessment_revision import AssessmentRevisionAdapter
from backend.adapters.outbound.generation.openai.adapter import _map_response
from backend.adapters.outbound.generation.parse_diagnostic import ParseDiagnostic
from backend.adapters.outbound.openai.contracts import OpenAIResponsesResponse, OpenAIResponseStatus
from backend.adapters.outbound.review.assessment_review import AssessmentReviewAdapter
from backend.infrastructure.composition.factories.r3_review_modify import R3AgentDispatcher
from tests.support.r3_fakes import harness, run
from tests.unit.test_openai_generation_adapter import _model, _provider
from tests.unit.test_r3_cap_a01_targeted import mutated


class SyntheticPort:
    def __init__(self, name):
        self.name = name
        self.calls = 0

    def generate(self, *, request):
        self.calls += 1
        return _map_response(
            request=request,
            response=OpenAIResponsesResponse(
                OpenAIResponseStatus.COMPLETED, json.dumps(mutated(self.name))
            ),
            provider_profile=_provider(),
            model_profile=_model(),
            diagnostic=ParseDiagnostic(),
        )


@pytest.mark.parametrize(
    "name",
    ["nominal", "all_three_locators", "expression_reference_unknown", "unit_label_whole_sentence"],
)
def test_actual_pipeline_preserves_fail_closed_publication_and_closed_export(name):
    conv, r3, jobs, prod = harness()
    port = SyntheticPort(name)
    jobs.dispatch = R3AgentDispatcher(
        AssessmentRevisionAdapter(port), AssessmentReviewAdapter(jobs.reviewer)
    )
    before = r3.service.assessment(prod.production_ref, prod.version_ref)
    try:
        result, _ = run(conv, r3, "assessment-preparations", prod)
        diagnostic = r3.service.diagnostic(result["operation_ref"])
        after = r3.service.assessment(prod.production_ref, prod.version_ref)
        assert port.calls == 1 and jobs.reviewer.calls == []
        if name == "nominal":
            assert result["state"] == "SUCCEEDED"
            assert diagnostic["cap_overall"] == "WARNING"
            assert len(diagnostic["checks"]) == 16
            assert diagnostic["checks"][5]["status"] == "PASS"
            assert diagnostic["checks"][15]["reason_code"] == "SEMANTIC_HUMAN_REVIEW_REQUIRED"
            assert conv.store.r3_bundle(prod.production_ref, prod.version_ref) is not None
            assert after["review_status"] == "REVIEW_NOT_RUN"
        else:
            assert result["state"] == "FAILED_OUTPUT"
            assert conv.store.r3_bundle(prod.production_ref, prod.version_ref) is None
            for key in (
                "bundle",
                "bundle_sha256",
                "versions",
                "validations",
                "current_candidate",
                "subject_sha256",
            ):
                assert before[key] == after[key]
            if name == "all_three_locators":
                assert diagnostic["cap_execution"] == "COMPLETED"
                assert diagnostic["cap_overall"] == "FAIL"
                assert [diagnostic["checks"][i]["reason_code"] for i in (2, 6, 14)] == [
                    "A03_LOCATOR_INVALID",
                    "A07_UNIT_LOCATOR_INVALID",
                    "A15_CALC_LOCATOR_INVALID",
                ]
                assert diagnostic["checks"][15]["status"] == "WARNING"
            else:
                assert diagnostic["cap_execution"] == "NOT_RUN"
        assert all(set(c) == {"check_id", "status", "reason_code"} for c in diagnostic["checks"])
        saved = json.loads(json.dumps(diagnostic))
    finally:
        r3.service.close()
    assert r3.service.diagnostic(result["operation_ref"])["cap_execution"] == "UNKNOWN"
    assert saved == diagnostic
