from __future__ import annotations

import hashlib
import json
from dataclasses import replace
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from typing import cast

import pytest

from backend.adapters.outbound.openai import (
    OpenAIIncompleteReason,
    OpenAIReasoningEffort,
    OpenAIResponsesResponse,
    OpenAIResponseStatus,
    OpenAIResponsesTransport,
    OpenAIResponseUsage,
    OpenAITransportError,
    OpenAITransportErrorCode,
)
from backend.infrastructure.config.secrets.provider import ProviderSecretValue
from tests.calibration.pedagogical.call_plan import (
    PEDAGOGICAL_CALIBRATION_CALL_MATRIX,
    PEDAGOGICAL_CALIBRATION_PLAN_VERSION,
    CalibrationProvider,
    CalibrationWorkload,
    call_matrix_sha256,
)
from tests.calibration.pedagogical.live_runner import (
    LiveCalibrationStop,
    LiveCalibrationStopCode,
    ProviderTransportCategory,
    ProviderWorkloadFamily,
    RealCalibrationExecutor,
    SystemicCanaryBreaker,
)
from tests.calibration.pedagogical.r2a_diagnostic import (
    R2_LEDGER_RELATIVE_PATH,
    R2_SUMMARY_RELATIVE_PATH,
    audit_anthropic_canary_reuse,
    audit_r2_local_evidence,
    classify_openai_raw_output,
)
from tests.calibration.pedagogical.remediation_plan import (
    R2_APPROVAL_REQUIRED,
    R2_CANARY_CALL_MATRIX,
    R2_CANARY_MATRIX_SHA256,
    R2_CANARY_PLAN_VERSION,
    R2_ESTIMATED_MAX_COST_USD,
    R2_LIVE_PROVIDER_CALL_COUNT,
    R2_PROVIDER_COST_USD,
    R2B_APPROVAL_REQUIRED,
    R2B_CANARY_CALL_MATRIX,
    R2B_CANARY_MATRIX_SHA256,
    R2B_CANARY_PLAN_VERSION,
    R2B_ESTIMATED_MAX_COST_BEFORE_MARGIN_USD,
    R2B_ESTIMATED_MAX_COST_USD,
    R2B_LIVE_PROVIDER_CALL_COUNT,
    R2B_PROVIDER_COST_USD,
    r2_canary_matrix_sha256,
    r2b_canary_matrix_sha256,
)
from tests.calibration.pedagogical.reuse_audit import audit_prior_openai_successes
from tests.providers.anthropic import (
    AnthropicScoringTransport,
    AnthropicTransportError,
    AnthropicTransportErrorCode,
)


def test_r2_canary_matrix_is_frozen_distinct_bounded_and_not_executed() -> None:
    assert R2_CANARY_PLAN_VERSION == "12.16-g2-r2-canary-v1"
    assert R2_APPROVAL_REQUIRED is True
    assert len(R2_CANARY_CALL_MATRIX) == 2
    assert [call.provider for call in R2_CANARY_CALL_MATRIX] == [
        CalibrationProvider.OPENAI,
        CalibrationProvider.ANTHROPIC,
    ]
    assert [call.workload for call in R2_CANARY_CALL_MATRIX] == [
        CalibrationWorkload.REVIEW,
        CalibrationWorkload.SCORING,
    ]
    assert [call.max_output_tokens for call in R2_CANARY_CALL_MATRIX] == [1_024, 512]
    assert [call.input_utf8_upper_bound_bytes for call in R2_CANARY_CALL_MATRIX] == [
        7_000,
        8_000,
    ]
    assert R2_ESTIMATED_MAX_COST_USD == Decimal("0.100200")
    assert R2_LIVE_PROVIDER_CALL_COUNT == 0
    assert R2_PROVIDER_COST_USD == 0
    assert r2_canary_matrix_sha256() == R2_CANARY_MATRIX_SHA256
    assert r2_canary_matrix_sha256() != call_matrix_sha256()


