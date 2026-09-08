"""Real parser/agent/Application wiring, strictly synthetic volatile stores."""
import json

import pytest

from backend.adapters.outbound.generation.assessment_revision import AssessmentRevisionAdapter
from backend.adapters.outbound.generation.openai.adapter import _map_response
from backend.adapters.outbound.generation.parse_diagnostic import ParseDiagnostic
from backend.adapters.outbound.openai.contracts import OpenAIResponsesResponse, OpenAIResponseStatus
from backend.adapters.outbound.review.assessment_review import AssessmentReviewAdapter
from backend.infrastructure.composition.factories.r3_review_modify import R3AgentDispatcher
from tests.support.r3_fakes import harness, run
from tests.support.r3_synthetic import supplements
from tests.unit.test_openai_generation_adapter import _model, _provider


class SyntheticResponsePort:
    def __init__(self, fault):
        self.fault = fault
        self.trace = ParseDiagnostic()
        self.requests = []

    def generate(self, *, request):
        self.requests.append(request)
        text = json.dumps(supplements()) if self.fault != "inner" else "{PRIVATE_SENTINEL"
        payload = json.dumps({"outcome": "OUTPUT",
            "sections": [{"code": "R3_RESULT_JSON", "text": text}], "warnings": [], "uncertainties": []})
        if self.fault == "outer":
            payload = "{PRIVATE_SENTINEL"
        return _map_response(request=request, response=OpenAIResponsesResponse(
            status=OpenAIResponseStatus.COMPLETED, output_text=payload),
            provider_profile=_provider(), model_profile=_model(), diagnostic=self.trace)


@pytest.mark.parametrize("fault", ["outer", "inner", None])
def test_parser_to_agents_to_application_keeps_cap_and_publication_semantics(monkeypatch, fault):
    conv, r3, jobs, prod = harness()
    port = SyntheticResponsePort(fault)
    revision = AssessmentRevisionAdapter(port)
    jobs.dispatch = R3AgentDispatcher(revision, AssessmentReviewAdapter(jobs.reviewer))
    before = r3.service.assessment(prod.production_ref, prod.version_ref)
    cap_calls = []
    validate = r3.service._validation
    def cap(*args, **kwargs):
        cap_calls.append(True)
        return validate(*args, **kwargs)
    monkeypatch.setattr(r3.service, "_validation", cap)
    result, _ = run(conv, r3, "assessment-preparations", prod)
    after = r3.service.assessment(prod.production_ref, prod.version_ref)
    processing = r3.service.diagnostic(result["operation_ref"])
    outer_trace, inner_trace = port.trace.snapshot(), revision.parse_diagnostic()
    assert len(port.requests) == 1 and jobs.reviewer.calls == []
    if fault:
        assert result["state"] == "FAILED_OUTPUT"
        assert cap_calls == []
        assert processing["cap_execution"] == "NOT_RUN"
        assert processing["checks"] == []
        for field in ("bundle", "bundle_sha256", "versions", "validations", "current_candidate", "subject_sha256"):
            assert before[field] == after[field]
        assert conv.store.r3_bundle(prod.production_ref, prod.version_ref) is None
        failed = outer_trace if fault == "outer" else inner_trace
        assert failed["parse_stage"] == "JSON_DECODE"
        assert failed["parse_code"] == "JSON_DECODE_FAILURE"
        assert inner_trace["parse_status"] == ("UNKNOWN" if fault == "outer" else "FAILED")
    else:
        assert result["state"] == "SUCCEEDED"
        assert len(cap_calls) == 1
        assert processing["cap_overall"] == "PASS"
        assert len(processing["checks"]) == 16
        assert outer_trace["parse_status"] == inner_trace["parse_status"] == "COMPLETED"
        assert after["review_status"] == "REVIEW_NOT_RUN"
        assert after["badge"] == "NON VALIDÉE"
    for metadata in (outer_trace, inner_trace, result, processing):
        assert "PRIVATE_SENTINEL" not in repr(metadata)
    assert "parse_stage" not in repr(result)
    r3.service.close()
    # Private snapshots were collected before disposal of the volatile Application service.
    assert r3.service.diagnostic(result["operation_ref"])["cap_execution"] == "UNKNOWN"
    assert outer_trace["schema_target"] == inner_trace["schema_target"] == "PREPARE_SUPPLEMENTS_V1"
