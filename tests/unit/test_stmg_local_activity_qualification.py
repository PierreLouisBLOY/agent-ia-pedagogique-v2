"""Synthetic local qualification tests; no SQL, stores, secrets or provider."""
from __future__ import annotations

import copy
import hashlib
import json

import pytest

from backend.adapters.inbound.application.stmg_local_activity import STMGLocalActivityInbound
from backend.infrastructure.composition.factories.stmg_local_activity import (
    build_stmg_local_activity_application,
)
from backend.modules.knowledge_reference.contracts.dto.admitted_institutional_sources import (
    ADMITTED_DOCUMENTS,
    OWNER_ADMISSION_SHA256,
)
from backend.modules.knowledge_reference.contracts.dto.stmg_frames import STMG_FRAMES
from backend.modules.pedagogical_context.contracts.dto.stmg_local_activity import (
    LocalActivityChoice,
    LocalActivityOwnerScope,
    project_local_capacities,
)
from backend.modules.pedagogical_design.contracts.dto.assessment_bundle import fingerprint
from backend.modules.work_orchestration.application.queries.stmg_local_activity import (
    PrepareSTMGLocalActivity,
)


def fixture(*, mode="QUIZ", host="MSDGN_TERMINALE_COMMON", support="SGN_PREMIERE", insufficient=False):
    text = "Synthetic complete disciplinary definition for the selected local activity."
    source = {"notion_ref": "notion:synthetic", "object_ref": "content:synthetic", "object_kind": "PEDAGOGICAL_CONTENT",
        "passage_ref": "chunk:synthetic", "version_or_checksum": "version:synthetic", "excerpt": text,
        "excerpt_truncated": False, "provenance": {"origin": "SYNTHETIC_UNIT_FIXTURE"},
        "source_status": {"lifecycle": "UNKNOWN"}, "authority": "UNKNOWN"}
    identity = {k: source[k] for k in ("notion_ref", "object_ref", "object_kind", "passage_ref", "version_or_checksum")}
    identity.update(excerpt_sha256=hashlib.sha256(text.encode()).hexdigest(), utf8_bytes=len(text.encode()))
    position = {"frame": host, "level": STMG_FRAMES[host][0], "discipline": STMG_FRAMES[host][6],
        "program_ref": "programme:synthetic-host", "program_version": "version:synthetic-host",
        "document_ref": "document:synthetic-host", "document_sha256": ADMITTED_DOCUMENTS["A03" if host.startswith("MSDGN") else "A02"],
        "theme_ref": "theme:synthetic", "question_ref": "question:synthetic-host", "capacity_refs": ["capacity:synthetic-host"]}
    question = {"id": "question:synthetic-support", "version_ref": "version:synthetic-support",
        "document_ref": "document:synthetic-support", "element_type": "QUESTION", "page": 9, "page_end": 9,
        "official_text": "Synthetic parent text. Identify indicators. Compare dimensions."}
    fragment = {"purpose": "REACTIVATED_FOUNDATION" if support != host else "POSITIONING_SUPPORT",
        "frame": support, "level": STMG_FRAMES[support][0], "program_ref": "programme:synthetic-support",
        "program_version": "version:synthetic-support", "document": {"id": "document:synthetic-support",
            "candidate_id": "A03" if support.startswith("MSDGN") else "A02",
            "sha256": ADMITTED_DOCUMENTS["A03" if support.startswith("MSDGN") else "A02"]},
        "question": question, "typed_capacities": [], "local_extracted_capacities": [],
        "native_relation_status": "ADMITTED_AT_FOUNDATION_ONLY" if support != host else "NOT_ADMITTED_FOR_POSITIONING"}
    basis = {"contract_id": "STMG-LOCAL-PROGRAMME-SUPPORT-1.0", "owner_admission_sha256": OWNER_ADMISSION_SHA256,
        "positioning": position, "fragments": [fragment]}
    choice = {"contract_id": "STMG-LOCAL-ACTIVITY-CHOICE-1.0", "choice_ref": "local-choice:SYNTHETIC_UNIT",
        "resource_type": "QUESTION_SET", "question_mode": mode, "role": "REACTIVATION",
        "positioning": position, "programme_support_sha256": fingerprint(basis), "source_identity": identity,
        "source_snapshot_sha256": fingerprint(source), "owner_local_decision_sha256": "0" * 64,
        "native_relationship_status": "NOT_ADMITTED_FOR_POSITIONING",
        "support_status": "INSUFFICIENT_FOR_HISTORICAL_CONTENT" if insufficient else "LIMITED_FOR_LOCAL_PREPARATION",
        "support_limits": ["SYNTHETIC_ONLY_NOT_AN_OFFICIAL_ATTACHMENT_OR_LIVE_QUALIFICATION"]}
    return choice, basis, source


