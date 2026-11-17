"""Chapter 3, Première STMG: structural replay, no external generation."""
from copy import deepcopy

import pytest

from backend.adapters.outbound.generation.openai.p0_content import (
    bind_p0_content,
    build_p0_content_request,
)
from backend.modules.pedagogical_design.contracts.dto.assessment_bundle import as_plain
from tests import normal_on_323a_fixture as f
from tests.unit.test_stmg_institutional_alignment import Catalog, app, prepare

PARTS = (
    ("I. Caractéristiques des groupes", "Groupes primaires et secondaires", "Le lundi matin de Yoann", "AFTER_OBSERVATION"),
    ("II. Appartenance et référence aux groupes", "Appartenance et référence", "Le parcours de Yoann", "AFTER_DOCUMENTS"),
    ("III. Statut et identité", "Statut et identité", "Les rôles des membres de DAT SECURITY", "AFTER_ANALYSIS"),
    ("IV. Communication interpersonnelle", "Communication interpersonnelle", "Les entretiens de recrutement", "AFTER_DOCUMENTS"),
)
TASKS = ("Activité 1 — Travailler la notion de groupe",
         "Activité 2 — Analyser les composantes de la communication interpersonnelle, le statut et l’identité de l’individu")


def selection():
    selected = f.context()
    selected.update(contract_id="P0-CONTEXT-COURSE-3.0", course_format="CHAPTER",
                    resource_type="COURSE", topics=[p[1] for p in PARTS])
    selected["local_progression"]["chapter"] = "3"
    return selected


def replay():
    questions, answers, docs, concepts, parts, tasks = [], [], [], [], [], []

    def document(title, function):
        ref = f"D{len(docs)+1}"
        docs.append({"id": ref, "title": title, "function": function, "table": None,
                     "text": f"Support synthétique de validation. {title}. Relever les acteurs puis justifier leur relation.",
                     "provenance": {"kind": "LOCAL_FICTION", "evidence_id": None}})
        return ref

    def question(prompt, support):
        number = len(questions)+1
        ref = f"Q{number}"
        questions.append({"id": ref, "number": number, "prompt": prompt,
                          "document_ids": [support], "capability_ids": ["C1"],
                          "response": {"kind": "LINES", "lines": 2, "table": None}})
        answers.append({"id": ref, "expected_answer": f"CORRIGE_PROF_{number}",
                        "rationale": "Justifier par le document.", "vigilance": "Relever un indice.",
                        "remediation": "Revenir à la situation."})
        return ref

    for i, (title, notion, support_title, position) in enumerate(PARTS, 1):
        doc = document(support_title, "METHOD" if i == 1 else "CASE")
        supports = [doc]
        if i == 3:
            supports.insert(0, document("Organigramme de DAT SECURITY", "CASE"))
        concept = f"K{i}"
        concepts.append({"id": concept, "notion": notion, "definition": f"Définition témoin de {notion}.",
                         "explanation": "Explication de validation.", "example": support_title})
        parts.append({"id": f"P{i}", "title": title, "document_ids": supports,
                      "observation": [question(f"Observer la situation {i}.", doc)],
                      "analysis": [question(f"Analyser les indices {i}.", doc)],
                      "concept_ids": [concept], "formalization": position,
                      "reinvestment": [question(f"Réinvestir la notion {i}.", doc)]})
    check = question("Trouver le mot mystère.", doc)
    for title, support_title in zip(TASKS, ("Les groupes de Florian", "Annexes de la situation de Djamila"), strict=True):
        doc = document(support_title, "CASE")
        tasks.append({"title": title, "document_ids": [doc],
                      "question_ids": [question("Justifier dans le cas suivant : "+support_title, doc)]})
    return {"title": "Les interactions individu-groupe et la communication interpersonnelle", "limitations": [],
            "course_chapter": {"context": {"title": "DAT SECURITY", "text": "Yoann dirige une équipe de protection des chantiers."},
                "documents": docs, "parts": parts, "questions": questions, "concepts": concepts,
                "knowledge_check": [check], "synthesis": "Relier groupe, statut et communication.",
                "transfer": tasks, "teacher_answers": answers}}


@pytest.mark.parametrize("mutation", ["collapse", "three_documents", "orphan", "future_doc", "single_activity", "swapped_questions", "untaught_notion"])
def test_refuses_broken_progressions(mutation):
    service = app(Catalog())
    prepared = prepare(service, selection())
    dispatch = as_plain(service.prepared[prepared["preparation_ref"]])
    content = deepcopy(replay())
    c = content["course_chapter"]
    if mutation == "collapse":
        c["parts"] = c["parts"][:1]
    elif mutation == "three_documents":
        c["parts"][0]["document_ids"] = ["D1", "D2", "D3"]
    elif mutation == "orphan":
        c["parts"][1]["concept_ids"] = ["K1"]
    elif mutation == "future_doc":
        c["questions"][0]["document_ids"] = ["D3"]
    elif mutation == "single_activity":
        c["transfer"].pop()
    elif mutation == "untaught_notion":
        c["concepts"][1]["notion"] = c["concepts"][0]["notion"]
    else:
        c["parts"][0]["observation"], c["parts"][0]["analysis"] = ["Q2"], ["Q1"]
    with pytest.raises(ValueError, match="COURSE_PROGRESSIVE_"):
        bind_p0_content(dispatch, content)

def test_chapter_three_wire_and_read_view():
    service = app(Catalog())
    prepared = prepare(service, selection())
    dispatch = as_plain(service.prepared[prepared["preparation_ref"]])
    wire = build_p0_content_request(dispatch, progressive_chapters=True)
    schema = wire.output_schema["properties"]["course_chapter"]["properties"]
    assert schema["transfer"]["type"] == "array"
    bound = bind_p0_content(dispatch, replay())
    assert [s["heading"] for s in bound.data["sections"]][2:] == [
        p[0] for p in PARTS
    ] + ["À retenir", "Tester ses connaissances", *TASKS]
