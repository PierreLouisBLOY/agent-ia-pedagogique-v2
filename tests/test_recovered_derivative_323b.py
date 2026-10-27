"""Pure local repair plus every normal deterministic content/business guard."""

from __future__ import annotations

import json
import re

import pytest

from backend.adapters.outbound.generation.openai.p0_content import INSTRUCTIONS, content_schema
from backend.infrastructure.composition.factories.captured_content_validation import (
    NormalCapturedContentValidation,
)
from backend.modules.pedagogical_context.contracts.dto.p0_context import P0Context
from backend.modules.pedagogical_design.application.commands.repair_adopted_capture import (
    RepairAdoptedCapture,
)
from backend.modules.pedagogical_design.application.commands.repair_captured_sections import (
    RepairCapturedSectionIds,
)
from backend.modules.pedagogical_design.contracts.dto.assessment_bundle import fingerprint
from backend.modules.pedagogical_design.contracts.dto.p0_production import (
    P0_PROVENANCE_LABEL,
    _question_id,
)
from backend.modules.pedagogical_design.contracts.dto.section_identity import QUESTION_ID_PATTERN
from backend.modules.work_orchestration.application.commands.prepare_recovered_capture import (
    PrepareRecoveredCapture,
)
from backend.modules.work_orchestration.contracts.dto.rejected_capture import (
    RejectedCapture,
    RejectedCaptureRequest,
)


@pytest.mark.parametrize("identity,valid", [("Q1", True), ("Q_DOC1", True), ("q1", False),
    ("Q1\n", False), ("Q", False), ("Q" + "A" * 63, True), ("Q" + "A" * 64, False)])
def test_question_schema_matches_canonical_guard(identity, valid):
    for field in ("questions", "corrections", "marking"):
        pattern = content_schema()["properties"][field]["items"]["properties"]["question_id"]["pattern"]
        assert pattern == QUESTION_ID_PATTERN and pattern in INSTRUCTIONS
        assert bool(re.search(pattern, identity)) is valid
    if valid:
        assert _question_id(identity) == identity
    else:
        with pytest.raises(ValueError, match="P0_QUESTION_ID"):
            _question_id(identity)


def test_unadopted_repair_plan_refused():
    with pytest.raises(ValueError, match="LOCAL_REPAIR_EXACT_ADOPTED_PLAN_REQUIRED"):
        RepairAdoptedCapture({"scope": "synthetic-unadopted"})


def content():
    return {
        "title": "Exercice synthétique sur la perception",
        "sections": [
            {
                "section_id": "s1",
                "heading": "Situation fictive",
                "text": "FICTIF : Nora écrit un rappel collectif.",
            },
            {
                "section_id": "s2",
                "heading": "Consigne",
                "text": "Lisez ce message sans inventer de faits.",
            },
        ],
        "questions": [
            {"question_id": "Q1", "prompt": "Relevez un fait observable.", "options": []}
        ],
        "corrections": [
            {
                "question_id": "Q1",
                "expected_answer": "Nora écrit un rappel.",
                "rationale": "Le message est explicite.",
            }
        ],
        "marking": [],
        "limitations": ["CANDIDATE — contenu synthétique non validé pédagogiquement."],
    }


def capture(proposed=None, *, evidence_changed=False):
    context = P0Context(
        {
            "contract_id": "R6-P0-CONTEXT-1.0",
            "resource_type": "EXERCISE",
            "question_mode": None,
            "level": "FIRST_STMG",
            "discipline": "Sciences de gestion",
            "topics": ["Perception"],
            "objectives": ["Distinguer fait et interprétation"],
            "difficulty": "STANDARD",
            "language": "fr",
            "duration_minutes": None,
            "total_points": None,
        }
    )
    text = "Perception"
    import hashlib

    ref = {
        "evidence_id": "evidence:" + "a" * 32,
        "source_ref": "notion:synthetic323b",
        "locator": "search-chunk:synthetic323b",
        "checksum_or_version": "a" * 64,
        "excerpt_sha256": hashlib.sha256(text.encode()).hexdigest(),
        "provenance_label": P0_PROVENANCE_LABEL,
    }
    dispatch = {
        "contract_id": "R6-P0-DISPATCH-1.0",
        "production_ref": "prod:" + "a" * 32,
        "version_ref": "ver:" + "a" * 32,
        "context": context.as_dict(),
        "context_sha256": context.sha256,
        "references": [ref],
        "evidence": {ref["evidence_id"]: "WRONG" if evidence_changed else text},
        "lineage": {
            "source_run_id": "run:" + "a" * 32,
            "source_step_id": "step:" + "a" * 32,
            "evidence_set_ref": "evidence:" + "a" * 32,
            "source_request_id": "req:" + "a" * 32,
            "conversation_id": "conv:" + "a" * 32,
            "context_sha256": context.sha256,
            "parent_version_ref": None,
        },
    }
    request = RejectedCaptureRequest(
        "d" * 32, "a" * 64, "b" * 64, 100, "c" * 64, "e" * 64, "f" * 64
    )
    return RejectedCapture(
        request,
        dispatch,
        json.dumps(proposed or content(), ensure_ascii=False),
        {
            "result_sha256": "c" * 64,
            "response_status": "completed",
            "outcome_marker": "PARSING_REJECTED",
        },
    )


