from __future__ import annotations

import hashlib
import json
import os
from collections.abc import Mapping
from pathlib import Path

import pytest

from backend.adapters.outbound.export.word import OOXMLWordWriter
from backend.adapters.outbound.persistence.saved_production import LocalSavedProductionStore
from backend.infrastructure.composition.factories.local_browser import Read15RuntimeTarget
from backend.infrastructure.composition.factories.r6_p0 import (
    R6_EXACT_SOURCE_BINDINGS,
    ExactSourceBinding,
    load_p0_exact_reference,
)
from backend.infrastructure.config.loaders.sqlite import SEED_PATH_ENV
from backend.modules.materialization_export.application.commands.export_saved import (
    ExportSavedCommand,
)
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

SCENARIOS = (
    ("R6-S01", "COURSE", None, "FIRST_STMG", ()),
    ("R6-S02", "EXERCISE", None, "FIRST_STMG", ()),
    ("R6-S03", "QUESTION_SET", "QCM", "FINAL_STMG", ()),
    ("R6-S04", "QUESTION_SET", "QUIZ", "FINAL_STMG", ()),
    ("R6-S05", "EXERCISE", None, "BTS_CG_YEAR_1", ("1 200", "700", "500")),
    (
        "R6-S06",
        "ASSESSMENT",
        None,
        "BTS_CG_YEAR_2",
        ("100 000", "135 000", "55 000", "35 000", "22 000", "7 000", "15 000"),
    ),
    ("R6-S07", "QUESTION_SET", "OPEN_QUESTIONS", "BTS_CG_YEAR_1", ("1 200", "700", "500")),
)


def _real_target() -> Read15RuntimeTarget:
    value = os.environ.get(SEED_PATH_ENV)
    assert value, "R6_REAL_SOURCE_PRECONDITION_REQUIRED"
    path = Path(value)
    return Read15RuntimeTarget(
        path, path.parent, hashlib.sha256(path.read_bytes()).hexdigest()
    )


def _binding(scenario: str) -> ExactSourceBinding:
    return next(item for item in R6_EXACT_SOURCE_BINDINGS if scenario in item.scenarios)


def test_six_exact_bindings_materialize_hashes_statuses_and_required_facts() -> None:
    target = _real_target()
    before = hashlib.sha256(target.runtime_path.read_bytes()).hexdigest()
    materialized = {
        binding.resource_ref: load_p0_exact_reference(
            target,
            resource_ref=binding.resource_ref,
            resource_version_ref=binding.resource_version_ref,
        )
        for binding in R6_EXACT_SOURCE_BINDINGS
    }
    assert len(materialized) == 6
    assert all(item["exact_source"]["body_sha256"] == binding.body_sha256 for binding in R6_EXACT_SOURCE_BINDINGS for item in (materialized[binding.resource_ref],))
    assert all(item["exact_source"]["resource_lifecycle_status"] == "REVIEW" for item in materialized.values())
    lettrage = str(materialized["revmax260921:exercise:6785b115e78c9f4bece895b8"]["evidence"])
    assert all(fact in lettrage for fact in ("1 200", "700", "500"))
    finance = str(materialized["revint260920:resource:ee0f10a68b6572bdeea986ff"]["evidence"])
    assert all(fact in finance for fact in ("100 000", "135 000", "55 000", "35 000", "22 000", "7 000", "20 000", "15 000"))
    assert hashlib.sha256(target.runtime_path.read_bytes()).hexdigest() == before


def _ids(scenario: str) -> dict[str, str]:
    def ref(prefix: str, suffix: str) -> str:
        return prefix + ":" + hashlib.sha256((scenario + suffix).encode()).hexdigest()[:32]

    return {
        "production_ref": ref("prod", "production"),
        "version_ref": ref("ver", "version"),
        "source_run_id": ref("run", "run"),
        "source_step_id": ref("step", "step"),
        "evidence_set_ref": ref("evidence", "evidence"),
        "source_request_id": ref("req", "request"),
        "conversation_id": ref("conv", "conversation"),
        "action_id": ref("action", "validation"),
    }


