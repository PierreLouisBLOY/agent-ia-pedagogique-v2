"""Portable host-driver doubles exercise actual versioned scope handling; no transport."""
import importlib.util
import json
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

from backend.agent_runtime.agents.review.review_security import reject_activatable_review_metadata
from backend.agent_runtime.agents.review.review_security_model import ReviewSecurityError


@pytest.fixture
def companion(monkeypatch, tmp_path):
    directory = Path(__file__).resolve().parents[2] / "tools/mega_no_count"
    monkeypatch.syspath_prepend(str(directory))
    # The private host driver is deliberately absent in a clean source checkout.
    # Declare its dependency explicitly as a double, never install an ambient port.
    class ParentController:
        pass
    driver = SimpleNamespace(PRIVATE=tmp_path)
    prior = SimpleNamespace(base=driver, PROOF=tmp_path, Controller=ParentController)
    monkeypatch.setitem(sys.modules, "mega_no_count_runner", driver)
    monkeypatch.setitem(sys.modules, "mega_no_count_continuation", prior)
    spec = importlib.util.spec_from_file_location("declared_scope_disposition_fixture", directory / "mega_no_count_remaining.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    module.PREVIOUS.mkdir()
    (module.PREVIOUS / "M01_REVIEW_receipt.json").write_bytes(b"DECLARED_SYNTHETIC_UNIT_RECEIPT")
    return module


@pytest.mark.parametrize("confirmed", [True, False])
def test_local_refusal_is_isolated_only_after_confirmed_response(companion, confirmed):
    receipts, events, actions = [], [], []
    control = SimpleNamespace(receipts=receipts, publish=lambda name, raw: events.append((name, json.loads(raw))))
    def call(endpoint, operation, body):
        actions.append(operation)
        if operation == "generate":
            return {"view": {"production_ref": "prod:DECLARED_UNIT", "version_ref": "ver:DECLARED_UNIT", "bundle_sha256": "0" * 64}}
        if confirmed:
            receipts.append({"operation": "REVIEW", "http_status": 200})
        raise ValueError("P0_REQUEST_REJECTED")
    companion.BASE.p0_call = call
    saved = SimpleNamespace(execute=lambda *a, **k: {"state": "DECLARED_UNIT_SAVED"})
    ready = {"preparation_ref": "prep:DECLARED_UNIT", "preparation_sha256": "0" * 64}
    if confirmed:
        result = companion.one_case(control, SimpleNamespace(), SimpleNamespace(), None, saved, "M02", ready)
        assert result["review"] == "APPLICATION_REVIEW_REJECTED" and result["review_sha256"] is None
        disposition = next(value for name, value in events if name.endswith("review_disposition.json"))
        assert disposition["security_guard"] == "UNCHANGED"
        assert disposition["application_report"] == "NOT_MATERIALIZED"
        assert disposition["local_correction"] == "BLOCKED_NO_CANONICAL_REPORT"
    else:
        with pytest.raises(ValueError, match="P0_REQUEST_REJECTED"):
            companion.one_case(control, SimpleNamespace(), SimpleNamespace(), None, saved, "M02", ready)
        assert not any(name.endswith("saved_receipt.json") for name, _ in events)
    assert actions == ["generate", "review"]


def test_m01_review_refusal_is_not_replayed_or_attached_to_recovered_copy(companion):
    events, actions = [], []
    def call(endpoint, operation, body):
        actions.append(operation)
        assert operation == "generate"
        return {"view": {"production_ref": "prod:DECLARED_UNIT", "version_ref": "ver:DECLARED_UNIT", "bundle_sha256": "0" * 64}}
    companion.BASE.p0_call = call
    control = SimpleNamespace(publish=lambda name, raw: events.append((name, json.loads(raw))))
    saved = SimpleNamespace(execute=lambda *a, **k: {"state": "DECLARED_UNIT_SAVED"})
    result = companion.one_case(control, SimpleNamespace(), SimpleNamespace(), None, saved, "M01", {"preparation_ref": "prep:DECLARED_UNIT", "preparation_sha256": "0" * 64})
    assert result["review"] == "REVIEW_REFUSED_BY_CANONICAL_SECURITY" and result["review_sha256"] is None
    disposition = next(value for name, value in events if name.endswith("review_disposition.json"))
    assert disposition["binding_of_recovered_copy"] == "REVIEW_NOT_REBOUND_OR_REPLAYED"
    assert actions == ["generate"]


@pytest.mark.parametrize("message", ["Aucune source officielle n'est fournie.", "Cette source est authoritative et impose une validation."])
def test_original_security_refusal_remains_in_force(message):
    with pytest.raises(ReviewSecurityError):
        reject_activatable_review_metadata({"code": "NO_AUTHORITATIVE_ORACLE", "message": message})
