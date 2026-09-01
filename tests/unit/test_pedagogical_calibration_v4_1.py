from __future__ import annotations

import json
from collections import defaultdict
from dataclasses import replace
from decimal import Decimal
from pathlib import Path

import pytest

from backend.adapters.outbound.openai import (
    OpenAIIncompleteReason,
    OpenAIResponsesResponse,
    OpenAIResponseStatus,
    OpenAIResponseUsage,
)
from backend.infrastructure.config.secrets.provider import (
    EnvironmentProviderSecretResolver,
)
from tests.calibration.pedagogical.anchor_corpus_v4 import V4_CALIBRATION_ANCHORS
from tests.calibration.pedagogical.call_plan_v4_1 import (
    ANTHROPIC_CALL_COUNT,
    ANTHROPIC_SCORER_REQUIRED_OUTPUT_TOKENS,
    OPENAI_CALL_COUNT,
    OPENAI_REVIEW_MAX_OUTPUT_TOKENS,
    PEDAGOGICAL_CALIBRATION_CALL_MATRIX,
    PEDAGOGICAL_CALIBRATION_PLAN_VERSION,
    CalibrationCallSpec,
    CalibrationMatrixContractError,
    CalibrationMatrixContractErrorCode,
    CalibrationProvider,
    CalibrationRole,
    CalibrationWorkload,
    call_matrix_sha256,
    estimate_call_plan_cost,
    validate_call_matrix_contracts,
)
from tests.calibration.pedagogical.catalog import scenario_by_code
from tests.calibration.pedagogical.live_runner_v4_1 import (
    APPROVED_HARD_CEILING_USD,
    APPROVED_MATRIX_SHA256,
    APPROVED_MAX_CALL_COUNT,
    APPROVED_PRICING_SHA256,
    BASELINE_LIVE_AUTHORIZATION_DEFAULT,
    CANARY_CALL_IDS,
    EXPECTED_MATRIX_SHA256,
    LEDGER_RELATIVE_PATH,
    OWNER_APPROVED_MANIFEST_SHA256,
    OWNER_CONFIGURATION_APPROVAL,
    PROPOSED_TECHNICAL_CEILING_USD,
    AtomicCalibrationLedger,
    LedgerCallStatus,
    LiveCalibrationRunner,
    LiveCalibrationStop,
    LiveCalibrationStopCode,
    ProviderCallResult,
    ProviderWorkloadFamily,
    RawOutputStore,
    ReviewOutputDiagnosticCategory,
    RuntimeAuthorizationProvenance,
    StructuredOutputValidationStatus,
    _model_profile,
    _openai_result,
    _provider_profile,
    _review_request,
    build_safe_aggregate,
    render_safe_reports,
    run_live_calibration,
)
from tests.calibration.pedagogical.metrics import CalibrationResponseStatus
from tests.calibration.pedagogical.pricing import (
    EXPECTED_PRICING_SNAPSHOT_SHA256,
    pricing_snapshot_sha256,
)
from tests.providers.anthropic import AnthropicEvaluationScorer


class _FakeExecutor:
    def __init__(self, *failed_call_ids: str) -> None:
        self.failed_call_ids = set(failed_call_ids)
        self.calls: list[str] = []

    def execute(
        self,
        call: CalibrationCallSpec,
        *,
        dependency_candidate: str | None,
    ) -> ProviderCallResult:
        self.calls.append(call.call_id)
        if call.call_id in self.failed_call_ids:
            return ProviderCallResult(
                CalibrationResponseStatus.ERROR,
                None,
                None,
                None,
                None,
                None,
                1,
                "FAKE_CONFIGURATION_FAILURE",
            )
        if call.provider is CalibrationProvider.OPENAI:
            scenario = scenario_by_code(call.scenario_code)
            raw = json.dumps(
                {
                    "outcome": "OUTPUT",
                    "sections": [
                        {"code": code, "text": f"synthetic-{code}"}
                        for code in scenario.required_sections
                    ],
                    "warnings": [],
                    "uncertainties": [],
                },
                separators=(",", ":"),
                sort_keys=True,
            )
            return ProviderCallResult(
                CalibrationResponseStatus.STRUCTURED,
                raw,
                100,
                0,
                25,
                125,
                1,
                structured_output_validation=(
                    StructuredOutputValidationStatus.PASSED
                    if call.workload is CalibrationWorkload.REVIEW
                    else None
                ),
            )
        if call.input_refs[0].startswith("output:"):
            assert dependency_candidate is not None
        raw = json.dumps(
            {
                "status": "SCORED",
                "score_numerator": 4,
                "score_denominator": 5,
            },
            separators=(",", ":"),
            sort_keys=True,
        )
        return ProviderCallResult(
            CalibrationResponseStatus.STRUCTURED,
            raw,
            80,
            0,
            12,
            92,
            1,
        )


