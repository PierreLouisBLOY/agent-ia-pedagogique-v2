from __future__ import annotations

import json
from collections import Counter
from decimal import Decimal

import pytest

from tests.calibration.pedagogical.call_plan import (
    CalibrationProvider,
    CalibrationWorkload,
)
from tests.calibration.pedagogical.repair_tranche_v4_2 import (
    APPROVED_REPAIR_TRANCHE_CEILING_USD,
    EXPECTED_CARRY_FORWARD_COUNT,
    EXPECTED_REPAIR_TRANCHE_MAX_CALL_COUNT,
    EXPECTED_V42_MATRIX_SHA256,
    LIVE_PROVIDER_RECALIBRATION_AUTHORIZED,
    PROPOSED_REPAIR_TRANCHE_CEILING_USD,
    ROOT,
    V41_SAFE_REPORT_PATH,
    V42_LOGICAL_CALL_MATRIX,
    CallIdentityVersion,
    CarryForwardReason,
    RepairPlanError,
    RepairPlanErrorCode,
    RepairRuntimeAuthorization,
    RepairTrancheBudgetGuard,
    build_carry_forward_audit,
    build_offline_provenance_aggregate,
    call_spec_identity,
    estimate_repair_tranche_cost,
    logical_matrix_sha256,
    repair_call_matrix,
    validate_live_authorization,
    validate_offline_readiness,
)
from tests.calibration.pedagogical.review_contract_v4_2 import (
    COMPACT_REVIEW_MAX_OUTPUT_TOKENS,
    COMPACT_REVIEW_REASONING_EFFORT,
    EXPECTED_COMPACT_REVIEW_CONTRACT_SHA256,
    MAX_CANONICAL_OUTPUT_UTF8_BYTES,
    MAX_FINDINGS,
    CompactReviewContractError,
    ReviewTruncationClassification,
    build_compact_review_request,
    classify_review_truncation,
    compact_review_contract_sha256,
    maximum_compact_review_fixture,
    v4_2_strong_projection,
    validate_compact_review_payload,
)


def _audit():  # type: ignore[no-untyped-def]
    return build_carry_forward_audit()


def _repair_calls():  # type: ignore[no-untyped-def]
    return repair_call_matrix(_audit())


def test_compact_review_request_contains_one_v4_source_and_strict_bounds() -> None:
    call = next(
        item
        for item in V42_LOGICAL_CALL_MATRIX
        if item.workload is CalibrationWorkload.REVIEW
    )
    request = build_compact_review_request(call)
    payload = json.loads(request.input_json)
    target = v4_2_strong_projection(call.scenario_code)
    assert payload["target_content"] == target
    assert sum(value == target for value in payload.values()) == 1
    assert set(payload).isdisjoint(
        {"target_payload", "coverage_context", "resolved_inputs", "output_contract"}
    )
    assert request.max_output_tokens == COMPACT_REVIEW_MAX_OUTPUT_TOKENS == 3_072
    assert request.reasoning_effort is COMPACT_REVIEW_REASONING_EFFORT
    assert request.schema_name == "technical_pedagogical_review_v4_2"
    assert request.output_schema["additionalProperties"] is False
    assert "target_content" not in json.dumps(request.output_schema)


def test_maximum_review_fixture_is_valid_and_has_conservative_headroom() -> None:
    fixture = maximum_compact_review_fixture()
    payload = validate_compact_review_payload(fixture)
    fixture_bytes = len(fixture.encode("utf-8"))
    assert len(payload["findings"]) == MAX_FINDINGS  # type: ignore[arg-type]
    assert fixture_bytes <= MAX_CANONICAL_OUTPUT_UTF8_BYTES
    assert COMPACT_REVIEW_MAX_OUTPUT_TOKENS - fixture_bytes >= 1_536
    assert compact_review_contract_sha256() == (
        EXPECTED_COMPACT_REVIEW_CONTRACT_SHA256
    )


