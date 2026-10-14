"""Synthetic contracts and Application gates; no real target or admitted draft."""
from __future__ import annotations

import copy
import hashlib
from contextlib import contextmanager

import pytest

from backend.core_contracts.outcome import OutcomeStatus
from backend.infrastructure.composition.factories.local_contribution import (
    build_local_contribution_application,
    contribution_adoption_scope,
)
from backend.modules.documents_provenance.contracts.dto.local_contribution_provenance import (
    LocalContributionProvenance,
    LocalContributionProvenanceV2,
    parse_local_contribution_provenance,
)
from backend.modules.pedagogical_design.contracts.dto.assessment_bundle import encoded
from backend.modules.resource_library.contracts.dto.local_contribution import (
    LocalContributionAuthority,
    LocalContributionRead,
    LocalContributionRecord,
    LocalContributionRequest,
)
from backend.modules.resource_library.ports.outbound.local_contribution_store import (
    LocalContributionPersistenceError,
)


class SyntheticStore:
    def __init__(self, authority):
        self.authority = authority
        self.record = None
        self.calls = []
        self.state = "ABSENT"
        self.failure = None

    def attest(self):
        self.calls.append("attest")
        return {**{k: self.authority.data[k] for k in ("target_ref", "target_binding_sha256", "operator_profile_sha256")},
            "binding_sha256": self.authority.sha256}

    @contextmanager
    def session(self, *, create=False):
        self.calls.append(("session", create))
        yield

    def inspect_operation(self, operation_key, binding_sha256):
        self.calls.append("inspect")
        assert binding_sha256 == self.authority.sha256
        if self.record is not None and operation_key != self.record.data["operation_key"]:
            return {"state": "UNKNOWN"}
        if self.state == "COMMITTED":
            return {"state": "COMMITTED", "record": self.record.as_dict(), "record_sha256": self.record.sha256}
        return {"state": self.state}

    def append(self, record, intention):
        self.calls.append("append")
        assert intention["record_sha256"] == record.sha256
        if self.failure:
            self.state = "UNKNOWN"
            raise self.failure
        self.record = record
        self.state = "COMMITTED"
        return record

    def read_exact(self, request):
        self.calls.append("read")
        assert self.record is not None
        if any(request.data[k] != self.record.data[k] for k in ("object_ref", "version_ref", "passage_ref")) or request.data["record_sha256"] != self.record.sha256:
            raise ValueError("SYNTHETIC_EXACT_READ_CHANGED")
        return self.record


def fixture(*, target_sha="6" * 64, profile_sha="7" * 64):
    text = "Synthetic full local educational contribution, deliberately longer than the bounded search excerpt. " * 5
    authority = {"contract_id": "LOCAL-CONTRIBUTION-AUTHORITY-1.0", "text_sha256": hashlib.sha256(text.encode()).hexdigest(),
        "utf8_bytes": len(text.encode()), "draft_origin_sha256": "1" * 64, "local_admission_decision_sha256": "2" * 64,
        "operation_authorization_sha256": "0" * 64, "local_context_sha256": "3" * 64,
        "target_ref": "local-target:" + target_sha, "target_binding_sha256": target_sha,
        "operator_profile_sha256": profile_sha, "max_new_contributions": 1}
    provenance = {"contract_id": "LOCAL-CONTRIBUTION-PROVENANCE-1.0", "origin_kind": "LOCAL_DRAFT", "author": "Synthetic author",
        "draft_created_at": "2026-01-01T00:00:00+00:00", "draft_origin_sha256": "1" * 64,
        "local_admission_decision_sha256": "2" * 64, "operation_authorization_sha256": "0" * 64,
        "local_context_sha256": "3" * 64, "authority": "UNKNOWN", "official_reference": False,
        "transmission_admission": "NOT_ADOPTED", "teacher_acceptance": "NOT_PERFORMED"}
    scope = contribution_adoption_scope(authority, provenance)
    proof = encoded({"schema": "LOCAL-CONTRIBUTION-OWNER-OPERATION-PROOF-1.0", "approved": True,
        "scope_sha256": scope, "candidate_commit": "a" * 40, "package_sha256": "b" * 64,
        "plan_sha256": "c" * 64, "prior_review_sha256": "d" * 64})
    authority["operation_authorization_sha256"] = provenance["operation_authorization_sha256"] = hashlib.sha256(proof).hexdigest()
    request = {"contract_id": "LOCAL-CONTRIBUTION-REGISTER-1.0", "command_key": "e" * 64, "text": text,
        "utf8_bytes": len(text.encode()), "text_sha256": authority["text_sha256"], "title": "Synthetic complete contribution",
        "notion_ref": "notion:synthetic", "local_context_sha256": "3" * 64}
    calls = []
    def reference_reader(notion):
        calls.append(notion)
        return {"notion_ref": notion, "identity_status": "CANONICAL", "local_context_sha256": "3" * 64,
            "native_scope_status": "CONTENT_GAP"}
    typed = LocalContributionAuthority(authority)
    store = SyntheticStore(typed)
    args = {"authority": typed, "provenance": LocalContributionProvenance(provenance),
        "owner_operation_evidence": proof, "expected_scope_sha256": scope, "expected_candidate_commit": "a" * 40,
        "expected_package_sha256": "b" * 64, "expected_plan_sha256": "c" * 64, "expected_prior_review_sha256": "d" * 64,
        "store": store, "reference_reader": reference_reader}
    return args, request, calls


