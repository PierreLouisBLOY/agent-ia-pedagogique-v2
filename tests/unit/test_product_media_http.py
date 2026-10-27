"""Local Application/HTTP mechanics with synthetic records, not source admission."""
import copy
import json

import pytest

from backend.adapters.inbound.api.p0_creation import P0CreationEndpoint
from backend.adapters.inbound.api.production_media import MEDIA_ROUTE, ProductionMediaEndpoint
from backend.adapters.inbound.api.saved_production import (
    MEDIA_EXPORT_REFUSAL_CONTRACT,
    R4_HTTP_CONTRACT,
    SavedProductionEndpoint,
    r4_error,
)
from backend.adapters.outbound.export.product_word import ProductWordWriter
from backend.infrastructure.composition.factories.p0_creation import build_p0_media
from backend.modules.materialization_export.application.commands.export_saved import (
    ExportSavedCommand,
)
from backend.modules.work_orchestration.application.services.p0_creation import P0CreationService
from backend.modules.work_orchestration.application.services.production_media import (
    ProductionMediaService,
)
from backend.modules.work_orchestration.contracts.dto.saved_production import SavedProduction
from tests.unit.test_product_media import FAMILIES, media_fixture


def request(parent, proposal=None, command="c" * 32):
    selection = ({"mode": "NO_MEDIA", "reason": "Les tableaux natifs suffisent à ce travail."}
                 if proposal is None else {"mode": "LOCAL_DIAGRAM", "entries": [{
                     k: proposal[k] for k in ("brief", "required", "dependency_refs")}]})
    return {"command_id": command, "production_ref": parent.production_ref,
            "version_ref": parent.version_ref, "bundle_sha256": parent.p0_bundle.sha256,
            "selection": selection}


def local_service(parent, inbound):
    service = P0CreationService(lambda selection: pytest.fail("No retrieval of historical source"))

    def read(p, v):
        if (p, v) != (parent.production_ref, parent.version_ref):
            raise ValueError("P0_NOT_FOUND")
        return parent

    service.saved_reader = read
    media = ProductionMediaService(service.saved_source, inbound.execute, service.publish_local_child)
    return service, media


@pytest.mark.parametrize("kind,mode", FAMILIES)
def test_reopened_child_is_published_with_exact_lineage_and_source_reserve(kind, mode):
    parent, proposal, inbound = media_fixture(kind, mode)
    raw = parent.mutable_copy()
    raw.update(provenance={"ORIGINAL_WITNESS": "a" * 64}, reservations=["Original reservation retained."])
    parent = SavedProduction(raw)
    before = parent.mutable_copy()
    lifecycle, media = local_service(parent, inbound)
    result = media.execute(request(parent, proposal))
    view = result["view"]
    child = lifecycle.saved_source(parent.production_ref, view["version_ref"])
    assert child.p0_bundle.data["lineage"] == {**parent.p0_bundle.data["lineage"], "parent_version_ref": parent.version_ref}
    assert parent.mutable_copy() == before
    assert child.data["provenance"]["ORIGINAL_WITNESS"] == "a" * 64
    assert "Original reservation retained." in child.data["reservations"]
    assert "HISTORICAL_EVIDENCE_NOT_REVALIDATED" in child.data["reservations"]
    assert child.sha256 == result["record_sha256"]
    assert result["quality"]["sources"] == "RESERVE" and result["active_authority"] == "NONE_RESTORED"
    assert result["validation"]["dispatch_permitted"] is False
    assert lifecycle.evidence[child.version_ref] == {} and child.version_ref in lifecycle.local_reopened
    assert lifecycle.read(child.production_ref, child.version_ref)["media_assets"] == view["media_assets"]
    assert media.execute(request(parent, proposal)) == result
    assert len(lifecycle.records) == 2 and result["provider_attempts"] == 0


