from __future__ import annotations

import copy
import hashlib
from collections.abc import Mapping

import pytest

from backend.adapters.outbound.persistence.saved_production import LocalSavedProductionStore
from backend.modules.materialization_export.application.commands.export_saved import (
    ExportSavedCommand,
)
from backend.modules.materialization_export.contracts.dto.word_document import WordDocument
from backend.modules.pedagogical_context.contracts.dto.p0_context import (
    P0_CONTEXT_CONTRACT,
    P0Context,
)
from backend.modules.pedagogical_design.application.commands.create_p0_candidate import (
    CreateP0Candidate,
    ReviseP0Candidate,
)
from backend.modules.pedagogical_design.contracts.dto.p0_production import (
    P0_PRODUCTION_CONTRACT,
    P0_PROVENANCE_LABEL,
    P0Production,
)
from backend.modules.validation_control.application.commands.validate_p0 import (
    ValidateP0Command,
)
from backend.modules.work_orchestration.application.services.saved_production import (
    SavedProductionService,
)
from backend.modules.work_orchestration.contracts.dto.p0_production_read_view import (
    P0ProductionReadView,
)
from backend.modules.work_orchestration.contracts.dto.saved_production import (
    SAVED_P0_CONTRACT,
    SavedProduction,
)

EVIDENCE_TEXT = "Référence CP645 : organisation, performance, lettrage, 700 + 500 = 1 200."
EVIDENCE_ID = "evidence:" + "a" * 32
IDS = {
    "production_ref": "prod:" + "1" * 32,
    "version_ref": "ver:" + "2" * 32,
    "source_run_id": "run:" + "3" * 32,
    "source_step_id": "step:" + "4" * 32,
    "evidence_set_ref": "evidence:" + "5" * 32,
    "source_request_id": "req:" + "6" * 32,
    "conversation_id": "conv:" + "7" * 32,
}


def context_data(kind: str, mode: str | None = None) -> dict[str, object]:
    assessment = kind == "ASSESSMENT"
    return {
        "contract_id": P0_CONTEXT_CONTRACT,
        "resource_type": kind,
        "question_mode": mode,
        "level": "BTS_CG_YEAR_2" if assessment else "FIRST_STMG",
        "discipline": "gestion",
        "topics": ["organisation"],
        "objectives": ["Mobiliser les notions et justifier la réponse"],
        "difficulty": "STANDARD",
        "duration_minutes": 60 if assessment else None,
        "total_points": 20 if assessment else None,
        "language": "fr-FR",
    }


def production_data(
    kind: str = "EXERCISE",
    mode: str | None = None,
    *,
    parent: str | None = None,
) -> dict[str, object]:
    context = P0Context(context_data(kind, mode))
    question = {"question_id": "Q01", "prompt": "Justifiez votre réponse.", "options": []}
    correction = {
        "question_id": "Q01",
        "expected_answer": "Réponse justifiée.",
        "rationale": "Les critères sont explicitement reliés aux faits.",
    }
    marking: list[dict[str, object]] = []
    if mode in {"QCM", "QUIZ"}:
        question["options"] = ["Réponse A", "Réponse B", "Réponse C"]
        correction["expected_answer"] = "Réponse A"
    if kind == "ASSESSMENT":
        marking = [
            {
                "question_id": "Q01",
                "points": "20.00",
                "criteria": ["Identification : 5 points", "Justification : 15 points"],
            }
        ]
    questions = [] if kind == "COURSE" else [question]
    corrections = [] if kind == "COURSE" else [correction]
    return {
        "contract_id": P0_PRODUCTION_CONTRACT,
        "production_ref": IDS["production_ref"],
        "version_ref": IDS["version_ref"],
        "title": "Candidat pédagogique local",
        "context": context.as_dict(),
        "context_sha256": context.sha256,
        "sections": [
            {
                "section_id": "S01",
                "heading": "Objectif",
                "text": "Mobiliser les notions demandées à partir de la référence fournie.",
            }
        ],
        "questions": questions,
        "corrections": corrections,
        "marking": marking,
        "references": [
            {
                "evidence_id": EVIDENCE_ID,
                "source_ref": "notion:organisation",
                "locator": "search-chunk:" + "b" * 24,
                "checksum_or_version": "c" * 64,
                "excerpt_sha256": hashlib.sha256(EVIDENCE_TEXT.encode()).hexdigest(),
                "provenance_label": P0_PROVENANCE_LABEL,
            }
        ],
        "lineage": {
            "source_run_id": IDS["source_run_id"],
            "source_step_id": IDS["source_step_id"],
            "evidence_set_ref": IDS["evidence_set_ref"],
            "source_request_id": IDS["source_request_id"],
            "conversation_id": IDS["conversation_id"],
            "context_sha256": context.sha256,
            "parent_version_ref": parent,
        },
        "limitations": ["CANDIDATE — validation et promotion distinctes."],
    }


