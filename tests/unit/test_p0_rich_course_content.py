"""Rich COURSE wire/binder regressions: entirely synthetic, no provider network."""
import hashlib
import json
from dataclasses import replace
from secrets import token_hex

import pytest

from backend.adapters.outbound.generation.openai.p0_content import (
    bind_p0_content,
    build_p0_content_request,
    content_fields_for,
)
from backend.adapters.outbound.generation.openai.p0_course_content_schema import (
    rich_course_content_schema,
)
from backend.adapters.outbound.generation.openai.p0_normal import NormalP0GenerationAdapter
from backend.adapters.outbound.generation.openai.p0_normal_agents import (
    agent_preparation,
    guard_and_bind,
    parse_content,
)
from backend.adapters.outbound.generation.openai.p0_normal_policy import HASH_FIELDS, canonical, sha
from backend.adapters.outbound.openai.contracts import OpenAIIncompleteReason, OpenAIResponseStatus
from backend.adapters.outbound.openai.schema import validate_openai_strict_schema
from backend.agent_runtime.agents.generation.generation_coordinator import GenerationCoordinator
from backend.modules.pedagogical_design.application.mappers.course_provider_content import (
    RICH_CONTENT_FIELDS,
    course_capability_rows,
)
from backend.modules.pedagogical_design.contracts.dto.assessment_bundle import as_plain, fingerprint
from backend.modules.pedagogical_design.contracts.dto.course_chapter import (
    COURSE_LINEAGE_CONTRACT,
    CourseChapter,
)
from tests.unit.test_course_chapter import chapter_data
from tests.unit.test_p0_content_projection import request_for
from tests.unit.test_p0_normal_generation import NOW, synthetic_configuration
from tests.unit.test_stmg_institutional_alignment import Catalog, app, context, prepare

# Actual baseline fafe6b1 pure projection, synthetic inputs only. Captured before
# asserting the successor; no Git execution or private oracle during tests.
LEGACY_WIRE_SHA256 = {
    "COURSE": "3fd6e74bcbfd8786550d28efddc64889b06951822b671b1c11feee0ceed4a991",
    "EXERCISE": "f7fabab9e9663721e0bce882f68b2c96347e9bfbab914039349ab540067e88f5",
    "OPEN_QUESTIONS": "1728da8ac6a568b04f119211c40885dae773dd52b3704a2c4fe5a38f8a6bcd03",
    "QCM": "b5b771f385c27de4fe16f739827e5b4b2cfd5ec94fb9035b97fb219a9965d791",
    "QUIZ": "2020912687c66e500ed0979bc72aa2163a07280bfe02094d1fa096e15653d0ae",
    "ASSESSMENT": "7e68f7c92b9cf575fbf641a264650ef6be342aa2378f367c07dc2e9aae79f247",
    "STMG_EXPLAINED": "793f8bf61cc4cbb654392df1607d3af01b8572fc93995693741939f42a7e18c1",
}


@pytest.mark.parametrize("family", LEGACY_WIRE_SHA256)
def test_synthetic_legacy_wire_bytes_remain_exact(family):
    if family == "STMG_EXPLAINED":
        service = app(Catalog())
        prepared = prepare(service, context())
        dispatch = as_plain(service.prepared[prepared["preparation_ref"]])
    else:
        dispatch = request_for(family)
    assert sha(NormalP0GenerationAdapter.body(build_p0_content_request(dispatch))) == LEGACY_WIRE_SHA256[family]


def rich_preparation(frame="MANAGEMENT_PREMIERE"):
    service = app(Catalog())
    selected = context(frame)
    selected.update(contract_id="P0-CONTEXT-COURSE-3.0", course_format="CHAPTER")
    selected["local_progression"]["chapter"] = "7"
    prepared = prepare(service, selected)
    return service, prepared, as_plain(service.prepared[prepared["preparation_ref"]])


def rich_content(dispatch):
    chapter = chapter_data(dispatch["context"])
    chapter["documents"][0].update(function="METHOD", text="Situation construite : relever un fait, puis expliquer sa relation avec la notion.")
    chapter["documents"][0]["provenance"] = {"kind": "LOCAL_FICTION", "evidence_id": None}
    chapter["documents"].append({"id": "D2", "title": "Passage de référence fourni",
        "function": "REFERENCE", "text": next(iter(dispatch["evidence"].values())),
        "table": None, "provenance": {"kind": "SUPPLIED_REFERENCE",
            "evidence_id": dispatch["references"][0]["evidence_id"]}})
    chapter["parts"][0]["document_ids"].append("D2")
    for answer in chapter["teacher_answers"]:
        answer["expected_answer"] = (
            "SENTINELLE_PROFESSEUR_" + answer["id"] +
            " cette réponse synthétique est exclusivement réservée à la version du professeur.")
    return {"title": "Chapitre riche de test indépendant", "limitations": [],
        "course_chapter": {key: value for key, value in chapter.items() if key not in {
            "contract_id", "chapter_number", "title", "program_header", "capabilities", "notions"}}}


