"""Actual producer -> parser -> AG03 -> Application -> CAP-A01, with no I/O."""
import json

import pytest

from backend.adapters.outbound.generation.assessment_revision import AssessmentRevisionAdapter
from backend.adapters.outbound.generation.openai.adapter import _map_response
from backend.adapters.outbound.generation.openai.mapping import build_openai_request
from backend.adapters.outbound.generation.openai.prepare_contract import FIELDS
from backend.adapters.outbound.generation.parse_diagnostic import ParseDiagnostic
from backend.adapters.outbound.openai.contracts import OpenAIResponsesResponse, OpenAIResponseStatus
from backend.adapters.outbound.review.assessment_review import AssessmentReviewAdapter
from backend.infrastructure.composition.factories.r3_review_modify import R3AgentDispatcher
from tests.support.r3_fakes import harness, run
from tests.support.r3_synthetic import supplements
from tests.unit.test_openai_generation_adapter import _model, _provider


class DirectPreparePort:
    def __init__(self, fault):
        self.fault, self.calls = fault, []
        self.trace = ParseDiagnostic()

    def generate(self, *, request):
        from tests.support.r3_locator_fixtures import wire_fixture

        emitted = build_openai_request(request=request, model_profile=_model())
        self.calls.append(emitted)
        assert set(emitted.output_schema["properties"]) == set(FIELDS)
        data = wire_fixture(supplements())
        if self.fault in FIELDS:
            del data[self.fault]
        elif self.fault == "extra":
            data["extra"] = True
        elif self.fault == "wrapper":
            data = {"supplements": data}
        elif self.fault == "arithmetic":
            data["case_data"]["base_case"]["computed"]["FRNG"] = "1.00"
        elif self.fault == "identity":
            data["correction"]["production_ref"] = "prod:" + "f" * 32
        status = {"refused": OpenAIResponseStatus.REFUSED,
                  "incomplete": OpenAIResponseStatus.INCOMPLETE,
                  "failed": OpenAIResponseStatus.FAILED}.get(self.fault,
                                                           OpenAIResponseStatus.COMPLETED)
        return _map_response(request=request,
            response=OpenAIResponsesResponse(status=status, output_text=json.dumps(data)),
            provider_profile=_provider(), model_profile=_model(), diagnostic=self.trace)


@pytest.mark.parametrize("fault", [None, *FIELDS, "extra", "wrapper",
                                  "refused", "incomplete", "failed", "arithmetic", "identity"])
def test_real_application_pipeline_with_closed_provider_output(fault):
    conv, r3, jobs, prod = harness()
    port = DirectPreparePort(fault)
    revision = AssessmentRevisionAdapter(port)
    jobs.dispatch = R3AgentDispatcher(revision, AssessmentReviewAdapter(jobs.reviewer))
    before = r3.service.assessment(prod.production_ref, prod.version_ref)
    result, _ = run(conv, r3, "assessment-preparations", prod)
    diagnostic = r3.service.diagnostic(result["operation_ref"])
    after = r3.service.assessment(prod.production_ref, prod.version_ref)
    assert len(port.calls) == 1 and jobs.reviewer.calls == []
    if fault is None:
        assert result["state"] == "SUCCEEDED"
        assert diagnostic["cap_overall"] == "PASS"
        assert len(diagnostic["checks"]) == 16
        assert revision.parse_diagnostic()["parse_status"] == "COMPLETED"
        assert port.trace.snapshot()["parse_status"] == "COMPLETED"
        assert conv.store.r3_bundle(prod.production_ref, prod.version_ref) is not None
        assert after["review_status"] == "REVIEW_NOT_RUN"
        assert after["badge"] == "NON VALIDÉE"
    else:
        assert result["state"] == "FAILED_OUTPUT"
        for field in ("bundle", "bundle_sha256", "versions", "validations",
                      "current_candidate", "subject_sha256"):
            assert after[field] == before[field]
        assert conv.store.r3_bundle(prod.production_ref, prod.version_ref) is None
        if fault == "arithmetic":
            assert len(diagnostic["checks"]) == 16
            assert diagnostic["cap_overall"] == "FAIL"
        else:
            assert diagnostic["cap_execution"] == "NOT_RUN"
            assert diagnostic["checks"] == []
    r3.service.close()
