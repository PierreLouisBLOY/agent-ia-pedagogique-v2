"""Separate synthetic library via the actual manual launcher; no provider/network secrets."""
import copy
import io
import json
import zipfile
from hashlib import sha256
from secrets import token_hex

import pytest

from backend.infrastructure.composition.factories.documentary_course_selection import (
    build_documentary_course_selection,
)
from backend.infrastructure.composition.factories.documentary_library import (
    build_documentary_library,
)
from backend.modules.pedagogical_context.contracts.dto.real_course_thread import RealCourseThread
from backend.modules.pedagogical_design.contracts.dto.assessment_bundle import as_plain
from tests import normal_on_323a_fixture as f
from tests.support.progressive_real_fixture import progressive_real_fixture
from tests.test_documentary_library_separate import archive_fixture
from tests.test_manual_provider_tests import Control, configuration, running
from tests.test_normal_on_323a import call, terminal, text
from tests.unit.test_course_notion_contract import notion_content, notion_preparation


def library(tmp_path):
    path, _ = archive_fixture(tmp_path)
    with zipfile.ZipFile(path) as z:
        files = {n.rsplit("/", 1)[-1]: z.read(n) for n in z.namelist()}
    name = "05_MANIFESTE_SOURCES_POUR_V2.json"
    manifest = json.loads(files[name])
    manifest["created_on"] = "2026-10-29"
    for d in manifest["documents"]:
        d["rights_policy"] = "SYNTHETIC rights, no third-party licence inferred"
    for source in manifest["sources"]:
        source.update(title="SYNTHETIC primary source", consulted_on="2026-10-29", rights_status="SYNTHETIC")
    files[name] = json.dumps(manifest, ensure_ascii=False).encode()
    files["08_MANIFESTE_SHA256.json"] = json.dumps({"count": len(files) - 1, "files": [
        {"filename": n, "bytes": len(raw), "sha256": sha256(raw).hexdigest()}
        for n, raw in files.items() if n != "08_MANIFESTE_SHA256.json"]}).encode()
    with zipfile.ZipFile(path, "w") as z:
        for n, raw in files.items():
            z.writestr("SYNTHETIC/" + n, raw)
    archive = sha256(path.read_bytes()).hexdigest()
    db = tmp_path / "SYNTHETIC-documentary.sqlite"
    app = build_documentary_library(database=db, data_root=tmp_path, archive=path, archive_sha256=archive)
    imported = app.execute("import")
    descriptor = {"database": str(db), "data_root": str(tmp_path), "database_sha256": sha256(db.read_bytes()).hexdigest(),
        "archive_sha256": archive, "snapshot_sha256": imported["snapshot_sha256"]}
    return descriptor, build_documentary_course_selection(descriptor)


def choice(descriptor, organization="DECATHLON", ids=None):
    return {"organization_id": organization, "document_ids": ["D01"] if ids is None else ids,
        "archive_sha256": descriptor["archive_sha256"], "snapshot_sha256": descriptor["snapshot_sha256"]}


def preparation(selection, selected):
    service, _, prior = notion_preparation()
    service.documentary_selection = selection.select
    service.course_thread_reader = selection.read
    context = copy.deepcopy(prior["context"])
    context["institutional_resolution"] = None
    prepared = service.execute("prepare", {"command_id": token_hex(16), "context": context,
        "reference": {"notion_id": "notion:shared", "passage_ref": "unit:passage"}, "documentary_selection": selected})
    return service, prepared, as_plain(service.prepared[prepared["preparation_ref"]])


def content(dispatch, thread):
    proposed = notion_content(dispatch)
    chapter = proposed["course_chapter"]
    chapter["context"].update(organization_id=thread.organization_id, title=thread.label)
    chapter["documents"][0]["text"] = thread.fiction_notice + " " + chapter["documents"][0]["text"]
    ref = thread.references()[1]
    chapter["documents"].append({"id": "D3", "title": "Synthèse locale SYNTHETIC", "function": "REFERENCE",
        "text": thread.evidence()[ref["evidence_id"]], "table": None,
        "provenance": {"kind": "SUPPLIED_REFERENCE", "evidence_id": ref["evidence_id"]}})
    chapter["parts"][0]["document_ids"].append("D3")
    return proposed