class NeverDispatched:
    def generate(self, *, request):
        raise AssertionError("No transport is used by this pure guard test")


def test_rich_schema_is_static_closed_and_has_no_local_authority_fields():
    _, _, dispatch = rich_preparation()
    _, _, second = rich_preparation("SGN_PREMIERE")
    first = build_p0_content_request(dispatch)
    other = build_p0_content_request(second)
    validate_openai_strict_schema(first.output_schema)
    assert first.output_schema == other.output_schema == rich_course_content_schema()
    assert set(first.output_schema["properties"]) == RICH_CONTENT_FIELDS
    assert first.model == "gpt-5.6-terra" and first.max_output_tokens == 4096
    assert first.reasoning_effort.value == "low" and first.service_tier == "default"
    forbidden = {"program_header", "production_ref", "version_ref", "lineage", "capabilities",
                 "authority_status", "media_assets", "visual_briefs"}
    def closed(node):
        if isinstance(node, dict):
            if node.get("type") == "object":
                assert node["additionalProperties"] is False
                assert set(node["required"]) == set(node["properties"])
                assert not forbidden & set(node["properties"])
            for value in node.values():
                closed(value)
        elif isinstance(node, list):
            for value in node:
                closed(value)
    closed(first.output_schema)


def test_rich_wire_uses_only_confirmed_content_and_is_random_identity_independent():
    _, _, first = rich_preparation()
    _, _, second = rich_preparation()
    assert first["production_ref"] != second["production_ref"]
    wire = build_p0_content_request(first)
    assert wire == build_p0_content_request(second)
    payload = json.loads(wire.input_json)
    assert payload["course_capabilities"] == [{"id": "C1", "label": "Capacité spécifique MANAGEMENT_PREMIERE"}]
    assert payload["context"]["course_format"] == "CHAPTER"
    assert "function=METHOD" in wire.instructions and "questions/corrections/marking vides" not in wire.instructions
    assert "aucune recette de nombre" in wire.instructions
    assert first["production_ref"] not in wire.input_json and first["version_ref"] not in wire.input_json
    assert "SENTINELLE_PROFESSEUR" not in wire.input_json


def test_pure_rich_guard_binds_complete_chapter_without_enrichment():
    _, _, dispatch = rich_preparation()
    content = rich_content(dispatch)
    result = NormalP0GenerationAdapter.technical_result(dispatch, canonical(content).decode())
    preparation = agent_preparation(dispatch, NOW)
    assert set(preparation.output_contract["fields"]) == RICH_CONTENT_FIELDS
    controls = []
    bound = guard_and_bind(dispatch, GenerationCoordinator(NeverDispatched()), preparation,
                           result, observer=controls.append)
    typed = bind_p0_content(dispatch, content)
    assert bound == as_plain(typed.data)
    chapter = bound["course_chapter"]
    assert chapter["contract_id"] == COURSE_LINEAGE_CONTRACT and chapter["chapter_number"] == 7
    assert chapter["capabilities"] == course_capability_rows(typed.context)
    assert chapter["program_header"]["question_label"] == dispatch["context"]["institutional_resolution"]["question"]["official_label"]
    assert chapter["notions"] == dispatch["context"]["topics"]
    assert chapter["teacher_answers"] == content["course_chapter"]["teacher_answers"]
    assert bound["questions"] == bound["corrections"] == bound["marking"] == []
    for key in ("production_ref", "version_ref", "context", "context_sha256", "references", "lineage"):
        assert bound[key] == dispatch[key]
    assert controls[0]["source_usage_declaration"] == "NOT_IN_OUTPUT_SCHEMA"
    assert controls[0]["source_status"] == "RESERVE" and controls[0]["declared_evidence_refs_used"] == []
    assert "SENTINELLE_PROFESSEUR" not in json.dumps(typed.student_projection())
    assert "SENTINELLE_PROFESSEUR" in json.dumps(typed.teacher_projection())


