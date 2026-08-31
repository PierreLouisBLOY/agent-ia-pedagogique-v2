"""Frozen G2 call matrix and offline-only cost controls prepared by G1."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from decimal import ROUND_CEILING, Decimal
from enum import StrEnum

from tests.calibration.pedagogical.anchor_corpus_v4 import (
    PEDAGOGICAL_CALIBRATION_CORPUS_V4_VERSION,
    V4_ANCHOR_EXPECTATIONS,
    V4_CALIBRATION_ANCHORS,
    v4_calibration_corpus_sha256,
)
from tests.calibration.pedagogical.catalog import CALIBRATION_SCENARIOS, AnchorTier
from tests.calibration.pedagogical.pricing import (
    MODEL_PRICE_QUOTES,
    PRICING_SNAPSHOT_ID,
    ModelPriceQuote,
    pricing_snapshot_sha256,
)

PEDAGOGICAL_CALIBRATION_PLAN_VERSION = "12.16-g2-v4-plan-v1"
RAW_OUTPUT_DIRECTORY = "artifacts/calibration/12.16-g2/raw"
COST_SAFETY_MARGIN = Decimal("1.25")
LIVE_PROVIDER_CALL_COUNT = 0
LIVE_PROVIDER_COST_USD = Decimal("0")


class CalibrationProvider(StrEnum):
    OPENAI = "openai"
    ANTHROPIC = "anthropic"


class CalibrationRole(StrEnum):
    PRIMARY = "PRIMARY"
    FALLBACK = "FALLBACK"
    JUDGE = "JUDGE"


class CalibrationWorkload(StrEnum):
    GENERATION = "generation"
    TRANSFORMATION = "transformation"
    CORRECTION = "correction"
    REVIEW = "review"
    SCORING = "scoring"


@dataclass(frozen=True, slots=True)
class CalibrationCallSpec:
    call_id: str
    provider: CalibrationProvider
    model: str
    model_profile_id: str
    role: CalibrationRole
    workload: CalibrationWorkload
    scenario_code: str
    task_kind: str
    repetition: int
    max_output_tokens: int
    input_utf8_upper_bound_bytes: int
    criterion_refs: tuple[str, ...]
    input_refs: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class CostEstimate:
    call_count: int
    estimated_input_tokens: int
    estimated_output_tokens: int
    estimated_base_usd: Decimal
    maximum_input_tokens: int
    maximum_output_tokens: int
    estimated_maximum_before_margin_usd: Decimal
    estimated_maximum_with_margin_usd: Decimal


def _openai_call(
    call_id: str,
    model: str,
    role: CalibrationRole,
    workload: CalibrationWorkload,
    scenario_code: str,
    task_kind: str,
    repetition: int,
    max_output_tokens: int,
    input_upper_bytes: int,
) -> CalibrationCallSpec:
    profile_workload = (
        "generation"
        if workload in {CalibrationWorkload.GENERATION, CalibrationWorkload.TRANSFORMATION}
        else workload.value
    )
    profile_suffix = "" if role is CalibrationRole.PRIMARY else "-fallback"
    return CalibrationCallSpec(
        call_id=call_id,
        provider=CalibrationProvider.OPENAI,
        model=model,
        model_profile_id=f"openai.{model}.{profile_workload}{profile_suffix}",
        role=role,
        workload=workload,
        scenario_code=scenario_code,
        task_kind=task_kind,
        repetition=repetition,
        max_output_tokens=max_output_tokens,
        input_utf8_upper_bound_bytes=input_upper_bytes,
        criterion_refs=(),
        input_refs=(f"corpus:{PEDAGOGICAL_CALIBRATION_PLAN_VERSION}:{scenario_code}",),
    )


_OPENAI_CALLS = (
    _openai_call(
        "cal.generation.course.primary.r1",
        "gpt-5.6-terra",
        CalibrationRole.PRIMARY,
        CalibrationWorkload.GENERATION,
        "SCN-03",
        "course",
        1,
        2_048,
        6_000,
    ),
    _openai_call(
        "cal.generation.course.primary.r2",
        "gpt-5.6-terra",
        CalibrationRole.PRIMARY,
        CalibrationWorkload.GENERATION,
        "SCN-03",
        "course",
        2,
        2_048,
        6_000,
    ),
    _openai_call(
        "cal.generation.course.fallback.r1",
        "gpt-5.6-sol",
        CalibrationRole.FALLBACK,
        CalibrationWorkload.GENERATION,
        "SCN-03",
        "course",
        1,
        2_048,
        6_000,
    ),
    _openai_call(
        "cal.generation.exercise.primary.r1",
        "gpt-5.6-terra",
        CalibrationRole.PRIMARY,
        CalibrationWorkload.GENERATION,
        "SCN-05",
        "exercise",
        1,
        2_048,
        6_000,
    ),
    _openai_call(
        "cal.generation.assessment.primary.r1",
        "gpt-5.6-terra",
        CalibrationRole.PRIMARY,
        CalibrationWorkload.GENERATION,
        "SCN-06",
        "assessment",
        1,
        2_048,
        6_000,
    ),
    _openai_call(
        "cal.generation.assessment.fallback.r1",
        "gpt-5.6-sol",
        CalibrationRole.FALLBACK,
        CalibrationWorkload.GENERATION,
        "SCN-06",
        "assessment",
        1,
        2_048,
        6_000,
    ),
    _openai_call(
        "cal.generation.qcm.primary.r1",
        "gpt-5.6-terra",
        CalibrationRole.PRIMARY,
        CalibrationWorkload.GENERATION,
        "SCN-08",
        "qcm",
        1,
        2_048,
        6_000,
    ),
    _openai_call(
        "cal.generation.qcm.fallback.r1",
        "gpt-5.6-sol",
        CalibrationRole.FALLBACK,
        CalibrationWorkload.GENERATION,
        "SCN-08",
        "qcm",
        1,
        2_048,
        6_000,
    ),
    _openai_call(
        "cal.transformation.resource.primary.r1",
        "gpt-5.6-terra",
        CalibrationRole.PRIMARY,
        CalibrationWorkload.TRANSFORMATION,
        "SCN-04",
        "resource",
        1,
        1_536,
        5_000,
    ),
    _openai_call(
        "cal.transformation.resource.primary.r2",
        "gpt-5.6-terra",
        CalibrationRole.PRIMARY,
        CalibrationWorkload.TRANSFORMATION,
        "SCN-04",
        "resource",
        2,
        1_536,
        5_000,
    ),
    _openai_call(
        "cal.correction.remediation.primary.r1",
        "gpt-5.6-sol",
        CalibrationRole.PRIMARY,
        CalibrationWorkload.CORRECTION,
        "SCN-07",
        "remediation",
        1,
        1_536,
        6_000,
    ),
    _openai_call(
        "cal.correction.remediation.primary.r2",
        "gpt-5.6-sol",
        CalibrationRole.PRIMARY,
        CalibrationWorkload.CORRECTION,
        "SCN-07",
        "remediation",
        2,
        1_536,
        6_000,
    ),
    _openai_call(
        "cal.correction.remediation.fallback.r1",
        "gpt-5.6-terra",
        CalibrationRole.FALLBACK,
        CalibrationWorkload.CORRECTION,
        "SCN-07",
        "remediation",
        1,
        1_536,
        6_000,
    ),
    _openai_call(
        "cal.review.exercise.primary.r1",
        "gpt-5.6-sol",
        CalibrationRole.PRIMARY,
        CalibrationWorkload.REVIEW,
        "SCN-05",
        "exercise",
        1,
        1_024,
        7_000,
    ),
    _openai_call(
        "cal.review.exercise.primary.r2",
        "gpt-5.6-sol",
        CalibrationRole.PRIMARY,
        CalibrationWorkload.REVIEW,
        "SCN-05",
        "exercise",
        2,
        1_024,
        7_000,
    ),
    _openai_call(
        "cal.review.exercise.fallback.r1",
        "gpt-5.6-terra",
        CalibrationRole.FALLBACK,
        CalibrationWorkload.REVIEW,
        "SCN-05",
        "exercise",
        1,
        1_024,
        7_000,
    ),
    _openai_call(
        "cal.review.assessment.primary.r1",
        "gpt-5.6-sol",
        CalibrationRole.PRIMARY,
        CalibrationWorkload.REVIEW,
        "SCN-06",
        "assessment",
        1,
        1_024,
        7_000,
    ),
    _openai_call(
        "cal.review.correction.primary.r1",
        "gpt-5.6-sol",
        CalibrationRole.PRIMARY,
        CalibrationWorkload.REVIEW,
        "SCN-07",
        "correction",
        1,
        1_024,
        7_000,
    ),
    _openai_call(
        "cal.review.qcm.primary.r1",
        "gpt-5.6-sol",
        CalibrationRole.PRIMARY,
        CalibrationWorkload.REVIEW,
        "SCN-08",
        "qcm",
        1,
        1_024,
        7_000,
    ),
    _openai_call(
        "cal.review.qcm.fallback.r1",
        "gpt-5.6-terra",
        CalibrationRole.FALLBACK,
        CalibrationWorkload.REVIEW,
        "SCN-08",
        "qcm",
        1,
        1_024,
        7_000,
    ),
)


def _criterion_slug(criterion_ref: str) -> str:
    return criterion_ref.rsplit(".", 1)[-1]


def _anthropic_call(
    call_id: str,
    scenario_code: str,
    criterion_ref: str,
    input_ref: str,
    repetition: int,
) -> CalibrationCallSpec:
    scenario = next(
        item for item in CALIBRATION_SCENARIOS if item.scenario_code == scenario_code
    )
    return CalibrationCallSpec(
        call_id=call_id,
        provider=CalibrationProvider.ANTHROPIC,
        model="claude-sonnet-5",
        model_profile_id="anthropic.claude-sonnet-5.scorer",
        role=CalibrationRole.JUDGE,
        workload=CalibrationWorkload.SCORING,
        scenario_code=scenario_code,
        task_kind=scenario.task_kind,
        repetition=repetition,
        max_output_tokens=512,
        input_utf8_upper_bound_bytes=8_000,
        criterion_refs=(criterion_ref,),
        input_refs=(input_ref,),
    )


_V4_ANCHOR_BY_ID = {anchor.anchor_id: anchor for anchor in V4_CALIBRATION_ANCHORS}
V4_ANCHOR_BY_SCENARIO_TIER = {
    (_V4_ANCHOR_BY_ID[item.anchor_id].scenario_code, item.tier): _V4_ANCHOR_BY_ID[
        item.anchor_id
    ]
    for item in V4_ANCHOR_EXPECTATIONS
}
V4_TIER_BY_ANCHOR_ID = {
    item.anchor_id: item.tier for item in V4_ANCHOR_EXPECTATIONS
}


def _tier_slug(tier: AnchorTier) -> str:
    return tier.value.casefold().replace("_but_structurally_valid", "")


_ANCHOR_SCORING_CALLS = tuple(
    _anthropic_call(
        call_id=(
            f"cal.score.anchor.{scenario.scenario_code.lower()}.{_tier_slug(tier)}."
            f"{_criterion_slug(criterion_ref)}.r1"
        ),
        scenario_code=scenario.scenario_code,
        criterion_ref=criterion_ref,
        input_ref=(
            "anchor:"
            f"{V4_ANCHOR_BY_SCENARIO_TIER[(scenario.scenario_code, tier)].anchor_id}"
        ),
        repetition=1,
    )
    for scenario in CALIBRATION_SCENARIOS
    for tier in (
        AnchorTier.STRONG,
        AnchorTier.MIXED,
        AnchorTier.WEAK_BUT_STRUCTURALLY_VALID,
    )
    for criterion_ref in scenario.criterion_refs
)


_ANCHOR_REPEAT_CALLS = tuple(
    _anthropic_call(
        call_id=(
            f"cal.score.anchor.{scenario.scenario_code.lower()}.strong."
            f"{_criterion_slug(criterion_ref)}.r2"
        ),
        scenario_code=scenario.scenario_code,
        criterion_ref=criterion_ref,
        input_ref=(
            "anchor:"
            f"{V4_ANCHOR_BY_SCENARIO_TIER[(scenario.scenario_code, AnchorTier.STRONG)].anchor_id}"
        ),
        repetition=2,
    )
    for scenario in CALIBRATION_SCENARIOS
    for criterion_ref in scenario.criterion_refs
)


_OUTPUTS_TO_SCORE = {
    ("SCN-03", CalibrationRole.PRIMARY): "cal.generation.course.primary.r1",
    ("SCN-03", CalibrationRole.FALLBACK): "cal.generation.course.fallback.r1",
    ("SCN-04", CalibrationRole.PRIMARY): "cal.transformation.resource.primary.r1",
    ("SCN-05", CalibrationRole.PRIMARY): "cal.generation.exercise.primary.r1",
    ("SCN-06", CalibrationRole.PRIMARY): "cal.generation.assessment.primary.r1",
    ("SCN-06", CalibrationRole.FALLBACK): "cal.generation.assessment.fallback.r1",
    ("SCN-07", CalibrationRole.PRIMARY): "cal.correction.remediation.primary.r1",
    ("SCN-07", CalibrationRole.FALLBACK): "cal.correction.remediation.fallback.r1",
    ("SCN-08", CalibrationRole.PRIMARY): "cal.generation.qcm.primary.r1",
}


_OUTPUT_SCORING_CALLS = tuple(
    _anthropic_call(
        call_id=(
            f"cal.score.output.{scenario.scenario_code.lower()}.{role.value.casefold()}."
            f"{_criterion_slug(criterion_ref)}.r1"
        ),
        scenario_code=scenario.scenario_code,
        criterion_ref=criterion_ref,
        input_ref=f"output:{source_call_id}",
        repetition=1,
    )
    for scenario in CALIBRATION_SCENARIOS
    for role in (CalibrationRole.PRIMARY, CalibrationRole.FALLBACK)
    if (source_call_id := _OUTPUTS_TO_SCORE.get((scenario.scenario_code, role)))
    is not None
    for criterion_ref in scenario.criterion_refs
)


PEDAGOGICAL_CALIBRATION_CALL_MATRIX = (
    *_OPENAI_CALLS,
    *_ANCHOR_SCORING_CALLS,
    *_ANCHOR_REPEAT_CALLS,
    *_OUTPUT_SCORING_CALLS,
)

OPENAI_CALL_COUNT = sum(
    call.provider is CalibrationProvider.OPENAI
    for call in PEDAGOGICAL_CALIBRATION_CALL_MATRIX
)
ANTHROPIC_CALL_COUNT = sum(
    call.provider is CalibrationProvider.ANTHROPIC
    for call in PEDAGOGICAL_CALIBRATION_CALL_MATRIX
)


def call_matrix_sha256() -> str:
    payload = {
        "plan_version": PEDAGOGICAL_CALIBRATION_PLAN_VERSION,
        "corpus_version": PEDAGOGICAL_CALIBRATION_CORPUS_V4_VERSION,
        "corpus_sha256": v4_calibration_corpus_sha256(),
        "pricing_snapshot_id": PRICING_SNAPSHOT_ID,
        "pricing_snapshot_sha256": pricing_snapshot_sha256(),
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
    canonical = json.dumps(
        payload,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    return hashlib.sha256(canonical).hexdigest()


def estimate_call_plan_cost() -> CostEstimate:
    """Use UTF-8 bytes/4 for base input and bytes/1 for a conservative maximum."""

    quotes = {quote.model: quote for quote in MODEL_PRICE_QUOTES}
    base_input = 0
    base_output = 0
    max_input = 0
    max_output = 0
    base_cost = Decimal("0")
    max_cost = Decimal("0")
    for call in PEDAGOGICAL_CALIBRATION_CALL_MATRIX:
        quote = quotes[call.model]
        estimated_input = _ceil_div(call.input_utf8_upper_bound_bytes, 4)
        estimated_output = _ceil_div(call.max_output_tokens, 2)
        maximum_input = call.input_utf8_upper_bound_bytes
        base_input += estimated_input
        base_output += estimated_output
        max_input += maximum_input
        max_output += call.max_output_tokens
        base_cost += _token_cost(
            estimated_input,
            estimated_output,
            quote,
        )
        max_cost += _token_cost(maximum_input, call.max_output_tokens, quote)
    return CostEstimate(
        call_count=len(PEDAGOGICAL_CALIBRATION_CALL_MATRIX),
        estimated_input_tokens=base_input,
        estimated_output_tokens=base_output,
        estimated_base_usd=_money(base_cost),
        maximum_input_tokens=max_input,
        maximum_output_tokens=max_output,
        estimated_maximum_before_margin_usd=_money(max_cost),
        estimated_maximum_with_margin_usd=_money(max_cost * COST_SAFETY_MARGIN),
    )


def _ceil_div(value: int, divisor: int) -> int:
    return (value + divisor - 1) // divisor


def _token_cost(
    input_tokens: int,
    output_tokens: int,
    quote: ModelPriceQuote,
) -> Decimal:
    million = Decimal(1_000_000)
    return (
        Decimal(input_tokens) * quote.input_usd_per_million_tokens
        + Decimal(output_tokens) * quote.output_usd_per_million_tokens
    ) / million


def _money(value: Decimal) -> Decimal:
    return value.quantize(Decimal("0.000001"), rounding=ROUND_CEILING)


class CalibrationBudgetErrorCode(StrEnum):
    PLAN_MISMATCH = "PLAN_MISMATCH"
    CALL_NOT_PLANNED = "CALL_NOT_PLANNED"
    MODEL_MISMATCH = "MODEL_MISMATCH"
    CALL_COUNT_EXCEEDED = "CALL_COUNT_EXCEEDED"
    APPROVED_CEILING_MISSING = "APPROVED_CEILING_MISSING"
    APPROVED_CEILING_TOO_LOW = "APPROVED_CEILING_TOO_LOW"
    ACTUAL_USAGE_EXCEEDS_POLICY = "ACTUAL_USAGE_EXCEEDS_POLICY"
    CREDENTIAL_UNAVAILABLE = "CREDENTIAL_UNAVAILABLE"


class CalibrationBudgetError(RuntimeError):
    code: CalibrationBudgetErrorCode

    def __init__(self, code: CalibrationBudgetErrorCode) -> None:
        self.code = code
        super().__init__(code.value)


class CalibrationBudgetGuard:
    """Pre-call G2 guard; deliberately unrelated to runtime recovery budgets."""

    def authorize_next(
        self,
        *,
        call_id: str,
        provider: CalibrationProvider,
        model: str,
        model_profile_id: str,
        matrix_checksum: str,
        approved_ceiling_usd: Decimal | None,
        credential_available: bool,
        completed_call_ids: tuple[str, ...],
        actual_cost_usd: Decimal,
    ) -> CalibrationCallSpec:
        if matrix_checksum != call_matrix_sha256():
            _budget_error(CalibrationBudgetErrorCode.PLAN_MISMATCH)
        if approved_ceiling_usd is None:
            _budget_error(CalibrationBudgetErrorCode.APPROVED_CEILING_MISSING)
        if approved_ceiling_usd < estimate_call_plan_cost().estimated_maximum_with_margin_usd:
            _budget_error(CalibrationBudgetErrorCode.APPROVED_CEILING_TOO_LOW)
        if actual_cost_usd > approved_ceiling_usd:
            _budget_error(CalibrationBudgetErrorCode.ACTUAL_USAGE_EXCEEDS_POLICY)
        if len(completed_call_ids) != len(set(completed_call_ids)):
            _budget_error(CalibrationBudgetErrorCode.CALL_COUNT_EXCEEDED)
        known_ids = {call.call_id for call in PEDAGOGICAL_CALIBRATION_CALL_MATRIX}
        if any(completed not in known_ids for completed in completed_call_ids):
            _budget_error(CalibrationBudgetErrorCode.PLAN_MISMATCH)
        try:
            call = next(
                item
                for item in PEDAGOGICAL_CALIBRATION_CALL_MATRIX
                if item.call_id == call_id
            )
        except StopIteration:
            _budget_error(CalibrationBudgetErrorCode.CALL_NOT_PLANNED)
        if call_id in completed_call_ids:
            _budget_error(CalibrationBudgetErrorCode.CALL_COUNT_EXCEEDED)
        if (
            call.provider is not provider
            or call.model != model
            or call.model_profile_id != model_profile_id
        ):
            _budget_error(CalibrationBudgetErrorCode.MODEL_MISMATCH)
        if not credential_available:
            _budget_error(CalibrationBudgetErrorCode.CREDENTIAL_UNAVAILABLE)
        return call


def _budget_error(code: CalibrationBudgetErrorCode) -> None:
    raise CalibrationBudgetError(code) from None