def scope_for(choices, *, owner_sha="0" * 64):
    return LocalActivityOwnerScope({"contract_id": "STMG-LOCAL-ACTIVITY-OWNER-SCOPE-1.0",
        "owner_local_decision_sha256": owner_sha, "owner_proposal_sha256": "1" * 64,
        "decision_item": 0, "choice_sha256s": sorted(LocalActivityChoice(c).sha256 for c in choices),
        "qualification_scope": "LOCAL_QUALIFICATION_ONLY", "evidence_kind": "TECHNICAL_TRANSCRIPTION_NOT_SIGNATURE"})


def query(choice, basis, source, *, enabled=True):
    scope = scope_for([choice])
    return PrepareSTMGLocalActivity([choice], owner_scope=scope, expected_owner_scope_sha256=scope.sha256,
        basis_reader=lambda _: basis, source_reader=lambda _: source, enabled=enabled)


def execute(choice, basis, source):
    return STMGLocalActivityInbound(query(choice, basis, source)).prepare(
        choice_sha256=LocalActivityChoice(choice).sha256)


def test_default_off_refuses_before_callbacks_and_metadata_has_no_rows():
    choice, _, _ = fixture()
    def forbidden(*_):
        raise AssertionError("NO_BOUNDARY_INVOCATION_WHEN_DISABLED")
    scope = scope_for([choice])
    local = PrepareSTMGLocalActivity([choice], owner_scope=scope, expected_owner_scope_sha256=scope.sha256,
        basis_reader=forbidden, source_reader=forbidden)
    assert local.metadata() == []
    with pytest.raises(ValueError, match="LOCAL_ACTIVITY_DISABLED"):
        local.execute(LocalActivityChoice(choice).sha256)


@pytest.mark.parametrize("mode", ["QCM", "QUIZ", "OPEN_QUESTIONS"])
def test_readiness_is_local_without_dispatch_grant_or_native_relation(mode):
    choice, basis, source = fixture(mode=mode)
    result = execute(choice, basis, source)
    assert result["state"] == "LOCAL_CONTEXT_SUPPORTED_FOR_PREPARATION"
    assert result["provider_dispatch_allowed"] is False
    assert result["transmission_admission"] == "NOT_ADOPTED"
    assert result["native_relationship_status"] == "NOT_ADMITTED_FOR_POSITIONING"
    assert result["institutional_alignment"] == "UNVERIFIED_FOR_LOCAL_ACTIVITY"
    assert result["teacher_acceptance"] == "NOT_PERFORMED"
    assert result["source_authority"] == "UNKNOWN"
    assert "generate" not in dir(query(choice, basis, source))
    assert not {"grant", "budget", "slot", "reservation", "production_ref", "version_ref"} & result.keys()


def test_first_source_and_final_positioning_are_kept_separate():
    choice, basis, source = fixture()
    result = execute(choice, basis, source)
    assert result["positioning"]["level"] == "FINAL_STMG"
    assert result["programme_support"]["fragments"][0]["level"] == "FIRST_STMG"
    assert result["programme_support"]["fragments"][0]["purpose"] == "REACTIVATED_FOUNDATION"