@pytest.mark.parametrize("mutation", ["header", "capabilities", "contract_id", "version_ref", "unknown",
    "source_unknown", "fiction_reference", "supplied_missing", "unknown_notion", "unknown_capability",
    "id", "method_missing", "method_orphan", "answer_link", "document_link", "extra_response",
    "document_title_oversize", "document_function_oversize"])
def test_rich_provider_cannot_invent_authority_or_break_links(mutation):
    _, _, dispatch = rich_preparation()
    content = rich_content(dispatch)
    chapter = content["course_chapter"]
    if mutation in {"header", "capabilities", "contract_id"}:
        chapter[{"header": "program_header", "capabilities": "capabilities", "contract_id": "contract_id"}[mutation]] = "invented"
    elif mutation in {"version_ref", "unknown"}:
        content[mutation] = "invented"
    elif mutation == "source_unknown":
        chapter["documents"][1]["provenance"]["evidence_id"] = "evidence:" + "f" * 32
    elif mutation == "fiction_reference":
        chapter["documents"][0]["provenance"]["evidence_id"] = dispatch["references"][0]["evidence_id"]
    elif mutation == "supplied_missing":
        chapter["documents"][1]["provenance"]["evidence_id"] = None
    elif mutation == "unknown_notion":
        chapter["concepts"][0]["notion"] = "Unselected notion"
    elif mutation == "unknown_capability":
        chapter["questions"][0]["capability_ids"] = ["C9"]
    elif mutation == "id":
        chapter["documents"][0]["id"] = "arbitrary/path"
    elif mutation == "method_missing":
        chapter["documents"][0]["function"] = "CASE"
    elif mutation == "method_orphan":
        chapter["parts"][0]["document_ids"] = ["D2"]
    elif mutation == "answer_link":
        chapter["teacher_answers"][0]["id"] = "Q99"
    elif mutation == "document_link":
        chapter["questions"][0]["document_ids"] = ["D99"]
    elif mutation == "document_title_oversize":
        chapter["documents"][0]["title"] = "x" * 201
    elif mutation == "document_function_oversize":
        chapter["documents"][0]["function"] = "x" * 201
    else:
        chapter["questions"][0]["response"]["hidden_answer"] = "forbidden"
    with pytest.raises(ValueError):
        bind_p0_content(dispatch, content)


@pytest.mark.parametrize("invalid", ["duplicate", "nonfinite", "legacy", "rich_with_no_dispatch", "oversize"])
def test_rich_parse_is_closed_and_legacy_default_stays_explicit(invalid):
    _, _, dispatch = rich_preparation()
    text = canonical(rich_content(dispatch)).decode()
    if invalid == "duplicate":
        text = text[:-1] + ', "title":"duplicate"}'
    elif invalid == "nonfinite":
        text = text.replace('"number":1', '"number":NaN', 1)
    elif invalid == "legacy":
        text = canonical({key: [] for key in ("title", "sections", "questions", "corrections", "marking", "limitations")}).decode()
    elif invalid == "oversize":
        text = "x" * 128001
    with pytest.raises(ValueError):
        parse_content(text, None if invalid == "rich_with_no_dispatch" else dispatch)
    assert content_fields_for() == {"title", "sections", "questions", "corrections", "marking", "limitations"}


def test_changed_evidence_is_refused_by_rich_wire_and_binder():
    _, _, dispatch = rich_preparation()
    content = rich_content(dispatch)
    dispatch["evidence"][dispatch["references"][0]["evidence_id"]] = "Changed synthetic passage"
    with pytest.raises(ValueError, match="P0_EVIDENCE_HASH"):
        build_p0_content_request(dispatch)
    with pytest.raises(ValueError, match="P0_EVIDENCE_HASH"):
        bind_p0_content(dispatch, content)


@pytest.mark.parametrize("theme_ref,label", [("theme:1", "Thème 1"),
    ("framework-element:opaque-internal-id", "Thème non renseigné")])
def test_missing_theme_label_does_not_display_an_internal_identifier(theme_ref, label):
    _, _, dispatch = rich_preparation()
    selected = dispatch["context"]["institutional"]
    selected["theme_ref"] = theme_ref
    resolution = dispatch["context"]["institutional_resolution"]
    resolution["theme_ref"] = theme_ref
    resolution.pop("theme", None)
    resolution["selection_sha256"] = fingerprint(selected)
    dispatch["context_sha256"] = fingerprint(dispatch["context"])
    dispatch["lineage"]["context_sha256"] = dispatch["context_sha256"]
    bound = bind_p0_content(dispatch, rich_content(dispatch))
    chapter = CourseChapter(bound.data["course_chapter"])
    assert chapter.data["program_header"]["theme_label"] == label
    assert "opaque-internal-id" not in chapter.visible_text()


