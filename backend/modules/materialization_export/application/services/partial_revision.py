"""Explicit local document edits; never repairs or replaces the captured source."""
import hashlib
from dataclasses import replace
from typing import cast

from backend.modules.materialization_export.contracts.dto.lot1_word_table import (
    Lot1WordTable,
)
from backend.modules.materialization_export.contracts.dto.partial_word_document import (
    PartialWordDocument,
)
from backend.modules.materialization_export.contracts.dto.word_document import WordBlock
from backend.modules.pedagogical_design.contracts.dto.assessment_bundle import (
    fingerprint,
    items,
    nonempty,
    object_data,
)

_FIELDS = {"schema", "id", "source_sha256", "base_projection_sha256", "changes",
    "insertions", "table_changes", "heights", "teacher_append"}
_KINDS = {"student", "correction"}


def _index(value: object, maximum: int, minimum: int = 0) -> int:
    if type(value) is not int or not minimum <= value < maximum:
        raise ValueError("PARTIAL_REVISION_INDEX")
    return value


def _views(value: object) -> tuple[str, ...]:
    if (not isinstance(value, (list, tuple)) or not value or len(value) > 2
            or any(type(x) is not str or x not in _KINDS for x in value)
            or len(set(value)) != len(value)):
        raise ValueError("PARTIAL_REVISION_VIEWS")
    return tuple(value)


def _blocks(value: object) -> tuple[WordBlock, ...]:
    result = []
    for item in items(value, 40):
        data = object_data(item, {"style", "text"})
        style, text = nonempty(data["style"], 20), nonempty(data["text"], 6000)
        if style not in {"Normal", "Heading1", "Heading2", "Note"}:
            raise ValueError("PARTIAL_REVISION_STYLE")
        result.append(WordBlock(style, text))
    if not result:
        raise ValueError("PARTIAL_REVISION_EMPTY")
    return tuple(result)


def _rows(value: object) -> tuple[tuple[str, ...], ...]:
    if not isinstance(value, (list, tuple)) or any(not isinstance(row, (list, tuple)) for row in value):
        raise ValueError("PARTIAL_REVISION_TABLE")
    result = tuple(tuple(cast(tuple[str, ...], row)) for row in value)
    Lot1WordTable(0, result)
    return result


