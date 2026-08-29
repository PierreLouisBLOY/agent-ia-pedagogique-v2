from __future__ import annotations

import json
from collections import Counter
from dataclasses import replace
from decimal import Decimal
from pathlib import Path

import pytest

from backend.adapters.outbound.openai import OpenAIReasoningEffort
from tests.calibration.pedagogical.call_plan import (
    PEDAGOGICAL_CALIBRATION_CALL_MATRIX,
    CalibrationProvider,
    CalibrationWorkload,
)
from tests.calibration.pedagogical.r3a_plan import (
    EXPECTED_G2_ORIGINAL_REUSABLE_SLOT_IDS,
    EXPECTED_SELECTED_OUTPUT_SOURCE_SLOT_IDS,
    G2_LEDGER_RELATIVE_PATH,
    R2_ANTHROPIC_REUSED_LOGICAL_SLOT_ID,
    R2B_REVIEW_REUSED_LOGICAL_SLOT_ID,
    R3_APPROVAL_REQUIRED,
    R3_CALL_MATRIX_SHA256,
    R3_COST_SAFETY_MARGIN,
    R3_PLAN_VERSION,
    R3_PRODUCTION_REVIEW_LIMIT_ADOPTION,
    R3_PROVIDER_COST_USD,
    R3_REMAINING_CALL_MATRIX,
    R3_REUSED_EVIDENCE_MANIFEST_SHA256,
    R3AError,
    R3AErrorCode,
    R3FamilyReadiness,
    R3LedgerStatus,
    R3ProviderFamily,
    ReusedEvidenceMapping,
    ReuseMappingClass,
    audit_r3a_evidence,
    block_after_failed_terra_canary,
    build_r3_ledger_template,
    default_external_evidence_sha256,
    estimate_r3_cost,
    import_external_readiness,
    mutated_first_call_for_checksum_test,
    next_executable_call_id,
    r3_call_matrix_sha256,
    r3_plan_payload,
    r3b_approval_text,
    render_evidence_baseline_markdown,
    render_remaining_plan_markdown,
    reused_evidence_manifest_sha256,
    validate_reuse_mappings,
)

ROOT = Path(__file__).resolve().parents[2]
REQUIRES_LOCAL_EVIDENCE = pytest.mark.skipif(
    not (ROOT / G2_LEDGER_RELATIVE_PATH).exists(),
    reason="local calibration evidence is intentionally outside Git",
)


def _mapping(
    logical_slot_id: str,
    *,
    remediation_call_id: str | None = None,
) -> ReusedEvidenceMapping:
    return ReusedEvidenceMapping(
        evidence_set="SYNTHETIC",
        provider="openai",
        model="gpt-5.6-sol",
        model_profile_id="openai.gpt-5.6-sol.review",
        remediation_call_id=remediation_call_id,
        original_logical_slot_id=logical_slot_id,
        status="COMPLETED",
        input_sha256="a" * 64,
        schema_sha256="b" * 64,
        output_sha256="c" * 64,
        input_tokens=1,
        cached_input_tokens=0,
        output_tokens=1,
        reasoning_tokens=None,
        total_tokens=2,
        cost_usd="0.000001",
        mapping_class=ReuseMappingClass.EXACT_ORIGINAL_RESULT,
    )


@REQUIRES_LOCAL_EVIDENCE
def test_local_evidence_consolidates_exactly_fifteen_reusable_results() -> None:
    audit = audit_r3a_evidence(ROOT)

    assert len(audit.reused_mappings) == 15
    assert Counter(item.mapping_class for item in audit.reused_mappings) == {
        ReuseMappingClass.EXACT_ORIGINAL_RESULT: 13,
        ReuseMappingClass.EXACT_REMEDIATION_EQUIVALENT: 1,
        ReuseMappingClass.AUTHORIZED_PARAMETER_REMEDIATION: 1,
    }
    assert reused_evidence_manifest_sha256(audit) == (R3_REUSED_EVIDENCE_MANIFEST_SHA256)


def test_missing_or_hash_mismatched_proof_set_fails_closed(tmp_path: Path) -> None:
    with pytest.raises(R3AError) as missing:
        audit_r3a_evidence(tmp_path)
    assert missing.value.code is R3AErrorCode.REUSABLE_CALIBRATION_EVIDENCE_UNAVAILABLE

    ledger = tmp_path / G2_LEDGER_RELATIVE_PATH
    ledger.parent.mkdir(parents=True)
    ledger.write_text("{}", encoding="utf-8")
    with pytest.raises(R3AError) as mismatched:
        audit_r3a_evidence(tmp_path)
    assert mismatched.value.code is R3AErrorCode.REUSABLE_CALIBRATION_EVIDENCE_UNAVAILABLE


