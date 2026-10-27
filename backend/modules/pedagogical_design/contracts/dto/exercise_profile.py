"""Closed exercise content, exact relationships and separate public projections."""
from __future__ import annotations

import re
from collections.abc import Mapping
from dataclasses import dataclass
from hashlib import sha256

from backend.modules.pedagogical_context.contracts.dto.exercise_context import exercise_focus
from backend.modules.pedagogical_design.contracts.dto.assessment_bundle import (
    as_plain,
    items,
    nonempty,
    object_data,
)
from backend.modules.pedagogical_design.contracts.dto.learning_links import (
    require_ordered_answers,
    require_provenance_kind,
    require_subset,
    require_unique_coverage,
)
from backend.modules.pedagogical_design.contracts.dto.section_identity import valid_question_id
from backend.shared_kernel._safe_data import freeze_safe_mapping

EXERCISE_PRODUCTION = "P0-PRODUCTION-EXERCISE-1.0"
EXERCISE_FIELDS = {"title", "exercise", "limitations"}
EXERCISE_CONTENT_FIELDS = {"instructions", "objectives", "situation", "documents", "questions", "teacher_answers"}
STAGES = ("OBSERVE", "ANALYSE", "APPLY")
EXERCISE_INSTRUCTIONS = (
    "Produisez un exercice structuré en français, proportionné à la demande et au temps de travail, "
    "sans quota de pages ou de tableaux. Utilisez uniquement les alias des capacités et notions du focus confirmé. "
    "Les objectifs et les questions couvrent toutes les capacités sélectionnées. "
    "Construisez une situation et des documents utiles ; LOCAL_FICTION porte evidence_id=null, "
    "SUPPLIED_REFERENCE porte un evidence_id fourni exact, sans inventer une provenance réelle. "
    "Le scénario local est affiché comme fictif par l'Application. Les documents sont tous utilisés. "
    "Questions Q1 à Qn sans rupture : observation puis analyse puis application, selon cette progression. "
    "Chaque question lie ses capacités, ses documents, ses critères de réussite observables et un espace de réponse adapté. "
    "teacher_answers reprend exactement les mêmes question_id, avec réponse attendue, justification, "
    "point de vigilance et remédiation actionnable. Aucun de ces quatre champs professeur dans les données élève. "
    "Ne produisez aucune identité locale, étiquette de programme, preuve d'admission ou validation. "
    "Signalez les limites. La conformité structurelle ne vaut pas acceptation pédagogique."
)


def _texts(value: object, maximum: int = 8) -> tuple[str, ...]:
    if not isinstance(value, (list, tuple)) or not 1 <= len(value) <= maximum:
        raise ValueError("EXERCISE_TEXT_ITEMS")
    result = tuple(nonempty(text, 2000) for text in value)
    if len(result) != len(set(result)):
        raise ValueError("EXERCISE_DUPLICATE")
    return result


def _rows(value: object, fields: set[str], maximum: int = 16) -> tuple[dict[str, object], ...]:
    rows = items(value, maximum)
    if not rows:
        raise ValueError("EXERCISE_REQUIRED_CONTENT")
    for row in rows:
        object_data(row, fields)
    return rows


def _source(value: object) -> None:
    row = object_data(value)
    nonempty(row["text"], 16000)
    require_provenance_kind(row["provenance"], code="EXERCISE_PROVENANCE")
    if row["provenance"] == "LOCAL_FICTION":
        if row["evidence_id"] is not None:
            raise ValueError("EXERCISE_FICTION_EVIDENCE")
    elif row["provenance"] == "SUPPLIED_REFERENCE":
        if re.fullmatch(r"evidence:[0-9a-f]{32}", str(row["evidence_id"])) is None:
            raise ValueError("EXERCISE_SOURCE_EVIDENCE")
    else:
        raise ValueError("EXERCISE_PROVENANCE")