def read_request(record):
    return {"contract_id": "LOCAL-CONTRIBUTION-READ-1.0", **{k: record.data[k] for k in ("object_ref", "version_ref", "passage_ref")},
        "record_sha256": record.sha256}


def fixture_v2(*, target_sha="6" * 64, profile_sha="7" * 64):
    args, request, calls = fixture(target_sha=target_sha, profile_sha=profile_sha)
    original = encoded({"schema": "LU-M02-LOCAL-COMPLEMENT-PROPOSAL-NON-ADOPTE-1.0", "status": "NON_ADOPTE",
        "contribution_kind": "LOCAL_PEDAGOGICAL_DRAFT", "author": "SUBAGENT_SYNTHETIC",
        "timestamp_utc": "2001-01-01T01:02:03+00:00", "authority": "UNKNOWN", "official_reference": False,
        "transmission_admission": "NOT_ADOPTED", "proposed_local_text": request["text"],
        "proposed_local_text_utf8_bytes": request["utf8_bytes"], "proposed_local_text_sha256": request["text_sha256"]})
    authority, provenance = dict(args["authority"].data), args["provenance"].as_dict()
    provenance.update(contract_id="LOCAL-CONTRIBUTION-PROVENANCE-2.0", author="SUBAGENT_SYNTHETIC", author_kind="SUBAGENT",
        draft_created_at=None, draft_creation_status="NOT_ESTABLISHED", draft_recorded_at="2001-01-01T01:02:03+00:00",
        recording_basis="ORIGINAL_PROPOSAL_RECEIPT", original_proposal_receipt_ref="local-draft-record:SYNTHETIC_PROPOSAL")
    args.update(original_proposal_receipt_evidence=original)
    rebind_synthetic_v2(args, authority, provenance, original)
    return args, request, calls


def rebind_synthetic_v2(args, authority, provenance, original):
    # Test-only trusted composition. Never models a caller changing an operation grant.
    original_sha = hashlib.sha256(original).hexdigest()
    authority["draft_origin_sha256"] = provenance["draft_origin_sha256"] = provenance["original_proposal_receipt_sha256"] = original_sha
    scope = contribution_adoption_scope(authority, provenance)
    proof = encoded({"schema": "LOCAL-CONTRIBUTION-OWNER-OPERATION-PROOF-1.0", "approved": True,
        "scope_sha256": scope, "candidate_commit": "a" * 40, "package_sha256": "b" * 64,
        "plan_sha256": "c" * 64, "prior_review_sha256": "d" * 64})
    authority["operation_authorization_sha256"] = provenance["operation_authorization_sha256"] = hashlib.sha256(proof).hexdigest()
    typed = LocalContributionAuthority(authority)
    args.update(authority=typed, provenance=LocalContributionProvenanceV2(provenance), store=SyntheticStore(typed),
        owner_operation_evidence=proof, expected_scope_sha256=scope, original_proposal_receipt_evidence=original,
        expected_original_proposal_receipt_sha256=original_sha)