def candidate(kind: str = "EXERCISE", mode: str | None = None) -> P0Production:
    return CreateP0Candidate().execute(
        production_data(kind, mode), evidence={EVIDENCE_ID: EVIDENCE_TEXT}
    )


@pytest.mark.parametrize(
    ("kind", "mode"),
    [
        ("COURSE", None),
        ("EXERCISE", None),
        ("QUESTION_SET", "OPEN_QUESTIONS"),
        ("QUESTION_SET", "QCM"),
        ("QUESTION_SET", "QUIZ"),
        ("ASSESSMENT", None),
    ],
)
def test_closed_p0_families_have_student_and_teacher_projections(
    kind: str, mode: str | None
) -> None:
    bundle = candidate(kind, mode)
    student = bundle.student_projection()
    teacher = bundle.teacher_projection()
    assert student["contract_id"] == "R6-P0-STUDENT-PROJECTION-1.0"
    assert "corrections" not in student and "marking" not in student
    assert teacher["corrections"] == bundle.mutable_copy()["corrections"]
    assert teacher["marking"] == bundle.mutable_copy()["marking"]
    assert ValidateP0Command().execute(bundle)["status"] == "PASS"


def saved_record(bundle: P0Production) -> SavedProduction:
    view = P0ProductionReadView.from_bundle(bundle)
    return SavedProduction(
        {
            "contract_id": SAVED_P0_CONTRACT,
            "view": view.data,
            "bundle": bundle.data,
            "reviews": [],
            "validations": [],
            "origin": "LOCAL_APPLICATION",
            "provenance": {},
            "reservations": [],
        }
    )


class _Writer:
    def write(self, document: WordDocument) -> bytes:
        return repr(document.as_dict()).encode("utf-8")


def test_save_reopen_validate_and_export_are_exact_versioned(tmp_path) -> None:
    bundle = candidate("ASSESSMENT")
    record = saved_record(bundle)
    store = LocalSavedProductionStore(tmp_path / "saved", create=True)
    service = SavedProductionService(store)
    assert service.save(record)["created"] is True
    reopened = service.open(bundle.production_ref, bundle.version_ref)
    assert reopened["record_sha256"] == record.sha256
    action = service.validate_p0(
        bundle.production_ref, bundle.version_ref, "action:" + "8" * 32, record.sha256
    )
    assert action["report"]["status"] == "PASS"
    exporter = ExportSavedCommand(_Writer())
    student = exporter.preview(record, "student").as_dict()
    correction = exporter.preview(record, "correction").as_dict()
    marking = exporter.preview(record, "marking").as_dict()
    assert "Réponse justifiée" not in repr(student)
    assert "Réponse justifiée" in repr(correction)
    assert "20.00" in repr(marking)
    with pytest.raises(ValueError, match="R4_NOT_FOUND"):
        service.open(bundle.production_ref, "ver:" + "9" * 32)