def test_case_only_mapping_exact_and_injective():
    before = content()
    repaired = RepairCapturedSectionIds().execute(before)
    assert repaired.audit["mapping"] == {"s1": "S1", "s2": "S2"}
    assert [list(row["field_path"]) for row in repaired.audit["diff"]] == [
        ["sections", 0, "section_id"],
        ["sections", 1, "section_id"],
    ]
    after = json.loads(json.dumps(dict(before)))
    for row in after["sections"]:
        row["section_id"] = row["section_id"].upper()
    assert fingerprint(repaired.content) == fingerprint(after)
    assert before == content()


@pytest.mark.parametrize(
    "fault", ["duplicate", "collision", "text_ref", "unknown_ref", "unrepairable"]
)
def test_ambiguous_repair_refused(fault):
    value = content()
    if fault == "duplicate":
        value["sections"][1]["section_id"] = "s1"
    if fault == "collision":
        value["sections"][1]["section_id"] = "S1"
    if fault == "text_ref":
        value["questions"][0]["prompt"] = "Relisez la section s1."
    if fault == "unknown_ref":
        value["questions"][0]["section_id"] = "s1"
    if fault == "unrepairable":
        value["sections"][0]["section_id"] = "document 1"
    with pytest.raises(ValueError):
        RepairCapturedSectionIds().execute(value)


def test_full_normal_guards_and_candidate_validation_without_effect():
    original = capture()
    usecase = PrepareRecoveredCapture(NormalCapturedContentValidation())
    first = usecase.execute(original)
    second = usecase.execute(original)
    assert first.record.sha256 == second.record.sha256
    assert first.record.production_ref != original.dispatch["production_ref"]
    assert first.record.version_ref != original.dispatch["version_ref"]
    assert first.record.p0_bundle.data["lineage"]["parent_version_ref"] is None
    assert first.record.data["reviews"] == first.record.data["validations"] == ()
    assert first.audit["business_validation"]["status"] == "PASS"
    assert first.audit["normal_guard"]["guard_disposition"] in {"ALLOW", "ALLOW_WITH_WARNINGS"}
    assert first.audit["publication"] == "NOT_PERFORMED"
    assert first.record.p0_bundle.student_projection()["questions"]
    assert "Nora écrit un rappel." not in str(first.record.p0_bundle.student_projection())
    assert "Nora écrit un rappel." in str(first.record.p0_bundle.teacher_projection())


@pytest.mark.parametrize(
    "fault,code",
    [
        ("question_id", "P0_QUESTION_ID"),
        ("correction_link", "P0_QUESTION_CORRECTION_LINKS"),
        ("options", "P0_OPEN_QUESTION_OPTIONS"),
        ("marking", "P0_MARKING_ASSESSMENT_ONLY"),
        ("candidate_label", "LOCAL_RECOVERY_NON_ID_CHANGE_BY_BINDING"),
    ],
)
def test_non_identifier_business_failures_remain_failures(fault, code):
    value = content()
    if fault == "question_id":
        value["questions"][0]["question_id"] = "q1"
    if fault == "correction_link":
        value["corrections"] = []
    if fault == "options":
        value["questions"][0]["options"] = ["Une option"]
    if fault == "marking":
        value["marking"] = [{"question_id": "Q1", "points": "1.00", "criteria": ["Fait"]}]
    if fault == "candidate_label":
        value["limitations"] = ["Relecture nécessaire."]
    with pytest.raises(ValueError, match=code):
        PrepareRecoveredCapture(NormalCapturedContentValidation()).execute(capture(value))


def test_changed_evidence_not_admitted():
    with pytest.raises(ValueError):
        PrepareRecoveredCapture(NormalCapturedContentValidation()).execute(
            capture(evidence_changed=True)
        )


def test_input_capture_not_modified():
    original = capture()
    before = (original.output_text, fingerprint(original.dispatch), fingerprint(original.metadata))
    PrepareRecoveredCapture(NormalCapturedContentValidation()).execute(original)
    assert before == (
        original.output_text,
        fingerprint(original.dispatch),
        fingerprint(original.metadata),
    )


def test_independent_diagnosis_does_not_erase_question_schema_failure():
    from backend.modules.pedagogical_design.application.commands.diagnose_captured_content import (
        diagnose_captured_content,
    )

    item = capture()
    value = content()
    value["questions"][0]["question_id"] = "q1"
    value["corrections"][0]["question_id"] = "q1"
    repaired = RepairCapturedSectionIds().execute(value)
    report = diagnose_captured_content(item.dispatch, repaired.content)
    checks = {row["check"]: row for row in report["checks"]}
    assert checks["SECTION_SCHEMA"]["status"] == "PASS"
    assert checks["QUESTION_SCHEMA"]["code"] == "P0_QUESTION_ID"
    assert checks["CORRECTION_SCHEMA"]["code"] == "P0_QUESTION_ID"
    assert checks["QUESTION_CORRECTION_LINKS_AND_FAMILY_SHAPE"]["status"] == "PASS"
    assert report["normal_full_candidate"] == "REFUSED_IF_ANY_SCHEMA_FAILURE"
