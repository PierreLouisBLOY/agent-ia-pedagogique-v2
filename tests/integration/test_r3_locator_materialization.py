"""Synthetic provider double -> local materializer -> canonical CAP -> volatile store."""
import json
from dataclasses import replace

import pytest

from backend.adapters.outbound.generation.assessment_revision import AssessmentRevisionAdapter
from backend.adapters.outbound.generation.openai.adapter import _map_response
from backend.adapters.outbound.generation.parse_diagnostic import ParseDiagnostic
from backend.adapters.outbound.openai.contracts import OpenAIResponsesResponse, OpenAIResponseStatus
from backend.adapters.outbound.review.assessment_review import AssessmentReviewAdapter
from backend.infrastructure.composition.factories.r3_review_modify import R3AgentDispatcher
from backend.modules.work_orchestration.application.dto.input.read_production import (
    ReadProductionRequest,
)
from backend.modules.work_orchestration.application.queries.read_production import (
    ReadProductionQuery,
)
from backend.shared_kernel.correlation import CorrelationId
from tests.support.r3_fakes import harness, run
from tests.support.r3_locator_fixtures import wire_supplements
from tests.support.r3_synthetic import subject
from tests.unit.test_openai_generation_adapter import _model, _provider


class AnchorPort:
    def __init__(self, fault=None):
        self.fault, self.calls, self.trace = fault, 0, ParseDiagnostic()

    def generate(self, *, request):
        self.calls += 1
        data = wire_supplements()
        # Extra exact occurrence must remain visible to A16, not silently discarded.
        data["correction"]["answers"][0]["expected_answer"] += " ; 100000.00"
        if self.fault == "wrong_dossier":
            data["questions"][0]["locator"]["section_id"] = "DOSSIER_2"
        elif self.fault == "absent":
            data["questions"][0]["locator"]["exact_text"] = "PRIVATE_SENTINEL"
        elif self.fault in {"ambiguous", "duplicate_section", "unit_ambiguous", "unit_absent"}:
            local = subject()
            if self.fault == "ambiguous":
                local["sections"][2]["text"] *= 2
            elif self.fault == "duplicate_section":
                local["sections"][0] = local["sections"][2]
            elif self.fault == "unit_ambiguous":
                local["sections"][1]["text"] += " EUR"
            else:
                local["sections"][1]["text"] = "Sans unité"
            request = replace(request, resolved_inputs={"subject": local})
        elif self.fault == "scale":
            data["case_data"]["source_scale"] = "kEUR"
        elif self.fault == "insufficient":
            answer = data["correction"]["answers"][1]
            answer["calculations"] *= 2
        elif self.fault == "answer_section":
            data["correction"]["answers"][0]["question_id"] = "unknown"
        elif self.fault == "total":
            data["marking"]["total_points"] = "19.00"
        elif self.fault == "expression":
            data["correction"]["answers"][0]["calculations"][0]["expression"] = {"ref": "computed.BFR"}
        return _map_response(request=request,
            response=OpenAIResponsesResponse(OpenAIResponseStatus.COMPLETED, json.dumps(data)),
            provider_profile=_provider(), model_profile=_model(), diagnostic=self.trace)


@pytest.mark.parametrize(("fault", "code"), [
    (None, None), ("wrong_dossier", "LOCATOR_SECTION_UNKNOWN"),
    ("absent", "LOCATOR_ANCHOR_NOT_FOUND"), ("ambiguous", "LOCATOR_ANCHOR_AMBIGUOUS"),
    ("duplicate_section", "LOCATOR_SECTION_UNKNOWN"),
    ("unit_ambiguous", "LOCATOR_ANCHOR_AMBIGUOUS"), ("unit_absent", "LOCATOR_ANCHOR_NOT_FOUND"),
    ("insufficient", "CALC_VALUE_OCCURRENCE_INSUFFICIENT"),
    ("answer_section", "CALC_ANSWER_SECTION_INVALID"),
    ("scale", "A07"), ("total", "A06"), ("expression", "A15"),
])
def test_actual_pipeline_and_exact_v1_read_preserve_all_authorities(fault, code):
    conv, r3, jobs, prod = harness()
    port = AnchorPort(fault)
    jobs.dispatch = R3AgentDispatcher(AssessmentRevisionAdapter(port), AssessmentReviewAdapter(jobs.reviewer))
    before = r3.service.assessment(prod.production_ref, prod.version_ref)
    try:
        result, _ = run(conv, r3, "assessment-preparations", prod)
        trace = r3.service.diagnostic(result["operation_ref"])
        after = r3.service.assessment(prod.production_ref, prod.version_ref)
        assert port.calls == 1 and jobs.reviewer.calls == []
        if fault is None:
            assert result["state"] == "SUCCEEDED"
            assert trace["cap_overall"] == "WARNING"
            assert [c["status"] for c in trace["checks"]] == ["PASS"] * 15 + ["WARNING"]
            assert trace["checks"][15]["reason_code"] == "SEMANTIC_HUMAN_REVIEW_REQUIRED"
            assert conv.store.r3_bundle(prod.production_ref, prod.version_ref) is not None
            assert after["bundle"]["correction"]["answers"][0]["expected_answer"].endswith("; 100000.00")
            assert after["review_status"] == "REVIEW_NOT_RUN" and after["badge"] == "NON VALIDÉE"
            exact = ReadProductionQuery(conv.store).execute(
                ReadProductionRequest(prod.production_ref, prod.version_ref),
                conversation_id=prod.conversation_id, correlation_id=CorrelationId("r3-locator"))
            assert exact.success and exact.data.version_ref == prod.version_ref
            assert exact.data.data == prod.data
            absent = ReadProductionQuery(conv.store).execute(
                ReadProductionRequest(prod.production_ref, "ver:" + "f" * 32),
                conversation_id=prod.conversation_id, correlation_id=CorrelationId("r3-locator"))
            assert not absent.success  # Never fallback to latest.
        else:
            assert result["state"] == "FAILED_OUTPUT"
            assert conv.store.r3_bundle(prod.production_ref, prod.version_ref) is None
            for key in ("bundle", "bundle_sha256", "versions", "validations", "current_candidate", "subject_sha256"):
                assert after[key] == before[key]
            if code.startswith("A"):
                assert trace["cap_overall"] == "FAIL"
                assert next(c for c in trace["checks"] if c["check_id"] == code)["status"] == "FAIL"
            else:
                assert trace["cap_execution"] == "NOT_RUN"
                assert port.trace.snapshot()["parse_stage"] == "DOMAIN_MAP"
                assert port.trace.snapshot()["parse_code"] == code
                assert port.trace.snapshot()["parse_status"] == "FAILED"
        assert "PRIVATE_SENTINEL" not in repr((trace, result, port.trace.snapshot()))
    finally:
        r3.service.close()