def rich_synthetic_configuration(tmp_path):
    config, _, _, _, identities, tokens, resolver, transport = synthetic_configuration(tmp_path)
    service, prepared, dispatch = rich_preparation()
    wire = build_p0_content_request(dispatch)
    body = NormalP0GenerationAdapter.body(wire)
    updates = {"request_sha256": sha(body), "request_bytes": len(body),
        "preparation_sha256": sha(canonical(dispatch)), "context_sha256": dispatch["context_sha256"],
        "reference_set_sha256": sha(canonical(dispatch["references"])),
        "output_schema_sha256": sha(canonical(wire.output_schema))}
    config["grant"].update(updates)
    identities.update({key: config["grant"][key] for key in HASH_FIELDS | {"baseline_commit", "request_bytes"}})
    tokens["request_sha256"] = sha(body)
    transport.response = replace(transport.response, output_text=canonical(rich_content(dispatch)).decode())
    service.generation = NormalP0GenerationAdapter(**config)
    return config, service, prepared, dispatch, resolver, transport


@pytest.mark.parametrize("mutation", ["incomplete", "completed_token_limit", "completed_filter", "truncated", "explained"])
def test_rich_incomplete_or_wrong_contract_is_captured_refused_and_not_retried(tmp_path, mutation):
    _, service, prepared, dispatch, _, transport = rich_synthetic_configuration(tmp_path)
    response = transport.response
    if mutation == "incomplete":
        response = replace(response, status=OpenAIResponseStatus.INCOMPLETE,
                           incomplete_reason=OpenAIIncompleteReason.MAX_OUTPUT_TOKENS)
    elif mutation.startswith("completed"):
        response = replace(response, incomplete_reason=OpenAIIncompleteReason.MAX_OUTPUT_TOKENS
                           if mutation == "completed_token_limit" else OpenAIIncompleteReason.CONTENT_FILTER)
    elif mutation == "truncated":
        response = replace(response, output_text=response.output_text[:-20])
    else:
        response = replace(response, output_text=canonical({key: [] for key in content_fields_for()}).decode())
    transport.response = response
    with pytest.raises(ValueError):
        service.execute("generate", {"command_id": token_hex(16), "preparation_ref": prepared["preparation_ref"],
            "preparation_sha256": prepared["preparation_sha256"]})
    adapter = service.generation
    assert transport.calls == 1 and not service.records
    assert adapter.receipt.exists("RESPONSE_CAPTURED") and adapter.receipt.exists("PARSING_REJECTED")
    assert not adapter.receipt.exists("CONSUMED")
    with pytest.raises(ValueError):
        adapter.generate(request=dispatch)
    assert transport.calls == 1


def test_stale_six_field_schema_grant_stops_before_synthetic_resolver(tmp_path):
    _, service, _, dispatch, resolver, transport = rich_synthetic_configuration(tmp_path)
    adapter = service.generation
    adapter.grant["output_schema_sha256"] = hashlib.sha256(b"old_six_field_schema").hexdigest()
    with pytest.raises(ValueError):
        adapter.authorize(request=dispatch)
    assert resolver.calls == transport.calls == 0 and not adapter.receipt.exists("RESERVED")


def test_rich_confirmed_recovery_uses_same_contract_without_another_effect(tmp_path):
    config, service, _, dispatch, resolver, transport = rich_synthetic_configuration(tmp_path)
    adapter = service.generation
    adapter.authorize(request=dispatch)
    bound = adapter.generate(request=dispatch)
    captured = {path.name: path.read_bytes() for path in config["receipt_root"].glob("*.json")}
    config["identity_source"] = lambda *args: (_ for _ in ()).throw(AssertionError("NO_IDENTITIES"))
    config["tokenizer"] = lambda *args: (_ for _ in ()).throw(AssertionError("NO_TOKENIZER"))
    restarted = NormalP0GenerationAdapter(**config)
    assert restarted.recover_confirmed(request=dispatch) == bound
    assert resolver.calls == transport.calls == 1
    assert {path.name: path.read_bytes() for path in config["receipt_root"].glob("*.json")} == captured
