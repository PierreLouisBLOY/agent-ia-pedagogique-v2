"""Synthetic full-source Application companion; native resolution stays separate."""
from __future__ import annotations

import copy
import hashlib

import pytest

from backend.infrastructure.composition.factories.local_contribution import (
    build_local_contribution_application,
)
from backend.infrastructure.composition.factories.stmg_local_contribution import (
    build_stmg_local_contribution_application,
)
from backend.modules.pedagogical_context.contracts.dto.stmg_local_activity import (
    LocalActivityChoice,
)
from backend.modules.pedagogical_design.contracts.dto.assessment_bundle import encoded, fingerprint
from tests.unit.test_local_contribution import fixture, fixture_v2, read_request
from tests.unit.test_stmg_local_activity_qualification import fixture as stmg_fixture
from tests.unit.test_stmg_local_activity_qualification import scope_for


def companion_fixture(*, insufficient=False, provenance_v2=False):
    make = fixture_v2 if provenance_v2 else fixture
    args, request, _ = make()
    contribution_app = build_local_contribution_application(**args, enabled=True)
    outcome = contribution_app.register(request, correlation="synthetic")
    assert outcome.success
    record = args["store"].record
    source = contribution_app.read(read_request(record))["source_snapshot"]
    choice, basis, _ = stmg_fixture(mode="QCM", host="SGN_PREMIERE", support="SGN_PREMIERE", insufficient=insufficient)
    choice["role"] = "PREPARATORY_READING"
    identity = {k: source[k] for k in ("notion_ref", "object_ref", "object_kind", "passage_ref", "version_or_checksum")}
    identity.update(excerpt_sha256=record.data["text_sha256"], utf8_bytes=record.data["utf8_bytes"])
    evidence = encoded({"schema": "LU-OWNER-LOCAL-DECISIONS-UI-REPLY-1.0", "decisions": [
        {"item": 0, "proposal_sha256": "1" * 64, "answer_verbatim": "SYNTHETIC_EXACT_LOCAL_SUCCESSOR_ONLY"}]})
    owner_sha = hashlib.sha256(evidence).hexdigest()
    choice.update(source_identity=identity, source_snapshot_sha256=fingerprint(source), owner_local_decision_sha256=owner_sha)
    choice["choice_ref"] = "local-choice:SYNTHETIC_OVERLAY_SUCCESSOR"
    scope = scope_for([choice], owner_sha=owner_sha)
    reads = {fingerprint(identity): read_request(record)}
    basis_calls = []
    def basis_reader(_):
        basis_calls.append("basis")
        return basis
    companion_args = {"contributions": contribution_app, "choices": [choice], "exact_reads": reads,
        "owner_scope": scope, "expected_owner_scope_sha256": scope.sha256,
        "owner_decision_evidence": evidence, "expected_owner_decision_sha256": owner_sha, "basis_reader": basis_reader}
    args["store"].calls.clear()
    return companion_args, choice, args["store"], basis_calls


def test_default_off_companion_has_no_boundary_calls():
    args, choice, store, calls = companion_fixture()
    app = build_stmg_local_contribution_application(**args)
    assert app.metadata() == []
    with pytest.raises(ValueError, match="LOCAL_ACTIVITY_DISABLED"):
        app.prepare(choice_sha256=LocalActivityChoice(choice).sha256)
    assert store.calls == calls == []


def test_full_contribution_is_reread_by_application_and_source_gap_stays_visible():
    args, choice, store, calls = companion_fixture()
    app = build_stmg_local_contribution_application(**args, enabled=True)
    result = app.prepare(choice_sha256=LocalActivityChoice(choice).sha256)
    assert result["state"] == "LOCAL_CONTEXT_SUPPORTED_FOR_PREPARATION"
    assert result["source_identity"]["utf8_bytes"] > 320
    assert result["source_identity"]["object_ref"] == store.record.data["object_ref"]
    assert result["source_provenance"]["source_kind"] == "LOCAL_CONTRIBUTION_OVERLAY"
    assert result["source_provenance"]["reference_snapshot"]["native_scope_status"] == "CONTENT_GAP"
    assert result["source_authority"] == "UNKNOWN" and result["source_status"]["lifecycle_status"] == "UNKNOWN"
    assert result["institutional_alignment"] == "UNVERIFIED_FOR_LOCAL_ACTIVITY"
    assert result["native_relationship_status"] == "NOT_ADMITTED_FOR_POSITIONING"
    assert result["transmission_admission"] == "NOT_ADOPTED" and result["provider_dispatch_allowed"] is False
    assert result["provider_calls"] == 0 and result["teacher_acceptance"] == "NOT_PERFORMED"
    assert calls == ["basis"] and "read" in store.calls
    assert app.metadata()[0]["provider_dispatch_allowed"] is False


