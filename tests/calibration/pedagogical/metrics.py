"""Threshold-free offline metrics prepared for the future approved G2 run."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from decimal import Decimal
from enum import StrEnum
from fractions import Fraction

from tests.calibration.pedagogical.catalog import CriterionOrdering


class CalibrationResponseStatus(StrEnum):
    STRUCTURED = "STRUCTURED"
    REFUSAL = "REFUSAL"
    ERROR = "ERROR"
    INCONCLUSIVE = "INCONCLUSIVE"


class CalibrationDecisionType(StrEnum):
    CALIBRATION_SUPPORTED = "CALIBRATION_SUPPORTED"
    CALIBRATION_INCONCLUSIVE = "CALIBRATION_INCONCLUSIVE"
    CALIBRATION_REJECTED = "CALIBRATION_REJECTED"


@dataclass(frozen=True, slots=True)
class OrderingMetrics:
    criterion_count: int
    strict_ordering_count: int
    weak_ordering_count: int
    tied_pair_count: int
    inverted_pair_count: int
    inconclusive_count: int


@dataclass(frozen=True, slots=True)
class RepeatScore:
    subject_id: str
    criterion_ref: str
    repetition: int
    score: Fraction | None


@dataclass(frozen=True, slots=True)
class RepeatabilityMetrics:
    group_count: int
    exact_agreement_count: int
    inconclusive_count: int
    exact_agreement_rate: Fraction
    inconclusive_rate: Fraction
    maximum_spread: Fraction | None
    mean_absolute_rational_delta: Fraction | None


@dataclass(frozen=True, slots=True)
class InvocationObservation:
    call_id: str
    provider: str
    model: str
    workload: str
    status: CalibrationResponseStatus
    input_tokens: int
    cached_input_tokens: int
    output_tokens: int
    latency_milliseconds: int
    observed_cost_usd: Decimal


@dataclass(frozen=True, slots=True)
class QualityScoreObservation:
    scenario_code: str
    criterion_ref: str
    model: str
    score: Fraction | None


@dataclass(frozen=True, slots=True)
class QualityMetric:
    scenario_code: str
    criterion_ref: str
    model: str
    observation_count: int
    inconclusive_count: int
    mean_score: Fraction | None


@dataclass(frozen=True, slots=True)
class PairwiseQualityObservation:
    scenario_code: str
    criterion_ref: str
    primary_model: str
    fallback_model: str
    primary_score: Fraction | None
    fallback_score: Fraction | None


@dataclass(frozen=True, slots=True)
class PairwiseQualityMetrics:
    comparison_count: int
    primary_win_count: int
    fallback_win_count: int
    tie_count: int
    inconclusive_count: int


@dataclass(frozen=True, slots=True)
class InvocationMetrics:
    provider: str
    workload: str
    call_count: int
    structured_count: int
    refusal_count: int
    error_count: int
    inconclusive_count: int
    valid_structured_response_rate: Fraction
    refusal_rate: Fraction
    error_rate: Fraction
    input_tokens: int
    cached_input_tokens: int
    output_tokens: int
    latency_milliseconds: int
    observed_cost_usd: Decimal


def summarize_orderings(
    orderings: tuple[CriterionOrdering, ...],
    scores: dict[tuple[str, str], Fraction | None],
) -> OrderingMetrics:
    strict = 0
    weak = 0
    ties = 0
    inversions = 0
    inconclusive = 0
    for ordering in orderings:
        values = tuple(
            scores.get((ordering.criterion_ref, anchor_id))
            for anchor_id in ordering.ordered_anchor_ids
        )
        if any(value is None for value in values):
            inconclusive += 1
            continue
        complete = tuple(value for value in values if value is not None)
        pairs = tuple(zip(complete, complete[1:], strict=False))
        strict += int(all(left > right for left, right in pairs))
        weak += int(all(left >= right for left, right in pairs))
        ties += sum(left == right for left, right in pairs)
        inversions += sum(left < right for left, right in pairs)
    return OrderingMetrics(
        criterion_count=len(orderings),
        strict_ordering_count=strict,
        weak_ordering_count=weak,
        tied_pair_count=ties,
        inverted_pair_count=inversions,
        inconclusive_count=inconclusive,
    )


def summarize_repeatability(
    observations: tuple[RepeatScore, ...],
) -> RepeatabilityMetrics:
    grouped: dict[tuple[str, str], list[RepeatScore]] = defaultdict(list)
    for observation in observations:
        grouped[(observation.subject_id, observation.criterion_ref)].append(observation)
    agreements = 0
    inconclusive = 0
    spreads: list[Fraction] = []
    deltas: list[Fraction] = []
    for items in grouped.values():
        ordered = sorted(items, key=lambda item: item.repetition)
        if len(ordered) < 2 or any(item.score is None for item in ordered):
            inconclusive += 1
            continue
        values = tuple(item.score for item in ordered if item.score is not None)
        agreements += int(len(set(values)) == 1)
        spreads.append(max(values) - min(values))
        baseline = values[0]
        deltas.extend(abs(value - baseline) for value in values[1:])
    return RepeatabilityMetrics(
        group_count=len(grouped),
        exact_agreement_count=agreements,
        inconclusive_count=inconclusive,
        exact_agreement_rate=(
            Fraction(agreements, len(grouped)) if grouped else Fraction(0, 1)
        ),
        inconclusive_rate=(
            Fraction(inconclusive, len(grouped)) if grouped else Fraction(0, 1)
        ),
        maximum_spread=max(spreads) if spreads else None,
        mean_absolute_rational_delta=(
            sum(deltas, start=Fraction(0, 1)) / len(deltas) if deltas else None
        ),
    )


def summarize_quality(
    observations: tuple[QualityScoreObservation, ...],
) -> tuple[QualityMetric, ...]:
    grouped: dict[tuple[str, str, str], list[Fraction | None]] = defaultdict(list)
    for observation in observations:
        grouped[
            (
                observation.scenario_code,
                observation.criterion_ref,
                observation.model,
            )
        ].append(observation.score)
    return tuple(
        QualityMetric(
            scenario_code=key[0],
            criterion_ref=key[1],
            model=key[2],
            observation_count=len(values),
            inconclusive_count=sum(value is None for value in values),
            mean_score=(
                sum(
                    (value for value in values if value is not None),
                    start=Fraction(0, 1),
                )
                / sum(value is not None for value in values)
                if any(value is not None for value in values)
                else None
            ),
        )
        for key, values in sorted(grouped.items())
    )


def summarize_pairwise_quality(
    observations: tuple[PairwiseQualityObservation, ...],
) -> PairwiseQualityMetrics:
    primary_wins = 0
    fallback_wins = 0
    ties = 0
    inconclusive = 0
    for observation in observations:
        if observation.primary_score is None or observation.fallback_score is None:
            inconclusive += 1
        elif observation.primary_score > observation.fallback_score:
            primary_wins += 1
        elif observation.primary_score < observation.fallback_score:
            fallback_wins += 1
        else:
            ties += 1
    return PairwiseQualityMetrics(
        comparison_count=len(observations),
        primary_win_count=primary_wins,
        fallback_win_count=fallback_wins,
        tie_count=ties,
        inconclusive_count=inconclusive,
    )


def summarize_invocations(
    observations: tuple[InvocationObservation, ...],
) -> tuple[InvocationMetrics, ...]:
    grouped: dict[tuple[str, str], list[InvocationObservation]] = defaultdict(list)
    for observation in observations:
        grouped[(observation.provider, observation.workload)].append(observation)
    return tuple(
        InvocationMetrics(
            provider=key[0],
            workload=key[1],
            call_count=len(items),
            structured_count=sum(
                item.status is CalibrationResponseStatus.STRUCTURED for item in items
            ),
            refusal_count=sum(
                item.status is CalibrationResponseStatus.REFUSAL for item in items
            ),
            error_count=sum(item.status is CalibrationResponseStatus.ERROR for item in items),
            inconclusive_count=sum(
                item.status is CalibrationResponseStatus.INCONCLUSIVE for item in items
            ),
            valid_structured_response_rate=Fraction(
                sum(item.status is CalibrationResponseStatus.STRUCTURED for item in items),
                len(items),
            ),
            refusal_rate=Fraction(
                sum(item.status is CalibrationResponseStatus.REFUSAL for item in items),
                len(items),
            ),
            error_rate=Fraction(
                sum(item.status is CalibrationResponseStatus.ERROR for item in items),
                len(items),
            ),
            input_tokens=sum(item.input_tokens for item in items),
            cached_input_tokens=sum(item.cached_input_tokens for item in items),
            output_tokens=sum(item.output_tokens for item in items),
            latency_milliseconds=sum(item.latency_milliseconds for item in items),
            observed_cost_usd=sum(
                (item.observed_cost_usd for item in items),
                start=Decimal("0"),
            ),
        )
        for key, items in sorted(grouped.items())
    )
