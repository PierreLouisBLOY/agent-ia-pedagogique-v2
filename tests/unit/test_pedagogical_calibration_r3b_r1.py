from __future__ import annotations

import hashlib
import json
from decimal import Decimal
from pathlib import Path

import pytest

from backend.infrastructure.config.secrets.provider import (
    EnvironmentProviderSecretResolver,
)
from tests.calibration.pedagogical.r3b_r1_diagnostic import (
    ANTHROPIC_INPUT_TOKEN_UPPER_BOUND,
    ANTHROPIC_MAX_OUTPUT_TOKENS,
    FAILED_R3_CALL_ID,
    R2_AUTOMATIC_RETRY_COUNT,
    R2_BASE_COST_USD,
    R2_HARD_CEILING_USD,
    R2_LEDGER_RELATIVE_PATH,
    R2_PLAN_VERSION,
    R2_PROVIDER_CALL_COUNT,
    R2_REMEDIATION_CALL_ID,
    R2_SAFETY_MARGIN_USD,
    R3_LEDGER_RELATIVE_PATH,
    R3_LEDGER_SHA256,
    R3_SUMMARY_RELATIVE_PATH,
    R3_SUMMARY_SHA256,
    AnthropicFailureClassification,
    R2LedgerStatus,
    R3BR1Error,
    R3BR1ErrorCode,
    audit_r3b_failure,
    build_r2_ledger_template,
    classify_anthropic_failure,
    mutated_remediation_call_for_checksum_test,
    next_r2_call_id,
    r2_approval_text,
    r2_plan_payload,
    reconstruct_failed_request_identity,
    remediation_matrix_sha256,
    render_cost_plan_json,
    render_cost_plan_markdown,
    render_diagnostic_markdown,
)
from tests.providers.anthropic.transport import AnthropicSDKScoringTransportFactory

ROOT = Path(__file__).resolve().parents[2]
REQUIRES_R3B_EVIDENCE = pytest.mark.skipif(
    not (ROOT / R3_LEDGER_RELATIVE_PATH).exists(),
    reason="local R3B evidence is intentionally outside Git",
)
EXPECTED_R2_MATRIX_SHA256 = "60ffe8fd1d99cf60c53d3ea0644624fe09f820d6a59552e7cd2fec3597c334a4"


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


@REQUIRES_R3B_EVIDENCE
def test_frozen_r3b_evidence_and_failed_record_are_audited_without_raw_text() -> None:
    before = (
        _sha256(ROOT / R3_LEDGER_RELATIVE_PATH),
        _sha256(ROOT / R3_SUMMARY_RELATIVE_PATH),
    )

    audit = audit_r3b_failure(ROOT)

    assert before == (R3_LEDGER_SHA256, R3_SUMMARY_SHA256)
    assert before == (
        _sha256(ROOT / R3_LEDGER_RELATIVE_PATH),
        _sha256(ROOT / R3_SUMMARY_RELATIVE_PATH),
    )
    evidence = audit["evidence"]
    assert type(evidence) is dict
    assert evidence["raw_file_count"] == 9
    assert evidence["state_counts"] == {
        "COMPLETED": 9,
        "FAILED": 1,
        "PENDING": 71,
        "STARTED": 0,
    }
    assert evidence["provider_calls_attempted"] == 10
    assert evidence["duplicate_call_count"] == 0
    failed = audit["failed_record"]
    assert type(failed) is dict
    assert failed["r3_call_id"] == FAILED_R3_CALL_ID
    assert failed["closed_error_code"] == "ANTHROPIC_SCORER_TRANSPORT_UNAVAILABLE"
    assert failed["systemic_failure_category"] == "UNAVAILABLE"
    assert failed["classification"] == "UNKNOWN_WITH_INSUFFICIENT_EVIDENCE"
    assert failed["raw_output_present"] is False
    assert failed["reserved_cost_usd"] == "0.021120"
    assert audit["r1_provider_calls"] == 0
    assert audit["r1_provider_cost_usd"] == "0.000000"


