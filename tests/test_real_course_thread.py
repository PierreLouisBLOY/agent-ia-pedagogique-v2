"""Synthetic documentary dossier through the normal chapter and saved Application."""
import copy
import json
from hashlib import sha256
from io import BytesIO
from secrets import token_hex
from zipfile import ZipFile

import pytest

from backend.adapters.outbound.generation.openai.p0_content import (
    bind_p0_content,
    build_p0_content_request,
)
from backend.adapters.outbound.generation.openai.p0_normal_policy import canonical
from backend.infrastructure.composition.factories.local_browser import build_saved_application
from backend.infrastructure.composition.factories.organization_capture import (
    organization_capture_reader,
)
from backend.modules.pedagogical_context.contracts.dto.real_course_thread import (
    REAL_CHAPTER,
    RealCourseThread,
)
from backend.modules.pedagogical_design.contracts.dto.assessment_bundle import as_plain
from backend.modules.resource_library.application.queries.read_course_threads import (
    ReadCourseThreads,
)
from backend.modules.work_orchestration.application.queries.p0_source_admission import (
    ReadP0SourceAdmission,
)
from tests.test_organization_evidence_325 import official_identity
from tests.unit.test_course_notion_contract import notion_content, notion_preparation
from tests.unit.test_p0_rich_course_content import rich_synthetic_configuration


def dossier():
    text = "EXTRAIT SYNTHÉTIQUE : ce document de test décrit une organisation collective."
    return RealCourseThread({"contract_id": "COURSE-REAL-THREAD-1.0",
        "identity": dict(official_identity().data), "documents": [{
            "id": "S1", "title": "Document strictement synthétique",
            "source_url": "https://example.org/SYNTHETIC-document", "publisher": "SYNTHETIC FIXTURE",
            "retrieved_on": "2026-10-01", "excerpt": text, "excerpt_sha256": sha256(text.encode()).hexdigest(),
            "rights": "Données synthétiques réservées aux essais locaux.", "notion_refs": ["notion:shared"]}]})


def real_preparation():
    service, _, old = notion_preparation()
    thread = dossier()
    service.course_thread_reader = ReadCourseThreads((thread,)).read
    selected = copy.deepcopy(old["context"])
    selected["institutional_resolution"] = None
    prepared = service.execute("prepare", {"command_id": token_hex(16), "context": selected,
        "reference": {"notion_id": "notion:shared", "passage_ref": "unit:passage"},
        "organization_selection": {"organization_id": thread.organization_id, "dossier_sha256": thread.sha256}})
    return service, prepared, as_plain(service.prepared[prepared["preparation_ref"]])


def real_content(dispatch):
    content = notion_content(dispatch)
    thread = dossier()
    chapter = content["course_chapter"]
    chapter["context"].update(organization_id=thread.organization_id, title=thread.label)
    chapter["documents"][0]["text"] = thread.fiction_notice + " " + chapter["documents"][0]["text"]
    ref = thread.references()[1]
    chapter["documents"].append({"id": "D3", "title": "Document documentaire de test",
        "function": "REFERENCE", "text": thread.evidence()[ref["evidence_id"]], "table": None,
        "provenance": {"kind": "SUPPLIED_REFERENCE", "evidence_id": ref["evidence_id"]}})
    chapter["parts"][0]["document_ids"].append("D3")
    return content


def real_configuration(tmp_path):
    return rich_synthetic_configuration(tmp_path, preparation_factory=real_preparation, content_factory=real_content)


