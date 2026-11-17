"""Same existing manual CLI, real source boundary, fake transport and private test budget."""
import copy
from secrets import token_hex
from types import SimpleNamespace

import pytest

from backend.adapters.outbound.generation.openai.p0_manual_tests import ManualTestGeneration
from backend.infrastructure.config.secrets.provider import ProviderCredentialRef
from backend.modules.resource_library.application.queries.read_course_threads import (
    ReadCourseThreads,
)
from tests import normal_on_323a_fixture as f
from tests.support.progressive_real_fixture import progressive_real_fixture
from tests.test_manual_provider_tests import Control, configuration, running
from tests.test_normal_on_323a import call, terminal, text
from tests.test_real_course_thread import dossier, real_content, real_preparation


def test_manual_launcher_real_dossier_refusals_one_attempt_and_word(tmp_path, monkeypatch):
    root = tmp_path / "manual"
    config = configuration(root)
    capture = f.artifact(root, "SYNTHETIC-documentary-dossier.json", {
        "schema": "LOCAL-ORGANIZATION-CAPTURES-3.0", "records": [dossier().as_dict()["identity"]],
        "index": [], "course_dossiers": [dossier().as_dict()]})
    control = Control()
    args = ["--organization-captures", capture["path"], "--organization-captures-sha256", capture["sha256"]]
    with running(root, monkeypatch, control, existing=config, extra_args=args) as (port, _):
        status, metadata = call(port, "GET", "/api/v2/p0")
        assert status == 200 and metadata["data"]["course_organizations"] == [dossier().summary()]
        nonce = metadata["data"]["transport_nonce"]
        assert f.request(port, "GET", "/assets/real-course.js")[0] == 200
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
        content = progressive_real_fixture(real_content(dispatch))
        monkeypatch.setattr(f, "CONTENT", content)
        command = {"command_id": token_hex(16), "preparation_ref": prepared["preparation_ref"],
                   "preparation_sha256": prepared["preparation_sha256"]}
        original = control.owner.generation.course_thread_reader
        def changed(_):
            raise ValueError("P0_REAL_ORGANIZATION_CHANGED")
        control.owner.generation.course_thread_reader = changed
        status, refusal = call(port, "POST", "/api/v2/p0/generate", command, nonce)
        assert status == 409 and refusal["error"]["code"] == "P0_REAL_ORGANIZATION_CHANGED"
        assert control.calls == control.builds == 0
        assert control.owner.generation.budget.snapshot()["reserved_usd"] == "0"
        control.owner.generation.course_thread_reader = original
        status, started = call(port, "POST", "/api/v2/p0/generate", command, nonce)
        assert status == 202, started
        done = terminal(port, command["command_id"])
        assert done["state"] == "LOCAL_COMMAND_COMPLETED", done
        assert done["phase"] == "APPLICATION_SAVED"
        view = done["result"]["view"]
        base = "/api/v2/productions/" + view["production_ref"] + "/versions/" + view["version_ref"]
        assert call(port, "GET", base + "/saved")[0] == 200
        for kind in ("student", "correction"):
            status, raw = f.request(port, "GET", base + "/word/" + kind)
            assert status == 200
            body = text(raw)
            assert "https://example.org/SYNTHETIC-document" in body
            assert ("SENTINELLE_PROFESSEUR" in body) == (kind == "correction")
        assert call(port, "POST", "/api/v2/p0/generate", command, nonce)[0] == 202
        assert control.calls == control.builds == 1 and control.prompt_calls == 0
        session = call(port, "GET", "/api/v2/p0")[1]["data"]["manual_test_session"]
        assert session["budget_usd"] == "5.00" and session["retry"] == 0
        assert session["per_call_ceiling_usd"] is None


@pytest.mark.parametrize("change", ["no_reader", "changed_reader", "extra_ref", "missing_ref", "changed_excerpt"])
def test_manual_documentary_guard_before_credential_reservation_and_effect(tmp_path, change):
    def forbidden(*_args, **_kwargs):
        raise AssertionError("NO_CREDENTIAL_OR_TRANSPORT")
    generation = ManualTestGeneration(root=tmp_path, resolver=SimpleNamespace(resolve=forbidden),
        credential_ref=ProviderCredentialRef("openai.p0.manual-tests"), transport=SimpleNamespace(build=forbidden))
    _, _, request = real_preparation()
    generation.course_thread_reader = ReadCourseThreads((dossier(),)).read
    assert generation.wire(request).max_output_tokens == 32768
    if change == "no_reader":
        generation.course_thread_reader = None
    elif change == "changed_reader":
        data = dossier().as_dict()
        data["documents"][0]["title"] = "Changed documentary identity"
        generation.course_thread_reader = lambda _: data
    elif change == "extra_ref":
        request["references"].append(copy.deepcopy(request["references"][-1]))
    elif change == "missing_ref":
        request["references"].pop()
    else:
        request["evidence"][dossier().references()[1]["evidence_id"]] += " substituted"
    with pytest.raises(ValueError):
        generation.prepare_transport(request)
    assert generation.budget.snapshot()["reserved_usd"] == "0"
