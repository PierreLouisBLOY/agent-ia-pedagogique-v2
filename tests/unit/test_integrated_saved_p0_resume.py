"""Local Application resume over synthetic saved records; no restored provider."""
from secrets import token_hex

import pytest

from backend.infrastructure.composition.factories.local_browser import build_saved_application
from backend.modules.pedagogical_context.contracts.dto.p0_context import P0Context
from backend.modules.pedagogical_design.contracts.dto.p0_production import P0Production
from backend.modules.work_orchestration.contracts.dto.p0_production_read_view import (
    P0ProductionReadView,
)
from backend.modules.work_orchestration.contracts.dto.saved_production import SavedProduction
from tests.integration.test_p0_creation_http import context
from tests.support.p0_generation_double import P0GenerationDouble
from tests.unit.test_p0_agentic_routing import candidate, identity
from tests.unit.test_p0_creation_contract import service


def stored_parent():
    app = service(P0GenerationDouble())
    view, _ = candidate(app)
    return app.saved_source(view["production_ref"], view["version_ref"])


def resume_with(records):
    app = service(None)
    app.saved_reader = lambda p, v: records[v]
    return app


def test_restart_resume_revision_preserves_parent_and_quarantines_authority():
    record = stored_parent()
    app = resume_with({record.version_ref: record})
    view = app.read(record.production_ref, record.version_ref)
    assert app.saved_source(record.production_ref, record.version_ref).sha256 == record.sha256
    result = app.execute("revise", {"command_id": token_hex(16), **identity(view),
                                   "edits": {"title": "Modification locale explicite"}})
    assert result["provider_attempts"] == 0
    assert result["quality"]["sources"] == "RESERVE"
    assert result["quality"]["source_reason"] == "HISTORICAL_EVIDENCE_NOT_REVALIDATED"
    child = app.saved_source(record.production_ref, result["view"]["version_ref"])
    assert child.data["bundle"]["lineage"]["parent_version_ref"] == record.version_ref
    assert child.data["bundle"]["references"] == record.data["bundle"]["references"]
    assert child.data["reviews"] == child.data["validations"] == ()
    assert app.saved_source(record.production_ref, record.version_ref).sha256 == record.sha256
    for active in (view, result["view"]):
        with pytest.raises(ValueError, match="P0_REOPENED_REVIEW_REQUIRES_FRESH_EVIDENCE"):
            app.execute("review", {"command_id": token_hex(16), **identity(active)})
    again = resume_with({record.version_ref: record, child.version_ref: child})
    assert again.read(child.production_ref, child.version_ref) == result["view"]
    assert again.saved_source(record.production_ref, record.version_ref).sha256 == record.sha256


@pytest.mark.parametrize("mutation", ("documentary", "hash", "production", "missing_parent"))
def test_invalid_resume_is_atomic(mutation):
    record = stored_parent()
    data = record.mutable_copy()
    command = identity(data["view"])
    if mutation == "documentary":
        data["origin"] = "IMPORTED_DOCUMENTARY"
        data["provenance"] = {"SOURCE_SHA256": "a" * 64}
        data["reviews"] = data["validations"] = []
        record = SavedProduction(data)
    if mutation == "hash":
        command["bundle_sha256"] = "0" * 64
    if mutation == "production":
        command["production_ref"] = "prod:" + "f" * 32
    if mutation == "missing_parent":
        app_before = service(P0GenerationDouble())
        view, _ = candidate(app_before)
        result = app_before.execute("revise", {"command_id": token_hex(16), **identity(view),
                                             "edits": {"title": "Enfant"}})
        record = app_before.saved_source(view["production_ref"], result["view"]["version_ref"])
        command = identity(result["view"])
    app = resume_with({record.version_ref: record})
    with pytest.raises((ValueError, KeyError)):
        app.execute("revise", {"command_id": token_hex(16), **command, "edits": {"title": "Refus"}})
    assert app.records == app.plans == app.resumed == {}


