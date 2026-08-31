from __future__ import annotations

from decimal import Decimal
from fractions import Fraction
from pathlib import Path

import pytest

from tests.calibration.pedagogical import pricing as pricing_module
from tests.calibration.pedagogical.anchor_corpus_v4 import (
    V4_CALIBRATION_ANCHORS,
    V4_CRITERION_ORDERINGS,
)
from tests.calibration.pedagogical.call_plan import (
    ANTHROPIC_CALL_COUNT,
    MODEL_PRICE_QUOTES,
    OPENAI_CALL_COUNT,
    PEDAGOGICAL_CALIBRATION_CALL_MATRIX,
    RAW_OUTPUT_DIRECTORY,
    CalibrationBudgetError,
    CalibrationBudgetErrorCode,
    CalibrationBudgetGuard,
    CalibrationProvider,
    CalibrationRole,
    CalibrationWorkload,
    call_matrix_sha256,
    estimate_call_plan_cost,
)
from tests.calibration.pedagogical.metrics import (
    CalibrationResponseStatus,
    InvocationObservation,
    PairwiseQualityObservation,
    QualityScoreObservation,
    RepeatScore,
    summarize_invocations,
    summarize_orderings,
    summarize_pairwise_quality,
    summarize_quality,
    summarize_repeatability,
)
from tests.calibration.pedagogical.pricing import (
    EXPECTED_PRICING_SNAPSHOT_SHA256,
    PRICING_SNAPSHOT_ID,
    pricing_snapshot_sha256,
)
from tests.calibration.pedagogical.protocol import (
    V4_CALIBRATION_CRITERION_ITEMS,
    build_v4_blind_scorer_observation,
)


def test_call_matrix_is_exact_versioned_bounded_and_covers_required_workloads() -> None:
    calls = PEDAGOGICAL_CALIBRATION_CALL_MATRIX
    assert len(calls) == 102
    assert OPENAI_CALL_COUNT == 20
    assert ANTHROPIC_CALL_COUNT == 82
    assert len({call.call_id for call in calls}) == len(calls)
    assert RAW_OUTPUT_DIRECTORY.startswith("artifacts/")
    generation = tuple(call for call in calls if call.workload is CalibrationWorkload.GENERATION)
    review = tuple(call for call in calls if call.workload is CalibrationWorkload.REVIEW)
    assert {call.task_kind for call in generation} == {
        "course",
        "exercise",
        "assessment",
        "qcm",
    }
    assert {call.task_kind for call in review} == {
        "exercise",
        "assessment",
        "correction",
        "qcm",
    }
    assert {call.workload for call in calls} == set(CalibrationWorkload)
    assert all(call.max_output_tokens <= 2_048 for call in calls)
    assert all(call.input_utf8_upper_bound_bytes <= 8_000 for call in calls)
    assert all(call.model_profile_id.startswith(f"{call.provider.value}.") for call in calls)
    assert any(call.role is CalibrationRole.FALLBACK for call in generation)
    assert sum(call.role is CalibrationRole.FALLBACK for call in generation) < len(generation)
    assert any(call.role is CalibrationRole.FALLBACK for call in review)
    assert sum(call.role is CalibrationRole.FALLBACK for call in review) < len(review)


def test_repeatability_and_selected_output_scoring_are_deterministic_subsets() -> None:
    anchor_repeats = tuple(
        call
        for call in PEDAGOGICAL_CALIBRATION_CALL_MATRIX
        if call.provider is CalibrationProvider.ANTHROPIC
        and call.repetition == 2
    )
    output_scores = tuple(
        call
        for call in PEDAGOGICAL_CALIBRATION_CALL_MATRIX
        if call.provider is CalibrationProvider.ANTHROPIC
        and call.input_refs[0].startswith("output:")
    )
    openai_repeats = tuple(
        call
        for call in PEDAGOGICAL_CALIBRATION_CALL_MATRIX
        if call.provider is CalibrationProvider.OPENAI and call.repetition == 2
    )
    assert len(anchor_repeats) == 16
    assert {call.criterion_refs[0] for call in anchor_repeats} == {
        ordering.criterion_ref for ordering in V4_CRITERION_ORDERINGS
    }
    assert len(output_scores) == 18
    assert {call.scenario_code for call in output_scores} == {
        "SCN-03",
        "SCN-04",
        "SCN-05",
        "SCN-06",
        "SCN-07",
        "SCN-08",
    }
    assert sum(".fallback." in call.call_id for call in output_scores) == 6
    assert {call.workload for call in openai_repeats} == {
        CalibrationWorkload.GENERATION,
        CalibrationWorkload.TRANSFORMATION,
        CalibrationWorkload.CORRECTION,
        CalibrationWorkload.REVIEW,
    }


