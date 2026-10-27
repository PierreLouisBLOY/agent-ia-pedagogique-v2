"""Closed, deeply immutable Word projection; text positions never accept objects."""
import re
from collections.abc import Mapping, Sequence
from typing import cast

from backend.modules.pedagogical_design.contracts.dto.assessment_bundle import items, object_data
from backend.shared_kernel._safe_data import freeze_safe_mapping


def require_student_editorial_text(texts: Sequence[str]) -> None:
    """Refuse technical metadata in visible text; never rewrite pedagogical text."""
    identities = r"(?<!\w)(?:search-chunk|notion|prod|ver|content|evidence|permission|slot|grant|receipt|framework-element|framework-version):\S+|\b[a-f0-9]{64}\b|\b[a-z][a-z0-9_-]*:[a-f0-9]{12,64}\b"
    statuses = r"\b(?:CANDIDATE|NOT_PERFORMED|APPLICATION_SAVED|PARSING_REJECTED|NOT_ESTABLISHED|RESERVED|PENDING|DISPATCH|SOURCE_USAGE_NOT_DECLARED|CONTENT_GAP)\b|\bSYNTHETIC_"
    if any(re.search(identities, text, re.IGNORECASE) or re.search(statuses, text) for text in texts):
        raise ValueError("EXERCISE_STUDENT_TECHNICAL_METADATA")


def _text(value: object, maximum: int = 16000) -> None:
    if not isinstance(value, str) or not value.strip() or len(value) > maximum:
        raise ValueError("EXERCISE_WORD_TEXT_TYPE")


def _texts(value: object, *, required: bool = True, maximum: int = 64) -> None:
    if not isinstance(value, (tuple, list)) or not int(required) <= len(value) <= maximum:
        raise ValueError("EXERCISE_WORD_LIST_TYPE")
    for text in value:
        _text(text)


def _source(row: Mapping[str, object]) -> None:
    _text(row["text"])
    _text(row["provenance"], 40)
    if row["evidence_id"] is not None:
        _text(row["evidence_id"], 100)


def validate_exercise_word_projection(value: object, kind: str) -> Mapping[str, object]:
    if kind not in {"student", "correction"}:
        raise ValueError("EXERCISE_WORD_KIND")
    teacher = kind == "correction"
    projected = object_data(value, {"content", "header", "source_notes", "notice"}
                            | ({"teacher_notes"} if teacher else set()))
    fields = {"instructions", "objectives", "situation", "documents", "questions"}
    content = object_data(projected["content"], fields | ({"teacher_answers"} if teacher else set()))
    header = object_data(projected["header"], {"level", "subject", "question", "notions"})
    for name in ("level", "subject", "question"):
        _text(header[name], 2000)
    _texts(header["notions"], maximum=16)
    _text(projected["notice"], 2000)
    _texts(projected["source_notes"], required=False)
    if teacher:
        _texts(projected["teacher_notes"], required=False)
    _text(content["instructions"], 4000)
    _source(object_data(content["situation"], {"text", "provenance", "evidence_id"}))
    for row in items(content["objectives"], 16):
        object_data(row, {"capability_id", "goal"})
        _text(row["capability_id"], 40)
        _text(row["goal"], 2000)
    for row in items(content["documents"], 12):
        object_data(row, {"document_id", "title", "text", "provenance", "evidence_id"})
        _text(row["document_id"], 40)
        _text(row["title"], 200)
        _source(row)
    for row in items(content["questions"], 30):
        object_data(row, {"question_id", "stage", "prompt", "capability_ids", "document_ids", "success_criteria", "answer_lines"})
        _text(row["question_id"], 40)
        _text(row["stage"], 40)
        _text(row["prompt"], 4000)
        for name in ("capability_ids", "document_ids", "success_criteria"):
            _texts(row[name], maximum=16)
        if type(row["answer_lines"]) is not int or not 1 <= row["answer_lines"] <= 20:
            raise ValueError("EXERCISE_WORD_RESPONSE_TYPE")
    if teacher:
        for row in items(content["teacher_answers"], 30):
            object_data(row, {"question_id", "expected_answer", "rationale", "vigilance", "remediation"})
            for name in row:
                _text(row[name], 4000)
    if not teacher:
        visible = [str(projected["notice"]), *(str(header[k]) for k in ("level", "subject", "question")),
                   *cast(Sequence[str], header["notions"]), *cast(Sequence[str], projected["source_notes"]),
                   str(content["instructions"]), str(object_data(content["situation"])["text"])]
        visible.extend(str(row["goal"]) for row in items(content["objectives"], 16))
        for row in items(content["documents"], 12):
            visible.extend((str(row["title"]), str(row["text"])))
        for row in items(content["questions"], 30):
            visible.extend((str(row["prompt"]), *cast(Sequence[str], row["success_criteria"])))
        require_student_editorial_text(visible)
    return freeze_safe_mapping(projected)