def _authorization(*, effective: bool) -> RuntimeAuthorizationProvenance:
    if not effective:
        return RuntimeAuthorizationProvenance()
    return RuntimeAuthorizationProvenance(
        effective=True,
        authorized_baseline_commit_sha="a" * 40,
        authorized_matrix_sha256=EXPECTED_MATRIX_SHA256,
        authorized_pricing_sha256=EXPECTED_PRICING_SNAPSHOT_SHA256,
        authorized_max_call_count=102,
        authorized_hard_ceiling_usd=PROPOSED_TECHNICAL_CEILING_USD,
        attestation_source="offline-test-attestation",
    )


def _runner(
    root: Path,
    executor: _FakeExecutor,
    *,
    authorization: RuntimeAuthorizationProvenance | None = None,
) -> LiveCalibrationRunner:
    return LiveCalibrationRunner(
        root=root,
        environment={},
        executor=executor,
        baseline_validator=lambda _: None,
        approved_ceiling_usd=PROPOSED_TECHNICAL_CEILING_USD,
        runtime_authorization=authorization or _authorization(effective=False),
        gates_prevalidated=True,
    )


def test_v4_1_matrix_contracts_counts_corpus_and_budget_are_exact() -> None:
    calls = PEDAGOGICAL_CALIBRATION_CALL_MATRIX
    assert PEDAGOGICAL_CALIBRATION_PLAN_VERSION == "12.16-g2-v4.1-plan-v1"
    assert len(calls) == 102
    assert (OPENAI_CALL_COUNT, ANTHROPIC_CALL_COUNT) == (20, 82)
    assert call_matrix_sha256() == EXPECTED_MATRIX_SHA256
    assert pricing_snapshot_sha256() == EXPECTED_PRICING_SNAPSHOT_SHA256
    assert estimate_call_plan_cost().estimated_maximum_with_margin_usd == Decimal(
        "4.984760"
    )
    assert PROPOSED_TECHNICAL_CEILING_USD == Decimal("4.984760")
    assert APPROVED_HARD_CEILING_USD == Decimal("4.984760")
    assert APPROVED_MATRIX_SHA256 == EXPECTED_MATRIX_SHA256
    assert APPROVED_PRICING_SHA256 == EXPECTED_PRICING_SNAPSHOT_SHA256
    assert APPROVED_MAX_CALL_COUNT == 102
    assert OWNER_APPROVED_MANIFEST_SHA256 == (
        "79a2a967dca8fdc575e5efcc1138f44d7bfe00e5ac3e4ecf5bbc7478dba3a81d"
    )
    assert OWNER_CONFIGURATION_APPROVAL == "APPROVED"
    assert BASELINE_LIVE_AUTHORIZATION_DEFAULT is False
    anthropic = tuple(
        call for call in calls if call.provider is CalibrationProvider.ANTHROPIC
    )
    reviews = tuple(
        call for call in calls if call.workload is CalibrationWorkload.REVIEW
    )
    assert {call.max_output_tokens for call in anthropic} == {
        ANTHROPIC_SCORER_REQUIRED_OUTPUT_TOKENS
    }
    assert {call.max_output_tokens for call in reviews} == {
        OPENAI_REVIEW_MAX_OUTPUT_TOKENS
    }
    anchor_ids = {
        call.input_refs[0].removeprefix("anchor:")
        for call in calls
        if call.input_refs[0].startswith("anchor:")
    }
    assert anchor_ids == {anchor.anchor_id for anchor in V4_CALIBRATION_ANCHORS}
    assert len(anchor_ids) == 24
    assert not any(
        "12.16-g2-v4-plan-v1" in ref
        for call in calls
        for ref in call.input_refs
    )
    sources = {call.call_id: call for call in calls}
    pairwise: defaultdict[tuple[str, str], set[CalibrationRole]] = defaultdict(set)
    for call in calls:
        if call.input_refs[0].startswith("output:"):
            source = sources[call.input_refs[0].removeprefix("output:")]
            pairwise[(call.scenario_code, call.criterion_refs[0])].add(source.role)
    assert sum(
        {CalibrationRole.PRIMARY, CalibrationRole.FALLBACK}.issubset(roles)
        for roles in pairwise.values()
    ) == 6


