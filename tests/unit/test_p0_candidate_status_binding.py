"""Candidate status regressions; synthetic content, no private receipts or provider."""
from copy import deepcopy

import pytest

from backend.adapters.outbound.generation.openai.p0_content import (
    CONTENT_FIELDS,
    bind_p0_content,
    build_p0_content_request,
)
from backend.modules.pedagogical_design.application.commands.create_p0_candidate import (
    CreateP0Candidate,
)
from backend.modules.pedagogical_design.contracts.dto.assessment_bundle import as_plain
from backend.modules.pedagogical_design.contracts.dto.p0_production import P0Production
from tests.support.p0_generation_double import P0GenerationDouble
from tests.unit.test_p0_content_projection import request_for

APPLICATION_LIMITATION = "CANDIDATE — ressource non validée, à relire par l'enseignant avant usage."
_BINDINGS = ("production_ref", "version_ref", "context", "context_sha256", "references", "lineage")


def original_bind(request, content):
    return P0Production({"contract_id": "R6-P0-PRODUCTION-1.0",
                         **{key: request[key] for key in _BINDINGS}, **content})


def synthetic(family="EXERCISE"):
    request = request_for(family)
    generated = P0GenerationDouble().generate(request=request)
    return request, {key: generated[key] for key in CONTENT_FIELDS}


@pytest.mark.parametrize("family", ["COURSE", "EXERCISE", "OPEN_QUESTIONS", "QCM", "QUIZ", "ASSESSMENT"])
@pytest.mark.parametrize("limits", [["Source synthétique non attestée."], ["Ressource candidate à relire."]])
def test_missing_local_status_is_added_preserving_all_content_and_bindings(family, limits):
    request, content = synthetic(family)
    content["limitations"] = limits
    before_request, before_content = deepcopy(request), deepcopy(content)
    original = original_bind(request, content)
    with pytest.raises(ValueError, match="P0_CANDIDATE_LIMITATION_REQUIRED"):
        CreateP0Candidate.validate_content(original)
    candidate = bind_p0_content(request, content)
    CreateP0Candidate().execute(as_plain(candidate.data), evidence=request["evidence"])
    expected = as_plain(original.data)
    expected["limitations"] = [*limits, APPLICATION_LIMITATION]
    assert as_plain(candidate.data) == expected
    assert candidate.sha256 != original.sha256
    assert request == before_request and content == before_content
    assert build_p0_content_request(request) == build_p0_content_request(before_request)


@pytest.mark.parametrize("family", ["COURSE", "EXERCISE", "OPEN_QUESTIONS", "QCM", "QUIZ", "ASSESSMENT"])
def test_existing_exact_status_remains_byte_identical(family):
    request, content = synthetic(family)
    original = original_bind(request, content)
    candidate = bind_p0_content(request, content)
    assert as_plain(candidate.data) == as_plain(original.data)
    assert candidate.sha256 == original.sha256


@pytest.mark.parametrize("limits", [[], [""], ["x" * 501], [None], ["x"] * 17])
def test_invalid_limitations_remain_refused(limits):
    request, content = synthetic()
    content["limitations"] = limits
    with pytest.raises(ValueError):
        original_bind(request, content)
    with pytest.raises(ValueError):
        bind_p0_content(request, content)


def test_full_limitations_without_status_refused_without_loss():
    request, content = synthetic()
    content["limitations"] = [f"Limite synthétique {i}" for i in range(16)]
    before = deepcopy(content)
    original_bind(request, content)
    with pytest.raises(ValueError, match="P0_LIMITATIONS"):
        bind_p0_content(request, content)
    assert content == before


def test_full_limitations_with_status_unchanged():
    request, content = synthetic()
    content["limitations"] = ["CANDIDATE", *[f"Limite {i}" for i in range(15)]]
    assert bind_p0_content(request, content).sha256 == original_bind(request, content).sha256


def test_provider_identity_substitution_and_broken_marking_remain_refused():
    request, content = synthetic("ASSESSMENT")
    content["limitations"] = ["Source synthétique"]
    with pytest.raises(ValueError):
        bind_p0_content(request, {**content, "version_ref": "ver:" + "c" * 32})
    content["marking"] = [{"question_id": "Q01", "points": "19.00", "criteria": ["Méthode"]}]
    with pytest.raises(ValueError, match="P0_MARKING_TOTAL"):
        bind_p0_content(request, content)


def test_existing_application_evidence_guard_remains_effective():
    request, content = synthetic()
    content["limitations"] = ["Source synthétique"]
    candidate = bind_p0_content(request, content)
    with pytest.raises(ValueError, match="P0_EVIDENCE_CHANGED"):
        CreateP0Candidate().execute(as_plain(candidate.data), evidence={key: "Substitution" for key in request["evidence"]})



@pytest.mark.parametrize("family", ["COURSE", "EXERCISE", "OPEN_QUESTIONS", "QCM", "QUIZ", "ASSESSMENT"])
def test_fifteen_provider_limitations_receive_status_without_truncation(family):
    request, content = synthetic(family)
    content["limitations"] = [f"Limite synthétique {i}" for i in range(15)]
    candidate = bind_p0_content(request, content)
    assert as_plain(candidate.data["limitations"]) == [*content["limitations"], APPLICATION_LIMITATION]
    CreateP0Candidate().execute(as_plain(candidate.data), evidence=request["evidence"])


@pytest.mark.parametrize("family", ["COURSE", "EXERCISE", "OPEN_QUESTIONS", "QCM", "QUIZ", "ASSESSMENT"])
def test_rebinding_is_idempotent(family):
    request, content = synthetic(family)
    content["limitations"] = ["Limite synthétique"]
    first = bind_p0_content(request, content)
    again = bind_p0_content(request, {key: as_plain(first.data[key]) for key in CONTENT_FIELDS})
    assert again.sha256 == first.sha256


@pytest.mark.parametrize("mutation", ["limitations", "title", "context", "lineage"])
def test_existing_marker_cannot_repair_other_invalid_data(mutation):
    request, content = synthetic()
    if mutation == "limitations":
        content["limitations"] = ["CANDIDATE", ""]
    elif mutation == "title":
        content["title"] = ""
    elif mutation == "context":
        request = deepcopy(request)
        request["context"]["level"] = "FINAL_STMG"
    else:
        request = deepcopy(request)
        request["lineage"]["context_sha256"] = "0" * 64
    with pytest.raises(ValueError):
        bind_p0_content(request, content)
