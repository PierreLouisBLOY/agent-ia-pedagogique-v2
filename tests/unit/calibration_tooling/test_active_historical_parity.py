from __future__ import annotations

import json
from decimal import Decimal

from calibration_tooling.adapters.anthropic.contracts import (
    ResolvedAnthropicConfiguration,
)
from calibration_tooling.contracts.models import (
    CALIBRATION_SCHEMA_V1,
    AbsoluteObservationResult,
    AbsoluteObservationSpec,
    AbsoluteScoreStatus,
    AnchorDescriptor,
    AnchorTier,
    AnchorTriplet,
    CallRef,
    CriterionRef,
    PairwiseDecision,
    PairwiseObservationResult,
    PairwiseObservationSpec,
    ProjectionRef,
    RawProviderResponse,
)
from calibration_tooling.contracts.parser import (
    ACTIVE_OUTPUT_SCHEMA_VERSION,
    CanonicalCalibrationOutputParser,
)
from calibration_tooling.contracts.policy import DurableCalibrationPolicy
from calibration_tooling.runtime.budget import ApprovedBudget


def test_durable_policy_matches_the_approved_historical_invariants() -> None:
    policy = DurableCalibrationPolicy()
    snapshot = {
        "blind_scoring": policy.blind_scoring,
        "deliverable_tiers": tuple(tier.value for tier in policy.deliverable_tiers),
        "one_shot_authorization": policy.one_shot_authorization,
        "fail_closed": policy.fail_closed,
        "retry_count": policy.retry_count,
        "release_threshold": policy.release_threshold,
    }
    assert snapshot == {
        "blind_scoring": True,
        "deliverable_tiers": ("STRONG",),
        "one_shot_authorization": True,
        "fail_closed": True,
        "retry_count": 0,
        "release_threshold": None,
    }


def test_anchor_contract_preserves_fixed_strong_mixed_weak_cardinality() -> None:
    triplet = AnchorTriplet(
        strong=AnchorDescriptor(ProjectionRef("anchor.strong"), AnchorTier.STRONG),
        mixed=AnchorDescriptor(ProjectionRef("anchor.mixed"), AnchorTier.MIXED),
        weak=AnchorDescriptor(ProjectionRef("anchor.weak"), AnchorTier.WEAK),
    )
    assert tuple(
        (descriptor.projection_ref.value, descriptor.tier.value)
        for descriptor in (triplet.strong, triplet.mixed, triplet.weak)
    ) == (
        ("anchor.strong", "STRONG"),
        ("anchor.mixed", "MIXED"),
        ("anchor.weak", "WEAK"),
    )


def test_active_parser_preserves_absolute_and_pairwise_output_shapes() -> None:
    absolute = AbsoluteObservationSpec(
        CALIBRATION_SCHEMA_V1,
        CallRef("call.parity.absolute"),
        CriterionRef("criterion.clarity"),
        ProjectionRef("projection.strong"),
        Decimal("0.010000"),
    )
    pairwise = PairwiseObservationSpec(
        CALIBRATION_SCHEMA_V1,
        CallRef("call.parity.pairwise"),
        CriterionRef("criterion.clarity"),
        ProjectionRef("projection.strong"),
        ProjectionRef("projection.mixed"),
        Decimal("0.010000"),
    )
    parser = CanonicalCalibrationOutputParser()

    absolute_result = parser.parse(
        absolute,
        RawProviderResponse(
            absolute.call_ref,
            json.dumps(
                {
                    "schema_version": ACTIVE_OUTPUT_SCHEMA_VERSION,
                    "call_ref": absolute.call_ref.value,
                    "kind": "ABSOLUTE",
                    "status": "SCORED",
                    "score_level": 4,
                }
            ),
            Decimal("0.001000"),
            True,
        ),
    )
    pairwise_result = parser.parse(
        pairwise,
        RawProviderResponse(
            pairwise.call_ref,
            json.dumps(
                {
                    "schema_version": ACTIVE_OUTPUT_SCHEMA_VERSION,
                    "call_ref": pairwise.call_ref.value,
                    "kind": "PAIRWISE",
                    "decision": "A_BETTER",
                }
            ),
            Decimal("0.001000"),
            True,
        ),
    )

    assert absolute_result == AbsoluteObservationResult(
        absolute.call_ref, AbsoluteScoreStatus.SCORED, 4
    )
    assert pairwise_result == PairwiseObservationResult(
        pairwise.call_ref, PairwiseDecision.A_BETTER
    )


def test_active_types_are_owned_directly_without_historical_reexports() -> None:
    assert AnchorTier.__module__ == "calibration_tooling.contracts.models"
    assert ApprovedBudget.__module__ == "calibration_tooling.runtime.budget"
    assert (
        ResolvedAnthropicConfiguration.__module__
        == "calibration_tooling.adapters.anthropic.contracts"
    )