def test_r2b_matrix_is_one_call_openai_only_bounded_and_not_executed() -> None:
    assert R2B_CANARY_PLAN_VERSION == "12.16-g2-r2b-openai-review-canary-v1"
    assert R2B_APPROVAL_REQUIRED is True
    assert len(R2B_CANARY_CALL_MATRIX) == 1
    spec = R2B_CANARY_CALL_MATRIX[0]
    assert spec.call.provider is CalibrationProvider.OPENAI
    assert spec.call.workload is CalibrationWorkload.REVIEW
    assert spec.call.model == "gpt-5.6-sol"
    assert spec.reasoning_effort is OpenAIReasoningEffort.LOW
    assert spec.call.max_output_tokens == 4_096
    assert spec.automatic_retry_count == 0
    assert R2B_ESTIMATED_MAX_COST_BEFORE_MARGIN_USD == Decimal("0.109920")
    assert R2B_ESTIMATED_MAX_COST_USD == Decimal("0.137400")
    assert R2B_LIVE_PROVIDER_CALL_COUNT == 0
    assert R2B_PROVIDER_COST_USD == 0
    assert r2b_canary_matrix_sha256() == R2B_CANARY_MATRIX_SHA256
    assert R2B_CANARY_MATRIX_SHA256 == (
        "f2f4b224299a958b1a2e0d82b61b671befb222bb244efbe18342b41823ce05d3"
    )
    assert all(
        item.call.provider is not CalibrationProvider.ANTHROPIC
        for item in R2B_CANARY_CALL_MATRIX
    )


def test_canary_success_unlocks_family_and_duplicate_canary_is_forbidden() -> None:
    breaker = SystemicCanaryBreaker()
    family = ProviderWorkloadFamily.OPENAI_REVIEW
    with pytest.raises(LiveCalibrationStop) as required:
        breaker.authorize(family, is_canary=False)
    assert required.value.code is LiveCalibrationStopCode.CANARY_REQUIRED

    breaker.authorize(family, is_canary=True)
    breaker.record_canary(family, succeeded=True)
    breaker.authorize(family, is_canary=False)
    with pytest.raises(LiveCalibrationStop) as duplicate:
        breaker.authorize(family, is_canary=True)
    assert duplicate.value.code is LiveCalibrationStopCode.CANARY_ALREADY_TERMINAL


@pytest.mark.parametrize("category", tuple(ProviderTransportCategory))
def test_canary_failure_blocks_family_without_retry(
    category: ProviderTransportCategory,
) -> None:
    breaker = SystemicCanaryBreaker()
    family = ProviderWorkloadFamily.ANTHROPIC_SCORER
    breaker.authorize(family, is_canary=True)
    breaker.record_canary(family, succeeded=False, failure_category=category)
    assert breaker.failure_category(family) is category
    with pytest.raises(LiveCalibrationStop) as blocked:
        breaker.authorize(family, is_canary=False)
    assert blocked.value.code is LiveCalibrationStopCode.CANARY_BLOCKED
    with pytest.raises(LiveCalibrationStop) as retry:
        breaker.authorize(family, is_canary=True)
    assert retry.value.code is LiveCalibrationStopCode.CANARY_BLOCKED


class _OpenAIErrorTransport:
    def create(self, **_: object) -> object:
        raise OpenAITransportError(OpenAITransportErrorCode.INVALID_REQUEST)


class _OpenAIErrorFactory:
    def build(
        self,
        *,
        secret: ProviderSecretValue,
        timeout_seconds: float,
    ) -> OpenAIResponsesTransport:
        return _OpenAIErrorTransport()  # type: ignore[return-value]


class _AnthropicErrorTransport:
    def create(self, **_: object) -> object:
        raise AnthropicTransportError(AnthropicTransportErrorCode.BILLING)


class _AnthropicErrorFactory:
    def build(
        self,
        *,
        secret: ProviderSecretValue,
        timeout_seconds: float,
    ) -> AnthropicScoringTransport:
        return _AnthropicErrorTransport()  # type: ignore[return-value]


class _OpenAIIncompleteTransport:
    def create(self, **_: object) -> OpenAIResponsesResponse:
        return OpenAIResponsesResponse(
            status=OpenAIResponseStatus.INCOMPLETE,
            output_text=None,
            usage=OpenAIResponseUsage(
                input_tokens=870,
                cached_input_tokens=0,
                output_tokens=1_024,
                total_tokens=1_894,
                reasoning_tokens=800,
            ),
            incomplete_reason=OpenAIIncompleteReason.MAX_OUTPUT_TOKENS,
        )


class _OpenAIIncompleteFactory:
    def build(
        self,
        *,
        secret: ProviderSecretValue,
        timeout_seconds: float,
    ) -> OpenAIResponsesTransport:
        return _OpenAIIncompleteTransport()  # type: ignore[return-value]