def test_default_off_has_zero_boundary_calls_and_no_allocation(monkeypatch):
    args, request, calls = fixture()
    def forbidden():
        raise AssertionError("NO_ALLOCATION")
    monkeypatch.setattr("backend.modules.resource_library.application.commands.register_local_contribution.uuid4", forbidden)
    inbound = build_local_contribution_application(**args)
    with pytest.raises(ValueError, match="DISABLED"):
        inbound.register(request, correlation="synthetic")
    with pytest.raises(ValueError, match="DISABLED"):
        inbound.inspect_operation(LocalContributionRequest(request).sha256)
    assert args["store"].calls == calls == []


def test_application_allocates_conserves_full_text_and_reads_exact_unknown_projection():
    args, request, calls = fixture()
    inbound = build_local_contribution_application(**args, enabled=True)
    result = inbound.register(request, correlation="synthetic")
    assert result.outcome_status == OutcomeStatus.SUCCESS and result.success
    record = args["store"].record
    assert len(request["text"]) > 320
    assert all(str(record.data[k]).startswith(prefix + ":") for k, prefix in (("object_ref", "local-content"),
        ("version_ref", "local-version"), ("passage_ref", "local-passage"), ("provenance_ref", "local-provenance")))
    projection = inbound.read(read_request(record))["source_snapshot"]
    assert projection["excerpt"] == request["text"] and projection["excerpt_truncated"] is False
    assert projection["authority"] == "UNKNOWN"
    assert projection["source_status"]["lifecycle_status"] == "UNKNOWN"
    assert projection["provenance"]["reference_snapshot"]["native_scope_status"] == "CONTENT_GAP"
    assert projection["provenance"]["transmission_admission"] == "NOT_ADOPTED"
    assert projection["provenance"]["native_relationship_status"] == "NOT_ADMITTED_FOR_POSITIONING"
    assert calls == ["notion:synthetic"]
    assert not {"generate", "dispatch", "repair", "delete"} & set(dir(inbound))


def test_confirmed_duplicate_returns_same_ids_without_allocation_or_new_effect(monkeypatch):
    args, request, _ = fixture()
    inbound = build_local_contribution_application(**args, enabled=True)
    first = inbound.register(request, correlation="synthetic")
    def forbidden():
        raise AssertionError("NO_NEW_ALLOCATION")
    monkeypatch.setattr("backend.modules.resource_library.application.commands.register_local_contribution.uuid4", forbidden)
    second = inbound.register(request, correlation="synthetic")
    assert first.data["record_sha256"] == second.data["record_sha256"]
    assert second.data["state"] == "ALREADY_STORED"
    assert second.side_effects[0]["new_effect"] is False
    assert args["store"].calls.count("append") == 1


@pytest.mark.parametrize("value", ["false", "true", 0, 1, None])
def test_enabled_must_be_boolean(value):
    args, _, _ = fixture()
    with pytest.raises(ValueError, match="ENABLED_BOOL"):
        build_local_contribution_application(**args, enabled=value)


@pytest.mark.parametrize("field,value", [("utf8_bytes", True), ("text_sha256", "f" * 64),
    ("text", "Different text"), ("notion_ref", "../relative"), ("command_key", "not-a-hash"),
    ("object_ref", "local-content:" + "1" * 32), ("authority", "OFFICIAL"), ("filesystem_path", "synthetic")])
def test_request_is_closed_and_exact(field, value):
    _, request, _ = fixture()
    request[field] = value
    with pytest.raises(ValueError):
        LocalContributionRequest(request)


@pytest.mark.parametrize("field,value", [("max_new_contributions", 2), ("max_new_contributions", True),
    ("utf8_bytes", True), ("target_ref", "relative"), ("authority", "OFFICIAL")])
def test_authority_has_one_effect_and_no_self_admission(field, value):
    args, _, _ = fixture()
    raw = dict(args["authority"].data)
    raw[field] = value
    with pytest.raises(ValueError):
        LocalContributionAuthority(raw)


