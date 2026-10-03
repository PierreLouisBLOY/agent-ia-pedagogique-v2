"""Provider-neutral P0 context for the closed R6 pedagogical typologies."""

from __future__ import annotations

import re
from collections.abc import Mapping
from dataclasses import dataclass

from backend.modules.pedagogical_design.contracts.dto.assessment_bundle import (
    as_plain,
    fingerprint,
    object_data,
)
from backend.shared_kernel._safe_data import freeze_safe_mapping

P0_CONTEXT_CONTRACT = "R6-P0-CONTEXT-1.0"
P0_RESOURCE_TYPES = frozenset({"COURSE", "EXERCISE", "QUESTION_SET", "ASSESSMENT"})
P0_QUESTION_MODES = frozenset({"OPEN_QUESTIONS", "QCM", "QUIZ"})
P0_LEVELS = frozenset({"FIRST_STMG", "FINAL_STMG", "BTS_CG_YEAR_1", "BTS_CG_YEAR_2"})
P0_DIFFICULTIES = frozenset({"INTRODUCTORY", "STANDARD", "ADVANCED"})

_FIELDS = {
    "contract_id",
    "resource_type",
    "question_mode",
    "level",
    "discipline",
    "topics",
    "objectives",
    "difficulty",
    "duration_minutes",
    "total_points",
    "language",
}


def _bounded_text(value: object, maximum: int = 500) -> str:
    if not isinstance(value, str) or not value.strip() or len(value) > maximum:
        raise ValueError("P0_CONTEXT_TEXT")
    return value


def _text_items(value: object, maximum: int = 8) -> tuple[str, ...]:
    if not isinstance(value, (list, tuple)) or not 1 <= len(value) <= maximum:
        raise ValueError("P0_CONTEXT_ITEMS")
    result = tuple(_bounded_text(item) for item in value)
    if len(set(result)) != len(result):
        raise ValueError("P0_CONTEXT_ITEMS")
    return result


@dataclass(frozen=True, slots=True)
class P0Context:
    data: Mapping[str, object]

    def __post_init__(self) -> None:
        data = object_data(self.data, _FIELDS)
        if data["contract_id"] != P0_CONTEXT_CONTRACT:
            raise ValueError("P0_CONTEXT_CONTRACT")
        if data["resource_type"] not in P0_RESOURCE_TYPES:
            raise ValueError("P0_RESOURCE_TYPE")
        mode = data["question_mode"]
        if data["resource_type"] == "QUESTION_SET":
            if mode not in P0_QUESTION_MODES:
                raise ValueError("P0_QUESTION_MODE")
        elif mode is not None:
            raise ValueError("P0_QUESTION_MODE")
        if data["level"] not in P0_LEVELS:
            raise ValueError("P0_LEVEL")
        _bounded_text(data["discipline"], 100)
        _text_items(data["topics"])
        _text_items(data["objectives"])
        if data["difficulty"] not in P0_DIFFICULTIES:
            raise ValueError("P0_DIFFICULTY")
        duration, points = data["duration_minutes"], data["total_points"]
        if data["resource_type"] == "ASSESSMENT":
            if type(duration) is not int or not 1 <= duration <= 480:
                raise ValueError("P0_DURATION")
            if type(points) is not int or not 1 <= points <= 200:
                raise ValueError("P0_TOTAL_POINTS")
        elif duration is not None or points is not None:
            raise ValueError("P0_ASSESSMENT_ONLY_FIELDS")
        if not isinstance(data["language"], str) or re.fullmatch(
            r"[a-z]{2}(?:-[A-Z]{2})?", data["language"]
        ) is None:
            raise ValueError("P0_LANGUAGE")
        object.__setattr__(self, "data", freeze_safe_mapping(data))

    @property
    def resource_type(self) -> str:
        return str(self.data["resource_type"])

    @property
    def question_mode(self) -> str | None:
        value = self.data["question_mode"]
        return str(value) if value is not None else None

    @property
    def sha256(self) -> str:
        return fingerprint(self.data)

    def as_dict(self) -> dict[str, object]:
        return object_data(as_plain(self.data))
