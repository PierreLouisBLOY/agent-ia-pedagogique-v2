"""Frozen two-call R2 canary scaffold; this module never executes providers."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from decimal import Decimal

from backend.adapters.outbound.openai import OpenAIReasoningEffort
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


@dataclass(frozen=True, slots=True)
class R2BReviewCanarySpec:
    call: CalibrationCallSpec
    failed_r2_call_id: str
    reasoning_effort: OpenAIReasoningEffort
    automatic_retry_count: int


R2B_CANARY_PLAN_VERSION = "12.16-g2-r2b-openai-review-canary-v1"
R2B_APPROVAL_REQUIRED = True
R2B_LIVE_PROVIDER_CALL_COUNT = 0
R2B_PROVIDER_COST_USD = Decimal("0")
R2B_INPUT_USD_PER_MILLION_TOKENS = Decimal("4.00")
R2B_OUTPUT_USD_PER_MILLION_TOKENS = Decimal("20.00")
R2B_COST_SAFETY_MARGIN = Decimal("1.25")
R2B_ESTIMATED_MAX_COST_BEFORE_MARGIN_USD = Decimal("0.109920")
R2B_ESTIMATED_MAX_COST_USD = Decimal("0.137400")

R2B_CANARY_CALL_MATRIX = (
    R2BReviewCanarySpec(
        call=CalibrationCallSpec(
            call_id="remediation.openai-review.scn-05.canary.r2b.r1",
            provider=CalibrationProvider.OPENAI,
            model="gpt-5.6-sol",
            model_profile_id="openai.gpt-5.6-sol.review",
            role=CalibrationRole.PRIMARY,
            workload=CalibrationWorkload.REVIEW,
            scenario_code="SCN-05",
            task_kind="exercise",
            repetition=1,
            max_output_tokens=4_096,
            input_utf8_upper_bound_bytes=7_000,
            criterion_refs=(),
            input_refs=(
                "remediation-source:remediation.openai-review.scn-05.canary.r1",
            ),
        ),
        failed_r2_call_id="remediation.openai-review.scn-05.canary.r1",
        reasoning_effort=OpenAIReasoningEffort.LOW,
        automatic_retry_count=0,
    ),
)


def r2b_canary_matrix_sha256() -> str:
    payload = {
        "approval_required": R2B_APPROVAL_REQUIRED,
        "plan_version": R2B_CANARY_PLAN_VERSION,
        "calls": [
            {
                "call_id": item.call.call_id,
                "provider": item.call.provider.value,
                "model": item.call.model,
                "model_profile_id": item.call.model_profile_id,
                "role": item.call.role.value,
                "workload": item.call.workload.value,
                "scenario_code": item.call.scenario_code,
                "task_kind": item.call.task_kind,
                "repetition": item.call.repetition,
                "max_output_tokens": item.call.max_output_tokens,
                "input_utf8_upper_bound_bytes": (
                    item.call.input_utf8_upper_bound_bytes
                ),
                "criterion_refs": item.call.criterion_refs,
                "input_refs": item.call.input_refs,
                "failed_r2_call_id": item.failed_r2_call_id,
                "reasoning_effort": item.reasoning_effort.value,
                "automatic_retry_count": item.automatic_retry_count,
            }
            for item in R2B_CANARY_CALL_MATRIX
        ],
        "pricing": {
            "input_usd_per_million_tokens": str(
                R2B_INPUT_USD_PER_MILLION_TOKENS
            ),
            "output_usd_per_million_tokens": str(
                R2B_OUTPUT_USD_PER_MILLION_TOKENS
            ),
            "safety_margin": str(R2B_COST_SAFETY_MARGIN),
            "estimated_max_before_margin_usd": str(
                R2B_ESTIMATED_MAX_COST_BEFORE_MARGIN_USD
            ),
            "estimated_max_with_margin_usd": str(R2B_ESTIMATED_MAX_COST_USD),
        },
    }
    canonical = json.dumps(payload, separators=(",", ":"), sort_keys=True).encode()
    return hashlib.sha256(canonical).hexdigest()


R2B_CANARY_MATRIX_SHA256 = (
    "f2f4b224299a958b1a2e0d82b61b671befb222bb244efbe18342b41823ce05d3"
)