@pytest.mark.parametrize("field,value", [("authority", "OFFICIAL"), ("official_reference", True),
    ("teacher_acceptance", "ACCEPTED"), ("transmission_admission", "ADOPTED"), ("draft_created_at", "2026-01-01"),
    ("origin_kind", "INSTITUTIONAL")])
def test_provenance_never_confers_official_or_supplier_authority(field, value):
    args, _, _ = fixture()
    raw = args["provenance"].as_dict()
    raw[field] = value
    with pytest.raises(ValueError):
        LocalContributionProvenance(raw)


@pytest.mark.parametrize("field", ["expected_scope_sha256", "expected_package_sha256", "expected_plan_sha256", "expected_prior_review_sha256", "expected_candidate_commit"])
def test_operation_requires_exact_external_candidate_package_plan_and_review(field):
    args, _, calls = fixture()
    args[field] = "f" * (40 if field.endswith("commit") else 64)
    with pytest.raises(ValueError, match="ADOPTION_BINDING"):
        build_local_contribution_application(**args, enabled=True)
    assert args["store"].calls == calls == []


@pytest.mark.parametrize("raw", [b'{"schema":"x","schema":"x"}', b'{"schema":NaN}', b'[]', b'{}', b'not-json'])
def test_owner_proof_rejects_ambiguous_json_even_with_matching_hash(raw):
    args, _, _ = fixture()
    authority, provenance = dict(args["authority"].data), args["provenance"].as_dict()
    authority["operation_authorization_sha256"] = provenance["operation_authorization_sha256"] = hashlib.sha256(raw).hexdigest()
    args.update(authority=LocalContributionAuthority(authority), provenance=LocalContributionProvenance(provenance), owner_operation_evidence=raw)
    with pytest.raises(ValueError):
        build_local_contribution_application(**args)


@pytest.mark.parametrize("field", ["text_sha256", "utf8_bytes", "local_context_sha256"])
def test_valid_request_outside_admission_has_no_store_or_reference_effect(field):
    args, request, calls = fixture()
    authority = dict(args["authority"].data)
    authority[field] = authority[field] + 1 if field == "utf8_bytes" else "f" * 64
    # Policy command is intentionally instantiated directly to probe its own gate.
    from backend.modules.resource_library.application.commands.register_local_contribution import (
        RegisterLocalContribution,
    )
    from backend.shared_kernel.correlation import CorrelationId
    provenance = args["provenance"].as_dict()
    if field == "local_context_sha256":
        provenance[field] = authority[field]
    command = RegisterLocalContribution(args["store"], authority=LocalContributionAuthority(authority),
        provenance=LocalContributionProvenance(provenance), reference_reader=args["reference_reader"], enabled=True)
    with pytest.raises(ValueError, match="OUTSIDE_ADMISSION"):
        command.execute(LocalContributionRequest(request), correlation=CorrelationId("synthetic"))
    assert args["store"].calls == calls == []


def test_another_store_binding_is_rejected_before_creation_or_reference(monkeypatch):
    args, request, calls = fixture()
    attestation = args["store"].attest()
    attestation["binding_sha256"] = "f" * 64
    args["store"].calls.clear()
    monkeypatch.setattr(args["store"], "attest", lambda: attestation)
    with pytest.raises(ValueError, match="TARGET_CHANGED"):
        build_local_contribution_application(**args, enabled=True).register(request, correlation="synthetic")
    assert args["store"].calls == calls == []


def test_incomplete_operation_refuses_allocation_and_never_retries(monkeypatch):
    args, request, _ = fixture()
    args["store"].state = "UNKNOWN"
    def forbidden():
        raise AssertionError("NO_ALLOCATION_AFTER_UNKNOWN")
    monkeypatch.setattr("backend.modules.resource_library.application.commands.register_local_contribution.uuid4", forbidden)
    result = build_local_contribution_application(**args, enabled=True).register(request, correlation="synthetic")
    assert result.outcome_status == OutcomeStatus.INDETERMINATE and result.success is False
    assert result.application_failure.message_key == "LOCAL_CONTRIBUTION_RECONCILE_REQUIRED"
    assert result.side_effects[0]["effect_state"] == "UNKNOWN"
    assert result.side_effects[0]["reconciliation_required"] is True
    assert "append" not in args["store"].calls