def test_call_matrix_checksum_and_decimal_cost_plan_are_frozen() -> None:
    assert (
        call_matrix_sha256()
        == "f159f200bf45d9df631007dd742e6ea9cc44a3e487ed76180f92c1392cd6245e"
    )
    estimate = estimate_call_plan_cost()
    assert estimate.call_count == 102
    assert estimate.estimated_input_tokens == 195_250
    assert estimate.estimated_output_tokens == 36_608
    assert estimate.estimated_base_usd == Decimal("0.877656")
    assert estimate.maximum_input_tokens == 781_000
    assert estimate.maximum_output_tokens == 73_216
    assert estimate.estimated_maximum_before_margin_usd == Decimal("2.601312")
    assert estimate.estimated_maximum_with_margin_usd == Decimal("3.251640")
    assert {quote.model for quote in MODEL_PRICE_QUOTES} == {
        "gpt-5.6-terra",
        "gpt-5.6-sol",
        "claude-sonnet-5",
    }
    assert all(quote.unit == "USD per 1M tokens" for quote in MODEL_PRICE_QUOTES)
    assert all(quote.verified_on == "2026-08-31" for quote in MODEL_PRICE_QUOTES)
    assert PRICING_SNAPSHOT_ID == "official-2026-08-31-v4"
    assert pricing_snapshot_sha256() == EXPECTED_PRICING_SNAPSHOT_SHA256


def test_call_matrix_uses_all_and_only_opaque_v4_anchor_ids() -> None:
    expected = {anchor.anchor_id for anchor in V4_CALIBRATION_ANCHORS}
    actual = {
        call.input_refs[0].removeprefix("anchor:")
        for call in PEDAGOGICAL_CALIBRATION_CALL_MATRIX
        if call.input_refs[0].startswith("anchor:")
    }
    assert actual == expected
    assert len(actual) == 24
    assert all(anchor_id.startswith("cal.v4.scn-") for anchor_id in actual)
    assert all(not anchor_id.startswith("cal.scn-") for anchor_id in actual)
    assert len(V4_CALIBRATION_CRITERION_ITEMS) == 48
    assert all(
        build_v4_blind_scorer_observation(item).fields
        for item in V4_CALIBRATION_CRITERION_ITEMS
    )