def test_compact_review_local_validation_rejects_duplicate_and_oversize() -> None:
    duplicate = json.loads(maximum_compact_review_fixture())
    duplicate["findings"][1]["id"] = duplicate["findings"][0]["id"]
    with pytest.raises(CompactReviewContractError, match="FINDING_ID_DUPLICATE"):
        validate_compact_review_payload(
            json.dumps(duplicate, separators=(",", ":"), sort_keys=True)
        )
    with pytest.raises(CompactReviewContractError, match="OUTPUT_BYTE_BOUND_EXCEEDED"):
        validate_compact_review_payload(" " * (MAX_CANONICAL_OUTPUT_UTF8_BYTES + 1))


def test_v41_review_truncation_is_confirmed_from_persisted_safe_fields() -> None:
    report = json.loads((ROOT / V41_SAFE_REPORT_PATH).read_text(encoding="utf-8"))
    record = next(
        item
        for item in report["execution"]["call_results"]
        if item["call_id"] == "cal.review.exercise.primary.r1"
    )
    classification = classify_review_truncation(
        provider_response_status=record["provider_response_status"],
        incomplete_reason=record["incomplete_reason"],
        output_tokens=record["output_tokens"],
        max_output_tokens=2_048,
        parse_error_category=record["parse_error_category"],
        structured_output_validation=record["structured_output_validation"],
    )
    assert classification is ReviewTruncationClassification.CONFIRMED


def test_call_identity_detects_actual_v41_projection_drift() -> None:
    call = V42_LOGICAL_CALL_MATRIX[0]
    v41 = call_spec_identity(call, CallIdentityVersion.V41_EXECUTED)
    v42 = call_spec_identity(call, CallIdentityVersion.V42_CORRECTIVE)
    assert "v4.1" in v41.declared_input_refs[0]
    assert "v4.2" in v42.declared_input_refs[0]
    assert v41.source_dependency_sha256 != v42.source_dependency_sha256
    assert v41.prompt_input_sha256 != v42.prompt_input_sha256
    assert v41.sha256() != v42.sha256()


def test_carry_forward_is_limited_to_63_equivalent_anchor_scores() -> None:
    audit = _audit()
    assert len(audit) == 102
    assert sum(item.eligible for item in audit) == EXPECTED_CARRY_FORWARD_COUNT == 63
    assert Counter(item.reason for item in audit) == {
        CarryForwardReason.EQUIVALENT: 63,
        CarryForwardReason.SOURCE_PROJECTION_CHANGED: 13,
        CarryForwardReason.UPSTREAM_CALL_SPEC_CHANGED: 18,
        CarryForwardReason.SOURCE_NOT_COMPLETED: 8,
    }
    eligible_ids = {item.call_id for item in audit if item.eligible}
    eligible_calls = [
        call for call in V42_LOGICAL_CALL_MATRIX if call.call_id in eligible_ids
    ]
    assert all(call.provider is CalibrationProvider.ANTHROPIC for call in eligible_calls)
    assert all(call.input_refs[0].startswith("anchor:") for call in eligible_calls)


def test_repair_tranche_is_exactly_39_and_canary_first_per_family() -> None:
    calls = _repair_calls()
    assert len(calls) == EXPECTED_REPAIR_TRANCHE_MAX_CALL_COUNT == 39
    assert Counter((call.provider, call.workload) for call in calls) == {
        (CalibrationProvider.OPENAI, CalibrationWorkload.GENERATION): 8,
        (CalibrationProvider.OPENAI, CalibrationWorkload.TRANSFORMATION): 2,
        (CalibrationProvider.OPENAI, CalibrationWorkload.CORRECTION): 3,
        (CalibrationProvider.OPENAI, CalibrationWorkload.REVIEW): 7,
        (CalibrationProvider.ANTHROPIC, CalibrationWorkload.SCORING): 19,
    }
    assert calls[0].call_id == "cal.generation.course.primary.r1"
    review = tuple(call for call in calls if call.workload is CalibrationWorkload.REVIEW)
    anthropic = tuple(
        call for call in calls if call.provider is CalibrationProvider.ANTHROPIC
    )
    assert review[0].call_id == "cal.review.exercise.primary.r1"
    assert anthropic[0].call_id == (
        "cal.score.anchor.scn-08.strong.feedback-quality.r2"
    )


