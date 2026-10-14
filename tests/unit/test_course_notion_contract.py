"""Versioned alias binding over synthetic admitted Application selections only."""
import copy
import json

import pytest

from backend.adapters.outbound.generation.openai.p0_content import (
    bind_p0_content,
    build_p0_content_request,
)
from backend.adapters.outbound.generation.openai.p0_course_content_schema import (
    rich_course_notion_content_schema,
)
from backend.adapters.outbound.generation.openai.p0_normal import NormalP0GenerationAdapter
from backend.adapters.outbound.generation.openai.p0_normal_agents import (
    agent_preparation,
    guard_and_bind,
)
from backend.adapters.outbound.generation.openai.p0_normal_policy import canonical
from backend.agent_runtime.agents.generation.generation_coordinator import GenerationCoordinator
from backend.infrastructure.composition.factories.local_browser import build_saved_application
from backend.modules.pedagogical_context.contracts.dto.course_notions import course_notion_rows
from backend.modules.pedagogical_context.contracts.dto.p0_context import P0Context
from backend.modules.pedagogical_design.contracts.dto.assessment_bundle import as_plain
from backend.modules.pedagogical_design.contracts.dto.course_chapter import CourseChapter
from backend.modules.pedagogical_design.contracts.dto.course_delivery import (
    validate_course_delivery,
)
from backend.modules.pedagogical_design.contracts.dto.p0_production import P0Production
from tests.unit.test_course_media_persistence import record_version
from tests.unit.test_p0_normal_generation import NOW
from tests.unit.test_p0_rich_course_content import (
    NeverDispatched,
    rich_content,
    rich_preparation,
    rich_synthetic_configuration,
)
from tests.unit.test_stmg_institutional_alignment import Catalog, app, context, prepare


def notion_preparation(frame="MANAGEMENT_PREMIERE", *, multiple=False):
    catalog = Catalog()
    catalog.data["notion"][0]["canonical_label"] = "Organisation"
    selected = context(frame)
    selected.update(contract_id="P0-CONTEXT-COURSE-4.0", course_format="CHAPTER",
                    topics=["Organiser l’action collective"])
    selected["local_progression"]["chapter"] = "7"
    if multiple:
        catalog.data["notion"].append({"id": "notion:second", "canonical_label": "Action collective",
                                      "identity_status": "CANONICAL"})
        catalog.data["institutional_attachment"].append({
            **catalog.data["institutional_attachment"][0], "id": "attachment:second",
            "notion_id": "notion:second"})
        selected["institutional"]["notion_refs"] = ["notion:second", "notion:shared"]
    service = app(catalog)
    prepared = prepare(service, selected)
    return service, prepared, as_plain(service.prepared[prepared["preparation_ref"]])


def notion_content(dispatch):
    content = rich_content(dispatch)
    concepts = content["course_chapter"]["concepts"]
    concepts[0].pop("notion")
    concepts[0]["notion_id"] = "N1"
    return content


def notion_synthetic_configuration(tmp_path):
    return rich_synthetic_configuration(tmp_path, preparation_factory=notion_preparation,
                                        content_factory=notion_content)


@pytest.mark.parametrize("frame", ["MANAGEMENT_PREMIERE", "SGN_PREMIERE", "MSDGN_TERMINALE_COMMON"])
def test_theme_and_canonical_notion_are_distinct_through_prepare_guard_and_bind(frame):
    _, _, dispatch = notion_preparation(frame)
    content = notion_content(dispatch)
    before = copy.deepcopy(content)
    result = NormalP0GenerationAdapter.technical_result(dispatch, canonical(content).decode())
    bound = guard_and_bind(dispatch, GenerationCoordinator(NeverDispatched()),
                           agent_preparation(dispatch, NOW), result)
    bundle = P0Production(bound)
    chapter = as_plain(bundle.data["course_chapter"])
    assert bundle.context.as_dict() == dispatch["context"]
    assert bundle.context.data["topics"] == ("Organiser l’action collective",)
    assert chapter["notions"] == ["Organisation"]
    assert chapter["concepts"][0]["notion"] == "Organisation"
    assert content == before
    for key in ("definition", "explanation", "example"):
        assert chapter["concepts"][0][key] == content["course_chapter"]["concepts"][0][key]
    for key in ("context", "parts", "questions", "teacher_answers", "synthesis", "knowledge_check", "transfer"):
        assert chapter[key] == content["course_chapter"][key]
    assert chapter["program_header"]["frame"] == frame
    assert chapter["contract_id"] == "COURSE-CHAPTER-LINEAGE-4.0"
    assert bundle.data["contract_id"] == "R6-P0-PRODUCTION-COURSE-3.0"
    assert "SENTINELLE_PROFESSEUR" not in json.dumps(bundle.student_projection())
    assert "SENTINELLE_PROFESSEUR" in json.dumps(bundle.teacher_projection())


