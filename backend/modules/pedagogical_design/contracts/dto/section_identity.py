"""One canonical simple-section identity, shared by contracts and projections."""
from __future__ import annotations

import re
from typing import TypeGuard

# JSON Schema uses regex search; its $ may also match before a terminal newline.
# The portable true-end assertion keeps exactly the existing fullmatch language.
SECTION_ID_PATTERN = r"^S[A-Z0-9_-]{1,63}$(?![\s\S])"
QUESTION_ID_PATTERN = r"^Q[A-Z0-9_-]{1,63}$(?![\s\S])"
SECTION_ID_INSTRUCTION = (
    f"Chaque section_id respecte exactement {SECTION_ID_PATTERN}, "
    "par exemple S1 ou S_DOC1 ; les identifiants des sections sont uniques. "
)
QUESTION_ID_INSTRUCTION = (
    f"Chaque question_id respecte exactement {QUESTION_ID_PATTERN}, par exemple Q1 ; "
    "les corrections et le barème reprennent exactement les identifiants des questions dans le même ordre. "
)


def valid_section_id(value: object) -> TypeGuard[str]:
    return isinstance(value, str) and re.fullmatch(SECTION_ID_PATTERN, value) is not None


def valid_question_id(value: object) -> TypeGuard[str]:
    return isinstance(value, str) and re.fullmatch(QUESTION_ID_PATTERN, value) is not None
