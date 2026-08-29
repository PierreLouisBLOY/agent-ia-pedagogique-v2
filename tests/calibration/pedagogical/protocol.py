"""Offline admissibility and blind-observation protocol for G1 anchors."""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import StrEnum

from evaluation_harness import (
    EvaluationObservationFieldCode,
    ObservationField,
    ObservationObject,
    ObservationScalar,
    ObservationScalarKind,
    ObservationSequence,
)
from tests.calibration.pedagogical.catalog import (
    CALIBRATION_ANCHORS,
    CalibrationAnchor,
    anchor_by_id,
    scenario_by_code,
)

MAX_CANDIDATE_PROJECTION_CHARACTERS = 2_500
ANCHOR_ADMISSIBILITY_RULE_IDS = (
    "calibration.synthetic-only",
    "calibration.required-sections-exact",
    "calibration.non-empty-sections",
    "calibration.candidate-bounded",
    "calibration.no-authority-or-sensitive-material",
)

SCORER_OBSERVATION_FIELD_CODES = (
    "criterion",
    "scenario",
    "pedagogical-level",
    "task-kind",
    "candidate-projection",
    "reference-constraints",
    "required-sections",
)

_LOCAL_PATH = re.compile(r"(?:[A-Za-z]:[\\/]|(?:^|\s)/(?:home|Users|var|tmp)/)")
_URL = re.compile(r"(?i)\b(?:https?|file)://")
_EMAIL = re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b")
_FORBIDDEN_MARKERS = (
    "api_key",
    "api-key",
    "password",
    "passwd",
    "bearer ",
    "gatedecision",
    "capability_id",
    "approved",
    "promotion",
    "private data",
    "openai",
    "anthropic",
    "provider",
    "model_id",
    "expected score",
    "strong",
    "mixed",
    "weak_but_structurally_valid",
)


class AnchorAdmissibilityStatus(StrEnum):
    ADMISSIBLE = "ADMISSIBLE"
    INVALID = "INVALID"


@dataclass(frozen=True, slots=True)
class AnchorAdmissibilityResult:
    anchor_id: str
    status: AnchorAdmissibilityStatus
    violated_rule_ids: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class CalibrationCriterionItem:
    anchor_id: str
    scenario_code: str
    criterion_ref: str


def assess_anchor_admissibility(anchor: CalibrationAnchor) -> AnchorAdmissibilityResult:
    """Apply the five G1 anchor rules, not the canonical 37 hard assertions."""

    scenario = scenario_by_code(anchor.scenario_code)
    violations: list[str] = []
    actual_sections = tuple(code for code, _ in anchor.sections)
    if actual_sections != scenario.required_sections:
        violations.append("calibration.required-sections-exact")
    if any(not text or text != text.strip() for _, text in anchor.sections):
        violations.append("calibration.non-empty-sections")
    candidate = anchor.candidate_projection()
    if not candidate or len(candidate) > MAX_CANDIDATE_PROJECTION_CHARACTERS:
        violations.append("calibration.candidate-bounded")
    normalized = candidate.casefold()
    if (
        _LOCAL_PATH.search(candidate)
        or _URL.search(candidate)
        or _EMAIL.search(candidate)
        or any(marker in normalized for marker in _FORBIDDEN_MARKERS)
    ):
        violations.append("calibration.no-authority-or-sensitive-material")
    if not anchor.anchor_id.startswith("cal.scn-"):
        violations.append("calibration.synthetic-only")
    return AnchorAdmissibilityResult(
        anchor_id=anchor.anchor_id,
        status=(
            AnchorAdmissibilityStatus.ADMISSIBLE
            if not violations
            else AnchorAdmissibilityStatus.INVALID
        ),
        violated_rule_ids=tuple(violations),
    )


CALIBRATION_CRITERION_ITEMS = tuple(
    CalibrationCriterionItem(
        anchor_id=anchor.anchor_id,
        scenario_code=anchor.scenario_code,
        criterion_ref=criterion_ref,
    )
    for anchor in CALIBRATION_ANCHORS
    for criterion_ref in scenario_by_code(anchor.scenario_code).criterion_refs
)


def build_blind_scorer_observation(item: CalibrationCriterionItem) -> ObservationObject:
    """Project only the seven fields needed by the independent scorer."""

    anchor = anchor_by_id(item.anchor_id)
    scenario = scenario_by_code(item.scenario_code)
    if item.criterion_ref not in scenario.criterion_refs:
        raise ValueError("criterion does not belong to the scenario rubric")

    def scalar(value: str) -> ObservationScalar:
        return ObservationScalar(ObservationScalarKind.STRING, value)

    def sequence(values: tuple[str, ...]) -> ObservationSequence:
        return ObservationSequence(tuple(scalar(value) for value in values))

    values = (
        scalar(item.criterion_ref),
        scalar(scenario.scenario_code),
        scalar(scenario.level_code),
        scalar(scenario.task_kind),
        scalar(anchor.candidate_projection()),
        sequence(scenario.reference_constraints),
        sequence(scenario.required_sections),
    )
    return ObservationObject(
        tuple(
            ObservationField(EvaluationObservationFieldCode(code), value)
            for code, value in zip(
                SCORER_OBSERVATION_FIELD_CODES,
                values,
                strict=True,
            )
        )
    )


def build_all_blind_scorer_observations() -> tuple[ObservationObject, ...]:
    return tuple(
        build_blind_scorer_observation(item)
        for item in CALIBRATION_CRITERION_ITEMS
    )
