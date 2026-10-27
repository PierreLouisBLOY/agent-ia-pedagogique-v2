"""Exercise quality through the normal CLI/HTTP composition with one double call."""
from io import BytesIO
from zipfile import ZipFile

import pytest

from tests.normal_on_323c_fixture import install
from tests.test_normal_on_323a import accept, call, prepare, terminal


def test_structured_exercise_full_normal_path_save_reopen_and_exports(tmp_path, monkeypatch):
    f = install(monkeypatch)
    control = f.Control()
    with f.running(tmp_path / "case", monkeypatch, control) as (port, configuration):
        nonce, command, shown = prepare(port)
        assert control.calls == 0
        decision = accept(command, shown)
        status, result = call(port, "POST", "/api/v2/p0/consent-generate", decision, nonce)
        assert status == 202, result
        done = terminal(port, decision["command_id"])
        assert done["state"] == "LOCAL_COMMAND_COMPLETED", done
        assert done["phase"] == "APPLICATION_SAVED"
        assert control.calls == control.builds == 1
        publication = done["result"]["publication"]
        view = done["result"]["view"]
        record_sha = publication["record_sha256"]
        base = "/api/v2/productions/" + view["production_ref"] + "/versions/" + view["version_ref"]
        status, opened = call(port, "GET", base + "/saved")
        assert status == 200 and opened["data"]["record_sha256"] == record_sha
        for kind in ("student", "correction"):
            status, raw = f.request(port, "GET", base + "/word/" + kind)
            assert status == 200
            with ZipFile(BytesIO(raw)) as archive:
                xml = archive.read("word/document.xml").decode()
            assert ("Remédiation" in xml) == (kind == "correction")
            assert "Document 1" in xml and "Démonstration locale" in xml
        # The same final command is consulted, never re-dispatched.
        call(port, "POST", "/api/v2/p0/consent-generate", decision, nonce)
        assert terminal(port, decision["command_id"])["state"] == "LOCAL_COMMAND_COMPLETED"
        assert control.calls == 1
    next_process = f.Control()
    with f.running(tmp_path / "case", monkeypatch, next_process, existing=configuration) as (port, _):
        status, opened = call(port, "GET", base + "/saved")
        assert status == 200 and opened["data"]["record_sha256"] == record_sha
        assert next_process.calls == next_process.builds == next_process.prompt_calls == 0


@pytest.mark.parametrize("field", ["transfer_accepted", "cost_bound_accepted"])
def test_structured_exercise_missing_consent_has_no_effect(tmp_path, monkeypatch, field):
    f = install(monkeypatch)
    control = f.Control()
    with f.running(tmp_path / "case", monkeypatch, control) as (port, configuration):
        nonce, command, shown = prepare(port)
        decision = accept(command, shown)
        decision[field] = False
        status, _ = call(port, "POST", "/api/v2/p0/consent-generate", decision, nonce)
        assert status >= 400
        assert control.calls == control.builds == 0
        assert control.owner.generation.ledger.slots() == []


def test_structured_exercise_invalid_output_is_not_published_or_retried(tmp_path, monkeypatch):
    f = install(monkeypatch, invalid_response=True)
    control = f.Control()
    with f.running(tmp_path / "case", monkeypatch, control) as (port, _):
        nonce, command, shown = prepare(port)
        decision = accept(command, shown)
        status, _ = call(port, "POST", "/api/v2/p0/consent-generate", decision, nonce)
        assert status == 202
        done = terminal(port, decision["command_id"])
        assert done["state"] == "LOCAL_COMMAND_UNCERTAIN", done
        assert done.get("phase") != "APPLICATION_SAVED"
        call(port, "POST", "/api/v2/p0/consent-generate", decision, nonce)
        assert control.calls == 1


def test_structured_exercise_incoherent_question_refused_before_generation(tmp_path, monkeypatch):
    f = install(monkeypatch, invalid_focus=True)
    control = f.Control()
    with f.running(tmp_path / "case", monkeypatch, control) as (port, _):
        status, metadata = call(port, "GET", "/api/v2/p0")
        assert status == 200
        status, result = call(port, "POST", "/api/v2/p0/prepare", {
            "command_id": "c" * 32, "context": f.context(),
            "reference": {"notion_id": "notion:shared", "passage_ref": f.SOURCE["passage_ref"]}},
            metadata["data"]["transport_nonce"])
        # The public HTTP boundary deliberately masks the underlying contract
        # detail; the pure context tests assert EXERCISE_SINGLE_QUESTION_BINDING.
        assert status == 409 and result["error"]["code"] == "P0_REQUEST_REJECTED"
        assert control.calls == control.builds == 0
        assert control.owner.generation.ledger.slots() == []