def test_application_exact_selection_classification_and_no_authority(tmp_path):
    descriptor, selected = library(tmp_path)
    before = open(descriptor["database"], "rb").read()
    catalogue = selected.catalogue()
    assert len(catalogue["organizations"]) == 2 and len(catalogue["documents"]) == 2
    doc = selected.inspect("D01")
    thread = RealCourseThread(selected.select(choice(descriptor)))
    assert thread.source_rows()[1]["citations"] == doc["sources"]
    assert thread.source_rows()[1]["origin"] == doc["document"]["origin"]
    assert "NOT PRIMARY QUOTATION" in thread.source_rows()[1]["excerpt"]
    assert thread.passages()[1]["authority"] == "LOCAL_PEDAGOGICAL_SYNTHESIS_NOT_ADMITTED"
    assert thread.data["authority"]["generation_right"] == "NONE"
    assert selected.read({"organization_id": thread.organization_id, "dossier_sha256": thread.sha256}) == thread.as_dict()
    service, prepared, _ = preparation(selected, choice(descriptor))
    assert prepared["provider_attempts"] == 0 and len(prepared["references"]) == 3
    assert service.execute("generate", {"command_id": token_hex(16), "preparation_ref": prepared["preparation_ref"],
        "preparation_sha256": prepared["preparation_sha256"]})["state"] == "AUTHORIZATION_REQUIRED"
    assert open(descriptor["database"], "rb").read() == before


@pytest.mark.parametrize("mutation", ["mixed", "foreign", "too_many", "duplicate", "empty", "snapshot", "archive"])
def test_selection_refusals(tmp_path, mutation):
    descriptor, selected = library(tmp_path)
    value = choice(descriptor)
    if mutation == "mixed":
        value["document_ids"] = ["D01", "O01"]
    if mutation == "foreign":
        value["organization_id"] = "FOREIGN"
    if mutation == "too_many":
        value["document_ids"] = ["D" + str(i) for i in range(7)]
    if mutation == "duplicate":
        value["document_ids"] = ["D01", "D01"]
    if mutation == "empty":
        value["document_ids"] = []
    if mutation == "snapshot":
        value["snapshot_sha256"] = "0" * 64
    if mutation == "archive":
        value["archive_sha256"] = "0" * 64
    with pytest.raises(ValueError):
        selected.select(value)


@pytest.mark.parametrize("pin", ["database_sha256", "snapshot_sha256", "archive_sha256"])
def test_changed_binding_refused(tmp_path, pin):
    descriptor, _ = library(tmp_path)
    descriptor[pin] = "0" * 64
    with pytest.raises(ValueError):
        build_documentary_course_selection(descriptor)


def test_revalidation_and_changed_selection_refused_before_any_effect(tmp_path):
    from types import SimpleNamespace

    from backend.adapters.outbound.generation.openai.p0_manual_tests import ManualTestGeneration
    from backend.infrastructure.config.secrets.provider import ProviderCredentialRef

    descriptor, selection = library(tmp_path)
    _, _, dispatch = preparation(selection, choice(descriptor))

    def forbidden(*_args, **_kwargs):
        raise AssertionError("NO_SECRET_OR_TRANSPORT")

    registry = tmp_path / "SYNTHETIC-registry"
    registry.mkdir()
    adapter = ManualTestGeneration(root=registry, resolver=SimpleNamespace(resolve=forbidden),
        credential_ref=ProviderCredentialRef("openai.p0.manual-tests"), transport=SimpleNamespace(build=forbidden))
    adapter.course_thread_reader = selection.read
    adapter.wire(dispatch)
    wrong = copy.deepcopy(dispatch)
    wrong["evidence"][wrong["references"][-1]["evidence_id"]] += " substituted"
    with pytest.raises(ValueError):
        adapter.prepare_transport(wrong)
    selection.database_sha256 = "0" * 64
    with pytest.raises(ValueError, match="DOCUMENTARY_DATABASE_CHANGED"):
        adapter.prepare_transport(dispatch)
    assert adapter.budget.snapshot()["reserved_usd"] == "0"