def test_duplicate_logical_slot_and_remediation_collision_are_rejected() -> None:
    known = PEDAGOGICAL_CALIBRATION_CALL_MATRIX[0].call_id
    first = _mapping(known, remediation_call_id="remediation.one")
    duplicate = replace(first, remediation_call_id="remediation.two")
    with pytest.raises(R3AError) as logical:
        validate_reuse_mappings((first, duplicate))
    assert logical.value.code is R3AErrorCode.LOGICAL_SLOT_DUPLICATE

    second = _mapping(
        PEDAGOGICAL_CALIBRATION_CALL_MATRIX[1].call_id,
        remediation_call_id="remediation.one",
    )
    with pytest.raises(R3AError) as remediation:
        validate_reuse_mappings((first, second))
    assert remediation.value.code is R3AErrorCode.REUSE_MAPPING_COLLISION


@REQUIRES_LOCAL_EVIDENCE
def test_r2b_review_is_authorized_parameter_remediation_not_exact() -> None:
    audit = audit_r3a_evidence(ROOT)
    mapping = next(
        item
        for item in audit.reused_mappings
        if item.original_logical_slot_id == R2B_REVIEW_REUSED_LOGICAL_SLOT_ID
    )

    assert mapping.mapping_class is ReuseMappingClass.AUTHORIZED_PARAMETER_REMEDIATION
    assert audit.r2b_original_logical_input_sha256 == (audit.r2b_remediation_logical_input_sha256)
    assert audit.r2b_original_schema_sha256 == audit.r2b_remediation_schema_sha256


@REQUIRES_LOCAL_EVIDENCE
def test_anthropic_r2_maps_to_one_exact_logical_slot() -> None:
    audit = audit_r3a_evidence(ROOT)
    mapping = next(
        item
        for item in audit.reused_mappings
        if item.original_logical_slot_id == R2_ANTHROPIC_REUSED_LOGICAL_SLOT_ID
    )

    assert mapping.mapping_class is ReuseMappingClass.EXACT_REMEDIATION_EQUIVALENT
    assert mapping.provider == CalibrationProvider.ANTHROPIC.value
    assert mapping.remediation_call_id == ("remediation.anthropic-scorer.scn-01.clarity.canary.r1")


@REQUIRES_LOCAL_EVIDENCE
def test_selected_output_dependencies_are_exactly_six_and_cover_twelve_scores() -> None:
    audit = audit_r3a_evidence(ROOT)

    assert (
        tuple(item.logical_slot_id for item in audit.selected_output_dependencies)
        == EXPECTED_SELECTED_OUTPUT_SOURCE_SLOT_IDS
    )
    assert all(len(item.scoring_call_ids) == 2 for item in audit.selected_output_dependencies)
    assert sum(len(item.scoring_call_ids) for item in audit.selected_output_dependencies) == 12


def test_set_subtraction_derives_96_to_15_plus_81_without_collision() -> None:
    original = {call.call_id for call in PEDAGOGICAL_CALIBRATION_CALL_MATRIX}
    reusable = {
        *EXPECTED_G2_ORIGINAL_REUSABLE_SLOT_IDS,
        R2_ANTHROPIC_REUSED_LOGICAL_SLOT_ID,
        R2B_REVIEW_REUSED_LOGICAL_SLOT_ID,
    }
    remaining = {call.logical_slot_id for call in R3_REMAINING_CALL_MATRIX}

    assert len(original) == 96
    assert len(reusable) == 15
    assert len(remaining) == 81
    assert original == reusable | remaining
    assert reusable.isdisjoint(remaining)


