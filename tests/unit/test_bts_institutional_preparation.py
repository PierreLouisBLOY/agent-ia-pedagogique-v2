"""Synthetic outbound fixtures exercise the product's native BTS preparation."""
import copy
import hashlib
from secrets import token_hex

import pytest

from backend.adapters.inbound.application.bts_alignment import BTSAlignmentInbound
from backend.modules.knowledge_reference.application.queries.bts_alignment import ReadBTSAlignment
from backend.modules.pedagogical_context.contracts.dto.p0_context import P0Context
from backend.modules.pedagogical_context.contracts.dto.stmg_institutional import (
    institutional_header,
)
from backend.modules.pedagogical_design.contracts.dto.p0_production import P0_PROVENANCE_LABEL
from backend.modules.work_orchestration.application.services.p0_creation import P0CreationService
from tests.support.p0_generation_double import P0GenerationDouble
from tests.unit.test_qualified_institutional_corpus import Catalog, qualified_catalog


def context():
    return {"contract_id": "P0-CONTEXT-2.0", "resource_type": "EXERCISE", "question_mode": None,
        "level": "BTS_CG_YEAR_2", "discipline": "Comptabilité et gestion", "topics": ["Notion de test"],
        "objectives": ["Appliquer la compétence sélectionnée"], "difficulty": "STANDARD", "language": "fr",
        "duration_minutes": None, "total_points": None,
        "institutional": {"contract_id": "BTS-INSTITUTIONAL-CONTEXT-1.0", "program_ref": "frame:test",
            "program_version": "version:test", "process_ref": "element:THEME", "activity_ref": "element:QUESTION",
            "competency_refs": ["element:CAPACITY"], "notion_refs": ["notion:test-0"],
            "depth": "APPLICATION", "local_year": "BTS_CG_YEAR_2"},
        "institutional_resolution": None, "local_progression": {"chapter": "Local", "sequence": None, "week": None}}


def reference():
    return {"notion_id": "notion:test-0", "object_ref": "notion:test-0", "object_kind": "NOTION",
        "passage_ref": "synthetic:canonical", "version_or_checksum": "synthetic:version"}


def service(data=None):
    inbound = BTSAlignmentInbound(ReadBTSAlignment(Catalog(data or qualified_catalog(bts=True))))
    text = "Notion canonique synthétique, sans admission disciplinaire implicite."
    double = P0GenerationDouble()
    app = P0CreationService(lambda _: {"excerpt": text, "reference": {
        "evidence_id": "evidence:" + "a" * 32, "source_ref": "notion:test-0", "locator": "synthetic:canonical",
        "checksum_or_version": "synthetic:version", "excerpt_sha256": hashlib.sha256(text.encode()).hexdigest(),
        "provenance_label": P0_PROVENANCE_LABEL}}, generation=double,
        institutional_resolver=lambda selection, selected: inbound.resolve(selection, {**reference(), **selected}),
        exact_institutional_required=True)
    return app, double, inbound


def prepare(app, data):
    return app.execute("prepare", {"command_id": token_hex(16), "context": data,
        "reference": {"notion_id": "notion:test-0", "passage_ref": "synthetic:canonical"}})


def test_bts_prepare_before_plan_and_generation_with_separate_authority_axes():
    app, double, inbound = service()
    catalog = inbound.catalog()
    assert catalog[0]["year_authority"] == "LOCAL_PROGRESSION_ONLY"
    result = prepare(app, context())
    resolved = result["context"]["institutional_resolution"]
    assert resolved["process"]["element_type"] == "PROCESS"
    assert resolved["activity"]["element_type"] == "ACTIVITY"
    assert "theme_ref" not in result["context"]["institutional"]
    assert resolved["competencies"][0]["element_type"] == "COMPETENCY"
    assert result["agentic"]["plan"]["institutional_resolution"] == resolved
    assert result["agentic"]["plan"]["review_axes"]["disciplinary_accuracy"] == "NOT_ASSESSED"
    pack = result["agentic"]["evidence_pack"]
    assert pack["institutional_evidence"] and not pack["disciplinary_evidence"]
    assert pack["pedagogical_evidence"] == [] and result["provider_attempts"] == 0
    assert "progression locale" in institutional_header(result["context"])
    generated = app.execute("generate", {"command_id": token_hex(16), "preparation_ref": result["preparation_ref"],
        "preparation_sha256": result["preparation_sha256"]})
    assert generated and len(double.requests) == 1
    assert double.requests[0]["context"]["institutional_resolution"] == resolved


@pytest.mark.parametrize("key,value", [
    ("program_version", "other:version"), ("program_ref", "other:framework"),
    ("process_ref", "element:QUESTION"), ("activity_ref", "element:THEME"),
    ("competency_refs", ["element:THEME"]), ("notion_refs", ["notion:test-1"]),
    ("local_year", "BTS_CG_YEAR_1"), ("competency_refs", []), ("notion_refs", []),
])
def test_mutated_selection_blocked_before_any_transport(key, value):
    app, double, _ = service()
    data = context()
    data["institutional"][key] = value
    with pytest.raises(ValueError, match="INSTITUTIONAL_"):
        prepare(app, data)
    assert double.requests == [] and app.prepared == {}


@pytest.mark.parametrize("key,value", [("object_kind", "METHOD"), ("object_ref", "another:notion"),
    ("notion_id", "another:notion"), ("passage_ref", ""), ("version_or_checksum", "")])
def test_reference_identity_not_promoted_by_context(key, value):
    _, _, inbound = service()
    selected = reference()
    selected[key] = value
    with pytest.raises(ValueError, match="EXACT_NOTION"):
        inbound.resolve(context()["institutional"], selected)


def test_unadmitted_legacy_rows_and_wrong_process_ancestry_are_refused():
    data = qualified_catalog(bts=True)
    data["institutional_qualifications"] = []
    _, _, inbound = service(data)
    with pytest.raises(ValueError, match="VERSION"):
        inbound.resolve(context()["institutional"], reference())
    data = qualified_catalog(bts=True)
    for row in data["institutional_qualifications"][0]["elements"]:
        if row["id"] == "element:QUESTION":
            row["parent_ref"] = None
    for row in data["official_framework_element"]:
        if row["id"] == "element:QUESTION":
            row["parent_element_id"] = None
    _, _, inbound = service(data)
    with pytest.raises(ValueError, match="PROCESS_SCOPE"):
        inbound.resolve(context()["institutional"], reference())


def test_no_legacy_bts_dispatch_but_saved_context_remains_readable():
    app, double, _ = service()
    legacy = {key: value for key, value in context().items() if key not in {"institutional", "institutional_resolution", "local_progression"}}
    legacy["contract_id"] = "R6-P0-CONTEXT-1.0"
    saved = P0Context(legacy)
    assert saved.as_dict() == legacy
    with pytest.raises(ValueError, match="CONTEXT_REQUIRED"):
        prepare(app, legacy)
    with pytest.raises(ValueError, match="CONTEXT_REQUIRED"):
        saved.require_institutional_dispatch()
    assert double.requests == []


def test_resolution_contract_or_selection_hash_substitution_refused():
    app, _, _ = service()
    resolved = prepare(app, context())["context"]
    for key, value in (("selection_sha256", "0" * 64), ("contract_id", "STMG-RESOLUTION-1.0")):
        changed = copy.deepcopy(resolved)
        changed["institutional_resolution"][key] = value
        with pytest.raises(ValueError, match="RESOLUTION_BINDING"):
            P0Context(changed)
