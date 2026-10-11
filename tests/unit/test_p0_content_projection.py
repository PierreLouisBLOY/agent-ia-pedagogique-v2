import hashlib
import json
from copy import deepcopy

import pytest

from backend.adapters.outbound.generation.openai.p0_content import (
    bind_p0_content,
    build_p0_content_request,
)
from backend.modules.pedagogical_design.contracts.dto.assessment_bundle import as_plain
from tests.support.p0_generation_double import P0GenerationDouble
from tests.unit.test_p0_creation_contract import context, service


def request_for(family):
    class Capture(P0GenerationDouble):
        def authorize(self, *, request):
            self.requests.append(as_plain(request))
            return False
    capture = Capture()
    app = service(capture)
    kind, mode = ("QUESTION_SET", family) if family in {"OPEN_QUESTIONS", "QCM", "QUIZ"} else (family, None)
    prepared = app.execute("prepare", {"command_id": "a" * 32, "context": context("BTS_CG_YEAR_2", kind, mode), "reference": {}})
    app.execute("generate", {"command_id": "b" * 32, "preparation_ref": prepared["preparation_ref"], "preparation_sha256": prepared["preparation_sha256"]})
    return capture.requests[0]


@pytest.mark.parametrize("family", ["COURSE", "EXERCISE", "OPEN_QUESTIONS", "QCM", "QUIZ", "ASSESSMENT"])
def test_same_ui_context_and_source_produce_same_wire_despite_local_random_ids(family):
    first, second = request_for(family), request_for(family)
    assert first["version_ref"] != second["version_ref"]
    request = build_p0_content_request(first)
    assert request == build_p0_content_request(second)
    assert first["version_ref"] not in request.input_json
    assert request.model == "gpt-5.6-terra" and request.max_output_tokens == 4096
    assert set(json.loads(request.input_json)) == {"contract_id", "context", "references", "evidence"}
    assert "expected_answer" not in request.input_json and "TEACHER_ONLY_SENTINEL" not in request.input_json
    content = dict(P0GenerationDouble().generate(request=first))
    content = {k: content[k] for k in ["title", "sections", "questions", "corrections", "marking", "limitations"]}
    candidate = bind_p0_content(first, content)
    assert candidate.version_ref == first["version_ref"]
    assert candidate.production_ref == first["production_ref"]


@pytest.mark.parametrize("mutation", ["context", "excerpt", "evidence_key", "oracle"])
def test_mutated_source_context_or_answer_oracle_cannot_enter_wire(mutation):
    request = deepcopy(request_for("EXERCISE"))
    if mutation == "context":
        request["context"] = {**request["context"], "level": "FINAL_STMG"}
    elif mutation == "excerpt":
        request["evidence"] = {k: "Substitué" for k in request["evidence"]}
    elif mutation == "evidence_key":
        request["evidence"] = {"unbound": "Substitué"}
    else:
        request["evaluation_oracle"] = {"expected_answer": "secret"}
    with pytest.raises(ValueError):
        build_p0_content_request(request)


def test_provider_cannot_substitute_version_identity_or_break_marking_total():
    request = request_for("ASSESSMENT")
    generated = dict(P0GenerationDouble().generate(request=request))
    content = {k: generated[k] for k in ["title", "sections", "questions", "corrections", "marking", "limitations"]}
    with pytest.raises(ValueError):
        bind_p0_content(request, {**content, "version_ref": "ver:" + "c" * 32})
    content["marking"] = [{"question_id": "Q01", "points": "19.00", "criteria": ["Méthode"]}]
    with pytest.raises(ValueError, match="P0_MARKING_TOTAL"):
        bind_p0_content(request, content)


def test_oversized_input_is_rejected_locally_without_client():
    request = deepcopy(request_for("EXERCISE"))
    key = next(iter(request["evidence"]))
    request["evidence"] = {key: "x" * 12289}
    request["references"] = [{**r, "excerpt_sha256": hashlib.sha256(b"x" * 12289).hexdigest()} for r in request["references"]]
    with pytest.raises(ValueError, match="P0_PROVIDER_INPUT_SIZE"):
        build_p0_content_request(request)
