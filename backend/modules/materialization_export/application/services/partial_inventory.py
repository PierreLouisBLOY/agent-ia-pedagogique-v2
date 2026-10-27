"""Fidelity checks inside Application; metadata output contains no raw captured text."""
import hashlib
from typing import cast

from backend.modules.materialization_export.application.services.partial_chapter import (
    capture_tree,
    present,
)
from backend.modules.materialization_export.contracts.dto.partial_word_document import (
    PartialWordDocument,
)
from backend.modules.pedagogical_design.contracts.dto.assessment_bundle import (
    fingerprint,
    items,
    object_data,
)
from backend.modules.work_orchestration.contracts.dto.p0_captured_partial import CapturedPartial


def partial_inventory(capture: CapturedPartial, documents: dict[str, PartialWordDocument]) -> dict[str, object]:
    text = capture.text
    root = capture_tree(text)
    chapter = root.members["course_chapter"]
    source_fields: list[tuple[str, str, str]] = []
    source_tables: list[dict[str, object]] = []

    def add(path: str, value: object, audience: str = "common") -> None:
        if type(value) is not str:
            raise ValueError("PARTIAL_INVENTORY_REJECTED")
        source_fields.append((path, value, audience))

    add("title", present(text, root.members["title"], "string"))
    for name in ("context", "transfer"):
        row = object_data(present(text, chapter.members[name], "object"))
        add(name + ".title", row["title"])
        if name == "context":
            add(name + ".text", row["text"])
    specs = {"documents": ("title", "text"), "parts": ("title",), "questions": ("prompt",),
        "concepts": ("definition", "explanation", "example")}
    for name, fields in specs.items():
        for index, row in enumerate(items(present(text, chapter.members[name], "array"))):
            path = f"{name}.{index}"
            for field in fields:
                add(path + "." + field, row[field])
            table = row.get("table") if name == "documents" else (
                object_data(row["response"])["table"] if name == "questions" else None)
            if table is not None:
                source_tables.append(object_data(table, {"columns", "rows"}))
    add("synthesis", present(text, chapter.members["synthesis"], "string"))
    missing: list[str] = []
    complete_answers = 0
    for index, node in enumerate(chapter.members["teacher_answers"].elements):
        if node.complete:
            row = object_data(present(text, node, "object"))
            for field in ("expected_answer", "rationale", "vigilance", "remediation"):
                add(f"teacher_answers.{index}.{field}", row[field], "teacher")
            complete_answers += 1
        else:
            fragment = node.members["expected_answer"]
            add(f"teacher_answers.{index}.fragment", text[fragment.start + 1:fragment.end], "teacher")
            missing.append(str(present(text, node.members["id"], "string")) + " incomplete")
    answer_ids = {str(present(text, node.members["id"], "string")) for node in chapter.members["teacher_answers"].elements}
    for row in items(present(text, chapter.members["questions"], "array")):
        if row["id"] not in answer_ids:
            missing.append(str(row["id"]) + " absent")
    field_checks: list[dict[str, object]] = []
    for path, value, audience in source_fields:
        found = {kind: value in doc.title or any(value in block.text for block in doc.blocks)
            for kind, doc in documents.items()}
        if not found["correction"] or (audience == "common" and not found["student"]):
            raise ValueError("PARTIAL_TEXT_FIDELITY_CHANGED")
        field_checks.append({"path": path, "sha256": hashlib.sha256(value.encode()).hexdigest(),
            "audience": audience, "present_in_student": found["student"], "present_in_teacher": found["correction"]})
    expected = [(tuple(cast(tuple[str, ...], table["columns"])),
        *(tuple(cast(tuple[str, ...], row)) for row in cast(tuple[object, ...], table["rows"]))) for table in source_tables]
    for doc in documents.values():
        if [table.rows for table in doc.tables] != expected:
            raise ValueError("PARTIAL_TABLE_FIDELITY_CHANGED")
    return {"source_sha256": capture.request.text_sha256, "source_bytes": capture.request.text_bytes,
        "command_id": capture.request.command_id,
        "complete_documents": len(chapter.members["documents"].elements),
        "complete_questions": len(chapter.members["questions"].elements),
        "complete_concepts": len(chapter.members["concepts"].elements),
        "complete_answers": complete_answers, "missing": missing,
        "table_sha256s": [fingerprint(rows) for rows in expected],
        "empty_cells": [sum(cell == "" for row in rows for cell in row) for rows in expected],
        "field_checks": field_checks, "tables_equal_in_both_views": True,
        "metadata_not_rendered": ["document function/provenance", "capability and notion identifiers", "progression links"],
        "source_capture_modified": False, "new_pedagogical_answers": False}
