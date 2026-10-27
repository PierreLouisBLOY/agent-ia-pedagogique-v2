"""Normal-path focus qualification, all sources, keys, receipts and effects synthetic."""

import pytest

from tests import test_normal_on_323c as existing_scenario
from tests.normal_focus_323d_fixture import install
from tests.test_normal_on_323a import accept, call, prepare


def test_full_focused_normal_path_and_single_attempt(tmp_path, monkeypatch):
    monkeypatch.setattr(existing_scenario, "install", install)
    existing_scenario.test_structured_exercise_full_normal_path_save_reopen_and_exports(
        tmp_path, monkeypatch
    )


def test_hash_provenance_is_exposed_only_by_opt_in_and_wrong_pin_is_refused(tmp_path, monkeypatch):
    f = install(monkeypatch)
    control = f.Control()
    with f.running(tmp_path / "case", monkeypatch, control, proposed=True) as (port, _):
        status, data = call(port, "GET", "/api/v2/p0")
        assert status == 200
        frame = next(
            row
            for row in data["data"]["institutional_catalog"]["frames"]
            if row["frame"] == "SGN_PREMIERE"
        )
        question = frame["questions"][0]
        assert (
            question["source_question_sha256"]
            == f.context()["exercise_focus_selection"]["source_question_sha256"]
        )
        c = f.context()
        c["exercise_focus_selection"]["source_question_sha256"] = "a" * 64
        status, _ = call(
            port,
            "POST",
            "/api/v2/p0/prepare",
            {
                "command_id": "d" * 32,
                "context": c,
                "reference": {"notion_id": "notion:shared", "passage_ref": f.SOURCE["passage_ref"]},
            },
            data["data"]["transport_nonce"],
        )
        assert status == 409 and control.calls == control.builds == control.prompt_calls == 0
        _, _, shown = prepare(port)
        assert shown["effect_enabled"] is False and control.calls == 0


@pytest.mark.parametrize("field", ["transfer_accepted", "cost_bound_accepted"])
def test_focused_path_without_each_consent_has_no_effect(tmp_path, monkeypatch, field):
    f = install(monkeypatch)
    control = f.Control()
    with f.running(tmp_path / "case", monkeypatch, control) as (port, _):
        nonce, command, shown = prepare(port)
        decision = accept(command, shown)
        decision[field] = False
        status, _ = call(port, "POST", "/api/v2/p0/consent-generate", decision, nonce)
        assert status >= 400
        assert control.calls == control.builds == control.prompt_calls == 0
        assert control.owner.generation.ledger.slots() == []
