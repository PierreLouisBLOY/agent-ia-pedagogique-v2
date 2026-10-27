"""Structured quality and historical compatibility; every I/O root is synthetic."""
import json
import os
import socket
import subprocess
import sys
from copy import deepcopy
from dataclasses import asdict
from io import BytesIO
from pathlib import Path
from xml.etree import ElementTree as ET
from zipfile import ZipFile

import pytest

from backend.adapters.inbound.application.structured_exercise import StructuredExerciseInbound
from backend.adapters.outbound.export.r6_readable_word import R6ReadableWordWriter
from backend.adapters.outbound.generation.openai.p0_content import (
    bind_p0_content,
    build_p0_content_request,
    content_fields_for,
)
from backend.adapters.outbound.generation.openai.p0_exercise_schema import exercise_content_schema
from backend.adapters.outbound.generation.openai.p0_normal import NormalP0GenerationAdapter
from backend.infrastructure.composition.factories.local_browser import build_saved_application
from backend.modules.materialization_export.application.commands.export_saved import (
    ExportSavedCommand,
)
from backend.modules.pedagogical_context.contracts.dto.p0_context import P0Context
from backend.modules.pedagogical_design.application.commands.prepare_structured_exercise import (
    PrepareStructuredExercise,
)
from backend.modules.pedagogical_design.contracts.dto.assessment_bundle import as_plain, fingerprint
from backend.modules.pedagogical_design.contracts.dto.exercise_profile import StructuredExercise
from backend.modules.pedagogical_design.contracts.dto.p0_production import P0Production
from backend.modules.validation_control.application.commands.validate_p0 import ValidateP0Command
from tests.exercise_quality_fixture import blueprint

W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"


@pytest.fixture(autouse=True)
def deny_network(monkeypatch):
    def denied(*args, **kwargs):
        raise AssertionError("NO_NETWORK_IN_QUALITY_LOT")
    monkeypatch.setattr(socket.socket, "connect", denied)


def prepare(dispatch=None, content=None):
    d, c = blueprint()
    return StructuredExerciseInbound(PrepareStructuredExercise()).prepare(dispatch or d, content or c)


def test_real_commands_closed_structure_and_no_acceptance():
    d, c = blueprint()
    original = deepcopy(c)
    record = prepare(d, c)
    bundle = record.p0_bundle
    report = ValidateP0Command().execute(bundle)
    assert report["status"] == "PASS" and report["dispatch_permitted"] is False
    assert report["pedagogical_acceptance"] == "NOT_PERFORMED"
    assert record.data["reviews"] == record.data["validations"] == ()
    assert bundle.data["contract_id"] == "P0-PRODUCTION-EXERCISE-1.0"
    assert bundle.context.data["institutional_resolution"]["status"] == "CONTENT_GAP"
    assert content_fields_for(d) == {"title", "exercise", "limitations"}
    assert bind_p0_content(d, c).sha256 == bundle.sha256
    assert c == original


@pytest.mark.parametrize("fault,code", [
    ("two_questions", "EXERCISE_SINGLE_QUESTION_BINDING"),
    ("wrong_question", "EXERCISE_SINGLE_QUESTION_BINDING"),
    ("wrong_program", "EXERCISE_PROGRAM_BINDING"),
    ("absent_relation", "EXERCISE_FOCUS_RELATION_MISSING"),
    ("other_capacity", "EXERCISE_FOCUS_COVERAGE"),
])
def test_exact_focus_refusals(fault, code):
    d, _ = blueprint()
    context = d["context"]
    resolution = context["institutional_resolution"]
    if fault == "two_questions":
        resolution["question"]["official_label"] = "Comment définir les différents types d'organisation ? Comment un individu devient-il acteur dans une organisation ?"
    elif fault == "wrong_question":
        resolution["question"]["id"] = "types-organisation"
    elif fault == "wrong_program":
        resolution["program_version"] = "another-version"
    elif fault == "absent_relation":
        resolution["notions"][0].pop("question_ref")
    else:
        resolution["capacities"][0]["capacity_ref"] = "other"
    with pytest.raises(ValueError, match=code):
        P0Context(context)