def _source_parts(exact: Mapping[str, object]) -> tuple[str, list[dict[str, object]]]:
    body = json.loads(str(exact["body"]))
    if not isinstance(body, dict):
        raise ValueError("R6_TEST_SOURCE_SHAPE")
    statement = str(body.get("case") or body.get("statement") or body.get("prompt"))
    questions = exact["questions"]
    if not isinstance(questions, list):
        raise ValueError("R6_TEST_SOURCE_SHAPE")
    return statement, [dict(item) for item in questions if isinstance(item, Mapping)]


def _candidate_data(
    scenario: str,
    kind: str,
    mode: str | None,
    level: str,
    loaded: Mapping[str, object],
) -> dict[str, object]:
    ids = _ids(scenario)
    exact = loaded["exact_source"]
    if not isinstance(exact, Mapping):
        raise ValueError("R6_TEST_SOURCE_SHAPE")
    statement, source_questions = _source_parts(exact)
    context = P0Context(
        {
            "contract_id": P0_CONTEXT_CONTRACT,
            "resource_type": kind,
            "question_mode": mode,
            "level": level,
            "discipline": "gestion et comptabilité",
            "topics": [str(exact["canonical_title"])],
            "objectives": ["Analyser et justifier à partir des données de la référence exacte"],
            "difficulty": "STANDARD",
            "duration_minutes": 60 if kind == "ASSESSMENT" else None,
            "total_points": 20 if kind == "ASSESSMENT" else None,
            "language": "fr-FR",
        }
    )
    questions: list[dict[str, object]] = []
    corrections: list[dict[str, object]] = []
    marking: list[dict[str, object]] = []
    if kind != "COURSE":
        for index, source_question in enumerate(source_questions, start=1):
            question_id = f"Q{index:02d}"
            expected = str(source_question["correction"])
            options: list[str] = []
            if mode in {"QCM", "QUIZ"}:
                options = [
                    expected,
                    "Le cas ne permet aucune conclusion argumentée.",
                    "Une seule dimension suffit toujours à conclure.",
                ]
            questions.append(
                {
                    "question_id": question_id,
                    "prompt": str(source_question["prompt"]),
                    "options": options,
                }
            )
            corrections.append(
                {
                    "question_id": question_id,
                    "expected_answer": expected,
                    "rationale": "La réponse est liée à la correction de la référence CP645 exacte.",
                }
            )
        if kind == "ASSESSMENT":
            points = ("12.00", "8.00")
            marking = [
                {
                    "question_id": question["question_id"],
                    "points": points[index],
                    "criteria": ["Calcul explicite", "Interprétation justifiée"],
                }
                for index, question in enumerate(questions)
            ]
    reference = loaded["reference"]
    if not isinstance(reference, Mapping):
        raise ValueError("R6_TEST_SOURCE_SHAPE")
    return {
        "contract_id": P0_PRODUCTION_CONTRACT,
        "production_ref": ids["production_ref"],
        "version_ref": ids["version_ref"],
        "title": scenario + " — candidat local",
        "context": context.as_dict(),
        "context_sha256": context.sha256,
        "sections": [{"section_id": "S01", "heading": "Cas", "text": statement}],
        "questions": questions,
        "corrections": corrections,
        "marking": marking,
        "references": [dict(reference)],
        "lineage": {
            "source_run_id": ids["source_run_id"],
            "source_step_id": ids["source_step_id"],
            "evidence_set_ref": ids["evidence_set_ref"],
            "source_request_id": ids["source_request_id"],
            "conversation_id": ids["conversation_id"],
            "context_sha256": context.sha256,
            "parent_version_ref": None,
        },
        "limitations": [
            "CANDIDATE — validation et promotion restent distinctes.",
            str(exact["provenance_label"]),
            "Statut source : " + str(exact["resource_lifecycle_status"]) + "/" + str(exact["resource_validation_status"]),
        ],
    }


def _saved(bundle: P0Production) -> SavedProduction:
    return SavedProduction(
        {
            "contract_id": SAVED_P0_CONTRACT,
            "view": P0ProductionReadView.from_bundle(bundle).data,
            "bundle": bundle.data,
            "reviews": [],
            "validations": [],
            "origin": "LOCAL_APPLICATION",
            "provenance": {},
            "reservations": [],
        }
    )


