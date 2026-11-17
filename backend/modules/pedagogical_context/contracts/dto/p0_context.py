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
P0_INSTITUTIONAL_CONTEXT_CONTRACT = "P0-CONTEXT-2.0"
P0_COURSE_CONTEXT_CONTRACT = "P0-CONTEXT-COURSE-3.0"
P0_NOTION_COURSE_CONTEXT_CONTRACT = "P0-CONTEXT-COURSE-4.0"
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
        from backend.modules.pedagogical_context.contracts.dto.exercise_context import (
            EXERCISE_CONTEXTS,
            FOCUSED_CONTEXTS,
            ExerciseQuestionFocus,
            exercise_focus,
        )

        course_choice = self.data.get("contract_id") in {P0_COURSE_CONTEXT_CONTRACT, P0_NOTION_COURSE_CONTEXT_CONTRACT}
        institutional = self.data.get("contract_id") in {P0_INSTITUTIONAL_CONTEXT_CONTRACT, P0_COURSE_CONTEXT_CONTRACT, P0_NOTION_COURSE_CONTEXT_CONTRACT, *EXERCISE_CONTEXTS}
        fields = _FIELDS | ({"institutional", "institutional_resolution", "local_progression"} if institutional else set())
        if self.data.get("contract_id") in EXERCISE_CONTEXTS:
            fields |= {"exercise_focus_justification"}
        if self.data.get("contract_id") in FOCUSED_CONTEXTS:
            fields |= {"exercise_focus_selection"}
        data = object_data(self.data, fields | ({"course_format"} if course_choice else set()))
        if data["contract_id"] not in {P0_CONTEXT_CONTRACT, P0_INSTITUTIONAL_CONTEXT_CONTRACT, P0_COURSE_CONTEXT_CONTRACT, P0_NOTION_COURSE_CONTEXT_CONTRACT, *EXERCISE_CONTEXTS}:
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
        if course_choice:
            if data["contract_id"] == P0_NOTION_COURSE_CONTEXT_CONTRACT and data["course_format"] != "CHAPTER":
                raise ValueError("P0_NOTION_COURSE_FORMAT")
            if data["resource_type"] != "COURSE" or data["course_format"] not in {"CHAPTER", "EXPLAINED"}:
                raise ValueError("P0_COURSE_FORMAT")
            if data["course_format"] == "CHAPTER" and not str(data["level"]).endswith("STMG"):
                raise ValueError("P0_RICH_COURSE_LEVEL_UNSUPPORTED")
        _bounded_text(data["discipline"], 200 if institutional else 100)
        if institutional:
            from backend.modules.pedagogical_context.contracts.dto.bts_institutional import (
                validate_bts_selection,
            )
            from backend.modules.pedagogical_context.contracts.dto.stmg_institutional import (
                validate_selection,
            )

            bts = str(data["level"]).startswith("BTS_")
            selection = (validate_bts_selection if bts else validate_selection)(
                data["institutional"], level=str(data["level"]), discipline=str(data["discipline"]))
            resolution = data["institutional_resolution"]
            if resolution is not None:
                resolved = object_data(resolution)
                if "course_thread" in resolved:
                    from backend.modules.pedagogical_context.contracts.dto.real_course_thread import (
                        RealCourseThread,
                    )

                    if data["contract_id"] != P0_NOTION_COURSE_CONTEXT_CONTRACT:
                        raise ValueError("P0_REAL_ORGANIZATION_CHAPTER_REQUIRED")
                    RealCourseThread(object_data(resolved["course_thread"]))
                if resolved.get("contract_id") != ("BTS-RESOLUTION-1.0" if bts else "STMG-RESOLUTION-1.0") or resolved.get("selection_sha256") != fingerprint(selection):
                    raise ValueError("P0_INSTITUTIONAL_RESOLUTION_BINDING")
                if resolved.get("status") not in {"RESOLVED_ADMITTED", "CONTENT_GAP"}:
                    raise ValueError("P0_INSTITUTIONAL_RESOLUTION_BINDING")
            progression = data["local_progression"]
            if progression is not None:
                for value in object_data(progression, {"chapter", "sequence", "week"}).values():
                    if value is not None:
                        _bounded_text(value, 200)
            if course_choice and data["course_format"] == "CHAPTER":
                chapter = object_data(progression).get("chapter") if progression is not None else None
                if not isinstance(chapter, str) or re.fullmatch(r"[1-9][0-9]?", chapter) is None:
                    raise ValueError("P0_RICH_COURSE_CHAPTER_NUMBER")
        _text_items(data["topics"], 16 if institutional and data["resource_type"] == "COURSE" else 8)
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
        if data["contract_id"] in EXERCISE_CONTEXTS:
            if data["resource_type"] != "EXERCISE":
                raise ValueError("EXERCISE_CONTEXT_REQUIRED")
            _bounded_text(data["exercise_focus_justification"], 2000)
            if data["contract_id"] in FOCUSED_CONTEXTS:
                ExerciseQuestionFocus.from_value(data["exercise_focus_selection"])
            # The normal prepare use case resolves this selection and constructs
            # P0Context again before declaring PREPARATION_READY.
            if data["institutional_resolution"] is not None:
                exercise_focus(data)
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

    @property
    def institutional(self) -> dict[str, object] | None:
        value = self.as_dict().get("institutional")
        return object_data(value) if value is not None else None

    def require_institutional_dispatch(self) -> None:
        if self.institutional is None:
            raise ValueError("P0_INSTITUTIONAL_CONTEXT_REQUIRED")
        resolution = self.data.get("institutional_resolution")
        if resolution is None or object_data(resolution).get("status") != "RESOLVED_ADMITTED":
            raise ValueError("P0_INSTITUTIONAL_CONTENT_GAP")

    @property
    def course_format(self) -> str:
        """Historical contexts retain their explained wire; choices are explicit."""
        return str(self.data.get("course_format", "EXPLAINED"))