def test_new_wire_schema_is_static_and_aliases_expose_no_notion_body_or_new_authority():
    _, _, dispatch = notion_preparation()
    _, _, other = notion_preparation("SGN_PREMIERE")
    wire = build_p0_content_request(dispatch)
    payload = json.loads(wire.input_json)
    assert wire.output_schema == build_p0_content_request(other).output_schema == rich_course_notion_content_schema()
    properties = wire.output_schema["properties"]["course_chapter"]["properties"]["concepts"]["items"]["properties"]
    assert "notion" not in properties and properties["notion_id"]["pattern"] == "^N(?:[1-9]|1[0-6])$"
    assert payload["course_notions"] == [{"id": "N1", "label": "Organisation"}]
    assert payload["contract_id"] == "R6-P0-COURSE-CONTENT-INPUT-3.0"
    assert payload["course_policy"]["provider_content_contract"] == "P0-COURSE-RICH-CONTENT-2.0"
    assert "topics confirmés" not in wire.instructions
    assert "chaque question une seule fois" in wire.instructions
    assert wire.model == "gpt-5.6-terra" and wire.max_output_tokens == 4096
    assert wire.reasoning_effort.value == "low" and wire.service_tier == "default"
    assert set(payload["course_notions"][0]) == {"id", "label"}
    assert dispatch["production_ref"] not in wire.input_json


def test_multiple_aliases_follow_selection_order_and_cover_every_selected_notion():
    _, _, dispatch = notion_preparation(multiple=True)
    rows = course_notion_rows(P0Context(dispatch["context"]))
    assert [(r["id"], r["label"]) for r in rows] == [("N1", "Action collective"), ("N2", "Organisation")]
    content = notion_content(dispatch)
    with pytest.raises(ValueError, match="NOTION_COVERAGE"):
        bind_p0_content(dispatch, content)
    content["course_chapter"]["concepts"].append({
        **content["course_chapter"]["concepts"][0], "id": "CONCEPT2", "notion_id": "N2"})
    content["course_chapter"]["parts"][0]["concept_ids"].append("CONCEPT2")
    bound = bind_p0_content(dispatch, content)
    assert bound.data["course_chapter"]["notions"] == ("Action collective", "Organisation")


@pytest.mark.parametrize("mutation", ["missing", "extra", "duplicate_ref", "empty_label", "ambiguous_label", "hash", "gap"])
def test_resolution_gaps_substitution_or_ambiguity_are_refused(mutation):
    _, _, dispatch = notion_preparation(multiple=True)
    data = dispatch["context"]
    resolution = data["institutional_resolution"]
    if mutation == "missing":
        resolution["notions"].pop()
    elif mutation == "extra":
        resolution["notions"].append({"notion_ref": "notion:foreign", "label": "Foreign"})
    elif mutation == "duplicate_ref":
        resolution["notions"].append(copy.deepcopy(resolution["notions"][0]))
    elif mutation == "empty_label":
        resolution["notions"][0]["label"] = " "
    elif mutation == "ambiguous_label":
        resolution["notions"][1]["label"] = "  " + resolution["notions"][0]["label"].upper() + " "
    elif mutation == "hash":
        resolution["selection_sha256"] = "0" * 64
    else:
        resolution["status"] = "CONTENT_GAP"
    with pytest.raises(ValueError):
        course_notion_rows(P0Context(data))


@pytest.mark.parametrize("alias", ["Organisation", "N0", "N2", "N17", "n1", " N1", None])
def test_label_or_out_of_selection_alias_is_rejected(alias):
    _, _, dispatch = notion_preparation()
    content = notion_content(dispatch)
    content["course_chapter"]["concepts"][0]["notion_id"] = alias
    with pytest.raises(ValueError, match="NOTION_ALIAS_UNKNOWN"):
        bind_p0_content(dispatch, content)


def test_old_context_still_rejects_a_canonical_label_outside_its_free_topics():
    _, _, dispatch = rich_preparation()
    content = rich_content(dispatch)
    content["course_chapter"]["concepts"][0]["notion"] = "Organisation"
    with pytest.raises(ValueError, match="P0_RICH_COURSE_NOTION_UNKNOWN"):
        bind_p0_content(dispatch, content)


