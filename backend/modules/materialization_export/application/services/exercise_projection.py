"""Project only allowlisted exercise fields; teacher content never enters student blocks."""
from typing import cast

from backend.modules.materialization_export.contracts.dto.exercise_word_projection import (
    require_student_editorial_text,
)
from backend.modules.materialization_export.contracts.dto.word_document import (
    WordBlock,
    WordDocument,
)
from backend.modules.pedagogical_context.contracts.dto.exercise_context import exercise_focus
from backend.modules.pedagogical_design.contracts.dto.assessment_bundle import items, object_data
from backend.modules.pedagogical_design.contracts.dto.exercise_profile import StructuredExercise
from backend.modules.pedagogical_design.contracts.dto.p0_production import P0Production


def project_exercise(bundle: P0Production, kind: str, *, reservations: tuple[str, ...] = ()) -> WordDocument:
    if kind not in {"student", "correction"}:
        return WordDocument(kind, "Barème", (WordBlock("Normal", "Exercice sans barème chiffré."),))
    focus = exercise_focus(bundle.context.data)
    exercise = StructuredExercise(object_data(bundle.data["exercise"]), case_study=bundle.context.data["contract_id"] == "P0-CONTEXT-CASE-STUDY-1.0")
    # Exclude teacher_answers before any student projection logic can access rows.
    content = exercise.projection(teacher=kind == "correction")
    if exercise.case_study:
        from backend.modules.pedagogical_design.contracts.dto.case_study import CaseStudyDossier
        dossier = CaseStudyDossier(object_data(content.pop("case_study")))
        situation = object_data(content["situation"])
        content["situation"] = {**situation, "text": str(situation["text"]) + "\n" + dossier.public_text()}
    level = {"FIRST_STMG": "Première STMG", "FINAL_STMG": "Terminale STMG",
             "BTS_CG_YEAR_1": "BTS CG première année", "BTS_CG_YEAR_2": "BTS CG deuxième année"}[str(bundle.context.data["level"])]
    blocks = [WordBlock("Note", level + " · " + str(bundle.context.data["discipline"])),
              WordBlock("Normal", str(focus["question_label"])),
              WordBlock("Note", "Notions : " + ", ".join(str(row["label"]) for row in items(focus["notions"], 16))),
              WordBlock("Heading1", "Objectifs de travail")]
    if "LOCAL_ORIGINAL_NO_PROVIDER_CALL" in reservations:
        blocks.insert(0, WordBlock("Note", "Démonstration locale sans génération fournisseur."))
    blocks.extend(WordBlock("Normal", str(row["goal"])) for row in items(content["objectives"], 16))
    blocks.extend((WordBlock("Heading1", "Situation"),
                   WordBlock("Normal", exercise._source_text(object_data(content["situation"])))))
    for document in items(content["documents"], 12):
        blocks.extend((WordBlock("Heading1", "Document " + str(document["document_id"])[1:] + " " + str(document["title"])),
                       WordBlock("Normal", exercise._source_text(document))))
    blocks.extend((WordBlock("Heading1", "Consignes"), WordBlock("Normal", str(content["instructions"]))))
    groups = []
    focus_notes: list[WordBlock] = []
    answers = {str(row["question_id"]): row for row in items(content.get("teacher_answers", []), 30)}
    stages = {"OBSERVE": "Observer", "ANALYSE": "Analyser", "APPLY": "Réinvestir"}
    for question in items(content["questions"], 30):
        start = len(blocks)
        qid = str(question["question_id"])
        ids = cast(tuple[str, ...], question["document_ids"])
        document_label = ("Document " if len(ids) == 1 else "Documents ") + ", ".join(str(int(ref[1:])) for ref in ids)
        blocks.extend((WordBlock("Heading1", "Question " + qid[1:] + " " + stages[str(question["stage"])]),
                       WordBlock("Note", document_label),
                       WordBlock("Normal", str(question["prompt"]))))
        if kind == "student":
            blocks.append(WordBlock("Note", "Réussir : " + " ; ".join(cast(tuple[str, ...], question["success_criteria"]))))
            blocks.append(WordBlock("Normal", "\n".join("................................................................................................" for _ in range(cast(int, question["answer_lines"])))) )
        else:
            answer = answers[qid]
            for field, heading in (("expected_answer", "Réponse attendue"), ("rationale", "Justification"),
                                    ("vigilance", "Point de vigilance"), ("remediation", "Remédiation")):
                blocks.extend((WordBlock("Heading2", heading), WordBlock("Normal", str(answer[field]))))
        groups.append((start, len(blocks) - 1))
    if kind == "correction":
        if focus.get("local_focus_authority"):
            focus_notes = [WordBlock("Note", "Question travaillée : focalisation pédagogique locale, sans relation officielle plus étroite."),
                           WordBlock("Note", "Libellé institutionnel complet : " + str(focus["source_question_label"])),
                           WordBlock("Note", "Empreinte de la question source : " + str(focus["source_question_sha256"]))]
            blocks.extend(focus_notes)
        blocks.extend((WordBlock("Heading1", "Traçabilité interne du professeur"),
                   WordBlock("Note", "Rattachement institutionnel à confirmer. Relecture enseignante requise."
                             if focus["institutional_status"] == "CONTENT_GAP" else "Cadrage institutionnel sélectionné. Relecture enseignante requise.")))
        for ref in items(bundle.data["references"], 8):
            blocks.append(WordBlock("Note", str(ref["source_ref"]) + " · " + str(ref["locator"])))
    if kind == "correction":
        blocks.append(WordBlock("Heading1", "Limites de cette candidate"))
        blocks.append(WordBlock("Note", "Version conservée : " + bundle.version_ref))
        blocks.extend(WordBlock("Note", text) for text in cast(tuple[str, ...], bundle.data["limitations"]))
        names = {"LOCAL_ORIGINAL_NO_PROVIDER_CALL": "Rédaction locale originale sans appel fournisseur.",
                 "TEACHER_ACCEPTANCE_NOT_PERFORMED": "Acceptation pédagogique par l'enseignant non effectuée."}
        blocks.extend(WordBlock("Note", names.get(text, text)) for text in reservations)
    if kind == "student":
        require_student_editorial_text([str(bundle.data["title"]), *(block.text for block in blocks)])
    local_original = "LOCAL_ORIGINAL_NO_PROVIDER_CALL" in reservations
    if kind == "correction":
        notice = "Corrigé professeur — qualification locale sans génération fournisseur." if local_original else "Corrigé professeur — propositions à relire."
    else:
        notice = "Démonstration locale sans génération fournisseur." if local_original else "Exercice"
    teacher_notes = [block.text for block in blocks[groups[-1][1]+1:] if block.style == "Note"] if kind == "correction" else []
    if focus_notes:
        # Only these generated metadata rows are compacted for print. Full
        # source label/hash remain in the Application blocks and saved context.
        teacher_notes = teacher_notes[len(focus_notes):]
        teacher_notes[0] += " Focalisation pédagogique locale, sans relation officielle plus étroite ; question institutionnelle complète et empreinte conservées dans V2."
        # Metadata only: keep every source/status/limitation verbatim while
        # avoiding a separate short paragraph for each internal marker.
        teacher_notes = [teacher_notes[0], " · ".join(teacher_notes[1:])]
    return WordDocument(kind, str(bundle.data["title"]), tuple(blocks),
                        exercise_profile="EXERCISE-WORD-1.0",
                        exercise_content={"content": content,
                            "notice": notice,
                            "header": {"level": level,
                            "subject": bundle.context.data["discipline"], "question": focus["question_label"],
                            "notions": [row["label"] for row in items(focus["notions"], 16)]},
                            "source_notes": [],
                            **({"teacher_notes": teacher_notes} if kind == "correction" else {})})