def test_remaining_matrix_is_six_review_and_seventy_five_anthropic() -> None:
    providers = Counter(call.provider for call in R3_REMAINING_CALL_MATRIX)
    workloads = Counter(call.workload for call in R3_REMAINING_CALL_MATRIX)

    assert providers == {
        CalibrationProvider.OPENAI: 6,
        CalibrationProvider.ANTHROPIC: 75,
    }
    assert workloads == {
        CalibrationWorkload.REVIEW: 6,
        CalibrationWorkload.SCORING: 75,
    }
    assert (
        sum(
            call.logical_slot_id.startswith("cal.score.anchor.") and call.repetition == 1
            for call in R3_REMAINING_CALL_MATRIX
        )
        == 47
    )
    assert (
        sum(
            call.logical_slot_id.startswith("cal.score.anchor.") and call.repetition == 2
            for call in R3_REMAINING_CALL_MATRIX
        )
        == 16
    )
    assert (
        sum(
            call.logical_slot_id.startswith("cal.score.output.")
            for call in R3_REMAINING_CALL_MATRIX
        )
        == 12
    )


def test_remaining_review_list_is_derived_from_original_owner() -> None:
    review_ids = tuple(
        call.logical_slot_id
        for call in R3_REMAINING_CALL_MATRIX
        if call.workload is CalibrationWorkload.REVIEW
    )

    assert review_ids == (
        "cal.review.exercise.fallback.r1",
        "cal.review.exercise.primary.r2",
        "cal.review.assessment.primary.r1",
        "cal.review.correction.primary.r1",
        "cal.review.qcm.primary.r1",
        "cal.review.qcm.fallback.r1",
    )


def test_terra_review_is_first_family_canary_and_all_reviews_use_low_4096() -> None:
    first = R3_REMAINING_CALL_MATRIX[0]
    reviews = tuple(
        call for call in R3_REMAINING_CALL_MATRIX if call.workload is CalibrationWorkload.REVIEW
    )

    assert first.logical_slot_id == "cal.review.exercise.fallback.r1"
    assert first.model == "gpt-5.6-terra"
    assert first.family is R3ProviderFamily.OPENAI_REVIEW_TERRA
    assert first.family_canary is True
    assert first.execution_role == "FAMILY_CANARY"
    assert all(call.execution_role == "MATRIX_MEMBER" for call in reviews[1:])
    assert all(call.reasoning_effort is OpenAIReasoningEffort.LOW for call in reviews)
    assert all(call.max_output_tokens == 4_096 for call in reviews)
    assert all(call.automatic_retry_count == 0 for call in reviews)
    assert R3_PRODUCTION_REVIEW_LIMIT_ADOPTION == "DEFERRED_TO_12.16-H"


def test_matrix_ids_are_new_deterministic_and_checksum_is_frozen() -> None:
    logical = [call.logical_slot_id for call in R3_REMAINING_CALL_MATRIX]
    r3_ids = [call.r3_call_id for call in R3_REMAINING_CALL_MATRIX]

    assert len(r3_ids) == len(set(r3_ids)) == 81
    assert all(r3_id == f"r3.{slot}" for r3_id, slot in zip(r3_ids, logical, strict=True))
    assert r3_call_matrix_sha256() == R3_CALL_MATRIX_SHA256
    assert r3_call_matrix_sha256(mutated_first_call_for_checksum_test()) != (R3_CALL_MATRIX_SHA256)


def test_cost_plan_uses_current_prices_and_exact_decimal_ceiling() -> None:
    cost = estimate_r3_cost()

    assert cost.call_count == 81
    assert cost.estimated_reference_usd == Decimal("0.739992")
    assert cost.maximum_before_margin_usd == Decimal("2.149984")
    assert cost.safety_margin_multiplier == R3_COST_SAFETY_MARGIN == Decimal("1.25")
    assert cost.safety_margin_amount_usd == Decimal("0.537496")
    assert cost.requested_hard_ceiling_usd == Decimal("2.687480")
    assert cost.maximum_by_model_usd == {
        "claude-sonnet-5": Decimal("1.584000"),
        "gpt-5.6-sol": Decimal("0.439680"),
        "gpt-5.6-terra": Decimal("0.126304"),
    }


def test_readiness_import_is_hash_bound_and_terra_remains_pending() -> None:
    readiness = import_external_readiness(default_external_evidence_sha256())

    assert readiness == {
        R3ProviderFamily.OPENAI_REVIEW_SOL: R3FamilyReadiness.PASSED,
        R3ProviderFamily.OPENAI_REVIEW_TERRA: R3FamilyReadiness.PENDING,
        R3ProviderFamily.ANTHROPIC_SCORER: R3FamilyReadiness.PASSED,
    }
    changed = default_external_evidence_sha256()
    changed["r2b_openai_raw"] = "0" * 64
    with pytest.raises(R3AError) as mismatch:
        import_external_readiness(changed)
    assert mismatch.value.code is R3AErrorCode.REUSABLE_CALIBRATION_EVIDENCE_UNAVAILABLE