def revise_partial(documents: dict[str, PartialWordDocument], value: object,
                   source_sha256: str) -> tuple[dict[str, PartialWordDocument], dict[str, object]]:
    plan = object_data(value, _FIELDS)
    base_sha = fingerprint({k: d.as_dict() for k, d in documents.items()})
    if (set(documents) != _KINDS or plan["schema"] != "V2-PARTIAL-LOCAL-REVISION-1.0"
            or plan["source_sha256"] != source_sha256 or plan["base_projection_sha256"] != base_sha):
        raise ValueError("PARTIAL_REVISION_IDENTITY")
    revision_id = nonempty(plan["id"], 80)
    trace: list[dict[str, object]] = []
    changes: dict[tuple[str, int], str] = {}
    insertions: dict[tuple[str, int], tuple[tuple[WordBlock, ...], tuple[Lot1WordTable, ...]]] = {}
    tables: dict[tuple[str, int], tuple[tuple[str, ...], ...]] = {}
    heights: dict[int, int] = {}
    for row in items(plan["changes"], 40):
        row = object_data(row, {"views", "block_index", "before_sha256", "text", "reason"})
        reason, text = nonempty(row["reason"], 500), nonempty(row["text"], 6000)
        for kind in _views(row["views"]):
            index = _index(row["block_index"], len(documents[kind].blocks), 3)
            before = documents[kind].blocks[index].text
            if hashlib.sha256(before.encode()).hexdigest() != row["before_sha256"] or (kind, index) in changes:
                raise ValueError("PARTIAL_REVISION_BEFORE")
            changes[kind, index] = text
            trace.append({"kind":kind, "type":"LOCAL_TEXT_CORRECTION", "block_index":index,
                "before_sha256":row["before_sha256"], "after_sha256":hashlib.sha256(text.encode()).hexdigest(),
                "reason":reason})
    for row in items(plan["insertions"], 20):
        row = object_data(row, {"views", "after_block_index", "blocks", "tables", "reason"})
        insert_blocks, reason = _blocks(row["blocks"]), nonempty(row["reason"], 500)
        added_tables: list[Lot1WordTable] = []
        for table_data in items(row["tables"], 8):
            table_data = object_data(table_data, {"after_block_index", "rows"})
            anchor = _index(table_data["after_block_index"], len(insert_blocks))
            if any(t.after_block_index == anchor for t in added_tables):
                raise ValueError("PARTIAL_REVISION_CONFLICT")
            added_tables.append(Lot1WordTable(anchor, _rows(table_data["rows"])))
        for kind in _views(row["views"]):
            index = _index(row["after_block_index"], len(documents[kind].blocks), 3)
            if (kind, index) in insertions:
                raise ValueError("PARTIAL_REVISION_CONFLICT")
            insertions[kind, index] = insert_blocks, tuple(added_tables)
            trace.append({"kind":kind, "type":"LOCAL_ADDITION", "after_block_index":index,
                "content_sha256":fingerprint(row), "reason":reason})
    for row in items(plan["table_changes"], 12):
        row = object_data(row, {"views", "table_index", "before_sha256", "rows", "reason"})
        reason, rows = nonempty(row["reason"], 500), _rows(row["rows"])
        for kind in _views(row["views"]):
            index = _index(row["table_index"], len(documents[kind].tables))
            if fingerprint(documents[kind].tables[index].rows) != row["before_sha256"] or (kind, index) in tables:
                raise ValueError("PARTIAL_REVISION_TABLE_BEFORE")
            tables[kind, index] = rows
            trace.append({"kind":kind, "type":"LOCAL_TABLE_CORRECTION", "table_index":index,
                "before_sha256":row["before_sha256"], "after_sha256":fingerprint(rows), "reason":reason})
    for row in items(plan["heights"], 12):
        row = object_data(row, {"table_index", "twips"})
        index = _index(row["table_index"], min(len(d.tables) for d in documents.values()))
        height = row["twips"]
        if type(height) is not int or not 360 <= height <= 2000 or index in heights:
            raise ValueError("PARTIAL_REVISION_HEIGHT")
        heights[index] = height
    teacher_append = _blocks(plan["teacher_append"])
    result: dict[str, PartialWordDocument] = {}
    for kind, document in documents.items():
        blocks = list(document.blocks[:3])
        if blocks[0].text != "BROUILLON PARTIEL NON VALIDÉ":
            raise ValueError("PARTIAL_REVISION_STATUS")
        blocks[1] = WordBlock("Note", "Version " + ("élève" if kind == "student" else "enseignant")
            + " — dérivée locale non validée. Les rectifications locales sont tracées ; la capture originale reste inchangée.")
        blocks.append(WordBlock("Note", "Révision locale " + revision_id
            + " — corrections de contenu et de présentation, soumises à validation enseignante."))
        new_tables: list[Lot1WordTable] = []
        row_heights: list[int] = []
        for index, original in enumerate(document.blocks[3:], 3):
            blocks.append(WordBlock(original.style, changes.get((kind, index), original.text)))
            for table_index, table in enumerate(document.tables):
                if table.after_block_index == index:
                    new_tables.append(Lot1WordTable(len(blocks)-1, tables.get((kind, table_index), table.rows)))
                    row_heights.append(heights.get(table_index, 0))
            if (kind, index) in insertions:
                added_blocks, inserted_tables = insertions[kind, index]
                offset = len(blocks)
                blocks.extend(added_blocks)
                new_tables.extend(Lot1WordTable(offset+t.after_block_index, t.rows) for t in inserted_tables)
                row_heights.extend(0 for _ in inserted_tables)
        if kind == "correction":
            blocks.extend((WordBlock("Heading1", "Compléments rédactionnels locaux"),
                WordBlock("Note", "Proposition non validée — non issue de la réponse fournisseur."),
                *teacher_append))
        result[kind] = replace(document, title=document.title+" — Révision locale "+revision_id,
            blocks=tuple(blocks), tables=tuple(new_tables), table_min_row_heights=tuple(row_heights))
    return result, {"revision_id":revision_id, "revision_sha256":fingerprint(plan),
        "base_projection_sha256":base_sha, "changes":trace, "capture_unchanged":True,
        "new_answers_origin":"LOCAL_UNVALIDATED_NOT_PROVIDER", "teacher_append_sha256":fingerprint(plan["teacher_append"]),
        "derived_table_counts":{k:len(d.tables) for k,d in result.items()},
        "heights":plan["heights"]}
