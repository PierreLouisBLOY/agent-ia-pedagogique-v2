"""Frozen two-call R2 canary scaffold; this module never executes providers."""

from __future__ import annotations

import hashlib
import json
from decimal import Decimal

from tests.calibration.pedagogical.call_plan import (
    CalibrationCallSpec,
    CalibrationProvider,
    CalibrationRole,
    CalibrationWorkload,
)

R2_CANARY_PLAN_VERSION = "12.16-g2-r2-canary-v1"
R2_APPROVAL_REQUIRED = True
R2_LIVE_PROVIDER_CALL_COUNT = 0
R2_PROVIDER_COST_USD = Decimal("0")
R2_ESTIMATED_MAX_COST_USD = Decimal("0.100200")
R2_CANARY_MATRIX_SHA256 = (
    "d0d972312a0c9922f9a0629728e7579836dd2abbbade034b5316003bf54fee13"
)

R2_CANARY_CALL_MATRIX = (
    CalibrationCallSpec(
        call_id="remediation.openai-review.scn-05.canary.r1",
        provider=CalibrationProvider.OPENAI,
        model="gpt-5.6-sol",
        model_profile_id="openai.gpt-5.6-sol.review",
        role=CalibrationRole.PRIMARY,
        workload=CalibrationWorkload.REVIEW,
        scenario_code="SCN-05",
        task_kind="exercise",
        repetition=1,
        max_output_tokens=1_024,
        input_utf8_upper_bound_bytes=7_000,
        criterion_refs=(),
        input_refs=("remediation-source:cal.review.exercise.primary.r1",),
    ),
    CalibrationCallSpec(
        call_id="remediation.anthropic-scorer.scn-01.clarity.canary.r1",
        provider=CalibrationProvider.ANTHROPIC,
        model="claude-sonnet-5",
        model_profile_id="anthropic.claude-sonnet-5.scorer",
        role=CalibrationRole.JUDGE,
        workload=CalibrationWorkload.SCORING,
        scenario_code="SCN-01",
        task_kind="resource-organization",
        repetition=1,
        max_output_tokens=512,
        input_utf8_upper_bound_bytes=8_000,
        criterion_refs=("scn-01.quality.clarity",),
        input_refs=("remediation-source:cal.score.anchor.scn-01.a.clarity.r1",),
    ),
)


def r2_canary_matrix_sha256() -> str:
    payload = {
        "approval_required": R2_APPROVAL_REQUIRED,
        "plan_version": R2_CANARY_PLAN_VERSION,
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
            for call in R2_CANARY_CALL_MATRIX
        ],
        "estimated_max_cost_usd": str(R2_ESTIMATED_MAX_COST_USD),
    }
    canonical = json.dumps(payload, separators=(",", ":"), sort_keys=True).encode()
    return hashlib.sha256(canonical).hexdigest()
