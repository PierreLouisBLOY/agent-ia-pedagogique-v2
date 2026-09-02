from __future__ import annotations

from decimal import Decimal

import pytest

from calibration_tooling.contracts.models import (
    CALIBRATION_SCHEMA_V1,
    AbsoluteObservationSpec,
    AnchorDescriptor,
    AnchorTier,
    AnchorTriplet,
    CalibrationPlan,
    CallRef,
    CriterionRef,
    PairwiseObservationSpec,
    ProjectionRef,
    RunRef,
    Sha256Digest,
)
from calibration_tooling.contracts.policy import DurableCalibrationPolicy

MATRIX = Sha256Digest("a" * 64)


def _absolute(call: str = "call.absolute") -> AbsoluteObservationSpec:
    return AbsoluteObservationSpec(
        schema_version=CALIBRATION_SCHEMA_V1,
        call_ref=CallRef(call),
        criterion_ref=CriterionRef("criterion.clarity"),
        projection_ref=ProjectionRef("projection.strong"),
        maximum_cost_usd=Decimal("0.010000"),
    )


def test_anchor_triplet_requires_exactly_one_distinct_projection_per_tier() -> None:
    triplet = AnchorTriplet(
        strong=AnchorDescriptor(ProjectionRef("anchor.strong"), AnchorTier.STRONG),
        mixed=AnchorDescriptor(ProjectionRef("anchor.mixed"), AnchorTier.MIXED),
        weak=AnchorDescriptor(ProjectionRef("anchor.weak"), AnchorTier.WEAK),
    )
    assert tuple(item.tier for item in (triplet.strong, triplet.mixed, triplet.weak)) == (
        AnchorTier.STRONG,
        AnchorTier.MIXED,
        AnchorTier.WEAK,
    )


def test_anchor_triplet_fails_closed_on_wrong_tier_or_duplicate_ref() -> None:
    with pytest.raises(ValueError):
        AnchorTriplet(
            strong=AnchorDescriptor(ProjectionRef("anchor.strong"), AnchorTier.MIXED),
            mixed=AnchorDescriptor(ProjectionRef("anchor.mixed"), AnchorTier.MIXED),
            weak=AnchorDescriptor(ProjectionRef("anchor.weak"), AnchorTier.WEAK),
        )
    with pytest.raises(ValueError):
        AnchorTriplet(
            strong=AnchorDescriptor(ProjectionRef("anchor.same"), AnchorTier.STRONG),
            mixed=AnchorDescriptor(ProjectionRef("anchor.same"), AnchorTier.MIXED),
            weak=AnchorDescriptor(ProjectionRef("anchor.weak"), AnchorTier.WEAK),
        )


def test_observation_specs_are_discriminated_and_pairwise_refs_must_differ() -> None:
    absolute = _absolute()
    pairwise = PairwiseObservationSpec(
        schema_version=CALIBRATION_SCHEMA_V1,
        call_ref=CallRef("call.pairwise"),
        criterion_ref=CriterionRef("criterion.clarity"),
        candidate_a_ref=ProjectionRef("projection.strong"),
        candidate_b_ref=ProjectionRef("projection.mixed"),
        maximum_cost_usd=Decimal("0.020000"),
    )
    assert absolute.kind.value == "ABSOLUTE"
    assert pairwise.kind.value == "PAIRWISE"
    with pytest.raises(ValueError):
        PairwiseObservationSpec(
            schema_version=CALIBRATION_SCHEMA_V1,
            call_ref=CallRef("call.invalid"),
            criterion_ref=CriterionRef("criterion.clarity"),
            candidate_a_ref=ProjectionRef("projection.same"),
            candidate_b_ref=ProjectionRef("projection.same"),
            maximum_cost_usd=Decimal("0.020000"),
        )


def test_plan_is_versioned_non_empty_bounded_and_has_unique_call_refs() -> None:
    plan = CalibrationPlan(
        schema_version=CALIBRATION_SCHEMA_V1,
        run_ref=RunRef("run.001"),
        matrix_sha256=MATRIX,
        observations=(_absolute(),),
    )
    assert len(plan.observations) == 1
    with pytest.raises(ValueError):
        CalibrationPlan(
            schema_version=CALIBRATION_SCHEMA_V1,
            run_ref=RunRef("run.empty"),
            matrix_sha256=MATRIX,
            observations=(),
        )
    with pytest.raises(ValueError):
        CalibrationPlan(
            schema_version=CALIBRATION_SCHEMA_V1,
            run_ref=RunRef("run.duplicate"),
            matrix_sha256=MATRIX,
            observations=(_absolute(), _absolute()),
        )


def test_durable_policy_is_blind_strong_only_one_shot_and_has_no_threshold() -> None:
    policy = DurableCalibrationPolicy()
    assert policy.is_deliverable(AnchorTier.STRONG)
    assert not policy.is_deliverable(AnchorTier.MIXED)
    assert not policy.is_deliverable(AnchorTier.WEAK)
    assert policy.release_threshold is None
    with pytest.raises(ValueError):
        DurableCalibrationPolicy(blind_scoring=False)
    with pytest.raises(ValueError):
        DurableCalibrationPolicy(deliverable_tiers=(AnchorTier.STRONG, AnchorTier.MIXED))
    with pytest.raises(ValueError):
        DurableCalibrationPolicy(retry_count=1)
    with pytest.raises(ValueError):
        DurableCalibrationPolicy(release_threshold=Decimal("0.800000"))