def test_documentary_working_memory_is_bounded_without_changing_full_proof_or_guard(tmp_path):
    from backend.modules.pedagogical_context.contracts.dto.p0_context import P0Context
    from backend.modules.pedagogical_design.contracts.dto.assessment_bundle import (
        encoded,
        fingerprint,
    )
    from backend.modules.work_orchestration.application.services.p0_agentic import evidence_pack

    descriptor, selection = library(tmp_path)
    _, _, dispatch = preparation(selection, choice(descriptor))
    context = copy.deepcopy(dispatch["context"])
    context["institutional_resolution"]["document_provenance"] = {"synthetic_lineage_proof": "SYNTHETIC" * 4000}
    before = copy.deepcopy(context)
    pack = evidence_pack(P0Context(context), dispatch["references"], dispatch["evidence"])
    assert context == before
    assert len(encoded(pack)) <= 32768
    assert pack["institutional_resolution"]["contract_id"] == "BOUNDED-INSTITUTIONAL-EVIDENCE-1.0"
    assert pack["documentary_selection"]["full_resolution_sha256"] == fingerprint(context["institutional_resolution"])
    assert pack["documentary_selection"]["dossier_sha256"] == RealCourseThread(context["institutional_resolution"]["course_thread"]).sha256
    assert {p["evidence_id"]: p["text"] for p in pack["passages"]} == dispatch["evidence"]
    huge = copy.deepcopy(dispatch["evidence"])
    huge[dispatch["references"][0]["evidence_id"]] = "x" * 16001
    with pytest.raises(ValueError, match="P0_EVIDENCE_PACK_SIZE"):
        evidence_pack(P0Context(context), dispatch["references"], huge)
    _, _, legacy = notion_preparation()
    old = evidence_pack(P0Context(legacy["context"]), legacy["references"], legacy["evidence"])
    assert "documentary_selection" not in old
    assert old["institutional_resolution"] == legacy["context"]["institutional_resolution"]


def test_true_launcher_http_preparation_one_fake_attempt_save_reopen_word(tmp_path, monkeypatch):
    root = tmp_path / "normal-launcher"
    config = configuration(root)
    descriptor, selection = library(root)
    args = ["--documentary-library", descriptor["database"], "--documentary-data-root", descriptor["data_root"],
        "--documentary-database-sha256", descriptor["database_sha256"], "--documentary-archive-sha256", descriptor["archive_sha256"],
        "--documentary-snapshot-sha256", descriptor["snapshot_sha256"]]
    control = Control()
    with running(root, monkeypatch, control, existing=config, extra_args=args) as (port, _):
        status, result = call(port, "GET", "/api/v2/p0")
        assert status == 200, result
        meta = result["data"]
        assert meta["documentary_library"] == selection.catalogue()
        assert call(port, "GET", "/api/v2/p0/documentary-library/D01")[1]["data"] == selection.inspect("D01")
        assert call(port, "POST", "/api/v2/p0/documentary-library/D01", {}, meta["transport_nonce"])[0] != 200
        assert f.request(port, "GET", "/assets/documentary-library.js")[0] == 200
        assert "documentary-library.js" in f.request(port, "GET", "/")[1].decode()
        _, _, example = notion_preparation()
        context = copy.deepcopy(example["context"])
        context["institutional_resolution"] = None
        status, result = call(port, "POST", "/api/v2/p0/prepare", {"command_id": token_hex(16), "context": context,
            "reference": {"notion_id": "notion:shared", "passage_ref": f.SOURCE["passage_ref"]},
            "documentary_selection": choice(descriptor)}, meta["transport_nonce"])
        assert status == 200, result
        prepared = result["data"]
        thread = RealCourseThread(prepared["context"]["institutional_resolution"]["course_thread"])
        dispatch = {"context": prepared["context"], "references": prepared["references"],
            "evidence": {prepared["references"][0]["evidence_id"]: f.SOURCE_TEXT, **thread.evidence()}}
        monkeypatch.setattr(f, "CONTENT", progressive_real_fixture(content(dispatch, thread)))
        assert control.calls == control.builds == 0
        assert meta["manual_test_session"]["reserved_usd"] == "0"
        command = {"command_id": token_hex(16), "preparation_ref": prepared["preparation_ref"],
            "preparation_sha256": prepared["preparation_sha256"]}
        assert call(port, "POST", "/api/v2/p0/generate", command, meta["transport_nonce"])[0] == 202
        done = terminal(port, command["command_id"])
        assert done["state"] == "LOCAL_COMMAND_COMPLETED", done
        assert done["phase"] == "APPLICATION_SAVED"
        view = done["result"]["view"]
        base = "/api/v2/productions/" + view["production_ref"] + "/versions/" + view["version_ref"]
        assert call(port, "GET", base + "/saved")[0] == 200
        for kind in ("student", "correction"):
            status, raw = f.request(port, "GET", base + "/word/" + kind)
            assert status == 200
            rendered = text(raw)
            assert "https://example.org/synthetic-dec" in rendered and "synthèse pédagogique locale" in rendered
            assert ("SENTINELLE_PROFESSEUR" in rendered) == (kind == "correction")
            with zipfile.ZipFile(io.BytesIO(raw)) as z:
                assert z.testzip() is None
        assert call(port, "POST", "/api/v2/p0/generate", command, meta["transport_nonce"])[0] == 202
        assert control.calls == control.builds == 1 and control.prompt_calls == 0