@pytest.mark.parametrize("fault,code", [
    ("missing_capacity", "EXERCISE_CAPABILITY_COVERAGE"),
    ("extra_capacity", "EXERCISE_CAPABILITY_COVERAGE"),
    ("unknown_document", "EXERCISE_DOCUMENT_LINK"),
    ("unused_document", "EXERCISE_UNUSED_DOCUMENT"),
    ("bad_sequence", "EXERCISE_QUESTION_SEQUENCE"),
    ("bad_progression", "EXERCISE_GRADUATION"),
    ("missing_apply", "EXERCISE_GRADUATION"),
    ("duplicate_answer", "EXERCISE_ANSWER_LINKS"),
    ("missing_remediation", "EXERCISE_REQUIRED"),
    ("false_observation", "EXERCISE_PROVENANCE"),
    ("invented_reference", "EXERCISE_UNSUPPLIED_REFERENCE"),
    ("fictive_evidence", "EXERCISE_FICTION_EVIDENCE"),
    ("zero_space", "EXERCISE_RESPONSE_SPACE"),
    ("bool_space", "EXERCISE_RESPONSE_SPACE"),
    ("empty_criterion", "BUNDLE_TEXT"),
])
def test_quality_refusals(fault, code):
    d, c = blueprint()
    ex = c["exercise"]
    if fault == "missing_capacity":
        ex["objectives"].pop()
    elif fault == "extra_capacity":
        ex["questions"][0]["capability_ids"].append("C99")
    elif fault == "unknown_document":
        ex["questions"][0]["document_ids"] = ["D99"]
    elif fault == "unused_document":
        ex["documents"].append({**ex["documents"][0], "document_id": "D3"})
    elif fault == "bad_sequence":
        ex["questions"][0]["question_id"] = "Q01"
    elif fault == "bad_progression":
        ex["questions"][0]["stage"] = "APPLY"
    elif fault == "missing_apply":
        ex["questions"][-1]["stage"] = "ANALYSE"
    elif fault == "duplicate_answer":
        ex["teacher_answers"][-1]["question_id"] = "Q1"
    elif fault == "missing_remediation":
        ex["teacher_answers"][0].pop("remediation")
    elif fault == "false_observation":
        ex["situation"]["provenance"] = "OBSERVED_REAL"
    elif fault == "invented_reference":
        ex["documents"][0].update(provenance="SUPPLIED_REFERENCE", evidence_id="evidence:" + "f" * 32)
    elif fault == "fictive_evidence":
        ex["situation"]["evidence_id"] = "evidence:" + "b" * 32
    elif fault == "zero_space":
        ex["questions"][0]["answer_lines"] = 0
    elif fault == "bool_space":
        ex["questions"][0]["answer_lines"] = True
    else:
        ex["questions"][0]["success_criteria"] = [""]
    with pytest.raises(ValueError) as raised:
        prepare(d, c)
    if fault == "missing_remediation":
        assert "FIELD" in str(raised.value) or "SHAPE" in str(raised.value)
    elif fault == "empty_criterion":
        assert str(raised.value) == "ASSESSMENT_TEXT"
    else:
        assert str(raised.value) == code


def test_closed_student_projection_and_actual_docx_no_teacher_fields():
    d, c = blueprint()
    for index, answer in enumerate(c["exercise"]["teacher_answers"]):
        for field in ("expected_answer", "rationale", "vigilance", "remediation"):
            answer[field] = "TEACHER_ONLY_" + field + str(index)
    record = prepare(d, c)
    student = record.p0_bundle.student_projection()
    assert "teacher_answers" not in student["exercise"]
    exporter = ExportSavedCommand(R6ReadableWordWriter(profile="product-v7"), product_projection=True)
    with ZipFile(BytesIO(exporter.execute(record, "student"))) as z:
        assert all(b"TEACHER_ONLY_" not in z.read(name) for name in z.namelist())
        root = ET.fromstring(z.read("word/document.xml"))
        margins = root.find(".//" + W + "pgMar")
        assert margins.get(W + "left") == "850"
    with ZipFile(BytesIO(exporter.execute(record, "correction"))) as z:
        text = z.read("word/document.xml")
        assert b"TEACHER_ONLY_remediation3" in text
        paragraphs = ET.fromstring(text).find(W + "body").findall(W + "p")
        protected = [p for p in paragraphs if "TEACHER_ONLY_" in "".join(p.itertext())]
        assert len(protected) == 16
        assert all(p.find(W + "pPr/" + W + "keepNext") is not None
                   and p.find(W + "pPr/" + W + "keepLines") is not None for p in protected)