def test_anthropic_failed_call_is_one_explicit_new_execution_without_retry() -> None:
    calls = _repair_calls()
    target = tuple(
        call
        for call in calls
        if call.call_id == "cal.score.anchor.scn-08.strong.feedback-quality.r2"
    )
    assert len(target) == 1
    identity = call_spec_identity(target[0], CallIdentityVersion.V42_CORRECTIVE)
    assert ("automatic_retries", 0) in identity.execution_parameters
    report = json.loads((ROOT / V41_SAFE_REPORT_PATH).read_text(encoding="utf-8"))
    source = next(
        item
        for item in report["execution"]["call_results"]
        if item["call_id"] == target[0].call_id
    )
    assert source["closed_error_code"] == "ANTHROPIC_SCORER_TRANSPORT_SERVER"


def test_matrix_and_repair_budget_are_exact_and_not_approved() -> None:
    calls = _repair_calls()
    estimate = estimate_repair_tranche_cost(calls)
    assert len(V42_LOGICAL_CALL_MATRIX) == 102
    assert logical_matrix_sha256() == EXPECTED_V42_MATRIX_SHA256
    assert estimate.call_count == 39
    assert (
        estimate.estimated_maximum_with_margin_usd
        == PROPOSED_REPAIR_TRANCHE_CEILING_USD
        == Decimal("2.111240")
    )
    assert APPROVED_REPAIR_TRANCHE_CEILING_USD is None


def test_budget_guard_and_live_authorization_fail_closed_offline() -> None:
    calls = _repair_calls()
    guard = RepairTrancheBudgetGuard()
    with pytest.raises(RepairPlanError) as missing_ceiling:
        guard.authorize_next(
            call_id=calls[0].call_id,
            matrix_sha256=logical_matrix_sha256(),
            calls=calls,
            approved_ceiling_usd=None,
            completed_call_ids=(),
            actual_cost_usd=Decimal("0"),
        )
    assert missing_ceiling.value.code is RepairPlanErrorCode.APPROVED_CEILING_MISSING
    assert LIVE_PROVIDER_RECALIBRATION_AUTHORIZED is False
    with pytest.raises(RepairPlanError) as live_closed:
        validate_live_authorization(RepairRuntimeAuthorization())
    assert live_closed.value.code is RepairPlanErrorCode.LIVE_AUTHORIZATION_REQUIRED


def test_aggregate_keeps_cross_run_provenance_per_record() -> None:
    audit = _audit()
    aggregate = build_offline_provenance_aggregate(audit)
    records = aggregate["records"]
    assert len(records) == 102  # type: ignore[arg-type]
    dispositions = Counter(item["disposition"] for item in records)  # type: ignore[union-attr]
    assert dispositions == {"CARRY_FORWARD": 63, "PENDING_NEW_EXECUTION": 39}
    carry = next(item for item in records if item["disposition"] == "CARRY_FORWARD")  # type: ignore[union-attr]
    pending = next(
        item for item in records if item["disposition"] == "PENDING_NEW_EXECUTION"  # type: ignore[union-attr]
    )
    assert carry["source_run_id"] == "12.16-g2-v4-1-live"
    assert carry["source_baseline_commit"] is not None
    assert pending["source_run_id"] is None
    assert carry["ledger_source"] != pending["ledger_source"]
    assert aggregate["cross_run_provenance_preserved"] is True


def test_offline_readiness_validates_source_hashes_counts_and_cost() -> None:
    validate_offline_readiness(_audit())
