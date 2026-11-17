"""Synthetic response for the current two-activity manual chapter contract."""
from copy import deepcopy


def progressive_course_fixture(content):
    result = deepcopy(content)
    chapter = result["course_chapter"]
    question_template = chapter["questions"][0]
    answer_template = chapter["teacher_answers"][0]
    document_ids = [d["id"] for d in chapter["documents"][:2]]
    questions, answers, parts = [], [], []

    def question(prompt):
        number = len(questions) + 1
        ref = f"Q{number}"
        questions.append({**deepcopy(question_template), "id": ref, "number": number,
                          "prompt": prompt, "document_ids": list(document_ids)})
        answers.append({**deepcopy(answer_template), "id": ref})
        return ref

    concepts = chapter["concepts"]
    for start in range(0, len(concepts), 3):
        number = len(parts) + 1
        parts.append({"id": f"P{number}", "title": f"Partie synthétique {number}",
                      "document_ids": list(document_ids), "formalization": "AFTER_ANALYSIS",
                      "observation": [question("Observer les faits du support synthétique.")],
                      "analysis": [question("Expliquer les relations observées.")],
                      "concept_ids": [c["id"] for c in concepts[start:start + 3]],
                      "reinvestment": [question("Réinvestir les notions dans la situation.")]})
    knowledge = [question("Vérifier les notions enseignées.")]
    activities = [{"title": f"Activité synthétique {number}",
                   "document_ids": list(document_ids),
                   "question_ids": [question(f"Appliquer les notions dans le cas {number}.")]}
                  for number in (1, 2)]
    chapter.update(parts=parts, questions=questions, teacher_answers=answers,
                   knowledge_check=knowledge, transfer=activities)
    return result