@pytest.mark.parametrize(
    ("call", "expected"),
    (
        (
            replace(
                next(
                    call
                    for call in PEDAGOGICAL_CALIBRATION_CALL_MATRIX
                    if call.provider is CalibrationProvider.ANTHROPIC
                ),
                max_output_tokens=512,
            ),
            CalibrationMatrixContractErrorCode.ANTHROPIC_SCORER_OUTPUT_BUDGET_TOO_LOW,
        ),
        (
            replace(
                next(
                    call
                    for call in PEDAGOGICAL_CALIBRATION_CALL_MATRIX
                    if call.workload is CalibrationWorkload.REVIEW
                ),
                max_output_tokens=1_024,
            ),
            CalibrationMatrixContractErrorCode.OPENAI_REVIEW_OUTPUT_BUDGET_TOO_LOW,
        ),
    ),
)
def test_matrix_contracts_fail_before_any_executor(
    call: CalibrationCallSpec,
    expected: CalibrationMatrixContractErrorCode,
) -> None:
    with pytest.raises(CalibrationMatrixContractError) as raised:
        validate_call_matrix_contracts((call,))
    assert raised.value.code is expected


def test_anthropic_scorer_configuration_accepts_corrective_matrix_without_transport() -> None:
    call = next(
        call
        for call in PEDAGOGICAL_CALIBRATION_CALL_MATRIX
        if call.provider is CalibrationProvider.ANTHROPIC
    )

    class _NoTransportFactory:
        constructions = 0

        def build(self, *, secret: object, timeout_seconds: float) -> object:
            self.constructions += 1
            raise AssertionError((secret, timeout_seconds))

    factory = _NoTransportFactory()
    scorer = AnthropicEvaluationScorer(
        provider_profile=_provider_profile(CalibrationProvider.ANTHROPIC),
        model_profile=_model_profile(call),
        secret_resolver=EnvironmentProviderSecretResolver({}),
        transport_factory=factory,  # type: ignore[arg-type]
    )
    assert "claude-sonnet-5" in repr(scorer)
    assert factory.constructions == 0


def test_review_request_uses_canonical_corrective_output_budget() -> None:
    call = next(
        call
        for call in PEDAGOGICAL_CALIBRATION_CALL_MATRIX
        if call.workload is CalibrationWorkload.REVIEW
    )
    request = _review_request(call)
    assert request.review_budget.max_tokens == OPENAI_REVIEW_MAX_OUTPUT_TOKENS


def _response(
    *,
    status: OpenAIResponseStatus,
    output_tokens: int,
    incomplete_reason: OpenAIIncompleteReason = OpenAIIncompleteReason.NONE,
) -> OpenAIResponsesResponse:
    return OpenAIResponsesResponse(
        status=status,
        output_text="{}",
        usage=OpenAIResponseUsage(
            input_tokens=100,
            cached_input_tokens=0,
            output_tokens=output_tokens,
            total_tokens=100 + output_tokens,
        ),
        incomplete_reason=incomplete_reason,
    )


def test_review_complete_valid_response_is_marked_structurally_valid() -> None:
    result = _openai_result(
        _response(status=OpenAIResponseStatus.COMPLETED, output_tokens=300),
        CalibrationResponseStatus.STRUCTURED,
        1,
        None,
        None,
        None,
        is_review=True,
        max_output_tokens=OPENAI_REVIEW_MAX_OUTPUT_TOKENS,
    )
    assert result.parse_error_category is None
    assert (
        result.structured_output_validation
        is StructuredOutputValidationStatus.PASSED
    )