def test_r4_synthetic_save_reopen_preserves_exact_record_and_exports(tmp_path):
    record = prepare()
    application = build_saved_application(tmp_path / "library", create=True)
    result = application.service.save(record)
    assert result["saved"] is True
    reopened = application.execute("open", record.production_ref, record.version_ref, correlation="quality-323b")
    assert reopened["record_sha256"] == record.sha256
    for kind in ("student", "correction"):
        result = application.execute("preview", record.production_ref, record.version_ref, kind=kind, correlation="quality-323b")
        assert result["exercise_profile"] == "EXERCISE-WORD-1.0"


def test_no_dispatch_without_effective_admission_and_no_legacy_override():
    d, _ = blueprint()
    with pytest.raises(ValueError, match="EXERCISE_INSTITUTIONAL_ADMISSION_REQUIRED"):
        build_p0_content_request(d)
    # Merely changing a declared status is not an admitted proof.
    d["context"]["institutional_resolution"]["status"] = "RESOLVED_ADMITTED"
    typed = P0Context(d["context"])
    d["context_sha256"] = typed.sha256
    with pytest.raises(ValueError, match="EXERCISE_INSTITUTIONAL_ADMISSION_REQUIRED"):
        build_p0_content_request(d)
    with pytest.raises(ValueError, match="EXERCISE_LEGACY_SCHEMA_FORBIDDEN"):
        build_p0_content_request(d, legacy_section_ids=True)


def test_strict_schema_and_production_projection_not_weakened():
    schema = exercise_content_schema()
    assert set(schema["required"]) == {"title", "exercise", "limitations"}
    record = prepare()
    changed = record.p0_bundle.mutable_copy()
    changed["questions"][0]["prompt"] += " altered"
    with pytest.raises(ValueError, match="EXERCISE_SIMPLE_PROJECTION_BINDING"):
        P0Production(changed)
    unchanged = deepcopy(record.mutable_copy())
    assert record.mutable_copy() == unchanged


@pytest.mark.skipif(not os.environ.get("V2_323C_BASELINE_SOURCE"),
                    reason="Historical 323B source archive required for byte comparison")
def test_old_contexts_and_serialized_bodies_unchanged():
    from tests.test_recovered_derivative_323b import capture

    dispatches = []
    for resource, mode in (("COURSE", None), ("EXERCISE", None), ("ASSESSMENT", None),
                           ("QUESTION_SET", "OPEN_QUESTIONS"), ("QUESTION_SET", "QCM"), ("QUESTION_SET", "QUIZ")):
        dispatch = as_plain(capture().dispatch)
        dispatch["context"].update(resource_type=resource, question_mode=mode,
                                   duration_minutes=30 if resource == "ASSESSMENT" else None,
                                   total_points=10 if resource == "ASSESSMENT" else None)
        dispatch["context_sha256"] = P0Context(dispatch["context"]).sha256
        dispatch["lineage"]["context_sha256"] = dispatch["context_sha256"]
        dispatches.append(dispatch)
    old = Path(os.environ["V2_323C_BASELINE_SOURCE"])
    code = """import json,sys,hashlib
from backend.adapters.outbound.generation.openai.p0_content import build_p0_content_request
from backend.adapters.outbound.generation.openai.p0_normal import NormalP0GenerationAdapter
rows=json.load(sys.stdin)
print(json.dumps([hashlib.sha256(NormalP0GenerationAdapter.body(build_p0_content_request(d,legacy_section_ids=v))).hexdigest() for d in rows for v in (False,True)]))
"""
    env = {key: os.environ[key] for key in ("SystemRoot", "WINDIR", "TEMP", "TMP") if key in os.environ}
    env.update(PYTHONPATH=str(old), PYTHONDONTWRITEBYTECODE="1", PYTHONIOENCODING="utf-8")
    result = subprocess.run([sys.executable, "-c", code], cwd=old, env=env, input=json.dumps(dispatches),
                            text=True, capture_output=True, check=True, timeout=30)
    from hashlib import sha256

    actual = [sha256(NormalP0GenerationAdapter.body(build_p0_content_request(dispatch, legacy_section_ids=v))).hexdigest()
              for dispatch in dispatches for v in (False, True)]
    assert actual == json.loads(result.stdout)
    assert all("exercise" not in asdict(build_p0_content_request(dispatch)) for dispatch in dispatches)