@pytest.mark.parametrize("uncertain,status", [(True, OutcomeStatus.INDETERMINATE), (False, OutcomeStatus.FAILED)])
def test_persistence_failure_is_not_success_and_preserves_uncertainty(uncertain, status):
    args, request, _ = fixture()
    args["store"].failure = LocalContributionPersistenceError("SYNTHETIC_FAILURE", uncertain=uncertain)
    result = build_local_contribution_application(**args, enabled=True).register(request, correlation="synthetic")
    assert result.outcome_status == status and result.success is False
    assert result.side_effects[0]["effect_state"] == ("UNKNOWN" if uncertain else "NONE")
    assert args["store"].calls.count("append") == 1


@pytest.mark.parametrize("field,value", [("authority", "OFFICIAL"), ("created_at", "no-date"), ("object_ref", "content:borrowed")])
def test_corrupt_record_or_added_authority_is_rejected(field, value):
    args, request, _ = fixture()
    build_local_contribution_application(**args, enabled=True).register(request, correlation="synthetic")
    raw = args["store"].record.as_dict()
    raw[field] = value
    with pytest.raises(ValueError):
        LocalContributionRecord(raw)


def test_read_requires_exact_allocated_refs_and_record_hash():
    args, request, _ = fixture()
    app = build_local_contribution_application(**args, enabled=True)
    app.register(request, correlation="synthetic")
    read = read_request(args["store"].record)
    changed = copy.deepcopy(read)
    changed["record_sha256"] = "f" * 64
    with pytest.raises(ValueError):
        app.read(changed)
    changed = copy.deepcopy(read)
    changed["version_ref"] = "local-version:" + "f" * 32
    with pytest.raises(ValueError):
        app.read(changed)
    changed["provider_calls"] = 0
    with pytest.raises(ValueError):
        LocalContributionRead(changed)


def test_mutated_local_provenance_cannot_replay_or_read_under_same_authority():
    args, request, _ = fixture()
    app = build_local_contribution_application(**args, enabled=True)
    app.register(request, correlation="synthetic")
    raw = args["store"].record.as_dict()
    raw["provenance"]["author"] = "Synthetic other author"
    args["store"].record = LocalContributionRecord(raw)
    with pytest.raises(ValueError, match="PROVENANCE"):
        app.read(read_request(args["store"].record))
    with pytest.raises(ValueError, match="RECONCILE_REQUIRED"):
        app.register(request, correlation="synthetic")


def test_v2_unknown_creation_original_recording_and_application_creation_are_distinct():
    args, request, calls = fixture_v2()
    off = build_local_contribution_application(**args)
    with pytest.raises(ValueError, match="DISABLED"):
        off.register(request, correlation="synthetic")
    assert args["store"].calls == calls == []
    app = build_local_contribution_application(**args, enabled=True)
    assert app.register(request, correlation="synthetic").success
    record = args["store"].record
    projection = app.read(read_request(record))["source_snapshot"]
    origin = projection["provenance"]["origin"]
    assert origin["draft_created_at"] is None and origin["draft_creation_status"] == "NOT_ESTABLISHED"
    assert origin["draft_recorded_at"] == "2001-01-01T01:02:03+00:00"
    assert record.data["created_at"] != origin["draft_recorded_at"] and record.data["created_at"] is not None
    assert origin["author_kind"] == "SUBAGENT" and origin["author"] == "SUBAGENT_SYNTHETIC"
    assert origin["recording_basis"] == "ORIGINAL_PROPOSAL_RECEIPT"
    assert origin["original_proposal_receipt_sha256"] == hashlib.sha256(args["original_proposal_receipt_evidence"]).hexdigest()
    assert args["original_proposal_receipt_evidence"].decode() not in str(projection)