@pytest.mark.parametrize(
    (
        "response",
        "private_diagnostic_code",
        "expected",
    ),
    (
        (
            _response(
                status=OpenAIResponseStatus.COMPLETED,
                output_tokens=OPENAI_REVIEW_MAX_OUTPUT_TOKENS,
            ),
            "OPENAI_REVIEW_CONTRACT_MISMATCH",
            ReviewOutputDiagnosticCategory.OUTPUT_TRUNCATION_SUSPECTED,
        ),
        (
            _response(
                status=OpenAIResponseStatus.INCOMPLETE,
                output_tokens=OPENAI_REVIEW_MAX_OUTPUT_TOKENS,
                incomplete_reason=OpenAIIncompleteReason.MAX_OUTPUT_TOKENS,
            ),
            "OPENAI_REVIEW_INCOMPLETE_MAX_OUTPUT_TOKENS",
            ReviewOutputDiagnosticCategory.OUTPUT_TRUNCATED_CONFIRMED,
        ),
        (
            _response(status=OpenAIResponseStatus.COMPLETED, output_tokens=120),
            "OPENAI_REVIEW_CONTRACT_MISMATCH",
            ReviewOutputDiagnosticCategory.STRUCTURED_OUTPUT_INVALID_OTHER,
        ),
    ),
)
def test_review_invalid_response_classification_is_evidence_bounded(
    response: OpenAIResponsesResponse,
    private_diagnostic_code: str,
    expected: ReviewOutputDiagnosticCategory,
) -> None:
    result = _openai_result(
        response,
        CalibrationResponseStatus.ERROR,
        1,
        "OPENAI_REVIEW_INVALID_RESPONSE",
        "INVALID_RESPONSE",
        private_diagnostic_code,
        is_review=True,
        max_output_tokens=OPENAI_REVIEW_MAX_OUTPUT_TOKENS,
    )
    assert result.parse_error_category is expected
    assert (
        result.structured_output_validation
        is StructuredOutputValidationStatus.FAILED
    )


def test_review_diagnostics_are_persisted_in_atomic_ledger(tmp_path: Path) -> None:
    authorization = _authorization(effective=True)
    ledger = AtomicCalibrationLedger(
        tmp_path / LEDGER_RELATIVE_PATH,
        approved_ceiling_usd=PROPOSED_TECHNICAL_CEILING_USD,
        runtime_authorization=authorization,
    )
    first = PEDAGOGICAL_CALIBRATION_CALL_MATRIX[0]
    ledger.initialize()
    ledger.mark_started(first.call_id)
    result = ProviderCallResult(
        CalibrationResponseStatus.ERROR,
        None,
        100,
        0,
        OPENAI_REVIEW_MAX_OUTPUT_TOKENS,
        100 + OPENAI_REVIEW_MAX_OUTPUT_TOKENS,
        1,
        "OPENAI_REVIEW_INVALID_RESPONSE",
        provider_response_status="incomplete",
        incomplete_reason="max_output_tokens",
        private_diagnostic_code="OPENAI_REVIEW_INCOMPLETE_MAX_OUTPUT_TOKENS",
        parse_error_category=(
            ReviewOutputDiagnosticCategory.OUTPUT_TRUNCATED_CONFIRMED
        ),
        structured_output_validation=StructuredOutputValidationStatus.FAILED,
    )
    ledger.mark_terminal(
        first.call_id,
        status=LedgerCallStatus.FAILED,
        result=result,
        raw_output_sha256=None,
        raw_output_path=None,
        cost_usd=Decimal("0.01"),
        canary_family=ProviderWorkloadFamily.OPENAI_GENERATION_CORRECTION,
        canary_succeeded=False,
    )
    record = ledger.read()["calls"][0]  # type: ignore[index]
    assert record["provider_response_status"] == "incomplete"
    assert record["incomplete_reason"] == "max_output_tokens"
    assert record["output_tokens"] == OPENAI_REVIEW_MAX_OUTPUT_TOKENS
    assert record["parse_error_category"] == "OUTPUT_TRUNCATED_CONFIRMED"
    assert record["structured_output_validation"] == "FAILED"


