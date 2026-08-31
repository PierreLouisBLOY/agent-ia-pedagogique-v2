from __future__ import annotations

import json
from copy import deepcopy
from dataclasses import replace
from decimal import Decimal
from pathlib import Path

import pytest

from tests.calibration.pedagogical import live_runner as live_runner_module
from tests.calibration.pedagogical.call_plan import (
    PEDAGOGICAL_CALIBRATION_CALL_MATRIX,
    RAW_OUTPUT_DIRECTORY,
    V4_TIER_BY_ANCHOR_ID,
    CalibrationCallSpec,
    CalibrationProvider,
)
from tests.calibration.pedagogical.catalog import scenario_by_code
from tests.calibration.pedagogical.live_runner import (
    APPROVED_CEILING_ENV,
    CANARY_CALL_IDS,
    EXPECTED_MATRIX_SHA256,
    LEDGER_RELATIVE_PATH,
    LIVE_FLAG,
    LIVE_OUTPUT_PATH_ENV,
    PROPOSED_TECHNICAL_CEILING_USD,
    AtomicCalibrationLedger,
    LedgerCallStatus,
    LiveCalibrationRunner,
    LiveCalibrationStop,
    LiveCalibrationStopCode,
    ProviderCallResult,
    ProviderTransportCategory,
    ProviderWorkloadFamily,
    RawOutputStore,
    _anthropic_result,
    _systemic_failure_category,
    build_safe_aggregate,
    render_safe_reports,
    run_live_calibration,
    validate_call_identity,
    validate_v4_baseline,
)
from tests.calibration.pedagogical.metrics import CalibrationResponseStatus
from tests.providers.anthropic import (
    AnthropicProviderErrorType,
    AnthropicStopReason,
    AnthropicTransportError,
    AnthropicTransportErrorCode,
)
from tests.providers.anthropic.scorer import (
    AnthropicScorerError,
    AnthropicScorerErrorCode,
)


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
                7,
                "FAKE_CLOSED_FAILURE",
            )
        if call.provider is CalibrationProvider.OPENAI:
            scenario = scenario_by_code(call.scenario_code)
            raw = json.dumps(
                {
                    "outcome": "OUTPUT",
                    "sections": [
                        {"code": code, "text": f"synthetic-{code}-{call.call_id}"}
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
                10,
                25,
                125,
                11,
            )
        if call.input_refs[0].startswith("output:"):
            assert dependency_candidate is not None
        subject = call.input_refs[0].split(":", 1)[1]
        if subject in V4_TIER_BY_ANCHOR_ID:
            tier = V4_TIER_BY_ANCHOR_ID[subject].value
            score = {
                "STRONG": (4, 5),
                "MIXED": (1, 2),
                "WEAK_BUT_STRUCTURALLY_VALID": (1, 5),
            }[tier]
        else:
            source = next(
                item
                for item in PEDAGOGICAL_CALIBRATION_CALL_MATRIX
                if item.call_id == subject
            )
            score = (4, 5) if source.role.value == "PRIMARY" else (1, 2)
        raw = json.dumps(
            {
                "status": "SCORED",
                "score_numerator": score[0],
                "score_denominator": score[1],
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
            13,
        )


@pytest.fixture
def live_root(tmp_path: Path) -> Path:
    root = tmp_path / "repo"
    root.mkdir()
    (root / ".gitignore").write_text("/artifacts/\n", encoding="utf-8")
    return root


def _environment() -> dict[str, str]:
    return {
        "OPENAI_API_KEY": "synthetic-openai",
        "ANTHROPIC_API_KEY": "synthetic-anthropic",
        LIVE_FLAG: "1",
        LIVE_OUTPUT_PATH_ENV: RAW_OUTPUT_DIRECTORY,
        APPROVED_CEILING_ENV: str(PROPOSED_TECHNICAL_CEILING_USD),
    }


def _offline_runner(root: Path, executor: _FakeExecutor) -> LiveCalibrationRunner:
    return LiveCalibrationRunner(
        root=root,
        environment=_environment(),
        executor=executor,
        baseline_validator=lambda _: None,
        approved_ceiling_usd=PROPOSED_TECHNICAL_CEILING_USD,
        live_authorized=True,
    )


def test_anthropic_runner_result_exposes_only_safe_closed_diagnostics() -> None:
    transport_error = AnthropicTransportError(
        AnthropicTransportErrorCode.REQUEST_TOO_LARGE,
        http_status=413,
        provider_error_type=AnthropicProviderErrorType.API_STATUS_ERROR,
        response_received=True,
        stop_reason=AnthropicStopReason.END_TURN,
        text_block_count=0,
        thinking_block_count=1,
        thinking_tokens=0,
        input_tokens=23,
        output_tokens=0,
        total_tokens=23,
    )
    scorer_error = AnthropicScorerError(
        AnthropicScorerErrorCode.PROVIDER_UNAVAILABLE,
        transport_error=transport_error,
    )

    result = _anthropic_result(
        None,
        CalibrationResponseStatus.ERROR,
        17,
        "ANTHROPIC_SCORER_TRANSPORT_REQUEST_TOO_LARGE",
        scorer_error=scorer_error,
    )

    assert result.transport_http_status == 413
    assert result.provider_error_type is AnthropicProviderErrorType.API_STATUS_ERROR
    assert result.response_received is True
    assert result.stop_reason is AnthropicStopReason.END_TURN
    assert result.text_block_count == 0
    assert result.thinking_block_count == 1
    assert result.thinking_tokens == 0
    assert (result.input_tokens, result.output_tokens, result.total_tokens) == (23, 0, 23)
    assert "request-id" not in repr(result)
    assert "header" not in repr(result)
    assert "body" not in repr(result)


def test_atomic_ledger_and_raw_output_hash_round_trip(live_root: Path) -> None:
    ledger = AtomicCalibrationLedger(live_root / LEDGER_RELATIVE_PATH)
    initialized = ledger.initialize()
    assert initialized["total_cost_usd"] == "0.000000"
    assert not tuple((live_root / "artifacts").rglob("*.tmp"))

    raw_store = RawOutputStore(live_root)
    digest, relative_path = raw_store.write("call.one", '{"safe":true}')
    assert raw_store.read(relative_path, digest) == '{"safe":true}'
    assert digest == "13f513fe32a8991557ebf28941b75597641e94717c08569b7723d998c7428423"


def test_completed_matrix_resumes_as_a_provider_noop_and_reports_are_safe(
    live_root: Path,
) -> None:
    first_executor = _FakeExecutor()
    first = _offline_runner(live_root, first_executor).run()
    assert len(first_executor.calls) == 102
    assert first["anchor_metrics"]["strict_monotonicity_count"] == 16  # type: ignore[index]
    assert first["selected_output_metrics"]["pairwise_comparison_count"] == 6  # type: ignore[index]
    assert first["selected_output_metrics"]["pairwise_primary_win_count"] == 6  # type: ignore[index]
    assert first["authorization"]["openai_call_count"] == 20  # type: ignore[index]
    assert first["authorization"]["anthropic_call_count"] == 82  # type: ignore[index]
    assert first["authorization"]["total_matrix_call_count"] == 102  # type: ignore[index]
    assert first["human_anchor_review"] == "PASS_WITH_CORRECTIVE_ATTESTATION"

    second_executor = _FakeExecutor()
    second = _offline_runner(live_root, second_executor).run()
    assert second_executor.calls == []
    assert first == second

    ledger = AtomicCalibrationLedger(
        live_root / LEDGER_RELATIVE_PATH,
        approved_ceiling_usd=PROPOSED_TECHNICAL_CEILING_USD,
    ).read()
    aggregate = build_safe_aggregate(ledger, RawOutputStore(live_root))
    json_report_a, markdown_report_a = render_safe_reports(aggregate)
    json_report_b, markdown_report_b = render_safe_reports(aggregate)
    assert json_report_a == json_report_b
    assert markdown_report_a == markdown_report_b
    assert b"synthetic-context" not in json_report_a
    assert b"synthetic-context" not in markdown_report_a
    assert b"synthetic-openai" not in json_report_a
    assert b"synthetic-anthropic" not in json_report_a


def test_ambiguous_started_call_stops_before_transport(live_root: Path) -> None:
    ledger = AtomicCalibrationLedger(
        live_root / LEDGER_RELATIVE_PATH,
        approved_ceiling_usd=PROPOSED_TECHNICAL_CEILING_USD,
    )
    ledger.initialize()
    ledger.mark_started(PEDAGOGICAL_CALIBRATION_CALL_MATRIX[0].call_id)
    executor = _FakeExecutor()
    with pytest.raises(LiveCalibrationStop) as raised:
        _offline_runner(live_root, executor).run()
    assert raised.value.code is LiveCalibrationStopCode.AMBIGUOUS_STARTED_CALL
    assert executor.calls == []


def test_failed_call_is_never_retried_and_selected_scores_skip_dependency(
    live_root: Path,
) -> None:
    source_call_id = PEDAGOGICAL_CALIBRATION_CALL_MATRIX[0].call_id
    executor = _FakeExecutor(source_call_id)
    _offline_runner(live_root, executor).run()
    assert executor.calls.count(source_call_id) == 1
    ledger = AtomicCalibrationLedger(
        live_root / LEDGER_RELATIVE_PATH,
        approved_ceiling_usd=PROPOSED_TECHNICAL_CEILING_USD,
    ).read()
    records = {
        record["call_id"]: record
        for record in ledger["calls"]  # type: ignore[union-attr]
    }
    assert records[source_call_id]["status"] == LedgerCallStatus.FAILED.value
    generation_family_ids = {
        call.call_id
        for call in PEDAGOGICAL_CALIBRATION_CALL_MATRIX
        if call.provider is CalibrationProvider.OPENAI
        and call.workload.value != "review"
    }
    assert generation_family_ids & set(executor.calls) == {source_call_id}
    canary = ledger["canaries"][  # type: ignore[index]
        ProviderWorkloadFamily.OPENAI_GENERATION_CORRECTION.value
    ]
    assert canary["state"] == "BLOCKED"
    assert canary["failure_category"] == ProviderTransportCategory.UNAVAILABLE.value
    skipped = [
        record
        for call_id, record in records.items()
        if call_id.startswith("cal.score.output.scn-03.")
    ]
    assert len(skipped) == 4
    assert {record["status"] for record in skipped} == {
        LedgerCallStatus.SKIPPED_DEPENDENCY_FAILED.value
    }

    resumed = _FakeExecutor()
    _offline_runner(live_root, resumed).run()
    assert resumed.calls == []


def test_next_call_budget_guard_stops_before_executor(live_root: Path) -> None:
    first = PEDAGOGICAL_CALIBRATION_CALL_MATRIX[0]
    ledger = AtomicCalibrationLedger(
        live_root / LEDGER_RELATIVE_PATH,
        approved_ceiling_usd=PROPOSED_TECHNICAL_CEILING_USD,
    )
    ledger.initialize()
    ledger.mark_started(first.call_id)
    ledger.mark_terminal(
        first.call_id,
        status=LedgerCallStatus.COMPLETED,
        result=ProviderCallResult(
            CalibrationResponseStatus.STRUCTURED,
            None,
            1,
            0,
            1,
            2,
            1,
        ),
        raw_output_sha256=None,
        raw_output_path=None,
        cost_usd=Decimal("3.250000"),
        canary_family=ProviderWorkloadFamily.OPENAI_GENERATION_CORRECTION,
        canary_succeeded=True,
    )
    executor = _FakeExecutor()
    with pytest.raises(LiveCalibrationStop) as raised:
        _offline_runner(live_root, executor).run()
    assert raised.value.code is LiveCalibrationStopCode.APPROVED_CEILING_INSUFFICIENT
    assert executor.calls == []


def test_matrix_and_model_mismatches_fail_closed(live_root: Path) -> None:
    ledger = AtomicCalibrationLedger(
        live_root / LEDGER_RELATIVE_PATH,
        approved_ceiling_usd=PROPOSED_TECHNICAL_CEILING_USD,
    )
    ledger.initialize()
    path = live_root / LEDGER_RELATIVE_PATH
    original = json.loads(path.read_text(encoding="utf-8"))
    changed_matrix = deepcopy(original)
    changed_matrix["matrix_sha256"] = "changed"
    path.write_text(json.dumps(changed_matrix), encoding="utf-8")
    with pytest.raises(LiveCalibrationStop) as ledger_error:
        ledger.read()
    assert ledger_error.value.code is LiveCalibrationStopCode.LEDGER_INVALID

    changed_pricing = deepcopy(original)
    changed_pricing["matrix_sha256"] = EXPECTED_MATRIX_SHA256
    changed_pricing["pricing_snapshot_sha256"] = "changed"
    path.write_text(json.dumps(changed_pricing), encoding="utf-8")
    with pytest.raises(LiveCalibrationStop) as pricing_error:
        ledger.read()
    assert pricing_error.value.code is LiveCalibrationStopCode.LEDGER_INVALID

    changed_model = replace(
        PEDAGOGICAL_CALIBRATION_CALL_MATRIX[0],
        model="unapproved-model",
    )
    with pytest.raises(LiveCalibrationStop) as identity_error:
        validate_call_identity(changed_model)
    assert identity_error.value.code is LiveCalibrationStopCode.CALL_IDENTITY_MISMATCH


def _valid_closure_payload() -> dict[str, object]:
    return {
        "corrected_form_sha256": (
            "5748b0f223b3039b463f975de8d99772a9f18ad729535a73bd27dfcfc27042a6"
        ),
        "trace_correction_check": "PASS",
        "gate_a": {"status": "PASS"},
        "gate_b": {"status": "PASS"},
        "human_v4_prevalidation": "PASS_WITH_CORRECTIVE_ATTESTATION",
        "methodological_status": "PASS",
    }


@pytest.mark.parametrize(
    ("mutation", "expected"),
    (
        ("ancestor", LiveCalibrationStopCode.V4_BASELINE_COMMIT_NOT_ANCESTOR),
        ("dirty", LiveCalibrationStopCode.V4_WORKTREE_DIRTY),
        ("closure", LiveCalibrationStopCode.V4_CLOSURE_BASELINE_MISMATCH),
        ("form", LiveCalibrationStopCode.V4_CORRECTED_FORM_MISMATCH),
        ("corpus", LiveCalibrationStopCode.V4_CORPUS_MISMATCH),
        ("trace", LiveCalibrationStopCode.V4_HUMAN_PREVALIDATION_NOT_PASS),
        ("gate_a", LiveCalibrationStopCode.V4_HUMAN_PREVALIDATION_NOT_PASS),
        ("gate_b", LiveCalibrationStopCode.V4_HUMAN_PREVALIDATION_NOT_PASS),
        ("human", LiveCalibrationStopCode.V4_HUMAN_PREVALIDATION_NOT_PASS),
        ("method", LiveCalibrationStopCode.V4_HUMAN_PREVALIDATION_NOT_PASS),
    ),
)
def test_v4_baseline_invariants_fail_independently_before_execution(
    live_root: Path,
    mutation: str,
    expected: LiveCalibrationStopCode,
) -> None:
    payload = _valid_closure_payload()
    ancestor = mutation != "ancestor"
    clean = mutation != "dirty"
    corpus_hash = (
        "changed"
        if mutation == "corpus"
        else "9c8e262028f1d63fa50963f2f8bcb742e4c24d4e106a73244861416f826ca034"
    )
    if mutation == "form":
        payload["corrected_form_sha256"] = "changed"
    elif mutation == "trace":
        payload["trace_correction_check"] = "FAIL"
    elif mutation == "gate_a":
        payload["gate_a"] = {"status": "FAIL"}
    elif mutation == "gate_b":
        payload["gate_b"] = {"status": "FAIL"}
    elif mutation == "human":
        payload["human_v4_prevalidation"] = "PARTIAL"
    elif mutation == "method":
        payload["methodological_status"] = "PARTIAL"

    def closure_builder(_: Path) -> dict[str, object]:
        if mutation == "closure":
            raise RuntimeError("synthetic closure failure")
        return payload

    with pytest.raises(LiveCalibrationStop) as raised:
        validate_v4_baseline(
            live_root,
            closure_builder=closure_builder,
            corpus_hash_builder=lambda: corpus_hash,
            git_probe=lambda _: (ancestor, clean),
        )
    assert raised.value.code is expected


def test_v4_canonical_baseline_passes_when_git_preconditions_are_satisfied() -> None:
    root = Path(__file__).resolve().parents[2]
    validate_v4_baseline(root, git_probe=lambda _: (True, True))


def test_baseline_validator_runs_before_executor(live_root: Path) -> None:
    executor = _FakeExecutor()

    def reject(_: Path) -> None:
        raise LiveCalibrationStop(LiveCalibrationStopCode.V4_CORPUS_MISMATCH)

    with pytest.raises(LiveCalibrationStop) as raised:
        LiveCalibrationRunner(
            root=live_root,
            environment=_environment(),
            executor=executor,
            baseline_validator=reject,
            approved_ceiling_usd=PROPOSED_TECHNICAL_CEILING_USD,
        ).run()
    assert raised.value.code is LiveCalibrationStopCode.V4_CORPUS_MISMATCH
    assert executor.calls == []
    assert not (live_root / LEDGER_RELATIVE_PATH).exists()


def test_live_entrypoint_stops_before_real_executor_without_live_authorization(
    live_root: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    constructions: list[dict[str, str]] = []
    monkeypatch.setattr(
        live_runner_module,
        "RealCalibrationExecutor",
        lambda environment: constructions.append(dict(environment)),
    )
    with pytest.raises(LiveCalibrationStop) as raised:
        run_live_calibration(
            root=live_root,
            environment={},
            baseline_validator=lambda _: None,
        )
    assert raised.value.code is LiveCalibrationStopCode.LIVE_OWNER_AUTHORIZATION_REQUIRED
    assert constructions == []


def test_non_systemic_canary_result_allows_family_fanout(live_root: Path) -> None:
    class _RefusalCanaryExecutor(_FakeExecutor):
        def execute(
            self,
            call: CalibrationCallSpec,
            *,
            dependency_candidate: str | None,
        ) -> ProviderCallResult:
            if call.call_id == CANARY_CALL_IDS[
                ProviderWorkloadFamily.OPENAI_GENERATION_CORRECTION
            ]:
                self.calls.append(call.call_id)
                return ProviderCallResult(
                    CalibrationResponseStatus.REFUSAL,
                    None,
                    10,
                    0,
                    5,
                    15,
                    1,
                    "OPENAI_PROVIDER_REFUSAL",
                )
            return super().execute(call, dependency_candidate=dependency_candidate)

    executor = _RefusalCanaryExecutor()
    _offline_runner(live_root, executor).run()
    generation_family_ids = {
        call.call_id
        for call in PEDAGOGICAL_CALIBRATION_CALL_MATRIX
        if call.provider is CalibrationProvider.OPENAI
        and call.workload.value != "review"
    }
    assert generation_family_ids.issubset(executor.calls)
    ledger = AtomicCalibrationLedger(
        live_root / LEDGER_RELATIVE_PATH,
        approved_ceiling_usd=PROPOSED_TECHNICAL_CEILING_USD,
    ).read()
    canary = ledger["canaries"][  # type: ignore[index]
        ProviderWorkloadFamily.OPENAI_GENERATION_CORRECTION.value
    ]
    assert canary["state"] == "PASSED"


@pytest.mark.parametrize(
    ("code", "expected"),
    (
        ("OPENAI_TRANSPORT_AUTHENTICATION", ProviderTransportCategory.AUTHENTICATION),
        ("OPENAI_TRANSPORT_PERMISSION", ProviderTransportCategory.PERMISSION),
        ("OPENAI_BILLING_CREDIT", ProviderTransportCategory.BILLING),
        ("OPENAI_RATE_LIMIT", ProviderTransportCategory.RATE_LIMIT),
        ("OPENAI_MODEL_NOT_FOUND", ProviderTransportCategory.NOT_FOUND),
        ("OPENAI_INVALID_REQUEST", ProviderTransportCategory.INVALID_REQUEST),
        ("OPENAI_CONNECTION", ProviderTransportCategory.CONNECTION),
        ("OPENAI_SERVER", ProviderTransportCategory.SERVER),
    ),
)
def test_systemic_canary_failure_mapping_is_deterministic(
    code: str,
    expected: ProviderTransportCategory,
) -> None:
    result = ProviderCallResult(
        CalibrationResponseStatus.ERROR,
        None,
        None,
        None,
        None,
        None,
        0,
        code,
    )
    assert _systemic_failure_category(result) is expected