def test_failed_request_reconstruction_is_exact_bounded_and_transformable() -> None:
    identity = reconstruct_failed_request_identity()

    assert identity == {
        "input_ref": "anchor:cal.scn-01.c",
        "criterion_ref": "scn-01.quality.clarity",
        "model": "claude-sonnet-5",
        "model_profile_id": "anthropic.claude-sonnet-5.scorer",
        "max_output_tokens": ANTHROPIC_MAX_OUTPUT_TOKENS,
        "observation_sha256": "ca1906fafb88814565125c344f31e051fd154d4bd17ca267517d991f70dabd79",
        "serialized_input_sha256": "b6cc367de3229a83ac3af9cdf717db21b00aad6a9dc23b490dd2fb35343b914f",
        "system_sha256": "fcbefdcfa849619f27637c581475b2d2bbfd45063e7e4f476bee802bf3eb69ea",
        "logical_schema_sha256": "968312b8f7f4059cfb47b4c70bff98ec14f61089b2b72fa78821368d62bc4dc1",
        "provider_schema_sha256": "607a6736853b8ab5ab3e95926a51ebef12191ffa8b2f43b5ef9826fca19d54f7",
        "serialized_input_bytes": 971,
        "input_utf8_upper_bound_bytes": ANTHROPIC_INPUT_TOKEN_UPPER_BOUND,
        "bounded": True,
        "logical_schema_valid": True,
        "provider_schema_transformable": True,
    }


@REQUIRES_R3B_EVIDENCE
def test_three_successes_are_distinct_calls_with_identical_rational_score_bytes() -> None:
    audit = audit_r3b_failure(ROOT)
    comparison = audit["comparison_conclusion"]
    assert type(comparison) is dict

    assert comparison == {
        "distinct_serialized_input_count": 4,
        "distinct_observation_count": 4,
        "distinct_success_logical_slot_count": 3,
        "distinct_logical_schema_count": 1,
        "distinct_provider_schema_count": 1,
        "distinct_raw_output_sha256_count": 1,
        "provider_call_count": 3,
        "identical_score_bytes_is_duplicate_provider_call": False,
    }
    successes = audit["successful_comparisons"]
    assert type(successes) is list
    assert {item["score"] for item in successes} == {"1/1"}
    assert {item["provider_call_count"] for item in successes} == {1}


@pytest.mark.parametrize(
    ("kwargs", "expected"),
    (
        (
            {
                "transport_code": "EMPTY_RESPONSE",
                "http_status": None,
                "provider_error_type": "EMPTY_RESPONSE",
                "response_received": True,
                "text_block_count": 0,
            },
            AnthropicFailureClassification.EMPTY_TEXT_RESPONSE,
        ),
        (
            {
                "transport_code": "UNAVAILABLE",
                "http_status": None,
                "provider_error_type": "UNMAPPED_SDK_ERROR",
                "response_received": False,
                "text_block_count": None,
            },
            AnthropicFailureClassification.UNMAPPED_ANTHROPIC_EXCEPTION,
        ),
        (
            {
                "transport_code": "CONFLICT",
                "http_status": 409,
                "provider_error_type": "API_STATUS_ERROR",
                "response_received": True,
                "text_block_count": None,
            },
            AnthropicFailureClassification.HTTP_CONFLICT,
        ),
        (
            {
                "transport_code": "REQUEST_TOO_LARGE",
                "http_status": 413,
                "provider_error_type": "API_STATUS_ERROR",
                "response_received": True,
                "text_block_count": None,
            },
            AnthropicFailureClassification.REQUEST_TOO_LARGE,
        ),
        (
            {
                "transport_code": "OVERLOADED",
                "http_status": 529,
                "provider_error_type": "OVERLOADED_ERROR",
                "response_received": True,
                "text_block_count": None,
            },
            AnthropicFailureClassification.OVERLOADED,
        ),
        (
            {
                "transport_code": None,
                "http_status": None,
                "provider_error_type": None,
                "response_received": None,
                "text_block_count": None,
            },
            AnthropicFailureClassification.UNKNOWN_WITH_INSUFFICIENT_EVIDENCE,
        ),
    ),
)
def test_failure_classification_never_invents_missing_provider_evidence(
    kwargs: dict[str, object],
    expected: AnthropicFailureClassification,
) -> None:
    assert classify_anthropic_failure(**kwargs) is expected  # type: ignore[arg-type]


@REQUIRES_R3B_EVIDENCE
def test_one_call_plan_checksum_cost_and_approval_are_frozen() -> None:
    plan = r2_plan_payload(ROOT)

    assert plan["plan_version"] == R2_PLAN_VERSION
    assert plan["matrix_sha256"] == EXPECTED_R2_MATRIX_SHA256
    assert remediation_matrix_sha256() == EXPECTED_R2_MATRIX_SHA256
    assert remediation_matrix_sha256((mutated_remediation_call_for_checksum_test(),)) != (
        EXPECTED_R2_MATRIX_SHA256
    )
    assert len(plan["calls"]) == R2_PROVIDER_CALL_COUNT == 1  # type: ignore[arg-type]
    assert R2_AUTOMATIC_RETRY_COUNT == 0
    assert R2_BASE_COST_USD == Decimal("0.021120")
    assert R2_SAFETY_MARGIN_USD == Decimal("0.005280")
    assert R2_HARD_CEILING_USD == Decimal("0.026400")
    assert plan["approval_text"] == r2_approval_text(EXPECTED_R2_MATRIX_SHA256)