def test_prepare_wire_schema_and_unchanged_legacy():
    _, _, old = notion_preparation()
    _, prepared, request = real_preparation()
    assert "course_thread" not in old["context"]["institutional_resolution"]
    assert len(prepared["references"]) == 3 and prepared["provider_attempts"] == 0
    assert request["context_sha256"] != old["context_sha256"]
    wire = build_p0_content_request(request)
    from backend.adapters.outbound.openai.schema import validate_openai_strict_schema
    validate_openai_strict_schema(wire.output_schema)
    payload = json.loads(wire.input_json)
    assert payload["organization_thread"]["organization_id"] == dossier().organization_id
    assert dossier().evidence()[dossier().references()[1]["evidence_id"]] in wire.input_json
    assert "organization_id" in wire.output_schema["properties"]["course_chapter"]["properties"]["context"]["required"]
    assert payload["organization_thread"]["fiction_notice"] == dossier().fiction_notice
    assert "exactement par fiction_notice" in wire.instructions


@pytest.mark.parametrize("mutation", ["empty", "hash", "url", "rights", "notions"])
def test_dossier_refuses_insufficient_or_changed_source(mutation):
    data = dossier().as_dict()
    if mutation == "empty":
        data["documents"] = []
    elif mutation == "hash":
        data["documents"][0]["excerpt"] += " changé"
    elif mutation == "url":
        data["documents"][0]["source_url"] = "http://example.org"
    elif mutation == "rights":
        data["documents"][0]["rights"] = ""
    else:
        data["documents"][0]["notion_refs"] = []
    with pytest.raises(ValueError):
        RealCourseThread(data)


def test_pinned_application_catalogue_and_inspection(tmp_path):
    thread = dossier()
    data = {"schema": "LOCAL-ORGANIZATION-CAPTURES-3.0", "records": [dict(official_identity().data)],
            "index": [], "course_dossiers": [thread.as_dict()]}
    raw = canonical(data)
    path = tmp_path / "SYNTHETIC-dossier.json"
    path.write_bytes(raw)
    reader = organization_capture_reader({"path": str(path), "sha256": sha256(raw).hexdigest()})
    assert reader.course_threads.catalogue() == [thread.summary()]
    observed = reader.inspect(thread.organization_id)
    assert observed["course_dossier"] == thread.as_dict()
    assert observed["canonical_admission"] == "NOT_GRANTED"
    with pytest.raises(ValueError):
        reader.course_threads.read({"organization_id": thread.organization_id, "dossier_sha256": "0" * 64})
    data["records"] = []
    path.write_bytes(canonical(data))
    with pytest.raises(ValueError):
        organization_capture_reader({"path": str(path), "sha256": sha256(canonical(data)).hexdigest()})


@pytest.mark.parametrize("mutation", ["organization", "title", "excerpt", "table", "unlinked", "fiction"])
def test_provider_cannot_substitute_identity_document_or_unmarked_construction(mutation):
    _, _, request = real_preparation()
    content = real_content(request)
    chapter = content["course_chapter"]
    if mutation == "organization":
        chapter["context"]["organization_id"] = "siren:000000000"
    elif mutation == "title":
        chapter["context"]["title"] = "Une autre organisation"
    elif mutation == "excerpt":
        chapter["documents"][-1]["text"] += " invention"
    elif mutation == "table":
        chapter["documents"][-1]["table"] = {"headers": ["Fait"], "rows": [["Inventé"]]}
    elif mutation == "unlinked":
        chapter["parts"][0]["document_ids"].remove("D3")
    else:
        chapter["documents"][0]["text"] = "Scène attribuée sans avertissement."
    with pytest.raises(ValueError):
        bind_p0_content(request, content)


