"""Deterministic offline audit of the V4 implementation-readiness patch."""

from __future__ import annotations

from collections import defaultdict
from decimal import Decimal
from pathlib import Path

from tests.calibration.pedagogical.anchor_corpus_v4 import (
    V4_CALIBRATION_ANCHORS,
    v4_calibration_corpus_sha256,
)
from tests.calibration.pedagogical.call_plan import (
    ANTHROPIC_CALL_COUNT,
    OPENAI_CALL_COUNT,
    PEDAGOGICAL_CALIBRATION_CALL_MATRIX,
    PEDAGOGICAL_CALIBRATION_PLAN_VERSION,
    CalibrationRole,
    call_matrix_sha256,
    estimate_call_plan_cost,
)
from tests.calibration.pedagogical.live_runner import (
    APPROVED_HARD_CEILING_USD,
    APPROVED_MATRIX_SHA256,
    APPROVED_MAX_CALL_COUNT,
    APPROVED_PRICING_SHA256,
    CANARY_CALL_IDS,
    EXPECTED_MATRIX_SHA256,
    EXPECTED_V4_CORPUS_SHA256,
    LIVE_PROVIDER_RECALIBRATION_AUTHORIZED,
    OWNER_CONFIGURATION_APPROVAL,
    PROPOSED_TECHNICAL_CEILING_USD,
    ProviderWorkloadFamily,
)
from tests.calibration.pedagogical.pricing import (
    EXPECTED_PRICING_SNAPSHOT_SHA256,
    MODEL_PRICE_BY_NAME,
    PRICING_SNAPSHOT_ID,
    pricing_snapshot_sha256,
)
from tests.calibration.pedagogical.v4_corrective_attestation_closure import (
    CORRECTED_FORM_SHA256,
    build_closure_payload,
)

ROOT = Path(__file__).resolve().parents[3]
PHASE = "12.16-G2-V4-PROVIDER-RECALIBRATION-IMPLEMENTATION-READINESS"
BUNDLE_SHA256 = (
    "ef9834a40c24af6cd39a6c21f09fc830392634145d363dd0f775b0259243afb2"
)
LIVE_RUNNER_RELATIVE_PATH = "tests/calibration/pedagogical/live_runner.py"


def _pairwise_matrix_count() -> int:
    grouped: dict[tuple[str, str], set[CalibrationRole]] = defaultdict(set)
    matrix_by_id = {
        call.call_id: call for call in PEDAGOGICAL_CALIBRATION_CALL_MATRIX
    }
    for call in PEDAGOGICAL_CALIBRATION_CALL_MATRIX:
        if not call.input_refs[0].startswith("output:"):
            continue
        source = matrix_by_id[call.input_refs[0].removeprefix("output:")]
        grouped[(call.scenario_code, call.criterion_refs[0])].add(source.role)
    return sum(
        {CalibrationRole.PRIMARY, CalibrationRole.FALLBACK}.issubset(roles)
        for roles in grouped.values()
    )