def test_content_insufficiency_is_not_repaired_by_using_a_longer_source_alone():
    args, choice, _, _ = companion_fixture(insufficient=True)
    result = build_stmg_local_contribution_application(**args, enabled=True).prepare(choice_sha256=LocalActivityChoice(choice).sha256)
    assert result["state"] == "LOCAL_CONTEXT_CONTENT_INSUFFICIENT"


def test_missing_exact_read_scope_never_falls_back_to_canonical_search():
    args, choice, store, calls = companion_fixture()
    args["exact_reads"] = {}
    with pytest.raises(ValueError, match="NOT_IN_EXACT_READ_SCOPE"):
        build_stmg_local_contribution_application(**args, enabled=True).prepare(choice_sha256=LocalActivityChoice(choice).sha256)
    assert store.calls == calls == []


def test_exact_read_mapping_is_frozen_at_factory_construction():
    args, choice, _, _ = companion_fixture()
    app = build_stmg_local_contribution_application(**args, enabled=True)
    reads = args["exact_reads"]
    next(iter(reads.values()))["record_sha256"] = "f" * 64
    reads.clear()
    assert app.prepare(choice_sha256=LocalActivityChoice(choice).sha256)["state"] == "LOCAL_CONTEXT_SUPPORTED_FOR_PREPARATION"


def test_another_allocated_version_or_modified_read_hash_is_refused():
    args, choice, _, _ = companion_fixture()
    key = next(iter(args["exact_reads"]))
    args["exact_reads"][key]["version_ref"] = "local-version:" + "f" * 32
    with pytest.raises(ValueError):
        build_stmg_local_contribution_application(**args, enabled=True).prepare(choice_sha256=LocalActivityChoice(choice).sha256)


def test_old_owner_scope_cannot_authorize_new_overlay_choice():
    args, choice, _, _ = companion_fixture()
    changed = copy.deepcopy(choice)
    changed["source_snapshot_sha256"] = "f" * 64
    args["choices"] = [changed]
    with pytest.raises(ValueError, match="OWNER_SCOPE"):
        build_stmg_local_contribution_application(**args, enabled=True)


@pytest.mark.parametrize("enabled", ["false", "true", 0, 1, None])
def test_companion_enablement_is_strict_and_no_provider_route_exists(enabled):
    args, _, store, calls = companion_fixture()
    with pytest.raises(ValueError, match="ENABLED_BOOL"):
        build_stmg_local_contribution_application(**args, enabled=enabled)
    assert store.calls == calls == []


def test_overlay_wrapper_does_not_expose_dispatch_or_native_resolver():
    args, _, _, _ = companion_fixture()
    app = build_stmg_local_contribution_application(**args)
    assert not {"generate", "dispatch", "reserve", "resolve_institutional_context", "promote"} & set(dir(app))


def test_v2_companion_keeps_unknown_creation_recording_basis_and_native_gap():
    args, choice, store, _ = companion_fixture(provenance_v2=True)
    app = build_stmg_local_contribution_application(**args, enabled=True)
    result = app.prepare(choice_sha256=LocalActivityChoice(choice).sha256)
    origin = result["source_provenance"]["origin"]
    assert result["state"] == "LOCAL_CONTEXT_SUPPORTED_FOR_PREPARATION"
    assert origin["draft_created_at"] is None and origin["draft_creation_status"] == "NOT_ESTABLISHED"
    assert origin["draft_recorded_at"] == "2001-01-01T01:02:03+00:00"
    assert origin["author_kind"] == "SUBAGENT" and origin["recording_basis"] == "ORIGINAL_PROPOSAL_RECEIPT"
    assert store.record.data["created_at"] != origin["draft_recorded_at"]
    assert result["source_provenance"]["reference_snapshot"]["native_scope_status"] == "CONTENT_GAP"
    assert result["source_authority"] == "UNKNOWN" and result["provider_dispatch_allowed"] is False
    assert result["native_relationship_status"] == "NOT_ADMITTED_FOR_POSITIONING"
    assert result["transmission_admission"] == "NOT_ADOPTED" and result["teacher_acceptance"] == "NOT_PERFORMED"
