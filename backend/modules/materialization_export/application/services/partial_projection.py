"""Readable projections of the same partial capture, with native table structures."""
from typing import cast

from backend.modules.materialization_export.application.services.partial_chapter import (
    capture_tree,
    present,
)
from backend.modules.materialization_export.contracts.dto.lot1_word_table import Lot1WordTable
from backend.modules.materialization_export.contracts.dto.partial_word_document import (
    PartialWordDocument,
)
from backend.modules.materialization_export.contracts.dto.word_document import WordBlock
from backend.modules.pedagogical_design.contracts.dto.assessment_bundle import items, object_data
from backend.modules.work_orchestration.contracts.dto.p0_captured_partial import CapturedPartial


def partial_document(capture: CapturedPartial, kind: str) -> PartialWordDocument:
    if type(capture) is not CapturedPartial or kind not in {"student", "correction"}:
        raise ValueError("PARTIAL_DOCUMENT_REJECTED")
    text = capture.text
    root = capture_tree(text)
    chapter = root.members["course_chapter"]
    title = str(present(text, root.members["title"], "string"))
    blocks = [WordBlock("Note", "BROUILLON PARTIEL NON VALIDÉ"), WordBlock("Note",
        "Version " + ("élève — sans corrigé." if kind == "student" else "enseignant — corrigé partiel.")
        + " Document à relire avant utilisation. Aucun contenu manquant n’a été complété."),
        WordBlock("Note", "Capture " + capture.request.command_id + " · Texte SHA256 " + capture.request.text_sha256)]
    tables: list[Lot1WordTable] = []

    def block(style: str, value: object) -> None:
        if type(value) is not str:
            raise ValueError("PARTIAL_TEXT_REJECTED")
        blocks.append(WordBlock(style, value))

    def table(value: object) -> None:
        data = object_data(value, {"columns", "rows"})
        if (not isinstance(data["columns"], (list, tuple))
                or not isinstance(data["rows"], (list, tuple))
                or any(not isinstance(row, (list, tuple)) for row in data["rows"])):
            raise ValueError("PARTIAL_TABLE_REJECTED")
        rows = (tuple(cast(tuple[str, ...], data["columns"])),
            *(tuple(cast(tuple[str, ...], row)) for row in cast(tuple[object, ...], data["rows"])))
        tables.append(Lot1WordTable(len(blocks) - 1, rows))

    context = object_data(present(text, chapter.members["context"], "object"))
    block("Heading1", context["title"])
    block("Normal", context["text"])
    for row in items(present(text, chapter.members["parts"], "array")):
        block("Heading1", row["title"])
    block("Heading1", "Documents")
    documents = items(present(text, chapter.members["documents"], "array"))
    for row in documents:
        block("Heading2", str(row["id"]) + " — " + str(row["title"]))
        block("Normal", row["text"])
        if row["table"] is not None:
            table(row["table"])
    block("Heading1", "Activités")
    questions = items(present(text, chapter.members["questions"], "array"), 60)
    transfer = object_data(present(text, chapter.members["transfer"], "object"))
    for row in questions:
        if row["id"] in cast(tuple[str, ...], transfer["question_ids"]):
            block("Heading2", transfer["title"])
        block("Heading2", row["id"])
        block("Normal", row["prompt"])
        response = object_data(row["response"])
        if response["table"] is not None:
            table(response["table"])
        else:
            lines = response["lines"]
            if type(lines) is not int or not 1 <= lines <= 30:
                raise ValueError("PARTIAL_RESPONSE_LINES")
            block("Normal", "\n".join("........................................................................" for _ in range(lines)))
    block("Heading1", "Notions")
    for row in items(present(text, chapter.members["concepts"], "array")):
        block("Heading2", row["id"])
        for key in ("definition", "explanation", "example"):
            block("Normal", row[key])
    block("Heading1", "Synthèse")
    block("Normal", present(text, chapter.members["synthesis"], "string"))
    if kind == "correction":
        block("Heading1", "Corrigé partiel")
        answers = chapter.members["teacher_answers"]
        if answers.kind != "array" or answers.complete:
            raise ValueError("PARTIAL_ANSWERS_SHAPE")
        answered: set[str] = set()
        for node in answers.elements:
            reference = str(present(text, node.members["id"], "string"))
            if reference in answered or reference not in {row["id"] for row in questions}:
                raise ValueError("PARTIAL_ANSWER_IDENTITY")
            answered.add(reference)
            block("Heading2", reference)
            if node.complete:
                row = object_data(present(text, node, "object"))
                for label, key in (("Réponse capturée", "expected_answer"), ("Justification", "rationale"),
                    ("Point de vigilance", "vigilance"), ("Remédiation", "remediation")):
                    block("Heading2", label)
                    block("Normal", row[key])
            else:
                fragment = node.members["expected_answer"]
                if fragment.complete or fragment.kind != "string" or fragment.end != len(text):
                    raise ValueError("PARTIAL_FRAGMENT_REJECTED")
                block("Note", "Réponse interrompue — fragment littéral, non complété.")
                block("Normal", text[fragment.start + 1:fragment.end])
                block("Note", "La suite de cette réponse et ses commentaires ne sont pas capturés.")
        for row in questions:
            if row["id"] not in answered:
                block("Heading2", row["id"])
                block("Note", "Réponse non capturée — aucun complément ajouté.")
    return PartialWordDocument(kind, title + (" Version élève" if kind == "student" else " Version enseignant"),
        tuple(blocks), tables=tuple(tables))
