"""Project the returned title as a section for question-only provider content."""
from __future__ import annotations

import copy
from typing import Any

LABELS = {"QCM": "QCM", "QUIZ": "Quiz", "OPEN_QUESTIONS": "Questions ouvertes",
          "EXERCISE": "Exercice", "ASSESSMENT": "Évaluation"}


def bind_question_title_section(content: dict[str, Any], family: str) -> tuple[dict[str, Any], dict[str, str] | None]:
    """Add only a presentation label and an exact copy of the existing title.

    No question, option, answer, marking, limitation or teaching instruction is
    synthesized. The original provider response is retained separately.
    """
    result = copy.deepcopy(content)
    sections = result["sections"]
    if not isinstance(sections, list):
        raise ValueError("P0_SECTION_PRESENTATION_ARRAY_REQUIRED")
    if sections:
        return result, None
    if family not in LABELS:
        raise ValueError("P0_EMPTY_SECTION_FAMILY_NOT_QUESTION_BASED")
    questions = result["questions"]
    title = result["title"]
    if not isinstance(questions, list) or not questions:
        raise ValueError("P0_SECTION_PRESENTATION_QUESTIONS_REQUIRED")
    if not isinstance(title, str) or not title.strip() or len(title) > 200:
        raise ValueError("P0_SECTION_PRESENTATION_TITLE_REQUIRED")
    result["sections"] = [{"section_id": "S_LOCAL_TITLE", "heading": LABELS[family], "text": title}]
    annotation = {"provenance": "LOCAL_FAMILY_TITLE_PRESENTATION_NOT_PROVIDER_SECTION",
                  "family": family, "section_id": "S_LOCAL_TITLE", "text_source": "EXACT_ORIGINAL_TITLE",
                  "questions_answers_marking": "UNCHANGED"}
    return result, annotation