def test_remediation_ledger_is_one_call_fail_closed_and_never_retries() -> None:
    ledger = build_r2_ledger_template()
    assert ledger["plan_version"] == R2_PLAN_VERSION
    assert ledger["matrix_sha256"] == EXPECTED_R2_MATRIX_SHA256
    assert ledger["automatic_retry_count"] == 0
    assert ledger["provider_calls_attempted"] == 0
    assert ledger["total_cost_usd"] == "0.000000"
    assert next_r2_call_id(ledger) == R2_REMEDIATION_CALL_ID

    call = ledger["calls"][0]  # type: ignore[index]
    call["status"] = R2LedgerStatus.STARTED.value
    with pytest.raises(R3BR1Error) as started:
        next_r2_call_id(ledger)
    assert started.value.code is R3BR1ErrorCode.STARTED_CALL_AMBIGUOUS

    for status in (R2LedgerStatus.COMPLETED, R2LedgerStatus.FAILED):
        terminal = build_r2_ledger_template()
        terminal["calls"][0]["status"] = status.value  # type: ignore[index]
        assert next_r2_call_id(terminal) is None

    rendered = json.dumps(build_r2_ledger_template(), sort_keys=True)
    assert R2_LEDGER_RELATIVE_PATH.startswith("artifacts/calibration/")
    assert "raw_output_text" not in rendered
    assert "ANTHROPIC_API_KEY" not in rendered
    assert "C:\\Users\\" not in rendered


@REQUIRES_R3B_EVIDENCE
def test_r1_report_generation_never_resolves_credentials_or_builds_transport(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        EnvironmentProviderSecretResolver,
        "resolve",
        lambda *_: pytest.fail("R1 must not resolve credentials"),
    )
    monkeypatch.setattr(
        AnthropicSDKScoringTransportFactory,
        "build",
        lambda *_args, **_kwargs: pytest.fail("R1 must not build provider transport"),
    )

    rendered = "\n".join(
        (
            render_diagnostic_markdown(ROOT),
            render_cost_plan_markdown(ROOT),
            render_cost_plan_json(ROOT),
        )
    )

    for forbidden in (
        "raw_output_text",
        "ANTHROPIC_API_KEY",
        "OPENAI_API_KEY",
        "C:\\Users\\",
        "/Users/",
        "request-id",
        "authorization",
    ):
        assert forbidden.casefold() not in rendered.casefold()
    assert EXPECTED_R2_MATRIX_SHA256 in rendered
    assert "UNKNOWN_WITH_INSUFFICIENT_EVIDENCE" in rendered

    diagnostic_path = (
        ROOT / "docs/development/PHASE_12_16_G2_R3B_R1_ANTHROPIC_FAILURE_DIAGNOSTIC.md"
    )
    cost_markdown_path = (
        ROOT / "docs/development/PHASE_12_16_G2_R3B_R1_ANTHROPIC_CANARY_COST_PLAN.md"
    )
    cost_json_path = ROOT / "docs/development/PHASE_12_16_G2_R3B_R1_ANTHROPIC_CANARY_COST_PLAN.json"
    assert diagnostic_path.read_text(encoding="utf-8").rstrip("\n") == (
        render_diagnostic_markdown(ROOT).rstrip("\n")
    )
    assert cost_markdown_path.read_text(encoding="utf-8").rstrip("\n") == (
        render_cost_plan_markdown(ROOT).rstrip("\n")
    )
    assert cost_json_path.read_text(encoding="utf-8") == render_cost_plan_json(ROOT)

    local_ledger = json.loads((ROOT / R2_LEDGER_RELATIVE_PATH).read_text(encoding="utf-8"))
    if local_ledger != build_r2_ledger_template():
        assert local_ledger["plan_version"] == R2_PLAN_VERSION
        assert local_ledger["matrix_sha256"] == EXPECTED_R2_MATRIX_SHA256
        assert local_ledger["automatic_retry_count"] == 0
        assert local_ledger["automatic_rerun_count"] == 0
        assert local_ledger["provider_calls_attempted"] == 1
        assert local_ledger["calls"][0]["call_id"] == R2_REMEDIATION_CALL_ID
        assert local_ledger["calls"][0]["status"] in {
            R2LedgerStatus.COMPLETED.value,
            R2LedgerStatus.FAILED.value,
        }
        assert next_r2_call_id(local_ledger) is None