def test_insufficient_support_remains_a_refusal_of_completeness():
    choice, basis, source = fixture(mode="QCM", host="SGN_PREMIERE", support="SGN_PREMIERE", insufficient=True)
    choice["role"] = "PREPARATORY_READING"
    result = execute(choice, basis, source)
    assert result["state"] == "LOCAL_CONTEXT_CONTENT_INSUFFICIENT"
    assert result["support_status"] == "INSUFFICIENT_FOR_HISTORICAL_CONTENT"
    assert result["support_limits"]


@pytest.mark.parametrize("mutation", ["authority", "text", "version", "provenance", "status", "private", "oracle", "teacher", "truncated", "notion"])
def test_native_source_changes_and_exclusions_are_rejected(mutation):
    choice, basis, source = fixture()
    changed = copy.deepcopy(source)
    key, value = {"authority": ("authority", "OFFICIAL"), "text": ("excerpt", "Different source"),
        "version": ("version_or_checksum", "other"), "provenance": ("provenance", {"origin": "forged"}),
        "status": ("source_status", {"lifecycle": "OFFICIAL"}), "private": ("is_private_evidence", True),
        "oracle": ("is_oracle", True), "teacher": ("is_teacher_reference", True),
        "truncated": ("excerpt_truncated", True), "notion": ("notion_ref", "notion:other")}[mutation]
    changed[key] = value
    with pytest.raises(ValueError, match="LOCAL_ACTIVITY_NATIVE_SOURCE_CHANGED_OR_EXCLUDED"):
        execute(choice, basis, changed)


@pytest.mark.parametrize("field,value", [("resource_type", "COURSE"), ("question_mode", "ESSAY"),
    ("role", "OFFICIAL_PRESCRIPTION"), ("native_relationship_status", "RESOLVED_ADMITTED"),
    ("support_status", "GLOBAL_PASS"), ("owner_local_decision_sha256", "forged")])
def test_closed_contract_refuses_wider_scopes(field, value):
    choice, _, _ = fixture()
    choice[field] = value
    with pytest.raises(ValueError):
        LocalActivityChoice(choice)


def test_other_exact_choice_not_in_allowlist_is_rejected_without_effect():
    choice, basis, source = fixture()
    with pytest.raises(ValueError, match="LOCAL_ACTIVITY_NOT_IN_OWNER_SCOPE"):
        query(choice, basis, source).execute("f" * 64)


def test_borrowed_programme_or_document_breaks_the_bound_basis():
    choice, basis, source = fixture()
    for field in ("program_version", "frame"):
        changed = copy.deepcopy(basis)
        changed["fragments"][0][field] = "borrowed"
        with pytest.raises(ValueError, match="LOCAL_ACTIVITY_PROGRAMME_BASIS_CHANGED"):
            execute(choice, changed, source)
    changed = copy.deepcopy(basis)
    changed["fragments"][0]["document"]["sha256"] = "f" * 64
    choice["programme_support_sha256"] = fingerprint(changed)
    with pytest.raises(ValueError, match="LOCAL_ACTIVITY_DOCUMENT_NOT_ADMITTED"):
        execute(choice, changed, source)


def test_reverse_cross_level_relation_cannot_be_fabricated():
    choice, basis, source = fixture(host="SGN_PREMIERE", support="MSDGN_TERMINALE_COMMON")
    with pytest.raises(ValueError, match="LOCAL_ACTIVITY_CROSS_LEVEL_BASIS"):
        execute(choice, basis, source)


def test_local_capacity_projection_has_parent_hash_and_no_native_id():
    _, basis, _ = fixture()
    question = basis["fragments"][0]["question"]
    projected = project_local_capacities(question, ["Identify indicators.", "Compare dimensions."])
    assert all(c["native_capacity_ref"] is None for c in projected)
    assert all(c["projection_kind"] == "LOCAL_EXTRACTED_FROM_ADMITTED_QUESTION" for c in projected)
    assert all(c["parent_question_ref"] == question["id"] for c in projected)
    assert projected[0]["text_sha256"] == hashlib.sha256(b"Identify indicators.").hexdigest()