def test_no_media_zero_assets_and_substituted_command_is_refused():
    parent, _, inbound = media_fixture()
    lifecycle, media = local_service(parent, inbound)
    body = request(parent)
    result = media.execute(body)
    assert result["view"]["media_assets"] == []
    assert lifecycle.saved_source(parent.production_ref, result["view"]["version_ref"]).p0_bundle.data["media_plan"]["no_media_reason"] == body["selection"]["reason"]
    mutated = copy.deepcopy(body)
    mutated["selection"]["reason"] += " Substitution."
    with pytest.raises(ValueError, match="P0_MEDIA_IDEMPOTENCY_CONFLICT"):
        media.execute(mutated)


@pytest.mark.parametrize("mutation", ["bundle", "version", "production", "bytes", "url", "path", "imported", "unknown_dependency", "capability", "student_answer"])
def test_closed_media_request_refuses_substitution_or_unauthorised_content(mutation):
    parent, proposal, inbound = media_fixture()
    lifecycle, media = local_service(parent, inbound)
    body = request(parent, proposal)
    entry = body["selection"]["entries"][0]
    if mutation == "bundle":
        body["bundle_sha256"] = "0" * 64
    elif mutation == "version":
        body["version_ref"] = "ver:" + "8" * 32
    elif mutation == "production":
        body["production_ref"] = "prod:" + "8" * 32
    elif mutation in {"bytes", "url", "path"}:
        entry[mutation] = "arbitrary-input"
    elif mutation == "imported":
        entry["brief"].update(source_policy="USER_SUPPLIED", visual_type="DIAGRAM", diagram=None)
    elif mutation == "unknown_dependency":
        entry["dependency_refs"] = ["section:UNKNOWN"]
    elif mutation == "capability":
        entry["brief"]["institutional_capability_ref"] = "capacity:wrong"
    else:
        entry["brief"]["alt_text"] = parent.p0_bundle.data["corrections"][0]["expected_answer"]
    with pytest.raises(ValueError):
        media.execute(body)
    assert len(lifecycle.records) <= 1


@pytest.mark.parametrize("field", ["provenance", "reservations"])
def test_reopened_parent_metadata_is_never_truncated_to_fit(field):
    parent, _, inbound = media_fixture()
    raw = parent.mutable_copy()
    raw[field] = ({"WITNESS_" + str(n): "a" * 64 for n in range(16)}
                  if field == "provenance" else ["Reservation " + str(n) for n in range(16)])
    full = SavedProduction(raw)
    lifecycle, media = local_service(full, inbound)
    with pytest.raises(ValueError, match="PRODUCTION_MEDIA_.*_FULL"):
        media.execute(request(full))
    assert full.mutable_copy() == raw and len(lifecycle.records) == 1


def test_rich_course_remains_explicitly_on_its_separate_media_path():
    from tests.unit.test_course_chapter import child_fixture

    _, rich = child_fixture()
    _, _, inbound = media_fixture()
    with pytest.raises(ValueError, match="PRODUCTION_MEDIA_LOCAL_P0_REQUIRED"):
        inbound.execute(rich, [], no_media_reason="Aucun média additionnel.")


def test_no_media_cannot_silently_drop_a_parent_required_asset():
    parent, proposal, inbound = media_fixture()
    child = inbound.execute(parent, [proposal])
    with pytest.raises(ValueError, match="PRODUCTION_MEDIA_REQUIRED_OMISSION_REJECTED"):
        inbound.execute(child, [], no_media_reason="Omission demandée.")


def test_uncertain_worker_cannot_be_replayed_and_does_not_publish():
    parent, proposal, inbound = media_fixture()
    lifecycle, _ = local_service(parent, inbound)
    calls = []

    def unavailable(*args, **kwargs):
        calls.append(1)
        raise RuntimeError("Private exception text never leaves boundary")

    media = ProductionMediaService(lifecycle.saved_source, unavailable, lifecycle.publish_local_child)
    body = request(parent, proposal)
    with pytest.raises(ValueError, match="P0_MEDIA_OUTCOME_UNKNOWN"):
        media.execute(body)
    assert media.execute(body) == {"state": "OUTCOME_UNKNOWN", "retry": 0}
    assert calls == [1] and len(lifecycle.records) == 1


