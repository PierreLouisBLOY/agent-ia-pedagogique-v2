"""Bounded provider view retains exact prescriptions and local full bindings."""
import json

import pytest

from backend.adapters.outbound.generation.openai.p0_content import (
    bind_p0_content,
    build_p0_content_request,
)
from backend.modules.pedagogical_design.contracts.dto.assessment_bundle import fingerprint
from tests.support.p0_generation_double import P0GenerationDouble
from tests.unit.test_bts_institutional_preparation import context, prepare, service
from tests.unit.test_qualified_institutional_corpus import qualified_catalog


def request(*, implicit=False):
    app, _, _ = service(qualified_catalog(bts=True, implicit=implicit))
    prepared = prepare(app, context())
    return dict(app.prepared[prepared["preparation_ref"]])


def test_provider_view_preserves_prescriptions_hash_and_bts_local_year_without_duplicate_inventory():
    dispatch = request()
    wire = build_p0_content_request(dispatch)
    assert len(wire.input_json.encode()) <= 12288
    payload = json.loads(wire.input_json)
    view = payload["context"]
    assert view["contract_id"] == "P0-PROVIDER-CONTEXT-VIEW-1.0"
    assert "institutional_resolution" not in view
    resolution = dispatch["context"]["institutional_resolution"]
    assert view["institutional_resolution_sha256"] == fingerprint(resolution)
    proof = payload["authority_layers"]["institutional_evidence"][0]
    assert proof["full_resolution_sha256"] == fingerprint(resolution)
    assert proof["document"]["sha256"] == resolution["document_provenance"]["sha256"]
    assert proof["capacities_or_competencies"][0]["official_label"] == resolution["competencies"][0]["official_label"]
    assert proof["attachments"][0]["disposition"] == "VERIFIED_EXPLICIT"
    assert proof["attachments"][0]["full_attachment_sha256"] == fingerprint(resolution["attachments"][0])
    assert proof["year_authority"] == "LOCAL_PROGRESSION_ONLY"
    assert all(set(row) == {"notion_ref", "label"} for row in proof["notions"])
    assert "SOURCE_GAP" not in proof["notions"][0]


def test_content_rebinds_full_application_context_and_cannot_replace_view():
    dispatch = request()
    output = P0GenerationDouble().generate(request=dispatch)
    fields = ("title", "sections", "questions", "corrections", "marking", "limitations")
    content = {key: output[key] for key in fields}
    bound = bind_p0_content(dispatch, content)
    assert bound.context.as_dict() == context_with_resolution(dispatch)
    assert bound.context.sha256 == dispatch["context_sha256"]
    with pytest.raises(ValueError):
        bind_p0_content(dispatch, {**content, "context": json.loads(build_p0_content_request(dispatch).input_json)["context"]})


def context_with_resolution(dispatch):
    from backend.modules.pedagogical_design.contracts.dto.assessment_bundle import as_plain

    return as_plain(dispatch["context"])


def test_implicit_justification_and_negative_authority_are_not_removed_by_projection():
    dispatch = request(implicit=True)
    payload = json.loads(build_p0_content_request(dispatch).input_json)
    proof = payload["authority_layers"]["institutional_evidence"][0]
    original = dispatch["context"]["institutional_resolution"]["attachments"][0]
    assert proof["attachments"][0]["justification"] == original["justification"]
    assert proof["review_axes"]["institutional_alignment"] == "VERIFIED_IMPLICIT"
    assert proof["review_axes"]["authority_claims"] == "IMPLICIT_NOT_OFFICIAL_CITATION"