def test_runner_preserves_closed_transport_category_without_raw_data(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "tests.calibration.pedagogical.live_runner.OpenAISDKResponsesTransportFactory",
        _OpenAIErrorFactory,
    )
    monkeypatch.setattr(
        "tests.calibration.pedagogical.live_runner.AnthropicSDKScoringTransportFactory",
        _AnthropicErrorFactory,
    )
    executor = RealCalibrationExecutor(
        {
            "OPENAI_API_KEY": "synthetic-openai",
            "ANTHROPIC_API_KEY": "synthetic-anthropic",
        }
    )
    review_call = next(
        call
        for call in PEDAGOGICAL_CALIBRATION_CALL_MATRIX
        if call.workload is CalibrationWorkload.REVIEW
    )
    score_call = next(
        call
        for call in PEDAGOGICAL_CALIBRATION_CALL_MATRIX
        if call.provider is CalibrationProvider.ANTHROPIC
    )
    review = executor.execute(review_call, dependency_candidate=None)
    scoring = executor.execute(
        replace(score_call, max_output_tokens=2_048),
        dependency_candidate=None,
    )
    assert review.closed_error_code == "OPENAI_REVIEW_TRANSPORT_INVALID_REQUEST"
    assert scoring.closed_error_code == "ANTHROPIC_SCORER_TRANSPORT_BILLING"
    assert review.raw_output_text is None
    assert scoring.raw_output_text is None
    assert "synthetic" not in repr((review, scoring))


def test_runner_preserves_public_and_private_incomplete_diagnostics(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "tests.calibration.pedagogical.live_runner.OpenAISDKResponsesTransportFactory",
        _OpenAIIncompleteFactory,
    )
    executor = RealCalibrationExecutor(
        {"OPENAI_API_KEY": "synthetic-openai"},
        review_reasoning_effort=OpenAIReasoningEffort.LOW,
    )
    review_call = next(
        call
        for call in PEDAGOGICAL_CALIBRATION_CALL_MATRIX
        if call.workload is CalibrationWorkload.REVIEW
    )

    result = executor.execute(review_call, dependency_candidate=None)

    assert result.closed_error_code == "OPENAI_REVIEW_INVALID_RESPONSE"
    assert result.provider_response_status == "incomplete"
    assert result.incomplete_reason == "max_output_tokens"
    assert result.reasoning_tokens == 800
    assert result.public_error_code == "INVALID_RESPONSE"
    assert (
        result.private_diagnostic_code
        == "OPENAI_REVIEW_INCOMPLETE_MAX_OUTPUT_TOKENS"
    )
    assert result.raw_output_text is None


def test_prior_output_audit_is_hash_only_read_only_and_retention_bounded(
    tmp_path: Path,
) -> None:
    call = next(
        item
        for item in PEDAGOGICAL_CALIBRATION_CALL_MATRIX
        if item.call_id == "cal.generation.course.primary.r1"
    )
    payload = json.dumps(
        {
            "outcome": "OUTPUT",
            "sections": [{"code": "lesson", "text": "synthetic"}],
            "warnings": [],
            "uncertainties": [],
        },
        separators=(",", ":"),
    ).encode()
    digest = hashlib.sha256(payload).hexdigest()
    relative = f"artifacts/calibration/12.16-g2/raw/{call.call_id}.{digest}.json"
    raw_path = tmp_path / relative
    raw_path.parent.mkdir(parents=True)
    raw_path.write_bytes(payload)
    ledger_path = tmp_path / "artifacts/calibration/12.16-g2/ledger.json"
    ledger = {
        "plan_version": PEDAGOGICAL_CALIBRATION_PLAN_VERSION,
        "calls": [
            {
                "call_id": call.call_id,
                "provider": "openai",
                "status": "COMPLETED",
                "raw_output_path": relative,
                "raw_output_sha256": digest,
                "completed_at": "2026-08-29T13:42:20+00:00",
            }
        ],
    }
    ledger_bytes = json.dumps(ledger, sort_keys=True).encode()
    ledger_path.write_bytes(ledger_bytes)

    audit = audit_prior_openai_successes(
        tmp_path,
        now=datetime(2026, 8, 29, 14, 0, tzinfo=UTC),
    )
    assert audit.success_count == 1
    assert audit.raw_hash_valid_count == 1
    assert audit.schema_parsable_count == 1
    assert audit.linked_call_count == 1
    assert audit.within_retention_count == 1
    assert audit.reusable is True
    assert ledger_path.read_bytes() == ledger_bytes

    raw_path.write_bytes(b"{}")
    invalid = audit_prior_openai_successes(
        tmp_path,
        now=datetime(2026, 8, 29, 14, 0, tzinfo=UTC),
    )
    assert invalid.raw_hash_valid_count == 0
    assert invalid.reusable is False