@pytest.mark.parametrize("raw", [b'{"command_id":"a","command_id":"b"}', b'[]', b'{}', b'{"path":"C:/private"}', b'x' * (80 * 1024 + 1)],
                         ids=["duplicate", "array", "empty", "path", "oversize"])
def test_media_endpoint_refuses_duplicate_extra_or_unbounded_payload(raw):
    # {} and path-only payloads are parsed then refused by a real service.
    parent, _, inbound = media_fixture()
    _, service = local_service(parent, inbound)
    endpoint = ProductionMediaEndpoint(service.execute)
    status, _, response, _ = endpoint.respond("POST", MEDIA_ROUTE, raw, "synthetic.media")
    assert status == 409 and b"error" in response and b"private" not in response


def test_composed_media_endpoint_has_no_fallback_and_uses_existing_p0_delegate():
    parent, proposal, inbound = media_fixture()
    lifecycle, _ = local_service(parent, inbound)
    media = build_p0_media(lifecycle)
    endpoint = P0CreationEndpoint(lifecycle.execute, lifecycle.read, [], nonce="synthetic-nonce", media_endpoint=media)
    raw = json.dumps(request(parent, proposal)).encode()
    status, _, response, template = endpoint.respond("POST", MEDIA_ROUTE, raw, "synthetic.media")
    result = json.loads(response)["data"]
    assert status == 200 and template == MEDIA_ROUTE and result["provider_attempts"] == 0
    assert endpoint.respond("POST", MEDIA_ROUTE + "?path=bad", raw, "synthetic.media")[0] == 409
    disabled = P0CreationEndpoint(lifecycle.execute, lifecycle.read, [], nonce="synthetic-nonce")
    assert b"P0_MEDIA_NOT_ENABLED" in disabled.respond("POST", MEDIA_ROUTE, raw, "synthetic.media")[2]


def test_changed_media_dependency_error_remains_precise_on_p0_revision_http():
    parent, proposal, inbound = media_fixture()
    lifecycle, media = local_service(parent, inbound)
    result = media.execute(request(parent, proposal))
    child = lifecycle.saved_source(parent.production_ref, result["view"]["version_ref"])
    questions = child.p0_bundle.mutable_copy()["questions"]
    questions[0]["prompt"] += " Modification qui exige une nouvelle décision média."
    body = {"command_id": "f" * 32, "production_ref": child.production_ref,
            "version_ref": child.version_ref, "bundle_sha256": child.p0_bundle.sha256,
            "edits": {"questions": questions}}
    endpoint = P0CreationEndpoint(lifecycle.execute, lifecycle.read, [], nonce="synthetic-nonce")
    status, _, raw, _ = endpoint.respond("POST", "/api/v2/p0/revise", json.dumps(body).encode(), "media.stale")
    assert status == 409 and json.loads(raw)["error"]["code"] == "PRODUCTION_MEDIA_DEPENDENCY_STALE"
    assert lifecycle.saved_source(child.production_ref, child.version_ref).sha256 == child.sha256