@pytest.mark.parametrize(("scenario", "kind", "mode", "level", "facts"), SCENARIOS)
def test_seven_scenarios_use_exact_application_source_and_full_local_lifecycle(
    tmp_path: Path,
    scenario: str,
    kind: str,
    mode: str | None,
    level: str,
    facts: tuple[str, ...],
) -> None:
    target = _real_target()
    binding = _binding(scenario)
    loaded = load_p0_exact_reference(
        target,
        resource_ref=binding.resource_ref,
        resource_version_ref=binding.resource_version_ref,
    )
    evidence = str(loaded["evidence"])
    reference = loaded["reference"]
    assert isinstance(reference, Mapping)
    bundle = CreateP0Candidate().execute(
        _candidate_data(scenario, kind, mode, level, loaded),
        evidence={str(reference["evidence_id"]): evidence},
        required_facts=facts,
    )
    assert ValidateP0Command().execute(bundle)["status"] == "PASS"
    student = bundle.student_projection()
    teacher = bundle.teacher_projection()
    assert "corrections" not in student and "marking" not in student
    assert teacher["corrections"] == bundle.mutable_copy()["corrections"]
    if scenario == "R6-S06":
        assert bundle.context.data["duration_minutes"] == 60
        assert bundle.context.data["total_points"] == 20
        assert sum(float(item["points"]) for item in teacher["marking"]) == 20.0
        assert all(fact in evidence for fact in facts)
    if scenario in {"R6-S05", "R6-S07"}:
        assert all(fact in evidence for fact in facts)

    record = _saved(bundle)
    service = SavedProductionService(LocalSavedProductionStore(tmp_path / "saved", create=True))
    assert service.save(record)["created"] is True
    reopened = service.open(bundle.production_ref, bundle.version_ref)
    assert reopened["record_sha256"] == record.sha256
    assert service.validate_p0(
        bundle.production_ref,
        bundle.version_ref,
        _ids(scenario)["action_id"],
        record.sha256,
    )["report"]["status"] == "PASS"
    exporter = ExportSavedCommand(OOXMLWordWriter())
    assert exporter.execute(record, "student").startswith(b"PK")
    assert exporter.execute(record, "correction").startswith(b"PK")
    if kind == "ASSESSMENT":
        assert exporter.execute(record, "marking").startswith(b"PK")
    if scenario == "R6-S06":
        child_data = bundle.mutable_copy()
        child_data["version_ref"] = _ids(scenario + "-REV1")["version_ref"]
        lineage = dict(child_data["lineage"])
        lineage["parent_version_ref"] = bundle.version_ref
        child_data["lineage"] = lineage
        questions = list(child_data["questions"])
        questions[0] = {**questions[0], "prompt": questions[0]["prompt"] + " Justifiez chaque étape."}
        child_data["questions"] = questions
        corrections = list(child_data["corrections"])
        corrections[0] = {
            **corrections[0],
            "rationale": corrections[0]["rationale"] + " La justification est attendue.",
        }
        child_data["corrections"] = corrections
        marking = list(child_data["marking"])
        marking[0] = {
            **marking[0],
            "criteria": ["Calcul explicite et justification", *marking[0]["criteria"][1:]],
        }
        child_data["marking"] = marking
        child = ReviseP0Candidate().execute(
            bundle,
            child_data,
            evidence={str(reference["evidence_id"]): evidence},
            required_facts=facts,
        )
        assert ValidateP0Command().execute(child, parent=bundle)["status"] == "PASS"
        child_record = _saved(child)
        assert service.save(child_record)["created"] is True
        assert service.open(bundle.production_ref, bundle.version_ref)["record_sha256"] == record.sha256
        assert service.open(child.production_ref, child.version_ref)["record_sha256"] == child_record.sha256
        assert exporter.execute(child_record, "correction").startswith(b"PK")
        assert exporter.execute(child_record, "marking").startswith(b"PK")


@pytest.mark.parametrize("value", (None, ""))
def test_missing_source_precondition_is_explicit_before_materialization(
    monkeypatch: pytest.MonkeyPatch, value: str | None,
) -> None:
    if value is None:
        monkeypatch.delenv(SEED_PATH_ENV, raising=False)
    else:
        monkeypatch.setenv(SEED_PATH_ENV, value)
    with pytest.raises(AssertionError, match="R6_REAL_SOURCE_PRECONDITION_REQUIRED"):
        _real_target()
