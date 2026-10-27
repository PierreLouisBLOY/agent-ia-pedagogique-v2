"""Existing chapter writer with shared components and explicit specialised layouts."""
from dataclasses import replace
from typing import cast
from xml.etree.ElementTree import Element, SubElement

from backend.adapters.outbound.export.course_media_word import draw_image
from backend.adapters.outbound.export.learning_word_components import (
    _document,
    _p,
    _question,
    _styles,
    _table,
    _w,
    keep_short_group,
    package_word,
    page_footer,
    page_header,
    page_section,
)
from backend.modules.materialization_export.contracts.dto.exercise_word_projection import (
    require_student_editorial_text,
)
from backend.modules.materialization_export.contracts.dto.word_document import WordDocument
from backend.modules.pedagogical_design.contracts.dto.assessment_bundle import items, object_data
from backend.modules.pedagogical_design.contracts.dto.chapter_assembly import (
    ASSEMBLY_CHAPTER_CONTRACT,
)


class CourseOOXMLWordWriter:
    def write(self, document: WordDocument) -> bytes:
        if document.exercise_profile is not None:
            return self._exercise(document)
        chapter = object_data(document.course_chapter)
        teacher = document.kind == "correction"
        assembled = chapter["contract_id"] == ASSEMBLY_CHAPTER_CONTRACT
        assembly = object_data(chapter["assembly"]) if assembled else {}
        if document.kind not in {"student", "correction"} or ("teacher_answers" in chapter) != teacher:
            raise ValueError("COURSE_WORD_PROJECTION")
        projected_media = items(chapter.get("media_assets", []), 8)
        expected_media = tuple(p.asset.projection(p.brief) for p in document.course_media)
        if projected_media != expected_media or any(not p.brief.data["teacher_visibility" if teacher else "student_visibility"] for p in document.course_media):
            raise ValueError("COURSE_WORD_MEDIA_PROVENANCE_BINDING")
        root = Element(_w("document"))
        body = SubElement(root, _w("body"))
        emitted: set[str] = set()
        def media_at(section_ref: str, position: str) -> None:
            for number, pair in enumerate(document.course_media, 1):
                brief = pair.brief.data
                if (brief["section_ref"] == section_ref and brief["preferred_position"] == position
                        and str(brief["visual_id"]) not in emitted):
                    draw_image(body, pair, number)
                    _p(body, str(brief["caption"]), "DocumentText")
                    provenance = object_data(pair.asset.data["provenance"])
                    if provenance["licence"] in {"CC-BY-4.0", "CC-BY-SA-4.0"}:
                        _p(body, "Source : "+str(provenance["source_ref"])+" — "+str(provenance["licence"]), "Footer")
                    emitted.add(str(brief["visual_id"]))
        header = object_data(chapter["program_header"])
        _p(body, "CHAPITRE " + str(chapter["chapter_number"]), "Chapter")
        _p(body, str(chapter["title"]), "Title")
        if assembled and teacher:
            _p(body, "Version professeur — propositions de correction à relire.", "Normal")
        _p(body, str(header["theme_label"]), "Heading2")
        caps = items(chapter["capabilities"])
        if assembled:
            _p(body, str(header["question_label"]), "Normal")
            _p(body, "Capacités travaillées — " + "; ".join(str(c["label"]) for c in caps))
            _p(body, "Notions — " + ", ".join(cast(tuple[str, ...], chapter["notions"])))
        else:
            _table(body, {"columns": ("Repère", "Contenu"), "rows": (
                ("Question du programme", str(header["question_label"])),
                ("Capacités travaillées", "\n".join(str(c["label"]) for c in caps)),
                ("Notions mobilisées", ", ".join(cast(tuple[str, ...], chapter["notions"]))),
            )})
        story = object_data(chapter["context"])
        _p(body, "Contexte — " + str(story["title"]), "Heading2")
        _p(body, str(story["text"]))
        if assembled:
            _p(body, str(object_data(assembly["thread"])["notice"]), "DocumentText")
        media_at("CONTEXT", "AFTER_CONTEXT")
        _p(body, "Votre travail — Lire les documents, relever les faits puis justifier chaque réponse avec les notions du chapitre.")
        docs = {str(d["id"]): d for d in items(chapter["documents"])}
        doc_numbers = {ref: i for i, ref in enumerate(docs, 1)}
        questions = {str(q["id"]): q for q in items(chapter["questions"], 60)}
        concepts = {str(c["id"]): c for c in items(chapter["concepts"])}
        answers = {str(a["id"]): a for a in items(chapter["teacher_answers"], 60)} if teacher else {}
        if assembled and teacher:
            criteria = {str(c["id"]): c["criteria"] for c in items(assembly["answer_criteria"], 60)}
            answers = {key: {**row, "criteria": criteria[key]} for key, row in answers.items()}
        def conceptualize(part: dict[str, object]) -> None:
            vigilance = ({str(v["id"]): v["text"] for v in items(assembly["concept_vigilance"])} if assembled else {})
            for ref in cast(tuple[str, ...], part["concept_ids"]):
                c = concepts[ref]
                _p(body, "Notion — " + str(c["notion"]), "ConceptTitle")
                concept_text = str(c["definition"]) + "\n" + str(c["explanation"]) + "\nExemple — " + str(c["example"])
                if ref in vigilance:
                    concept_text += "\nAttention — " + str(vigilance[ref])
                concept_p = _p(body, concept_text, "ConceptText")
                if assembled:
                    properties = concept_p.find(_w("pPr"))
                    assert properties is not None
                    SubElement(properties, _w("keepLines"))
                media_at(ref, "AFTER_CONCEPT")
        flowing_teacher = teacher and bool(document.course_media)
        enriched = any(p.brief.data["style_policy"] == "COURSE_LOCAL_ILLUSTRATION_V2" for p in document.course_media)
        for part_index, part in enumerate(items(chapter["parts"])):
            _p(body, str(part["title"]), "Heading1", before=(part_index == 0 or not flowing_teacher) and not assembled)
            meta = next((m for m in items(assembly["parts"]) if m["id"] == part["id"]), {}) if assembled else {}
            if assembled:
                transition_p = _p(body, str(meta["transition"]))
                transition_props = transition_p.find(_w("pPr"))
                assert transition_props is not None
                SubElement(transition_props, _w("keepNext"))
            early = assembled and object_data(meta["formalization"])["position"] == "BEFORE_ACTIVITY"
            if early:
                conceptualize(part)
            for ref in cast(tuple[str, ...], part["document_ids"]):
                _document(body, docs[ref], doc_numbers[ref], grouped=assembled)
                media_at(ref, "AFTER_DOCUMENT")
            for role in ("observation", "analysis"):
                for ref in cast(tuple[str, ...], part[role]):
                    _question(body, questions[ref], answers.get(ref), keep_responses=enriched or assembled)
            if not early:
                conceptualize(part)
            for ref in cast(tuple[str, ...], part["reinvestment"]):
                _question(body, questions[ref], answers.get(ref), keep_responses=enriched or assembled)
        if assembled:
            _p(body, "À retenir", "Heading1")
            _p(body, str(chapter["synthesis"]), "ConceptText")
        _p(body, "Tester ses connaissances", "Heading1", before=not flowing_teacher and not enriched and not assembled)
        for ref in cast(tuple[str, ...], chapter["knowledge_check"]):
            _question(body, questions[ref], answers.get(ref), keep_responses=enriched or assembled)
        if not assembled:
            _p(body, "À retenir", "Heading2")
            _p(body, str(chapter["synthesis"]), "ConceptText")
        transfer = object_data(chapter["transfer"])
        _p(body, str(transfer["title"]), "Heading1", before=not flowing_teacher and not assembled)
        for ref in cast(tuple[str, ...], transfer["document_ids"]):
            _document(body, docs[ref], doc_numbers[ref], grouped=assembled)
            media_at(ref, "AFTER_DOCUMENT")
        for ref in cast(tuple[str, ...], transfer["question_ids"]):
            _question(body, questions[ref], answers.get(ref), keep_responses=enriched or assembled)
        if assembled and teacher:
            _p(body, "Sources et choix pédagogiques", "Heading1")
            for source in items(assembly["sources"]):
                _p(body, str(source["title"]) + " — " + str(source["publisher"]) + " — consultation " + str(source["consulted_on"]), "DocumentTitle")
                _p(body, str(source["fact"]) + "\n" + str(source["locator"]) + "\n" + str(source["rights"]), "DocumentText")
                if source["url"]:
                    _p(body, str(source["url"]), "DocumentText")
            for source in items(assembly["document_sources"]):
                _p(body, "Document " + str(doc_numbers[str(source["id"])]) + " — " + str(source["nature"]) + " — " + str(source["limits"]), "DocumentText")
        page_section(body, reference001=assembled and not teacher)
        header_node = page_header(str(header["subject_label"]), str(header["level_label"]))
        footer_node = page_footer("Chapitre " + str(chapter["chapter_number"]) + " • Version " + ("professeur" if teacher else "élève"))
        if len(emitted) != len(document.course_media):
            raise ValueError("COURSE_WORD_MEDIA_NOT_PLACED")
        if assembled:
            for table in body.findall(_w("tbl")):
                first_row = table.find(_w("tr"))
                assert first_row is not None
                for paragraph in first_row.findall(".//" + _w("pPr")):
                    SubElement(paragraph, _w("keepNext"))
                if not teacher:
                    for shade in first_row.findall(".//" + _w("shd")):
                        shade.set(_w("fill"), "4B3268")
        return package_word(root, _styles(reference001=assembled and not teacher), header_node,
                            footer_node, tuple(pair.asset.raw for pair in document.course_media))

    @staticmethod
    def _exercise(document: WordDocument) -> bytes:
        """A proportionate layout on the very same chapter OOXML components."""
        document = replace(document)  # Revalidate a forged or substituted DTO before rendering.
        projected = object_data(document.exercise_content)
        content = object_data(projected["content"])
        header = object_data(projected["header"])
        teacher = document.kind == "correction"
        if ("teacher_answers" in content) != teacher:
            raise ValueError("EXERCISE_WORD_STUDENT_TEACHER_BINDING")
        if not teacher:
            require_student_editorial_text([document.title])
        root = Element(_w("document"))
        body = SubElement(root, _w("body"))
        _p(body, document.title, "Title")
        if projected["notice"]:
            _p(body, str(projected["notice"]), "DocumentText")
        _p(body, str(header["question"]), "Normal")
        _p(body, "Notions — " + ", ".join(cast(list[str], header["notions"])), "DocumentText")
        _p(body, "Objectifs de travail", "Heading1")
        for goal in items(content["objectives"], 16):
            _p(body, str(goal["goal"]), "Normal")
        story = object_data(content["situation"])
        _p(body, "Situation", "Heading1")
        _p(body, ("Situation fictive. " if story["provenance"] == "LOCAL_FICTION" else "Référence fournie. ") + str(story["text"]))
        for row in items(content["documents"], 12):
            number = int(str(row["document_id"])[1:])
            text = ("Situation fictive. " if row["provenance"] == "LOCAL_FICTION" else "Référence fournie. ") + str(row["text"])
            _document(body, {"title": row["title"], "text": text, "table": None}, number, grouped=True)
        _p(body, "Consignes", "Heading1")
        _p(body, str(content["instructions"]))
        answers = {str(row["question_id"]): row for row in items(content.get("teacher_answers", []), 30)}
        labels = {"OBSERVE": "Observer", "ANALYSE": "Analyser", "APPLY": "Réinvestir"}
        last_stage = None
        for number, row in enumerate(items(content["questions"], 30), 1):
            start = len(body)
            if row["stage"] != last_stage:
                _p(body, labels[str(row["stage"])], "Heading2")
                last_stage = row["stage"]
            ids = cast(tuple[str, ...], row["document_ids"])
            prompt = str(row["prompt"]) + " (" + ("Document " if len(ids) == 1 else "Documents ") + ", ".join(str(int(ref[1:])) for ref in ids) + ")"
            criteria = "; ".join(cast(list[str], row["success_criteria"]))
            answer = answers.get(str(row["question_id"]))
            if answer is not None:
                answer = {**answer, "criteria": criteria}
            _question(body, {"number": number, "prompt": prompt,
                            "response": {"lines": row["answer_lines"], "table": None}}, answer,
                      keep_responses=True, student_criteria=criteria, keep_answer_criteria=False)
            keep_short_group(body, start)
        if projected["source_notes"] or teacher:
            _p(body, "Traçabilité interne du professeur" if teacher else "Sources", "Heading1")
        for note in cast(list[str], projected["source_notes"]):
            _p(body, note, "Footer")
        if teacher:
            for note in cast(list[str], projected["teacher_notes"]):
                _p(body, note, "Footer")
        page_section(body, reference001=not teacher)
        return package_word(root, _styles(exercise_compact=teacher), page_header(str(header["subject"]), str(header["level"])),
                            page_footer("Exercice • Version " + ("professeur" if teacher else "élève")))