def test_nominal_one_attempt_saved_reopened_and_both_actual_word_exports(tmp_path):
    _, service, prepared, _, resolver, transport = real_configuration(tmp_path)
    command = {"command_id": token_hex(16), "preparation_ref": prepared["preparation_ref"],
               "preparation_sha256": prepared["preparation_sha256"]}
    generated = service.execute("generate", command)
    assert transport.calls == resolver.calls == 1
    assert generated["state"] == "CANDIDATE"
    view = generated["view"]
    record = service.saved_source(view["production_ref"], view["version_ref"])
    assert record.p0_bundle.data["course_chapter"]["contract_id"] == REAL_CHAPTER
    saved = build_saved_application(tmp_path / "library", create=True, source=service.saved_source, word_profile="product-v7")
    saved.execute("save", body={"production_ref": record.production_ref, "version_ref": record.version_ref}, correlation="real.save")
    reopened = build_saved_application(tmp_path / "library", word_profile="product-v7")
    opened = reopened.execute("open", record.production_ref, record.version_ref, correlation="real.open")
    assert opened["record_sha256"] == record.sha256
    for kind in ("student", "correction"):
        export = reopened.execute("word", record.production_ref, record.version_ref, kind=kind, correlation="real.word")
        with ZipFile(BytesIO(export)) as docx:
            xml = docx.read("word/document.xml").decode()
        assert "https://example.org/SYNTHETIC-document" in xml and "SYNTHETIC FIXTURE" in xml
        assert dossier().fiction_notice in xml
        assert ("SENTINELLE_PROFESSEUR" in xml) == (kind == "correction")
    assert service.execute("generate", command) == generated
    with pytest.raises(ValueError):
        service.execute("generate", {**command, "command_id": token_hex(16)})
    assert transport.calls == 1


def test_absent_generation_authority_has_no_effect():
    service, prepared, _ = real_preparation()
    assert service.execute("generate", {"command_id": token_hex(16), "preparation_ref": prepared["preparation_ref"],
        "preparation_sha256": prepared["preparation_sha256"]})["state"] == "AUTHORIZATION_REQUIRED"


def admission_fixture(request, *, omit_public=False):
    ref = request["references"][0]
    primary = {"object_ref": ref["source_ref"], "passage_ref": ref["locator"],
        "version_or_checksum": ref["checksum_or_version"], "notion_ref": "notion:shared", "object_kind": "NOTION",
        "excerpt": request["evidence"][ref["evidence_id"]], "excerpt_truncated": False,
        "authority": "SYNTHETIC", "authority_basis": "SYNTHETIC", "provenance": {}, "source_status": {}}
    passages = [primary, *dossier().passages()]
    entries = []
    for p in passages[:1] if omit_public else passages:
        entry = {"notion_ref": p["notion_ref"], "source_ref": p["object_ref"], "object_kind": p["object_kind"],
            "locator": p["passage_ref"], "checksum_or_version": p["version_or_checksum"],
            "excerpt_sha256": sha256(p["excerpt"].encode()).hexdigest(), "provenance": p["provenance"],
            "source_status": p["source_status"], "available_authority": p["authority"], "authority_basis": p["authority_basis"]}
        entry["admission_scope_sha256"] = sha256(canonical(entry)).hexdigest()
        entries.append(entry)
    manifest = {"schema": "P0-SOURCE-ADMISSION-MANIFEST-1.0", "status": "NON_ADOPTE",
        "application_inventory_sha256": "1" * 64, "catalogue_sha256": "2" * 64,
        "source_scope_sha256": sha256(canonical(entries)).hexdigest(), "entries": entries, "exclusions": []}
    checksum = sha256(canonical(manifest)).hexdigest()
    query = ReadP0SourceAdmission(manifest, manifest_sha256=checksum, adopted_manifest_sha256=checksum,
                                owner_admission_sha256="3" * 64)
    return query, passages


def test_public_sources_require_their_own_exact_admission_not_just_catalogue_presence():
    _, _, request = real_preparation()
    resolution = request["context"]["institutional_resolution"]
    query, passages = admission_fixture(request)
    receipts = query.execute(request=request, passages=passages, resolution=resolution)
    assert len(receipts) == 3 and receipts[-1]["available_authority"] == "PUBLIC_DOCUMENTARY_PROPOSAL"
    missing, _ = admission_fixture(request, omit_public=True)
    with pytest.raises(ValueError, match="NOT_IN_ADOPTED_MANIFEST"):
        missing.execute(request=request, passages=passages, resolution=resolution)
    passages[-1]["excerpt"] += " changed"
    with pytest.raises(ValueError):
        query.execute(request=request, passages=passages, resolution=resolution)
