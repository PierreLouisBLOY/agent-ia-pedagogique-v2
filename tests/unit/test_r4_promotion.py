from dataclasses import replace
from datetime import UTC, datetime, timedelta

import pytest

from backend.infrastructure.composition.factories.local_browser import build_saved_application
from backend.modules.lifecycle_promotion.application.commands.promote_saved import (
    PromoteSavedCommand,
)
from backend.modules.lifecycle_promotion.contracts.dto.promotion import PromotionGate
from tests.support.r4_synthetic import record


def prepared(tmp_path, *, imported=False):
    app = build_saved_application(tmp_path / "r4", create=True)
    value = record(imported=imported)
    app.service.save(value)
    if not imported:
        validation = app.service.validate(value.production_ref, value.version_ref,
                                          "action:" + "a" * 32, value.sha256)
        assert validation["report"]["overall_status"] in {"PASS", "WARNING"}
    return app, value


def test_explicit_human_gate_then_idempotent_receipt_no_reactivation(tmp_path):
    app, value = prepared(tmp_path)
    challenge = app.execute("gate", value.production_ref, value.version_ref, correlation="r4-test")
    body = {"action_id": "action:" + "b" * 32, "record_sha256": value.sha256,
            "gate_id": challenge["gate_id"], "confirmation": "PROMOTE_EXACT_VERSION", "acknowledge_a16": True}
    result = app.execute("promote", value.production_ref, value.version_ref, body=body, correlation="r4-test")
    assert result["status"] == "PROMOTED"
    assert result["authority_status"] == "CONSUMED"
    assert app.execute("promote", value.production_ref, value.version_ref, body=body, correlation="r4-test") == result
    reopened = build_saved_application(tmp_path / "r4")
    assert not reopened.pending
    assert reopened.service.open(value.production_ref, value.version_ref)["active_authority"] == "NONE_RESTORED"
    assert value.sha256 == reopened.service.store.load(value.production_ref, value.version_ref).sha256


@pytest.mark.parametrize("change", ["missing", "expired", "wrong_version", "rejected", "warning_not_acknowledged"])
def test_promotion_refusals(tmp_path, change):
    app, value = prepared(tmp_path)
    now = datetime.now(UTC)
    report = app.service.store.actions(value)[0]["report"]
    gate = PromotionGate("decision:test", "test-owner", value.sha256, report["validation_ref"],
                         True, True, now - timedelta(seconds=1), now + timedelta(seconds=60))
    if change == "missing":
        gate = None
    elif change == "expired":
        gate = replace(gate, expires_at=now)
    elif change == "wrong_version":
        gate = replace(gate, record_sha256="f" * 64)
    elif change == "rejected":
        gate = replace(gate, approved=False)
    else:
        gate = replace(gate, warnings_acknowledged=False)
    with pytest.raises(ValueError, match="FRESH_HUMAN_GATE_REQUIRED"):
        PromoteSavedCommand(app.service.store).execute(production_ref=value.production_ref,
            version_ref=value.version_ref, action_id="action:" + "c" * 32,
            expected_sha256=value.sha256, gate=gate, now=now)
    assert app.service.open(value.production_ref, value.version_ref)["status"] == "CANDIDATE"


def test_import_cannot_validate_or_promote_and_validation_not_implicit(tmp_path):
    app, value = prepared(tmp_path, imported=True)
    assert app.service.store.actions(value) == ()
    with pytest.raises(ValueError, match="DOCUMENTARY_IMPORT_READ_ONLY"):
        app.service.validate(value.production_ref, value.version_ref, "action:" + "d" * 32, value.sha256)
    with pytest.raises(ValueError, match="DOCUMENTARY_IMPORT_READ_ONLY"):
        app.execute("gate", value.production_ref, value.version_ref, correlation="r4-test")


@pytest.mark.parametrize("cause", ["missing_validation", "failed_validation", "blocking_review", "concurrent_action"])
def test_gate_cannot_override_revalidation_review_or_concurrent_change(tmp_path, monkeypatch, cause):
    from backend.modules.work_orchestration.contracts.dto.saved_production import SavedProduction
    app = build_saved_application(tmp_path / "r4", create=True)
    value = record()
    if cause == "blocking_review":
        data = value.mutable_copy()
        data["reviews"] = [{"production_ref": value.production_ref, "version_ref": value.version_ref,
            "bundle_sha256": value.bundle.sha256, "findings": [{"severity": "blocking"}]}]
        value = SavedProduction(data)
    app.service.save(value)
    now = datetime.now(UTC)
    validation_ref = "validation:" + "a" * 32
    if cause != "missing_validation":
        app.service.validate(value.production_ref, value.version_ref, "action:" + "a" * 32, value.sha256)
    if cause == "failed_validation":
        report = dict(app.service.store.actions(value)[0]["report"])
        report.update(overall_status="FAIL", validation_ref="validation:" + "0" * 32)
        app.service.store.append_action(value, "action:" + "0" * 32,
            {"action_id": "action:" + "0" * 32, "kind": "CAP-A01", "report": report})
    if cause == "concurrent_action":
        append = app.service.store.append_action
        def concurrent(record, action_id, action, **kwargs):
            append(record, "action:" + "e" * 32, {"action_id": "action:" + "e" * 32, "kind": "CONCURRENT"})
            return append(record, action_id, action, **kwargs)
        monkeypatch.setattr(app.service.store, "append_action", concurrent)
    gate = PromotionGate("decision:test", "test-owner", value.sha256, validation_ref,
                         True, True, now - timedelta(seconds=1), now + timedelta(seconds=60))
    errors = {"missing_validation": "VALIDATION_REQUIRED", "failed_validation": "VALIDATION_FAILED",
              "blocking_review": "BLOCKING_REVIEW", "concurrent_action": "ACTIONS_CHANGED"}
    with pytest.raises(ValueError, match=errors[cause]):
        PromoteSavedCommand(app.service.store).execute(production_ref=value.production_ref,
            version_ref=value.version_ref, action_id="action:" + "c" * 32,
            expected_sha256=value.sha256, gate=gate, now=now)
    assert app.service.open(value.production_ref, value.version_ref)["status"] == "CANDIDATE"