@pytest.mark.parametrize("mutation", ["missing_chapter", "method", "teacher_copy", "document_reference", "question_coverage", "question_number", "official_claim"])
def test_v4_runs_delivery_checks_without_the_old_early_return(mutation):
    _, _, dispatch = notion_preparation()
    bound = bind_p0_content(dispatch, notion_content(dispatch))
    chapter = as_plain(bound.data["course_chapter"])
    if mutation == "missing_chapter":
        chapter = None
    elif mutation == "method":
        chapter["documents"][0]["function"] = "CASE"
    elif mutation == "teacher_copy":
        chapter["context"]["text"] = chapter["teacher_answers"][0]["expected_answer"]
    elif mutation == "document_reference":
        chapter["documents"][1]["provenance"]["source_ref"] = "evidence:" + "f" * 32
    elif mutation == "question_coverage":
        chapter["parts"][0]["analysis"] = chapter["parts"][0]["observation"]
    elif mutation == "question_number":
        chapter["questions"][0]["number"] = 2
    else:
        chapter["teacher_answers"][0]["rationale"] = "En BTS CG 1, cette activité est officiellement prescrite."
    with pytest.raises(ValueError):
        validate_course_delivery(bound.context, chapter, dispatch["references"])


@pytest.mark.parametrize("mutation", ["production", "chapter", "context", "concept", "notions", "chapter_number"])
def test_saved_contract_triplet_and_selected_concept_labels_are_bound(mutation):
    _, _, dispatch = notion_preparation()
    bound = bind_p0_content(dispatch, notion_content(dispatch))
    data = bound.mutable_copy()
    if mutation == "production":
        data["contract_id"] = "R6-P0-PRODUCTION-COURSE-2.0"
    elif mutation == "chapter":
        data["course_chapter"]["contract_id"] = "COURSE-CHAPTER-LINEAGE-3.0"
    elif mutation == "context":
        old = P0Context({**data["context"], "contract_id": "P0-CONTEXT-COURSE-3.0"})
        data.update(context=old.as_dict(), context_sha256=old.sha256)
        data["lineage"]["context_sha256"] = old.sha256
    elif mutation == "concept":
        data["course_chapter"]["concepts"][0]["notion"] = "Unknown"
        data["sections"] = CourseChapter(data["course_chapter"]).sections()
    elif mutation == "notions":
        data["course_chapter"]["notions"] = list(data["context"]["topics"])
    else:
        data["course_chapter"]["chapter_number"] = 9
    with pytest.raises(ValueError):
        P0Production(data)


def test_new_context_cannot_be_explained_or_bts():
    _, _, dispatch = notion_preparation()
    data = copy.deepcopy(dispatch["context"])
    data["course_format"] = "EXPLAINED"
    with pytest.raises(ValueError, match="P0_NOTION_COURSE_FORMAT"):
        P0Context(data)
    data["course_format"] = "CHAPTER"
    data["level"] = "BTS_CG_YEAR_1"
    with pytest.raises(ValueError, match="P0_RICH_COURSE_LEVEL_UNSUPPORTED"):
        P0Context(data)


@pytest.mark.parametrize("imported", [False, True])
def test_new_lineage_retains_bounded_local_ancestry_and_imported_limit(tmp_path, imported):
    from secrets import token_hex

    from backend.modules.work_orchestration.contracts.dto.saved_production import SavedProduction

    _, service, prepared, _, _, _ = notion_synthetic_configuration(tmp_path)
    generated = service.execute("generate", {"command_id": token_hex(16),
        "preparation_ref": prepared["preparation_ref"], "preparation_sha256": prepared["preparation_sha256"]})
    parent = service.saved_source(generated["view"]["production_ref"], generated["view"]["version_ref"])
    chapter = CourseChapter(parent.p0_bundle.data["course_chapter"])
    from backend.adapters.outbound.persistence.saved_production import LocalSavedProductionStore

    store = LocalSavedProductionStore(tmp_path / "version-library", create=True)
    def record(number):
        data = record_version(parent, chapter, number).mutable_copy()
        if imported:
            data["origin"] = "IMPORTED_DOCUMENTARY"
        return SavedProduction(data)
    limit = 3 if imported else 32
    for number in range(1, limit + 1):
        store.save(record(number))
    before = {r.version_ref: r.sha256 for r in store.list_versions()}
    with pytest.raises(ValueError, match="R4_VERSION_LIMIT"):
        store.save(record(limit + 1))
    assert {r.version_ref: r.sha256 for r in store.list_versions()} == before
    library = build_saved_application(tmp_path / "version-library", word_profile="product-v7")
    opened = library.execute("open", parent.production_ref, record(limit).version_ref,
                             correlation="notion.ancestry.open")
    assert opened["record_sha256"] == before[record(limit).version_ref]
    assert opened["active_authority"] == "NONE_RESTORED"