@pytest.mark.parametrize("with_media", [False, True])
def test_http_title_revision_keeps_exact_asset_or_justified_no_media(with_media):
    parent, proposal, inbound = media_fixture()
    lifecycle, media = local_service(parent, inbound)
    result = media.execute(request(parent, proposal if with_media else None))
    before = lifecycle.saved_source(parent.production_ref, result["view"]["version_ref"])
    body = {"command_id": "f" * 32, "production_ref": before.production_ref,
            "version_ref": before.version_ref, "bundle_sha256": before.p0_bundle.sha256,
            "edits": {"title": "Titre révisé localement"}}
    endpoint = P0CreationEndpoint(lifecycle.execute, lifecycle.read, [], nonce="synthetic-nonce")
    status, _, raw, _ = endpoint.respond("POST", "/api/v2/p0/revise", json.dumps(body).encode(), "media.title")
    assert status == 200
    revised = json.loads(raw)["data"]
    assert revised["view"]["media_assets"] == result["view"]["media_assets"]
    assert revised["quality"]["sources"] == "RESERVE" and revised["provider_attempts"] == 0
    assert lifecycle.saved_source(before.production_ref, before.version_ref).sha256 == before.sha256
    child = lifecycle.saved_source(before.production_ref, revised["view"]["version_ref"])
    assert child.p0_bundle.data["media_plan"]["no_media_reason"] == before.p0_bundle.data["media_plan"]["no_media_reason"]


def test_p0_endpoint_does_not_expose_unbounded_or_infrastructure_exception_text():
    def unavailable(operation, body):
        raise ValueError("COURSE_private/path/and context that cannot be public")

    endpoint = P0CreationEndpoint(unavailable, lambda p, v: {}, [], nonce="synthetic-nonce")
    status, _, raw, _ = endpoint.respond("POST", "/api/v2/p0/revise", b"{}", "media.private")
    assert status == 409 and json.loads(raw)["error"]["code"] == "P0_REQUEST_REJECTED"
    assert b"private" not in raw.replace(b"media.private", b"")


def test_reopened_media_child_save_restart_and_docx_keep_exact_asset(tmp_path):
    from backend.infrastructure.composition.factories.local_browser import build_saved_application

    parent, proposal, inbound = media_fixture()
    first = build_saved_application(tmp_path / "library", create=True,
        source=lambda p, v: parent, word_profile="product-v7")
    first.execute("save", body={"production_ref": parent.production_ref, "version_ref": parent.version_ref}, correlation="media.parent")
    lifecycle = P0CreationService(lambda selection: pytest.fail("No retrieval"))
    lifecycle.saved_reader = first.read_local_p0
    endpoint = build_p0_media(lifecycle)
    result = json.loads(endpoint.respond("POST", MEDIA_ROUTE, json.dumps(request(parent, proposal)).encode(), "media.local")[2])["data"]
    version = result["view"]["version_ref"]
    child = lifecycle.saved_source(parent.production_ref, version)
    saved = build_saved_application(tmp_path / "library", source=lifecycle.saved_source, word_profile="product-v7")
    saved.execute("save", body={"production_ref": child.production_ref, "version_ref": version}, correlation="media.child")
    before = saved.execute("word", child.production_ref, version, kind="student", correlation="media.before")
    restarted = build_saved_application(tmp_path / "library", word_profile="product-v7")
    opened = restarted.execute("open", child.production_ref, version, correlation="media.restart")
    assert opened["record_sha256"] == result["record_sha256"]
    assert restarted.execute("word", child.production_ref, version, kind="student", correlation="media.after") == before
    assert restarted.read_local_p0(child.production_ref, version).p0_bundle.student_projection()["media_assets"] == result["view"]["media_assets"]