def test_v1_stays_strict_and_is_not_implicitly_migrated_to_v2():
    args, _, _ = fixture()
    assert type(parse_local_contribution_provenance(args["provenance"].as_dict())) is LocalContributionProvenance
    raw = args["provenance"].as_dict()
    raw["draft_created_at"] = None
    with pytest.raises(ValueError, match="DATE"):
        LocalContributionProvenance(raw)
    v2, _, _ = fixture_v2()
    with pytest.raises(ValueError):
        LocalContributionProvenance(v2["provenance"].as_dict())
    assert type(parse_local_contribution_provenance(v2["provenance"].as_dict())) is LocalContributionProvenanceV2
    raw = args["provenance"].as_dict()
    raw["draft_recorded_at"] = "2001-01-01T01:02:03+00:00"
    with pytest.raises(ValueError):
        LocalContributionProvenance(raw)


@pytest.mark.parametrize("field,value", [("draft_created_at", "2001-01-01T01:02:03+00:00"),
    ("draft_created_at", ""), ("draft_creation_status", "ESTABLISHED"), ("draft_recorded_at", "2001-01-01"),
    ("recording_basis", "FILE_MTIME"), ("author_kind", "HUMAN"), ("author", "Synthetic teacher"),
    ("original_proposal_receipt_ref", "../file"), ("original_proposal_receipt_sha256", "f" * 64),
    ("authority", "OFFICIAL"), ("teacher_acceptance", "ACCEPTED"), ("additional_field", True)])
def test_v2_does_not_invent_creation_authority_or_recording_basis(field, value):
    args, _, _ = fixture_v2()
    raw = args["provenance"].as_dict()
    raw[field] = value
    with pytest.raises(ValueError):
        LocalContributionProvenanceV2(raw)


@pytest.mark.parametrize("field,value", [("original_proposal_receipt_evidence", None),
    ("expected_original_proposal_receipt_sha256", None), ("expected_original_proposal_receipt_sha256", "f" * 64),
    ("original_proposal_receipt_evidence", b"FORGED"), ("original_proposal_receipt_evidence", "not-bytes")])
def test_v2_factory_requires_the_exact_trusted_original_bytes_and_hash(field, value):
    args, _, calls = fixture_v2()
    args[field] = value
    with pytest.raises(ValueError, match="ORIGINAL_PROPOSAL"):
        build_local_contribution_application(**args, enabled=True)
    assert args["store"].calls == calls == []


@pytest.mark.parametrize("field,value", [("author", "SUBAGENT_OTHER"), ("timestamp_utc", "2001-01-02T01:02:03+00:00"),
    ("schema", "OTHER_RECEIPT"), ("status", "ADOPTED"), ("contribution_kind", "OFFICIAL"),
    ("authority", "OFFICIAL"), ("official_reference", True), ("transmission_admission", "ADOPTED"),
    ("proposed_local_text", "CHANGED"), ("proposed_local_text_utf8_bytes", True), ("proposed_local_text_sha256", "f" * 64)])
def test_v2_original_fields_are_checked_even_when_a_synthetic_scope_is_self_consistent(field, value):
    import json
    args, _, calls = fixture_v2()
    original = json.loads(args["original_proposal_receipt_evidence"])
    original[field] = value
    raw = encoded(original)
    rebind_synthetic_v2(args, dict(args["authority"].data), args["provenance"].as_dict(), raw)
    with pytest.raises(ValueError):
        build_local_contribution_application(**args, enabled=True)
    assert args["store"].calls == calls == []


@pytest.mark.parametrize("raw", [b'{"schema":"x","schema":"x"}', b'{"schema":NaN}', b'[]', b'{}', b'not-json', b'\xff'])
def test_v2_original_json_is_utf8_and_unambiguous(raw):
    args, _, calls = fixture_v2()
    rebind_synthetic_v2(args, dict(args["authority"].data), args["provenance"].as_dict(), raw)
    with pytest.raises(ValueError):
        build_local_contribution_application(**args)
    assert args["store"].calls == calls == []


@pytest.mark.parametrize("field,value", [("original_proposal_receipt_evidence", b"SYNTHETIC_UNUSED"),
    ("expected_original_proposal_receipt_sha256", "f" * 64)])
def test_v1_refuses_original_receipt_inputs_instead_of_ignoring_them(field, value):
    args, _, calls = fixture()
    args[field] = value
    with pytest.raises(ValueError, match="UNUSED_ORIGINAL_PROPOSAL"):
        build_local_contribution_application(**args)
    assert args["store"].calls == calls == []