def test_pricing_snapshot_mutation_fails_closed(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    changed = tmp_path / "pricing.json"
    changed.write_text('{"snapshot_id":"changed"}\n', encoding="utf-8")
    monkeypatch.setattr(pricing_module, "SNAPSHOT_PATH", changed)
    with pytest.raises(RuntimeError, match="PRICING_SNAPSHOT_SHA256_MISMATCH"):
        pricing_module.pricing_snapshot_sha256()


def test_budget_guard_blocks_before_call_on_every_closed_failure() -> None:
    guard = CalibrationBudgetGuard()
    first = PEDAGOGICAL_CALIBRATION_CALL_MATRIX[0]
    ceiling = estimate_call_plan_cost().estimated_maximum_with_margin_usd

    def authorize(**overrides: object):  # type: ignore[no-untyped-def]
        values: dict[str, object] = {
            "call_id": first.call_id,
            "provider": first.provider,
            "model": first.model,
            "model_profile_id": first.model_profile_id,
            "matrix_checksum": call_matrix_sha256(),
            "approved_ceiling_usd": ceiling,
            "credential_available": True,
            "completed_call_ids": (),
            "actual_cost_usd": Decimal("0"),
        }
        values.update(overrides)
        return guard.authorize_next(**values)  # type: ignore[arg-type]

    assert authorize() == first
    cases = (
        ({"matrix_checksum": "changed"}, CalibrationBudgetErrorCode.PLAN_MISMATCH),
        ({"call_id": "unplanned"}, CalibrationBudgetErrorCode.CALL_NOT_PLANNED),
        ({"model": "other"}, CalibrationBudgetErrorCode.MODEL_MISMATCH),
        (
            {"model_profile_id": "other-profile"},
            CalibrationBudgetErrorCode.MODEL_MISMATCH,
        ),
        (
            {"completed_call_ids": (first.call_id,)},
            CalibrationBudgetErrorCode.CALL_COUNT_EXCEEDED,
        ),
        (
            {"approved_ceiling_usd": None},
            CalibrationBudgetErrorCode.APPROVED_CEILING_MISSING,
        ),
        (
            {"approved_ceiling_usd": Decimal("3.25")},
            CalibrationBudgetErrorCode.APPROVED_CEILING_TOO_LOW,
        ),
        (
            {"actual_cost_usd": ceiling + Decimal("0.01")},
            CalibrationBudgetErrorCode.ACTUAL_USAGE_EXCEEDS_POLICY,
        ),
        (
            {"credential_available": False},
            CalibrationBudgetErrorCode.CREDENTIAL_UNAVAILABLE,
        ),
    )
    for overrides, expected in cases:
        with pytest.raises(CalibrationBudgetError) as raised:
            authorize(**overrides)
        assert raised.value.code is expected


def test_threshold_free_metrics_cover_ordering_repeatability_quality_and_usage() -> None:
    ordering = V4_CRITERION_ORDERINGS[0]
    scores = {
        (ordering.criterion_ref, ordering.ordered_anchor_ids[0]): Fraction(4, 5),
        (ordering.criterion_ref, ordering.ordered_anchor_ids[1]): Fraction(1, 2),
        (ordering.criterion_ref, ordering.ordered_anchor_ids[2]): Fraction(1, 5),
    }
    ordering_metrics = summarize_orderings((ordering,), scores)
    assert ordering_metrics.strict_ordering_count == 1
    assert ordering_metrics.weak_ordering_count == 1
    assert ordering_metrics.tied_pair_count == 0
    assert ordering_metrics.inverted_pair_count == 0
    repeatability = summarize_repeatability(
        (
            RepeatScore("subject", ordering.criterion_ref, 1, Fraction(3, 4)),
            RepeatScore("subject", ordering.criterion_ref, 2, Fraction(1, 2)),
        )
    )
    assert repeatability.maximum_spread == Fraction(1, 4)
    assert repeatability.mean_absolute_rational_delta == Fraction(1, 4)
    assert repeatability.exact_agreement_rate == Fraction(0, 1)
    assert repeatability.inconclusive_rate == Fraction(0, 1)
    quality = summarize_quality(
        (
            QualityScoreObservation("SCN-01", ordering.criterion_ref, "model-a", Fraction(1, 2)),
            QualityScoreObservation("SCN-01", ordering.criterion_ref, "model-a", None),
        )
    )
    assert quality[0].mean_score == Fraction(1, 2)
    assert quality[0].inconclusive_count == 1
    pairwise = summarize_pairwise_quality(
        (
            PairwiseQualityObservation(
                "SCN-01",
                ordering.criterion_ref,
                "model-a",
                "model-b",
                Fraction(3, 4),
                Fraction(1, 2),
            ),
        )
    )
    assert pairwise.primary_win_count == 1
    invocation = InvocationObservation(
        "call",
        "provider",
        "model",
        "workload",
        CalibrationResponseStatus.STRUCTURED,
        100,
        0,
        50,
        250,
        Decimal("0.001250"),
    )
    assert invocation.latency_milliseconds == 250
    invocation_metrics = summarize_invocations((invocation,))
    assert invocation_metrics[0].call_count == 1
    assert invocation_metrics[0].input_tokens == 100
    assert invocation_metrics[0].output_tokens == 50
    assert invocation_metrics[0].valid_structured_response_rate == Fraction(1, 1)
    assert invocation_metrics[0].observed_cost_usd == Decimal("0.001250")
