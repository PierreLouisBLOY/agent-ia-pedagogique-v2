"""New wire response for the single-notion documentary regression scenarios."""


def progressive_real_fixture(content):
    chapter = content["course_chapter"]
    part = chapter["parts"][0]
    part.update(formalization="AFTER_OBSERVATION", document_ids=["D1", "D3"])
    chapter["questions"].append({**chapter["questions"][-1], "number": 6, "id": "Q6",
                                 "prompt": "Comparer le passage fourni à la situation documentaire.",
                                 "document_ids": ["D2"]})
    chapter["teacher_answers"].append({**chapter["teacher_answers"][-1], "id": "Q6"})
    chapter["transfer"] = [chapter["transfer"], {"title": "Comparer dans un autre contexte",
                          "document_ids": ["D2"], "question_ids": ["Q6"]}]
    return content