def test_r2_artifact_audit_is_terminal_hash_only_and_raw_free(
    tmp_path: Path,
) -> None:
    raw_payload = (
        b'{"score_denominator":1,"score_numerator":1,"status":"SCORED"}'
    )
    raw_sha = hashlib.sha256(raw_payload).hexdigest()
    raw_relative = (
        "artifacts/calibration/12.16-g2-r2/raw/"
        f"remediation.anthropic-scorer.scn-01.clarity.canary.r1.{raw_sha}.json"
    )
    raw_path = tmp_path / raw_relative
    raw_path.parent.mkdir(parents=True)
    raw_path.write_bytes(raw_payload)
    ledger = {
        "plan_version": R2_CANARY_PLAN_VERSION,
        "matrix_sha256": R2_CANARY_MATRIX_SHA256,
        "approved_ceiling_usd": "0.100200",
        "provider_calls_attempted": 2,
        "automatic_retry_count": 0,
        "automatic_rerun_count": 0,
        "total_cost_usd": "0.027598",
        "calls": [
            {
                "call_id": "remediation.openai-review.scn-05.canary.r1",
                "provider": "openai",
                "model": "gpt-5.6-sol",
                "status": "FAILED",
                "response_status": "ERROR",
                "input_tokens": 870,
                "cached_input_tokens": 0,
                "output_tokens": 1_024,
                "total_tokens": 1_894,
                "cost_usd": "0.023960",
                "closed_error_code": "OPENAI_REVIEW_INVALID_RESPONSE",
                "failure_category": "UNAVAILABLE",
                "raw_output_path": None,
                "raw_output_sha256": None,
            },
            {
                "call_id": (
                    "remediation.anthropic-scorer.scn-01.clarity.canary.r1"
                ),
                "provider": "anthropic",
                "model": "claude-sonnet-5",
                "status": "PASSED",
                "response_status": "STRUCTURED",
                "input_tokens": 979,
                "cached_input_tokens": 0,
                "output_tokens": 168,
                "total_tokens": 1_147,
                "cost_usd": "0.003638",
                "closed_error_code": None,
                "failure_category": None,
                "raw_output_path": raw_relative,
                "raw_output_sha256": raw_sha,
            },
        ],
    }
    ledger_bytes = (json.dumps(ledger, sort_keys=True) + "\n").encode()
    ledger_path = tmp_path / R2_LEDGER_RELATIVE_PATH
    ledger_path.parent.mkdir(parents=True, exist_ok=True)
    ledger_path.write_bytes(ledger_bytes)
    summary = {
        "provider_calls_attempted": 2,
        "automatic_retry_count": 0,
        "automatic_rerun_count": 0,
        "total_cost_usd": "0.027598",
        "ledger_sha256": hashlib.sha256(ledger_bytes).hexdigest(),
    }
    summary_path = tmp_path / R2_SUMMARY_RELATIVE_PATH
    summary_path.write_text(json.dumps(summary), encoding="utf-8")

    audit = audit_r2_local_evidence(tmp_path)
    classification = classify_openai_raw_output(tmp_path, audit["calls"][0])
    rendered = json.dumps(audit, sort_keys=True)

    assert audit["terminal_call_count"] == 2
    assert audit["pending_call_count"] == 0
    assert audit["started_call_count"] == 0
    assert audit["duplicate_call_count"] == 0
    assert classification["classification"] == "NO_OUTPUT_TEXT"
    assert classification["json_parse_status"] == "NOT_APPLICABLE"
    assert raw_payload.decode() not in rendered
    assert str(tmp_path) not in rendered


def test_anthropic_canary_is_byte_identical_to_logical_g2_score() -> None:
    audit = audit_anthropic_canary_reuse()

    assert audit["anthropic_canary_reusable_as_g2_score"] is True
    assert audit["anthropic_family_readiness"] == "PASSED"
    assert all(cast(bool, value) for value in audit["comparisons"].values())
    assert audit["logical_observation_sha256"] == audit[
        "canary_observation_sha256"
    ]