@pytest.mark.parametrize("effective", (False, True))
def test_reporting_distinguishes_baseline_default_and_runtime_authorization(
    tmp_path: Path,
    effective: bool,
) -> None:
    authorization = _authorization(effective=effective)
    ledger = AtomicCalibrationLedger(
        tmp_path / LEDGER_RELATIVE_PATH,
        approved_ceiling_usd=PROPOSED_TECHNICAL_CEILING_USD,
        runtime_authorization=authorization,
    )
    aggregate = build_safe_aggregate(ledger.initialize(), RawOutputStore(tmp_path))
    report_json, report_markdown = render_safe_reports(aggregate)
    auth = aggregate["authorization"]
    assert auth["baseline_live_authorization_default"] is False  # type: ignore[index]
    assert auth["runtime_live_authorization_effective"] is effective  # type: ignore[index]
    assert auth["owner_configuration_approval"] == "APPROVED"  # type: ignore[index]
    assert auth["owner_approved_manifest_sha256"] == OWNER_APPROVED_MANIFEST_SHA256  # type: ignore[index]
    if effective:
        assert auth["authorized_baseline_commit_sha"] == "a" * 40  # type: ignore[index]
        assert b"Autorisation d'ex\xc3\xa9cution live : `ABSENT`" not in report_markdown
        assert "requires separate runtime authorization" not in aggregate["limitations"]
    else:
        assert auth["authorized_baseline_commit_sha"] is None  # type: ignore[index]
        assert b"Autorisation d'ex\xc3\xa9cution live : `ABSENT`" in report_markdown
        assert "requires separate runtime authorization" in " ".join(
            aggregate["limitations"]  # type: ignore[arg-type]
        )
    assert b"OPENAI_API_KEY" not in report_json
    assert b"ANTHROPIC_API_KEY" not in report_json


def test_canary_failure_persists_and_resume_is_a_provider_noop(
    tmp_path: Path,
) -> None:
    canary_id = CANARY_CALL_IDS[
        ProviderWorkloadFamily.OPENAI_GENERATION_CORRECTION
    ]
    first = _FakeExecutor(canary_id)
    _runner(tmp_path, first).run()
    assert first.calls.count(canary_id) == 1
    generation_family_ids = {
        call.call_id
        for call in PEDAGOGICAL_CALIBRATION_CALL_MATRIX
        if call.provider is CalibrationProvider.OPENAI
        and call.workload is not CalibrationWorkload.REVIEW
    }
    assert generation_family_ids & set(first.calls) == {canary_id}
    ledger = AtomicCalibrationLedger(
        tmp_path / LEDGER_RELATIVE_PATH,
        approved_ceiling_usd=PROPOSED_TECHNICAL_CEILING_USD,
    ).read()
    canary = ledger["canaries"][  # type: ignore[index]
        ProviderWorkloadFamily.OPENAI_GENERATION_CORRECTION.value
    ]
    assert canary["state"] == "BLOCKED"
    resumed = _FakeExecutor()
    _runner(tmp_path, resumed).run()
    assert resumed.calls == []


def test_configuration_approved_but_live_closed_stops_before_real_executor(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    constructions: list[dict[str, str]] = []
    monkeypatch.setattr(
        "tests.calibration.pedagogical.live_runner_v4_1.RealCalibrationExecutor",
        lambda environment: constructions.append(dict(environment)),
    )
    with pytest.raises(LiveCalibrationStop) as raised:
        run_live_calibration(
            root=tmp_path,
            environment={},
            baseline_validator=lambda _: None,
        )
    assert raised.value.code is LiveCalibrationStopCode.LIVE_OWNER_AUTHORIZATION_REQUIRED
    assert constructions == []
    assert not (tmp_path / LEDGER_RELATIVE_PATH).exists()


def test_matrix_contract_preflight_failure_stops_before_real_executor(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    constructions: list[dict[str, str]] = []
    monkeypatch.setattr(
        "tests.calibration.pedagogical.live_runner_v4_1.RealCalibrationExecutor",
        lambda environment: constructions.append(dict(environment)),
    )

    def reject_matrix() -> None:
        raise CalibrationMatrixContractError(
            CalibrationMatrixContractErrorCode.ANTHROPIC_SCORER_OUTPUT_BUDGET_TOO_LOW
        )

    monkeypatch.setattr(
        "tests.calibration.pedagogical.live_runner_v4_1.validate_call_matrix_contracts",
        reject_matrix,
    )
    with pytest.raises(LiveCalibrationStop) as raised:
        run_live_calibration(
            root=tmp_path,
            environment={},
            baseline_validator=lambda _: None,
        )
    assert raised.value.code is LiveCalibrationStopCode.MATRIX_MISMATCH
    assert constructions == []
    assert not (tmp_path / LEDGER_RELATIVE_PATH).exists()