@pytest.mark.parametrize("phrases", [["Borrowed from another question."], ["Identify indicators.", "Identify indicators."], []])
def test_capacity_from_another_question_or_duplicates_are_refused(phrases):
    _, basis, _ = fixture()
    with pytest.raises(ValueError, match="LOCAL_CAPACITY"):
        project_local_capacities(basis["fragments"][0]["question"], phrases)


def test_local_projection_cannot_be_relabelled_native():
    choice, basis, source = fixture()
    fragment = basis["fragments"][0]
    fragment["local_extracted_capacities"] = project_local_capacities(fragment["question"], ["Identify indicators."])
    fragment["local_extracted_capacities"][0]["native_capacity_ref"] = "capacity:forged"
    choice["programme_support_sha256"] = fingerprint(basis)
    with pytest.raises(ValueError, match="LOCAL_ACTIVITY_LOCAL_CAPACITY_CHANGED"):
        execute(choice, basis, source)


def test_local_metadata_is_never_a_transmission_admission():
    choice, basis, source = fixture()
    rows = query(choice, basis, source).metadata()
    assert len(rows) == 1 and rows[0]["provider_dispatch_allowed"] is False
    assert rows[0]["transmission_admission"] == "NOT_ADOPTED"
    assert "institutional_resolution" not in rows[0]


def fixture_with_selectable_local_capacities():
    choice, basis, source = fixture()
    fragment = basis["fragments"][0]
    fragment["local_extracted_capacities"] = project_local_capacities(
        fragment["question"], ["Identify indicators.", "Compare dimensions."])
    choice["programme_support_sha256"] = fingerprint(basis)
    return choice, basis, source


def test_capacities_are_selectable_through_real_application_inbound_metadata_and_prepare():
    choice, basis, source = fixture_with_selectable_local_capacities()
    inbound = STMGLocalActivityInbound(query(choice, basis, source))
    available = inbound.metadata()[0]["local_capability_choices"]
    assert len(available) == 2
    assert all(c["support_level"] == "FIRST_STMG" and c["positioning_level"] == "FINAL_STMG" for c in available)
    selected_ref = available[1]["local_capacity_ref"]
    result = inbound.prepare(choice_sha256=LocalActivityChoice(choice).sha256,
        selected_local_capacity_refs=[selected_ref])
    assert result["selected_local_capacity_refs"] == [selected_ref]
    assert result["selected_local_capacities"][0]["exact_text"] == "Compare dimensions."
    assert result["selected_local_capacities"][0]["native_capacity_ref"] is None
    assert result["provider_dispatch_allowed"] is False


@pytest.mark.parametrize("bad", [["capacity:synthetic-host"], ["local-capacity:borrowed"], "not-an-array"])
def test_native_borrowed_or_untyped_capacity_selection_is_refused(bad):
    choice, basis, source = fixture_with_selectable_local_capacities()
    with pytest.raises(ValueError, match="LOCAL_ACTIVITY_LOCAL_CAPACITY_SELECTION"):
        query(choice, basis, source).execute(LocalActivityChoice(choice).sha256, selected_local_capacity_refs=bad)


def test_duplicate_capacity_selection_is_refused():
    choice, basis, source = fixture_with_selectable_local_capacities()
    ref = basis["fragments"][0]["local_extracted_capacities"][0]["local_capacity_ref"]
    with pytest.raises(ValueError, match="LOCAL_ACTIVITY_LOCAL_CAPACITY_SELECTION"):
        query(choice, basis, source).execute(LocalActivityChoice(choice).sha256, selected_local_capacity_refs=[ref, ref])


@pytest.mark.parametrize("bad", ["false", "true", 0, 1, None])
def test_enabled_requires_a_real_boolean(bad):
    choice, basis, source = fixture()
    with pytest.raises(ValueError, match="LOCAL_ACTIVITY_ENABLED_BOOL_REQUIRED"):
        query(choice, basis, source, enabled=bad)