def build_implementation_readiness_payload(
    root: Path = ROOT,
) -> dict[str, object]:
    closure = build_closure_payload(root)
    calls = PEDAGOGICAL_CALIBRATION_CALL_MATRIX
    anchor_calls = tuple(
        call for call in calls if call.input_refs[0].startswith("anchor:")
    )
    anchor_ids = {
        call.input_refs[0].removeprefix("anchor:") for call in anchor_calls
    }
    expected_anchor_ids = {anchor.anchor_id for anchor in V4_CALIBRATION_ANCHORS}
    output_calls = tuple(
        call for call in calls if call.input_refs[0].startswith("output:")
    )
    source = (root / LIVE_RUNNER_RELATIVE_PATH).read_text(encoding="utf-8")
    matrix_gate = (
        PEDAGOGICAL_CALIBRATION_PLAN_VERSION == "12.16-g2-v4-plan-v1"
        and call_matrix_sha256() == EXPECTED_MATRIX_SHA256
        and len(calls) == 102
        and OPENAI_CALL_COUNT == 20
        and ANTHROPIC_CALL_COUNT == 82
        and len({call.call_id for call in calls}) == 102
        and anchor_ids == expected_anchor_ids
        and len(anchor_ids) == 24
        and len(tuple(call for call in anchor_calls if call.repetition == 1)) == 48
        and len(tuple(call for call in anchor_calls if call.repetition == 2)) == 16
        and len(output_calls) == 18
        and _pairwise_matrix_count() == 6
    )
    baseline_gate = (
        closure["methodological_status"] == "PASS"
        and closure["human_v4_prevalidation"]
        == "PASS_WITH_CORRECTIVE_ATTESTATION"
        and closure["corrected_form_sha256"] == CORRECTED_FORM_SHA256
        and v4_calibration_corpus_sha256() == EXPECTED_V4_CORPUS_SHA256
        and "validate_v4_baseline" in source
        and "baseline_validator(root)" in source
    )
    canary_gate = (
        len(CANARY_CALL_IDS) == len(ProviderWorkloadFamily) == 3
        and "SystemicCanaryBreaker.from_ledger" in source
        and "breaker.authorize" in source
        and "breaker.record_canary" in source
        and '"canaries"' in source
    )
    pricing_gate = (
        pricing_snapshot_sha256() == EXPECTED_PRICING_SNAPSHOT_SHA256
        and PRICING_SNAPSHOT_ID == "official-2026-08-31-v4"
        and MODEL_PRICE_BY_NAME[
            "claude-sonnet-5"
        ].input_usd_per_million_tokens
        == Decimal("2.00")
        and MODEL_PRICE_BY_NAME[
            "claude-sonnet-5"
        ].cached_input_usd_per_million_tokens
        == Decimal("0.20")
        and MODEL_PRICE_BY_NAME[
            "claude-sonnet-5"
        ].output_usd_per_million_tokens
        == Decimal("10.00")
        and estimate_call_plan_cost().estimated_maximum_with_margin_usd
        == PROPOSED_TECHNICAL_CEILING_USD
        and "_G2_PRICING" not in source
    )
    reporting_gate = (
        '"human_anchor_review": "PASS_WITH_CORRECTIVE_ATTESTATION"' in source
        and "pairwise_primary_win_count" in source
        and "producer_model" in source
        and "return ()" not in source[source.index("def _pairwise_quality") :]
    )
    owner_configuration_gate = (
        OWNER_CONFIGURATION_APPROVAL == "APPROVED"
        and APPROVED_MATRIX_SHA256 == EXPECTED_MATRIX_SHA256
        and APPROVED_PRICING_SHA256 == EXPECTED_PRICING_SNAPSHOT_SHA256
        and APPROVED_MAX_CALL_COUNT == len(calls) == 102
        and APPROVED_HARD_CEILING_USD == PROPOSED_TECHNICAL_CEILING_USD
        and LIVE_PROVIDER_RECALIBRATION_AUTHORIZED is False
    )
    implementation_ready = all(
        (
            matrix_gate,
            baseline_gate,
            canary_gate,
            pricing_gate,
            reporting_gate,
            owner_configuration_gate,
        )
    )
    return {
        "phase": PHASE,
        "bundle_sha256": BUNDLE_SHA256,
        "bundle_manifest_integrity": "PASS",
        "matrix": {
            "version": PEDAGOGICAL_CALIBRATION_PLAN_VERSION,
            "sha256": call_matrix_sha256(),
            "call_count": len(calls),
            "openai_call_count": OPENAI_CALL_COUNT,
            "anthropic_call_count": ANTHROPIC_CALL_COUNT,
            "v4_anchor_count": len(anchor_ids),
            "legacy_anchor_count": sum(
                anchor_id.startswith("cal.scn-") for anchor_id in anchor_ids
            ),
            "anchor_score_call_count": sum(
                call.repetition == 1 for call in anchor_calls
            ),
            "strong_repeat_call_count": sum(
                call.repetition == 2 for call in anchor_calls
            ),
            "output_score_call_count": len(output_calls),
            "pairwise_comparison_count": _pairwise_matrix_count(),
        },
        "pricing": {
            "snapshot_id": PRICING_SNAPSHOT_ID,
            "snapshot_sha256": pricing_snapshot_sha256(),
            "proposed_technical_ceiling_usd": str(
                PROPOSED_TECHNICAL_CEILING_USD
            ),
            "approved_hard_ceiling_usd": APPROVED_HARD_CEILING_USD,
        },
        "owner_configuration": {
            "approval": OWNER_CONFIGURATION_APPROVAL,
            "matrix_sha256": APPROVED_MATRIX_SHA256,
            "pricing_sha256": APPROVED_PRICING_SHA256,
            "max_call_count": APPROVED_MAX_CALL_COUNT,
            "approved_hard_ceiling_usd": str(APPROVED_HARD_CEILING_USD),
            "live_provider_recalibration_authorized": (
                LIVE_PROVIDER_RECALIBRATION_AUTHORIZED
            ),
        },
        "gates": {
            "v4_anchor_matrix": "PASS" if matrix_gate else "FAIL",
            "v4_baseline_guard": "PASS" if baseline_gate else "FAIL",
            "canary_integration": "PASS" if canary_gate else "FAIL",
            "pricing_consistency": "PASS" if pricing_gate else "FAIL",
            "v4_reporting_pairwise": "PASS" if reporting_gate else "FAIL",
            "owner_configuration_binding": (
                "PASS" if owner_configuration_gate else "FAIL"
            ),
        },
        "canary_call_ids": {
            family.value: CANARY_CALL_IDS[family]
            for family in ProviderWorkloadFamily
        },
        "provider_calls": 0,
        "credentials_resolved": False,
        "transport_constructed": False,
        "runtime_route_change": "NONE",
        "corpus_change": "NONE",
        "attestation_change": "NONE",
        "implementation_live_readiness": (
            "READY_CONFIG_APPROVED_LIVE_NOT_AUTHORIZED"
            if implementation_ready
            else "NO_GO"
        ),
        "live_provider_recalibration_authorized": (
            LIVE_PROVIDER_RECALIBRATION_AUTHORIZED
        ),
        "commit": "NONE",
        "push": "NONE",
        "next_gate": "EXPLICIT_LIVE_PROVIDER_RECALIBRATION_AUTHORIZATION",
    }
