"""CAP-A03 from complete structured fields, never from locator slices."""
from collections.abc import Callable
from typing import cast

from backend.modules.materialization_export.contracts.dto.word_document import (
    WordBlock,
    WordDocument,
)
from backend.modules.materialization_export.ports.outbound.word_writer import WordWriter
from backend.modules.pedagogical_design.contracts.dto.assessment_bundle import items, object_data
from backend.modules.work_orchestration.contracts.dto.saved_production import SavedProduction


class ExportSavedCommand:
    def __init__(self, writer: WordWriter, *, presentation: Callable[[WordDocument], WordDocument] | None = None) -> None:
        self.writer = writer
        self.presentation = presentation

    def preview(self, record: SavedProduction, kind: str, *, promoted: bool = False) -> WordDocument:
        document = self._preview(record, kind, promoted=promoted)
        if document.course_chapter is not None:
            return document
        if (self.presentation and kind != "student" and record.p0_bundle is not None
                and "fictif" in str(record.p0_bundle.data["title"]).casefold()):
            document = WordDocument(document.kind, document.title, (WordBlock("Note", "Cas fictif"), *document.blocks))
        return self.presentation(document) if self.presentation else document

    def _preview(self, record: SavedProduction, kind: str, *, promoted: bool = False) -> WordDocument:
        titles = {"student": "Sujet élève", "correction": "Corrigé professeur", "marking": "Barème"}
        if kind not in titles:
            raise ValueError("R4_EXPORT_KIND")
        if record.p0_bundle is not None:
            return self._preview_p0(record, kind, promoted=promoted)
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

    @staticmethod
    def _preview_p0(record: SavedProduction, kind: str, *, promoted: bool) -> WordDocument:
        bundle = record.p0_bundle
        if bundle is None:
            raise ValueError("R6_P0_BUNDLE_REQUIRED")
        if "course_chapter" in bundle.data:
            if kind == "marking":
                return WordDocument(kind, "Barème", (WordBlock("Normal", "Aucun barème chiffré pour ce cours."),))
            from backend.modules.pedagogical_design.contracts.dto.course_chapter import (
                CourseChapter,
            )

            chapter = CourseChapter(object_data(bundle.data["course_chapter"]))
            chapter.bind_context(bundle.context)
            preview = tuple(block for section in chapter.sections() for block in (
                WordBlock("Heading1", str(section["heading"])), WordBlock("Normal", str(section["text"]))))
            if kind == "correction":
                preview += tuple(block for answer in items(chapter.data["teacher_answers"], 60) for block in (
                    WordBlock("Heading2", str(answer["id"])),
                    WordBlock("Normal", str(answer["expected_answer"]) + "\n" + str(answer["rationale"]))))
            return WordDocument(kind, str(chapter.data["title"]), preview,
                                course_chapter=chapter.projection(teacher=kind == "correction"),
                                course_media=chapter.media(teacher=kind == "correction"))
        titles = {"student": "Document élève", "correction": "Corrigé professeur",
                  "marking": "Barème"}
        blocks: list[WordBlock] = []
        from backend.modules.pedagogical_context.contracts.dto.stmg_institutional import (
            institutional_header,
        )

        context = object_data(bundle.data["context"])
        header = institutional_header(context)
        if header is not None:
            blocks.append(WordBlock("Normal", header))
            resolution = context.get("institutional_resolution")
            if resolution is not None:
                exact = object_data(resolution)
                if exact.get("contract_id") == "BTS-RESOLUTION-1.0":
                    process, activity = object_data(exact["process"]), object_data(exact["activity"])
                    blocks.append(WordBlock("Normal", str(process["official_label"]) + " · " + str(activity["official_label"])))
                else:
                    question = object_data(exact["question"])
                    theme_data = exact.get("theme")
                    theme = str(object_data(theme_data)["official_label"]) if theme_data is not None else "Thème " + str(exact["theme_ref"]).removeprefix("theme:") if exact["theme_ref"] else "Thème non renseigné"
                    blocks.append(WordBlock("Normal", theme + " · " + str(question["official_label"])))
            blocks.append(WordBlock("Note", "CANDIDATE — à valider par l’enseignant."))
        if kind != "student":
            blocks.append(WordBlock(
                "Note",
                "PROMOTION EXPLICITE ENREGISTRÉE"
                if promoted
                else "CANDIDATE — NON VALIDÉE. Sauvegarder/exporter ne vaut pas valider.",
            ))
            blocks.append(WordBlock("Note", "Version exacte : " + record.version_ref))
        if kind == "student":
            before: dict[str, dict[str, object]] = {}
            question_ids = [str(q["question_id"]) for q in items(bundle.data["questions"], 60)]
            for section in items(bundle.data["sections"], 16):
                section_id = str(section["section_id"])
                if section_id.startswith("S_BEFORE_"):
                    question_id = section_id.removeprefix("S_BEFORE_")
                    if question_id not in question_ids or question_id in before:
                        raise ValueError("P0_ASSEMBLY_QUESTION_LINK")
                    before[question_id] = section
                    continue
                blocks.extend((WordBlock("Heading1", str(section["heading"])),
                               WordBlock("Normal", str(section["text"]))))
            for question in items(bundle.data["questions"], 60):
                introduction = before.get(str(question["question_id"]))
                if introduction is not None:
                    blocks.extend((WordBlock("Heading1", str(introduction["heading"])),
                                   WordBlock("Normal", str(introduction["text"]))))
                blocks.append(WordBlock("Heading2", str(question["question_id"])))
                blocks.append(WordBlock("Normal", str(question["prompt"])))
                for option in cast(tuple[str, ...], question["options"]):
                    blocks.append(WordBlock("Normal", "• " + option))
        elif kind == "correction":
            for correction in items(bundle.data["corrections"], 60):
                blocks.extend((WordBlock("Heading1", str(correction["question_id"])),
                               WordBlock("Normal", str(correction["expected_answer"])),
                               WordBlock("Heading2", "Justification"),
                               WordBlock("Normal", str(correction["rationale"]))))
        else:
            marking = items(bundle.data["marking"], 60)
            if not marking:
                blocks.append(WordBlock("Normal", "Aucun barème chiffré pour cette typologie."))
            for entry in marking:
                blocks.append(WordBlock(
                    "Heading1", str(entry["question_id"]) + " — " + str(entry["points"])
                    + " points",
                ))
                for criterion in cast(tuple[str, ...], entry["criteria"]):
                    blocks.append(WordBlock("Normal", criterion))
        title = str(bundle.data["title"]) if header is not None and kind == "student" else titles[kind]
        return WordDocument(kind, title, tuple(blocks))

    def execute(self, record: SavedProduction, kind: str, *, promoted: bool = False) -> bytes:
        return self.writer.write(self.preview(record, kind, promoted=promoted))