@pytest.mark.parametrize("level,kind,mode", (
    ("FIRST_STMG", "COURSE", None),
    ("BTS_CG_YEAR_1", "EXERCISE", None),
    ("FINAL_STMG", "QUESTION_SET", "OPEN_QUESTIONS"),
    ("FIRST_STMG", "QUESTION_SET", "QCM"),
    ("FINAL_STMG", "QUESTION_SET", "QUIZ"),
    ("BTS_CG_YEAR_2", "ASSESSMENT", None),
))
def test_application_restart_local_edit_save_and_native_export_all_families(tmp_path, level, kind, mode):
    original = service(P0GenerationDouble())
    prepared = original.execute("prepare", {"command_id": token_hex(16),
        "context": context(level, kind, mode), "reference": {}})
    view = original.execute("generate", {"command_id": token_hex(16),
        "preparation_ref": prepared["preparation_ref"], "preparation_sha256": prepared["preparation_sha256"]})["view"]
    parent = original.saved_source(view["production_ref"], view["version_ref"])
    saved = build_saved_application(tmp_path / "library", create=True, source=original.saved_source,
                                    word_profile="product-v7")
    refs = {"production_ref": parent.production_ref, "version_ref": parent.version_ref}
    saved.execute("save", body=refs, correlation="unit.initial")
    # Full Application store read after discarding the first session.
    resumed = service(None)
    resumed.saved_reader = saved.read_local_p0
    opened = resumed.read(parent.production_ref, parent.version_ref)
    child_view = resumed.execute("revise", {"command_id": token_hex(16), **identity(opened),
        "edits": {"title": "Nouvelle consigne locale — variante " + mode if mode else "Nouvelle consigne locale — " + kind}})["view"]
    saved.source = resumed.saved_source
    saved.execute("save", body={"production_ref": parent.production_ref, "version_ref": child_view["version_ref"]}, correlation="unit.child")
    reopened = build_saved_application(tmp_path / "library", word_profile="product-v7")
    exact = reopened.read_local_p0(parent.production_ref, child_view["version_ref"])
    assert exact.data["bundle"]["lineage"]["parent_version_ref"] == parent.version_ref
    assert reopened.read_local_p0(parent.production_ref, parent.version_ref).sha256 == parent.sha256
    assert "HISTORICAL_EVIDENCE_NOT_REVALIDATED" in exact.data["reservations"]
    import io
    import zipfile
    publics = ("student", "correction", "marking") if kind == "ASSESSMENT" else ("student", "correction") if kind != "COURSE" else ("student",)
    for public in publics:
        raw = reopened.execute("word", exact.production_ref, exact.version_ref, kind=public, correlation="unit.export")
        with zipfile.ZipFile(io.BytesIO(raw)) as document:
            xml = document.read("word/document.xml")
            assert b"TEACHER_ONLY_SENTINEL" not in xml if public == "student" else True
            assert b"Nouvelle consigne locale" in xml


def test_local_revision_never_truncates_reservations():
    parent = stored_parent()
    data = parent.mutable_copy()
    data["reservations"] = ["Réserve historique " + str(i) for i in range(16)]
    parent = SavedProduction(data)
    app = resume_with({parent.version_ref: parent})
    child = app.execute("revise", {"command_id": token_hex(16), **identity(app.read(parent.production_ref,parent.version_ref)),
                                 "edits": {"title": "Titre local"}})
    with pytest.raises(ValueError, match="P0_SAVED_RESERVATIONS_FULL"):
        app.saved_source(parent.production_ref, child["view"]["version_ref"])
    assert app.saved_source(parent.production_ref, parent.version_ref).sha256 == parent.sha256


@pytest.mark.parametrize("mutation", ("source_request_id", "conversation_id", "evidence_set_ref", "context", "references"))
@pytest.mark.parametrize("parent_in_memory", (False, True))
def test_saved_chain_rejects_unwitnessed_origin_change_atomically(mutation, parent_in_memory):
    original = service(P0GenerationDouble())
    view, _ = candidate(original)
    parent = original.saved_source(view["production_ref"], view["version_ref"])
    child_view = original.execute("revise", {"command_id": token_hex(16), **identity(view),
        "edits": {"title": "Enfant légitime avant substitution"}})["view"]
    child_data = original.saved_source(parent.production_ref, child_view["version_ref"]).mutable_copy()
    data = child_data["bundle"]
    if mutation == "context":
        data["context"]["difficulty"] = "ADVANCED"
        changed = P0Context(data["context"])
        data["context_sha256"] = data["lineage"]["context_sha256"] = changed.sha256
    elif mutation == "references":
        data["references"][0]["checksum_or_version"] += "-SUBSTITUTION"
    else:
        prefix = {"source_request_id": "req", "conversation_id": "conv", "evidence_set_ref": "evidence"}[mutation]
        data["lineage"][mutation] = prefix + ":" + "f" * 32
    changed = P0Production(data)
    child_data.update(bundle=changed.mutable_copy(), view=P0ProductionReadView.from_bundle(changed).data,
                      reviews=[], validations=[])
    substituted = SavedProduction(child_data)  # Individually valid, relation is invalid.
    app = resume_with({parent.version_ref: parent, substituted.version_ref: substituted})
    if parent_in_memory:
        app.read(parent.production_ref, parent.version_ref)
    before = dict(app.records)
    with pytest.raises(ValueError, match="P0_SAVED_LINEAGE_BINDING"):
        app.read(parent.production_ref, substituted.version_ref)
    assert app.records == before and substituted.version_ref not in app.plans
    assert parent.sha256 == original.saved_source(parent.production_ref, parent.version_ref).sha256