def test_teacher_claim_in_rich_only_field_is_checked():
    d, c = blueprint()
    c["exercise"]["teacher_answers"][0]["remediation"] = "Cette activité est conforme au programme officiel."
    with pytest.raises(ValueError, match="PROGRAM_ALIGNMENT_UNVERIFIED_HUMAN_REVIEW_REQUIRED"):
        prepare(d, c)


def test_source_reference_link_and_adaptation_status_separate():
    d, c = blueprint()
    c["exercise"]["documents"][0].update(provenance="SUPPLIED_REFERENCE", evidence_id=d["references"][0]["evidence_id"],
                                       text=d["evidence"][d["references"][0]["evidence_id"]])
    record = prepare(d, c)
    exercise = StructuredExercise(record.p0_bundle.data["exercise"])
    assert "Référence fournie" in exercise.sections()[-2]["text"]
    assert fingerprint(record.data) == record.sha256


def test_reference_identity_is_not_a_license_to_invent_text():
    d, c = blueprint()
    c["exercise"]["documents"][0].update(provenance="SUPPLIED_REFERENCE", evidence_id=d["references"][0]["evidence_id"])
    with pytest.raises(ValueError, match="EXERCISE_REFERENCE_TEXT_CHANGED"):
        prepare(d, c)


def test_synthetic_admitted_request_uses_selected_profile_schema_and_parameters():
    from backend.modules.knowledge_reference.contracts.dto.admitted_institutional_sources import (
        ADMITTED_DOCUMENTS,
        OWNER_ADMISSION_SHA256,
    )

    d, _ = blueprint()
    candidate_id, document_hash = next(iter(ADMITTED_DOCUMENTS.items()))
    resolution = d["context"]["institutional_resolution"]
    resolution.update(status="RESOLVED_ADMITTED", owner_admission_sha256=OWNER_ADMISSION_SHA256,
                      qualification_sha256="d" * 64, version_label="Synthetic test snapshot",
                      document_provenance={"candidate_id": candidate_id, "sha256": document_hash},
                      attachments=[], gaps=[])
    d["context_sha256"] = P0Context(d["context"]).sha256
    d["lineage"]["context_sha256"] = d["context_sha256"]
    request = build_p0_content_request(d)
    assert request.output_schema == exercise_content_schema()
    assert request.max_output_tokens == 4096 and request.model == "gpt-5.6-terra"
    assert request.reasoning_effort.value == "low" and request.service_tier == "default"
    payload = json.loads(request.input_json)
    assert payload["contract_id"] == "P0-EXERCISE-CONTENT-INPUT-1.0"
    assert len(payload["exercise_focus"]["capacities"]) == 2
    assert "teacher_answers" in request.instructions


def test_export_keeps_formal_document_links_caveats_and_version():
    record = prepare()
    exporter = ExportSavedCommand(R6ReadableWordWriter(profile="product-v7"), product_projection=True)
    student = exporter.preview(record, "student")
    teacher = exporter.preview(record, "correction")
    assert any(block.text == "Documents 1, 2" for block in student.blocks)
    assert any(record.version_ref in block.text for block in teacher.blocks)
    assert all(any(text == block.text for block in teacher.blocks) for text in record.p0_bundle.data["limitations"])
    assert any("Acceptation pédagogique" in block.text for block in teacher.blocks)


def test_rich_content_through_normal_parser_guard_and_binding():
    from backend.infrastructure.composition.factories.captured_content_validation import (
        NormalCapturedContentValidation,
    )

    d, c = blueprint()
    bound, checks = NormalCapturedContentValidation().bind(d, c)
    assert bound.sha256 == prepare(d, c).p0_bundle.sha256
    assert checks["guard_disposition"] == "ALLOW"