def test_ledger_template_has_no_reused_calls_no_retry_and_pending_only() -> None:
    ledger = build_r3_ledger_template()
    calls = ledger["calls"]
    assert type(calls) is list
    typed_calls = calls
    reusable = {
        *EXPECTED_G2_ORIGINAL_REUSABLE_SLOT_IDS,
        R2_ANTHROPIC_REUSED_LOGICAL_SLOT_ID,
        R2B_REVIEW_REUSED_LOGICAL_SLOT_ID,
    }

    assert ledger["plan_version"] == R3_PLAN_VERSION
    assert ledger["matrix_sha256"] == R3_CALL_MATRIX_SHA256
    assert ledger["approved_ceiling_usd"] is None
    assert ledger["approval_required"] is R3_APPROVAL_REQUIRED is True
    assert ledger["reused_slot_count"] == 15
    assert ledger["automatic_retry_count"] == 0
    assert ledger["automatic_rerun_count"] == 0
    assert ledger["provider_calls_attempted"] == 0
    assert ledger["total_cost_usd"] == "0.000000"
    assert R3_PROVIDER_COST_USD == 0
    assert len(typed_calls) == 81
    assert all(item["status"] == R3LedgerStatus.PENDING.value for item in typed_calls)
    assert all(item["logical_slot_id"] not in reusable for item in typed_calls)


def test_resume_stops_on_started_and_never_reselects_terminal_records() -> None:
    ledger = build_r3_ledger_template()
    calls = ledger["calls"]
    assert type(calls) is list
    first_id = calls[0]["r3_call_id"]
    assert next_executable_call_id(ledger) == first_id

    calls[0]["status"] = R3LedgerStatus.STARTED.value
    with pytest.raises(R3AError) as started:
        next_executable_call_id(ledger)
    assert started.value.code is R3AErrorCode.STARTED_CALL_AMBIGUOUS

    calls[0]["status"] = R3LedgerStatus.COMPLETED.value
    assert next_executable_call_id(ledger) == calls[1]["r3_call_id"]


def test_failed_terra_canary_blocks_every_pending_call() -> None:
    ledger = build_r3_ledger_template()
    calls = ledger["calls"]
    assert type(calls) is list
    calls[0]["status"] = R3LedgerStatus.FAILED.value

    assert next_executable_call_id(ledger) is None
    blocked = block_after_failed_terra_canary(ledger)
    blocked_calls = blocked["calls"]
    assert type(blocked_calls) is list
    assert all(
        item["status"] == R3LedgerStatus.BLOCKED_BY_CANARY.value for item in blocked_calls[1:]
    )


def test_ledger_template_is_json_serializable_and_raw_free() -> None:
    rendered = json.dumps(build_r3_ledger_template(), sort_keys=True)

    assert "raw_output_text" not in rendered
    assert "OPENAI_API_KEY" not in rendered
    assert "ANTHROPIC_API_KEY" not in rendered
    assert "C:\\Users\\" not in rendered


@REQUIRES_LOCAL_EVIDENCE
def test_reports_are_deterministic_safe_and_contain_exact_approval() -> None:
    audit = audit_r3a_evidence(ROOT)
    payload_a = r3_plan_payload(audit)
    payload_b = r3_plan_payload(audit)
    baseline_a = render_evidence_baseline_markdown(audit)
    baseline_b = render_evidence_baseline_markdown(audit)
    plan_a = render_remaining_plan_markdown(audit)
    plan_b = render_remaining_plan_markdown(audit)
    rendered = json.dumps(payload_a, ensure_ascii=False, sort_keys=True)

    assert payload_a == payload_b
    assert baseline_a == baseline_b
    assert plan_a == plan_b
    assert payload_a["approval_text"] == r3b_approval_text()
    assert R3_CALL_MATRIX_SHA256 in plan_a
    assert R3_REUSED_EVIDENCE_MANIFEST_SHA256 in baseline_a
    for safe in (rendered, baseline_a, plan_a):
        assert "raw_output_text" not in safe
        assert "OPENAI_API_KEY" not in safe
        assert "ANTHROPIC_API_KEY" not in safe
        assert "C:\\Users\\" not in safe
        assert "/Users/" not in safe
