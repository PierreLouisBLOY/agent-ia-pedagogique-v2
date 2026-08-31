"""Frozen pre-V4 G2 matrix retained only for historical evidence audits."""

from __future__ import annotations

import hashlib
import json
from dataclasses import replace

from tests.calibration.pedagogical.call_plan import (
    _OPENAI_CALLS,
    _anthropic_call,
    _criterion_slug,
)
from tests.calibration.pedagogical.call_plan import (
    RAW_OUTPUT_DIRECTORY as RAW_OUTPUT_DIRECTORY,
)
from tests.calibration.pedagogical.call_plan import (
    CalibrationCallSpec as CalibrationCallSpec,
)
from tests.calibration.pedagogical.call_plan import (
    CalibrationProvider as CalibrationProvider,
)
from tests.calibration.pedagogical.call_plan import (
    CalibrationRole as CalibrationRole,
)
from tests.calibration.pedagogical.call_plan import (
    CalibrationWorkload as CalibrationWorkload,
)
from tests.calibration.pedagogical.catalog import CALIBRATION_SCENARIOS

PEDAGOGICAL_CALIBRATION_PLAN_VERSION = "12.16-g2-plan-v1"
PRICING_SNAPSHOT_ID = "official-2026-08-29"

_LEGACY_OPENAI_CALLS = tuple(
    replace(
        call,
        input_refs=(
            f"corpus:{PEDAGOGICAL_CALIBRATION_PLAN_VERSION}:{call.scenario_code}",
        ),
    )
    for call in _OPENAI_CALLS
)

_LEGACY_ANCHOR_SCORING_CALLS = tuple(
    _anthropic_call(
        call_id=(
            f"cal.score.anchor.{scenario.scenario_code.lower()}.{suffix}."
            f"{_criterion_slug(criterion_ref)}.r1"
        ),
        scenario_code=scenario.scenario_code,
        criterion_ref=criterion_ref,
        input_ref=f"anchor:cal.{scenario.scenario_code.lower()}.{suffix}",
        repetition=1,
    )
    for scenario in CALIBRATION_SCENARIOS
    for suffix in ("a", "b", "c")
    for criterion_ref in scenario.criterion_refs
)

_LEGACY_ANCHOR_REPEAT_CALLS = tuple(
    _anthropic_call(
        call_id=(
            f"cal.score.anchor.{scenario.scenario_code.lower()}.a."
            f"{_criterion_slug(criterion_ref)}.r2"
        ),
        scenario_code=scenario.scenario_code,
        criterion_ref=criterion_ref,
        input_ref=f"anchor:cal.{scenario.scenario_code.lower()}.a",
        repetition=2,
    )
    for scenario in CALIBRATION_SCENARIOS
    for criterion_ref in scenario.criterion_refs
)

_LEGACY_SELECTED_OUTPUTS = {
    "SCN-03": "cal.generation.course.primary.r1",
    "SCN-04": "cal.transformation.resource.primary.r1",
    "SCN-05": "cal.generation.exercise.primary.r1",
    "SCN-06": "cal.generation.assessment.primary.r1",
    "SCN-07": "cal.correction.remediation.primary.r1",
    "SCN-08": "cal.generation.qcm.primary.r1",
}

_LEGACY_OUTPUT_SCORING_CALLS = tuple(
    _anthropic_call(
        call_id=(
            f"cal.score.output.{scenario.scenario_code.lower()}."
            f"{_criterion_slug(criterion_ref)}.r1"
        ),
        scenario_code=scenario.scenario_code,
        criterion_ref=criterion_ref,
        input_ref=f"output:{_LEGACY_SELECTED_OUTPUTS[scenario.scenario_code]}",
        repetition=1,
    )
    for scenario in CALIBRATION_SCENARIOS
    if scenario.scenario_code in _LEGACY_SELECTED_OUTPUTS
    for criterion_ref in scenario.criterion_refs
)

PEDAGOGICAL_CALIBRATION_CALL_MATRIX = (
    *_LEGACY_OPENAI_CALLS,
    *_LEGACY_ANCHOR_SCORING_CALLS,
    *_LEGACY_ANCHOR_REPEAT_CALLS,
    *_LEGACY_OUTPUT_SCORING_CALLS,
)


def call_matrix_sha256() -> str:
    payload = {
        "plan_version": PEDAGOGICAL_CALIBRATION_PLAN_VERSION,
        "pricing_snapshot_id": PRICING_SNAPSHOT_ID,
        "calls": [
            {
                "call_id": call.call_id,
                "provider": call.provider.value,
                "model": call.model,
                "model_profile_id": call.model_profile_id,
                "role": call.role.value,
                "workload": call.workload.value,
                "scenario_code": call.scenario_code,
                "task_kind": call.task_kind,
                "repetition": call.repetition,
                "max_output_tokens": call.max_output_tokens,
                "input_utf8_upper_bound_bytes": call.input_utf8_upper_bound_bytes,
                "criterion_refs": call.criterion_refs,
                "input_refs": call.input_refs,
            }
            for call in PEDAGOGICAL_CALIBRATION_CALL_MATRIX
        ],
    }
    canonical = json.dumps(payload, separators=(",", ":"), sort_keys=True).encode()
    return hashlib.sha256(canonical).hexdigest()
