"""CAP-A03 from complete structured fields, never from locator slices."""
from typing import cast

from backend.modules.materialization_export.contracts.dto.word_document import (
    WordBlock,
    WordDocument,
)
from backend.modules.materialization_export.ports.outbound.word_writer import WordWriter
from backend.modules.pedagogical_design.contracts.dto.assessment_bundle import items, object_data
from backend.modules.work_orchestration.contracts.dto.saved_production import SavedProduction


class ExportSavedCommand:
    def __init__(self, writer: WordWriter) -> None:
        self.writer = writer

    def preview(self, record: SavedProduction, kind: str, *, promoted: bool = False) -> WordDocument:
        titles = {"student": "Sujet élève", "correction": "Corrigé professeur", "marking": "Barème"}
        if kind not in titles:
            raise ValueError("R4_EXPORT_KIND")
        blocks: list[WordBlock] = []
        if kind == "student":
            # No correction, metadata, calculations or report is handed to the writer.
            for section in items(record.view.data["sections"], 5):
                blocks.extend((WordBlock("Heading1", str(section["section_id"]).replace("_", " ")),
                               WordBlock("Normal", str(section["text"]))))
            return WordDocument(kind, titles[kind], tuple(blocks))
        blocks.append(WordBlock("Note", "PROMOTION EXPLICITE ENREGISTRÉE" if promoted
                                else "CANDIDATE — NON VALIDÉE. Sauvegarder/exporter ne vaut pas valider."))
        blocks.append(WordBlock("Note", "Version exacte : " + record.version_ref))
        blocks.append(WordBlock("Note", "A16 : appréciation pédagogique humaine distincte ; "
                                "une review d'une autre version n'est pas héritée."))
        blocks.extend(WordBlock("Note", s) for s in cast(tuple[str, ...], record.data["reservations"]))
        bundle = record.bundle
        if bundle is None:
            raise ValueError("R4_BUNDLE_REQUIRED")
        blocks.extend(WordBlock("Note", s) for s in cast(tuple[str, ...], bundle.data["limitations"]))
        if kind == "correction":
            for answer in items(object_data(bundle.data["correction"])["answers"]):
                blocks.extend((WordBlock("Heading1", str(answer["question_id"])),
                               WordBlock("Normal", str(answer["expected_answer"])),
                               WordBlock("Heading2", "Justification"),
                               WordBlock("Normal", str(answer["rationale"]))))
        else:
            marking = object_data(bundle.data["marking"])
            blocks.append(WordBlock("Normal", "Total : " + str(marking["total_points"]) + " points"))
            for dossier in items(marking["dossiers"]):
                blocks.append(WordBlock("Heading1", str(dossier["dossier_id"]) + " — "
                                        + str(dossier["duration_minutes"]) + " minutes"))
                for question in items(dossier["questions"]):
                    blocks.append(WordBlock("Heading2", str(question["question_id"]) + " — "
                                            + str(question["points"]) + " points"))
                    for criterion in items(question["criteria"]):
                        blocks.append(WordBlock("Normal", str(criterion["criterion_id"]) + " : "
                            + str(criterion["description"]) + " — " + str(criterion["points"]) + " points"))
        return WordDocument(kind, titles[kind], tuple(blocks))

    def execute(self, record: SavedProduction, kind: str, *, promoted: bool = False) -> bytes:
        return self.writer.write(self.preview(record, kind, promoted=promoted))