def test_revision_keeps_parent_and_recalculates_dependent_projections() -> None:
    first = candidate("EXERCISE")
    revised_data = production_data("EXERCISE", parent=first.version_ref)
    revised_data["version_ref"] = "ver:" + "9" * 32
    revised_data["corrections"][0]["expected_answer"] = "Réponse révisée et justifiée."
    revised = ReviseP0Candidate().execute(
        first, revised_data, evidence={EVIDENCE_ID: EVIDENCE_TEXT}
    )
    assert revised.data["lineage"]["parent_version_ref"] == first.version_ref
    assert revised.teacher_projection()["corrections"] != first.teacher_projection()["corrections"]
    assert ValidateP0Command().execute(revised, parent=first)["status"] == "PASS"


def mutated(**changes: object) -> dict[str, object]:
    data = production_data()
    for path, value in changes.items():
        target: object = data
        parts = path.split("__")
        for part in parts[:-1]:
            target = target[int(part)] if part.isdigit() else target[part]  # type: ignore[index]
        if isinstance(target, list):
            target[int(parts[-1])] = value
        else:
            target[parts[-1]] = value  # type: ignore[index]
    return data


@pytest.mark.parametrize(
    ("data", "code"),
    [
        (mutated(context__resource_type="VIDEO"), "P0_RESOURCE_TYPE"),
        (mutated(corrections__0__question_id="Q99"), "P0_QUESTION_CORRECTION_LINKS"),
        (mutated(questions__0__options=["A"]), "P0_OPEN_QUESTION_OPTIONS"),
        (mutated(references=[]), "P0_REFERENCES"),
    ],
)
def test_malformed_contracts_fail_closed(data: Mapping[str, object], code: str) -> None:
    with pytest.raises(ValueError, match=code):
        P0Production(data)


def test_qcm_key_duplicates_and_assessment_total_fail_closed() -> None:
    missing_key = production_data("QUESTION_SET", "QCM")
    missing_key["corrections"][0]["expected_answer"] = "Absente"
    with pytest.raises(ValueError, match="P0_CHOICE_SHAPE"):
        P0Production(missing_key)
    duplicate = production_data("QUESTION_SET", "QCM")
    duplicate["questions"][0]["options"] = ["A", "A"]
    with pytest.raises(ValueError, match="P0_OPTIONS"):
        P0Production(duplicate)
    wrong_total = production_data("ASSESSMENT")
    wrong_total["marking"][0]["points"] = "19.00"
    with pytest.raises(ValueError, match="P0_MARKING_TOTAL"):
        P0Production(wrong_total)


def test_evidence_missing_required_fact_or_changed_fails_closed() -> None:
    command = CreateP0Candidate()
    data = production_data()
    with pytest.raises(ValueError, match="P0_EVIDENCE_INSUFFICIENT"):
        command.execute(data, evidence={})
    with pytest.raises(ValueError, match="P0_REQUIRED_FACT_MISSING"):
        command.execute(
            data,
            evidence={EVIDENCE_ID: EVIDENCE_TEXT},
            required_facts=("donnée indispensable absente",),
        )
    with pytest.raises(ValueError, match="P0_EVIDENCE_CHANGED"):
        command.execute(data, evidence={EVIDENCE_ID: EVIDENCE_TEXT + " mutation"})


def test_unknown_provider_field_and_export_error_fail_closed() -> None:
    data = copy.deepcopy(production_data())
    data["provider"] = "forbidden"
    with pytest.raises(ValueError, match="ASSESSMENT_FIELDS"):
        P0Production(data)

    class BrokenWriter:
        def write(self, document: WordDocument) -> bytes:
            raise OSError("EXPORT_FAILED")

    with pytest.raises(OSError, match="EXPORT_FAILED"):
        ExportSavedCommand(BrokenWriter()).execute(saved_record(candidate()), "student")