@dataclass(frozen=True, slots=True)
class StructuredExercise:
    """EXERCISE_STRUCTURED only: three stages are not a rule for legacy micro-exercises."""

    data: Mapping[str, object]
    case_study: bool = False

    def __post_init__(self) -> None:
        data = object_data(self.data, EXERCISE_CONTENT_FIELDS | ({"case_study"} if self.case_study else set()))
        nonempty(data["instructions"], 4000)
        objectives = _rows(data["objectives"], {"capability_id", "goal"})
        for row in objectives:
            nonempty(row["capability_id"], 40)
            nonempty(row["goal"], 2000)
        situation = object_data(data["situation"], {"text", "provenance", "evidence_id"})
        _source(situation)
        documents = _rows(data["documents"], {"document_id", "title", "text", "provenance", "evidence_id"}, 12)
        ids = []
        for document in documents:
            ref = nonempty(document["document_id"], 40)
            if re.fullmatch(r"D[1-9][0-9]?", ref) is None:
                raise ValueError("EXERCISE_DOCUMENT_ID")
            ids.append(ref)
            nonempty(document["title"], 200)
            _source(document)
        if len(ids) != len(set(ids)):
            raise ValueError("EXERCISE_DUPLICATE")
        questions = _rows(data["questions"], {"question_id", "stage", "prompt", "capability_ids",
                                               "document_ids", "success_criteria", "answer_lines"}, 30)
        stages: list[int] = []
        used_documents: set[str] = set()
        for number, question in enumerate(questions, 1):
            if not valid_question_id(question["question_id"]) or question["question_id"] != "Q" + str(number):
                raise ValueError("EXERCISE_QUESTION_SEQUENCE")
            nonempty(question["prompt"], 4000)
            if question["stage"] not in STAGES:
                raise ValueError("EXERCISE_STAGE")
            stages.append(STAGES.index(str(question["stage"])))
            _texts(question["capability_ids"], 16)
            doc_ids = _texts(question["document_ids"], 12)
            require_subset(doc_ids, set(ids), code="EXERCISE_DOCUMENT_LINK")
            used_documents.update(doc_ids)
            _texts(question["success_criteria"])
            if type(question["answer_lines"]) is not int or not 1 <= int(question["answer_lines"]) <= 20:
                raise ValueError("EXERCISE_RESPONSE_SPACE")
        if stages != sorted(stages) or set(stages) != {0, 1, 2}:
            raise ValueError("EXERCISE_GRADUATION")
        if used_documents != set(ids):
            raise ValueError("EXERCISE_UNUSED_DOCUMENT")
        answers = _rows(data["teacher_answers"], {"question_id", "expected_answer", "rationale", "vigilance", "remediation"}, 30)
        require_ordered_answers([row["question_id"] for row in questions],
                                [row["question_id"] for row in answers], code="EXERCISE_ANSWER_LINKS")
        for answer in answers:
            for field in ("expected_answer", "rationale", "vigilance", "remediation"):
                nonempty(answer[field], 4000)
        if self.case_study:
            from backend.modules.pedagogical_design.contracts.dto.case_study import CaseStudyDossier
            CaseStudyDossier(object_data(data["case_study"])).bind(data)
        object.__setattr__(self, "data", freeze_safe_mapping(data))

    def bind(self, context: Mapping[str, object], references: object) -> None:
        focus = exercise_focus(context)
        capacities = {str(row["id"]) for row in items(focus["capacities"], 16)}
        objective_ids = [str(row["capability_id"]) for row in items(self.data["objectives"], 16)]
        question_ids = {cap for row in items(self.data["questions"], 30) for cap in _texts(row["capability_ids"], 16)}
        require_unique_coverage(objective_ids, capacities, code="EXERCISE_CAPABILITY_COVERAGE")
        if question_ids != capacities:
            raise ValueError("EXERCISE_CAPABILITY_COVERAGE")
        known = {str(row["evidence_id"]): row for row in items(references, 8)}
        for row in (object_data(self.data["situation"]), *items(self.data["documents"], 12)):
            if row["provenance"] == "SUPPLIED_REFERENCE":
                reference = known.get(str(row["evidence_id"]))
                if reference is None:
                    raise ValueError("EXERCISE_UNSUPPLIED_REFERENCE")
                if sha256(str(row["text"]).encode()).hexdigest() != reference["excerpt_sha256"]:
                    raise ValueError("EXERCISE_REFERENCE_TEXT_CHANGED")

    def projection(self, *, teacher: bool = False) -> dict[str, object]:
        return {key: as_plain(value) for key, value in self.data.items()
                if teacher or key != "teacher_answers"}

    def sections(self) -> list[dict[str, object]]:
        result: list[dict[str, object]] = [{"section_id": "S_SITUATION", "heading": "Situation", "text": self._source_text(object_data(self.data["situation"]))},
                  {"section_id": "S_INSTRUCTIONS", "heading": "Consignes", "text": self.data["instructions"]}]
        if self.case_study:
            from backend.modules.pedagogical_design.contracts.dto.case_study import CaseStudyDossier
            result.append({"section_id": "S_DOSSIER", "heading": "Dossier et missions", "text": CaseStudyDossier(object_data(self.data["case_study"])).public_text()})
        for document in items(self.data["documents"], 12):
            result.append({"section_id": "S_" + str(document["document_id"]), "heading": document["title"],
                           "text": self._source_text(document)})
        return result

    @staticmethod
    def _source_text(row: Mapping[str, object]) -> str:
        return ("Situation fictive. " if row["provenance"] == "LOCAL_FICTION" else "Référence fournie. ") + str(row["text"])

    def simple_questions(self) -> list[dict[str, object]]:
        return [{"question_id": row["question_id"], "prompt": row["prompt"], "options": []}
                for row in items(self.data["questions"], 30)]

    def simple_answers(self) -> list[dict[str, object]]:
        return [{key: row[key] for key in ("question_id", "expected_answer", "rationale")}
                for row in items(self.data["teacher_answers"], 30)]