@pytest.mark.parametrize("operation", ["preview", "word"])
def test_required_missing_export_is_precise_http_refusal_from_real_application(operation):
    parent, proposal, inbound = media_fixture()
    proposal.update(materialize=False, omission_reason="Pièce locale encore indisponible.")
    proposal["brief"]["teacher_visibility"] = False
    child = inbound.execute(parent, [proposal])
    before = child.mutable_copy()
    exporter = ExportSavedCommand(ProductWordWriter(), product_projection=True)

    def invoke(op, production, version, **kwargs):
        assert (production, version) == (child.production_ref, child.version_ref)
        if op == "word":
            return exporter.execute(child, kwargs["kind"])
        return exporter.preview(child, kwargs["kind"]).as_dict()

    endpoint = SavedProductionEndpoint(invoke, nonce="synthetic-nonce")
    status, _, raw = endpoint.respond(operation, child.production_ref, child.version_ref,
                                      "student", b"{}", "media.export")
    result = json.loads(raw)
    assert status == 409 and result["error"] == {
        "code": "PRODUCTION_MEDIA_REQUIRED_MISSING", "visual_ref": proposal["brief"]["visual_id"]}
    assert result["meta"]["contract_id"] == MEDIA_EXPORT_REFUSAL_CONTRACT
    teacher_status, _, _ = endpoint.respond(operation, child.production_ref, child.version_ref,
                                            "correction", b"{}", "media.teacher")
    assert teacher_status == 200 and child.mutable_copy() == before


@pytest.mark.parametrize("teacher_only", [False, True])
def test_reopened_application_teacher_media_is_separate_from_student_view(teacher_only):
    parent, proposal, inbound = media_fixture()
    proposal["brief"].update(student_visibility=not teacher_only, teacher_visibility=teacher_only)
    lifecycle, media = local_service(parent, inbound)
    result = media.execute(request(parent, proposal))
    version = result["view"]["version_ref"]
    teacher = lifecycle.read(parent.production_ref, version, teacher=True)
    student = lifecycle.read(parent.production_ref, version)
    assert bool(teacher["media_assets"]) is teacher_only
    assert bool(student["media_assets"]) is not teacher_only
    child = lifecycle.saved_source(parent.production_ref, version)
    assert teacher["media_assets"] == child.p0_bundle.teacher_projection()["media_assets"]
    assert "media_plan" not in teacher and "corrections" not in student


@pytest.mark.parametrize("code,expected", [
    ("PRODUCTION_MEDIA_EXPORT_ANCHOR_UNAVAILABLE:S_SECTION", {"code": "PRODUCTION_MEDIA_EXPORT_ANCHOR_UNAVAILABLE", "anchor_ref": "S_SECTION"}),
    ("PRODUCTION_WORD_ANCHOR_AMBIGUOUS", {"code": "PRODUCTION_WORD_ANCHOR_AMBIGUOUS"}),
])
def test_export_refusal_companion_projects_only_fixed_codes_and_exact_reference(code, expected):
    def invoke(*args, **kwargs):
        raise ValueError(code)

    status, _, raw = SavedProductionEndpoint(invoke, nonce="synthetic").respond(
        "word", "prod:" + "a" * 32, "ver:" + "b" * 32, "student", b"{}", "media.bounded")
    assert status == 409 and json.loads(raw)["error"] == expected


@pytest.mark.parametrize("operation,code", [
    ("word", "PRODUCTION_MEDIA_REQUIRED_MISSING:C:/private/file"),
    ("word", "PRODUCTION_MEDIA_REQUIRED_MISSING:" + "A" * 41),
    ("preview", "PRODUCTION_MEDIA_EXPORT_ANCHOR_UNAVAILABLE:S_SECTION:C:/private"),
    ("save", "PRODUCTION_MEDIA_REQUIRED_MISSING:V1"),
    ("word", "PRODUCTION_WORD_ANCHOR_AMBIGUOUS:C:/private"),
])
def test_export_refusal_never_exposes_unknown_suffix_or_applies_to_other_operation(operation, code):
    def invoke(*args, **kwargs):
        raise ValueError(code)

    status, _, raw = SavedProductionEndpoint(invoke, nonce="synthetic").respond(
        operation, "prod:" + "a" * 32, "ver:" + "b" * 32, "student", b"{}", "media.bounded")
    result = json.loads(raw)
    assert status == 500 and result["error"] == {"code": "R4_APPLICATION_FAILURE"}
    assert result["meta"]["contract_id"] == R4_HTTP_CONTRACT and b"private" not in raw
    assert r4_error(code, "media.bounded")[2] == raw
