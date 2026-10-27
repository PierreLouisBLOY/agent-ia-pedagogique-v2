"""Shared learning-link checks extracted from the chapter contract.

Callers retain their own cardinalities, validation order and public error codes.
These checks prove relationships, never semantic quality or owner acceptance.
"""
from collections.abc import Iterable, Sequence


def require_subset(references: Iterable[str], available: set[str], *, code: str) -> None:
    if not set(references) <= available:
        raise ValueError(code)


def require_ordered_answers(questions: Sequence[object], answers: Sequence[object], *, code: str) -> None:
    if list(answers) != list(questions):
        raise ValueError(code)


def require_unique_coverage(references: Sequence[str], available: set[str], *, code: str) -> None:
    if len(references) != len(set(references)) or set(references) != available:
        raise ValueError(code)


def require_provenance_kind(value: object, *, code: str) -> None:
    if value not in {"LOCAL_FICTION", "SUPPLIED_REFERENCE"}:
        raise ValueError(code)
