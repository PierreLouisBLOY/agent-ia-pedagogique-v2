"""Real CLI/factories/HTTP and native controls, with declared synthetic sources/effects."""
import copy
import json
from pathlib import Path
from secrets import token_hex

from backend.adapters.outbound.generation.openai.p0_course_content_schema import (
    rich_course_real_content_schema,
)
from backend.adapters.outbound.generation.openai.p0_normal_policy import canonical, sha
from tests import normal_on_323a_fixture as f
from tests.test_normal_on_323a import accept, call, terminal, text
from tests.test_real_course_thread import dossier, real_content, real_preparation


def configuration(root):
    envelope_path, target, saved, receipts = f.configuration(root)
    envelope = json.loads(envelope_path.read_bytes())
    profile = envelope["profile"]
    permission = json.loads(Path(envelope["permission"]["path"]).read_bytes())
    decision = json.loads(Path(envelope["decision"]["path"]).read_bytes())
    sources = json.loads(Path(profile["source_admission_manifest"]["path"]).read_bytes())
    for p in dossier().passages():
        entry = {"notion_ref": p["notion_ref"], "source_ref": p["object_ref"], "object_kind": p["object_kind"],
            "locator": p["passage_ref"], "checksum_or_version": p["version_or_checksum"],
            "excerpt_sha256": sha(p["excerpt"].encode()), "provenance": p["provenance"],
            "source_status": p["source_status"], "available_authority": p["authority"], "authority_basis": p["authority_basis"]}
        entry["admission_scope_sha256"] = sha(canonical(entry))
        sources["entries"].append(entry)
    sources["source_scope_sha256"] = sha(canonical(sources["entries"]))
    profile["source_admission_manifest"] = f.artifact(root, "SYNTHETIC-real-source-admission.json", sources)
    permission.update(allowed_families=["COURSE"], source_admission_manifest_sha256=profile["source_admission_manifest"]["sha256"],
        output_schema_sha256=sha(canonical(rich_course_real_content_schema())), profile_sha256=sha(canonical(profile)))
    decision.update(profile_sha256=permission["profile_sha256"],
        source_admission_manifest_sha256=permission["source_admission_manifest_sha256"],
        permission_policy_sha256=sha(canonical({k: v for k, v in permission.items() if k != "owner_decision_sha256"})))
    envelope["decision"] = f.artifact(root, "SYNTHETIC-real-decision-NOT-OWNER-ACCORD.json", decision)
    permission["owner_decision_sha256"] = envelope["decision"]["sha256"]
    envelope["permission"] = f.artifact(root, "SYNTHETIC-real-permission-NOT-LIVE.json", permission)
    envelope_path.write_bytes(canonical(envelope))
    capture = f.artifact(root, "SYNTHETIC-course-dossier.json", {"schema": "LOCAL-ORGANIZATION-CAPTURES-3.0",
        "records": [dossier().as_dict()["identity"]], "index": [], "course_dossiers": [dossier().as_dict()]})
    return (envelope_path, target, saved, receipts), capture


def test_normal_launcher_documentary_course_consent_once_save_reopen_and_word(tmp_path, monkeypatch):
    config, capture = configuration(tmp_path / "normal")
    control = f.Control()
    args = ["--organization-captures", capture["path"], "--organization-captures-sha256", capture["sha256"]]
    with f.running(tmp_path / "normal", monkeypatch, control, existing=config, extra_args=args) as (port, _):
        status, metadata = call(port, "GET", "/api/v2/p0")
        assert status == 200 and metadata["data"]["course_organizations"] == [dossier().summary()]
        nonce = metadata["data"]["transport_nonce"]
        status, observed = call(port, "GET", "/api/v2/p0/organizations/" + dossier().organization_id)
        assert status == 200 and observed["data"]["dossier_sha256"] == dossier().sha256
        for asset in ("/", "/assets/real-course.js"):
            assert f.request(port, "GET", asset)[0] == 200
        _, _, example = real_preparation()
        selected = copy.deepcopy(example["context"])
        selected["institutional_resolution"] = None
        status, result = call(port, "POST", "/api/v2/p0/prepare", {"command_id": token_hex(16),
            "context": selected, "reference": {"notion_id": "notion:shared", "passage_ref": f.SOURCE["passage_ref"]},
            "organization_selection": {"organization_id": dossier().organization_id, "dossier_sha256": dossier().sha256}}, nonce)
        assert status == 200, result
        prepared = result["data"]
        dispatch = {"context": prepared["context"], "references": prepared["references"],
            "evidence": {prepared["references"][0]["evidence_id"]: f.SOURCE_TEXT, **dossier().evidence()}}
        monkeypatch.setattr(f, "CONTENT", real_content(dispatch))
        command = {"command_id": token_hex(16), "preparation_ref": prepared["preparation_ref"],
                   "preparation_sha256": prepared["preparation_sha256"]}
        status, shown = call(port, "POST", "/api/v2/p0/consent-preview", command, nonce)
        assert status == 200, shown
        assert len(shown["data"]["preview"]["source_receipts"]) == 3
        decision = accept(command, shown["data"])
        for missing in ("transfer_accepted", "cost_bound_accepted"):
            status, refused = call(port, "POST", "/api/v2/p0/consent-generate", {**decision, missing: False}, nonce)
            assert status == 409, refused
            assert control.calls == control.builds == 0 and control.owner.generation.ledger.slots() == []
        status, engaged = call(port, "POST", "/api/v2/p0/consent-generate", decision, nonce)
        assert status == 202, engaged
        done = terminal(port, decision["command_id"])
        assert done["state"] == "LOCAL_COMMAND_COMPLETED", done
        assert done["phase"] == "APPLICATION_SAVED" and control.calls == 1
        view = done["result"]["view"]
        base = "/api/v2/productions/" + view["production_ref"] + "/versions/" + view["version_ref"]
        status, opened = call(port, "GET", base + "/saved")
        assert status == 200 and opened["data"]["record_sha256"] == done["result"]["publication"]["record_sha256"]
        for kind in ("student", "correction"):
            status, raw = f.request(port, "GET", base + "/word/" + kind)
            assert status == 200
            body = text(raw)
            assert "https://example.org/SYNTHETIC-document" in body and dossier().fiction_notice in body
            assert ("SENTINELLE_PROFESSEUR" in body) == (kind == "correction")
        call(port, "POST", "/api/v2/p0/consent-generate", decision, nonce)
        assert control.calls == control.builds == 1 and control.prompt_calls == 0