def test_same_owner_hash_cannot_authorize_changed_choice_list():
    choice, basis, source = fixture()
    scope = scope_for([choice])
    changed = copy.deepcopy(choice)
    changed["support_limits"] = ["ANOTHER_SCOPE_WITH_THE_SAME_OWNER_HASH"]
    with pytest.raises(ValueError, match="LOCAL_ACTIVITY_OWNER_SCOPE"):
        PrepareSTMGLocalActivity([changed], owner_scope=scope,
            expected_owner_scope_sha256=scope.sha256, basis_reader=lambda _: basis, source_reader=lambda _: source,
            enabled=True)
    expanded = scope_for([choice, changed])
    with pytest.raises(ValueError, match="LOCAL_ACTIVITY_OWNER_SCOPE"):
        PrepareSTMGLocalActivity([choice, changed], owner_scope=expanded,
            expected_owner_scope_sha256=scope.sha256, basis_reader=lambda _: basis, source_reader=lambda _: source,
            enabled=True)


def factory_fixture():
    choice, basis, source = fixture_with_selectable_local_capacities()
    evidence = json.dumps({"schema": "LU-OWNER-LOCAL-DECISIONS-UI-REPLY-1.0", "decisions": [
        {"item": 0, "proposal_sha256": "1" * 64, "answer_verbatim": "SYNTHETIC_LOCAL_QUALIFICATION_ONLY"}]}).encode()
    owner_sha = hashlib.sha256(evidence).hexdigest()
    choice["owner_local_decision_sha256"] = owner_sha
    scope = scope_for([choice], owner_sha=owner_sha)
    return {"choices": [choice], "owner_scope": scope, "expected_owner_scope_sha256": scope.sha256,
        "owner_decision_evidence": evidence, "expected_owner_decision_sha256": owner_sha,
        "basis_reader": lambda _: basis, "source_reader": lambda _: source}


def test_normal_factory_default_off_and_enabled_application_path():
    args = factory_fixture()
    off = build_stmg_local_activity_application(**args)
    assert off.metadata() == []
    with pytest.raises(ValueError, match="LOCAL_ACTIVITY_DISABLED"):
        off.prepare(choice_sha256=args["owner_scope"].data["choice_sha256s"][0])
    on = build_stmg_local_activity_application(**args, enabled=True)
    refs = on.metadata()[0]["local_capability_choices"]
    result = on.prepare(choice_sha256=args["owner_scope"].data["choice_sha256s"][0],
        selected_local_capacity_refs=[refs[0]["local_capacity_ref"]])
    assert result["owner_scope_sha256"] == args["expected_owner_scope_sha256"]
    assert result["owner_evidence_kind"] == "TECHNICAL_TRANSCRIPTION_NOT_SIGNATURE"
    assert len(result["selected_local_capacities"]) == 1
    assert result["provider_dispatch_allowed"] is False


@pytest.mark.parametrize("field,value", [("enabled", "false"), ("owner_decision_evidence", b"forged"),
    ("expected_owner_decision_sha256", "f" * 64), ("expected_owner_scope_sha256", "f" * 64)])
def test_normal_factory_refuses_unverified_scope_or_evidence(field, value):
    args = factory_fixture()
    args[field] = value
    with pytest.raises(ValueError, match="LOCAL_ACTIVITY_"):
        build_stmg_local_activity_application(**args)


def test_factory_refuses_another_proposal_even_with_other_self_consistent_evidence_hash():
    args = factory_fixture()
    evidence = json.loads(args["owner_decision_evidence"])
    evidence["decisions"][0]["proposal_sha256"] = "f" * 64
    args["owner_decision_evidence"] = json.dumps(evidence).encode()
    args["expected_owner_decision_sha256"] = hashlib.sha256(args["owner_decision_evidence"]).hexdigest()
    with pytest.raises(ValueError, match="LOCAL_ACTIVITY_OWNER_SCOPE"):
        build_stmg_local_activity_application(**args)
