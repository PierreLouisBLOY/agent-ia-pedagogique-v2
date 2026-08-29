from __future__ import annotations

import json
from dataclasses import replace
from decimal import Decimal
from pathlib import Path

import pytest

from tests.calibration.pedagogical.call_plan import (
    PEDAGOGICAL_CALIBRATION_CALL_MATRIX,
    RAW_OUTPUT_DIRECTORY,
    CalibrationCallSpec,
    CalibrationProvider,
)
from tests.calibration.pedagogical.catalog import scenario_by_code
from tests.calibration.pedagogical.live_runner import (
    APPROVED_CEILING_ENV,
    APPROVED_HARD_CEILING_USD,
    LEDGER_RELATIVE_PATH,
    LIVE_FLAG,
    LIVE_OUTPUT_PATH_ENV,
    AtomicCalibrationLedger,
    LedgerCallStatus,
    LiveCalibrationRunner,
    LiveCalibrationStop,
    LiveCalibrationStopCode,
    ProviderCallResult,
    RawOutputStore,
    _anthropic_result,
    build_safe_aggregate,
    render_safe_reports,
    validate_call_identity,
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
        suffix = call.input_refs[0].rsplit(".", 1)[-1]
        score = {"a": (4, 5), "b": (1, 2), "c": (1, 5)}.get(suffix, (3, 4))
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
        APPROVED_CEILING_ENV: str(APPROVED_HARD_CEILING_USD),
    }


def test_anthropic_runner_result_exposes_only_safe_closed_diagnostics() -> None:
    transport_error = AnthropicTransportError(
        AnthropicTransportErrorCode.REQUEST_TOO_LARGE,
        http_status=413,
        provider_error_type=AnthropicProviderErrorType.API_STATUS_ERROR,
        response_received=True,
        stop_reason=AnthropicStopReason.END_TURN,
        text_block_count=0,
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
    first = LiveCalibrationRunner(
        root=live_root,
        environment=_environment(),
        executor=first_executor,
    ).run()
    assert len(first_executor.calls) == 96
    assert first["anchor_metrics"]["strict_monotonicity_count"] == 16  # type: ignore[index]

    second_executor = _FakeExecutor()
    second = LiveCalibrationRunner(
        root=live_root,
        environment=_environment(),
        executor=second_executor,
    ).run()
    assert second_executor.calls == []
    assert first == second

    ledger = AtomicCalibrationLedger(live_root / LEDGER_RELATIVE_PATH).read()
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
    ledger = AtomicCalibrationLedger(live_root / LEDGER_RELATIVE_PATH)
    ledger.initialize()
    ledger.mark_started(PEDAGOGICAL_CALIBRATION_CALL_MATRIX[0].call_id)
    executor = _FakeExecutor()
    with pytest.raises(LiveCalibrationStop) as raised:
        LiveCalibrationRunner(
            root=live_root,
            environment=_environment(),
            executor=executor,
        ).run()
    assert raised.value.code is LiveCalibrationStopCode.AMBIGUOUS_STARTED_CALL
    assert executor.calls == []


def test_failed_call_is_never_retried_and_selected_scores_skip_dependency(
    live_root: Path,
) -> None:
    source_call_id = PEDAGOGICAL_CALIBRATION_CALL_MATRIX[0].call_id
    executor = _FakeExecutor(source_call_id)
    LiveCalibrationRunner(
        root=live_root,
        environment=_environment(),
        executor=executor,
    ).run()
    assert executor.calls.count(source_call_id) == 1
    ledger = AtomicCalibrationLedger(live_root / LEDGER_RELATIVE_PATH).read()
    records = {
        record["call_id"]: record
        for record in ledger["calls"]  # type: ignore[union-attr]
    }
    assert records[source_call_id]["status"] == LedgerCallStatus.FAILED.value
    skipped = [
        record
        for call_id, record in records.items()
        if call_id.startswith("cal.score.output.scn-03.")
    ]
    assert len(skipped) == 2
    assert {record["status"] for record in skipped} == {
        LedgerCallStatus.SKIPPED_DEPENDENCY_FAILED.value
    }

    resumed = _FakeExecutor()
    LiveCalibrationRunner(
        root=live_root,
        environment=_environment(),
        executor=resumed,
    ).run()
    assert resumed.calls == []


def test_next_call_budget_guard_stops_before_executor(live_root: Path) -> None:
    first = PEDAGOGICAL_CALIBRATION_CALL_MATRIX[0]
    ledger = AtomicCalibrationLedger(live_root / LEDGER_RELATIVE_PATH)
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
        cost_usd=Decimal("4.090000"),
    )
    executor = _FakeExecutor()
    with pytest.raises(LiveCalibrationStop) as raised:
        LiveCalibrationRunner(
            root=live_root,
            environment=_environment(),
            executor=executor,
        ).run()
    assert raised.value.code is LiveCalibrationStopCode.APPROVED_CEILING_INSUFFICIENT
    assert executor.calls == []


def test_matrix_and_model_mismatches_fail_closed(live_root: Path) -> None:
    ledger = AtomicCalibrationLedger(live_root / LEDGER_RELATIVE_PATH)
    ledger.initialize()
    path = live_root / LEDGER_RELATIVE_PATH
    raw = json.loads(path.read_text(encoding="utf-8"))
    raw["matrix_sha256"] = "changed"
    path.write_text(json.dumps(raw), encoding="utf-8")
    with pytest.raises(LiveCalibrationStop) as ledger_error:
        ledger.read()
    assert ledger_error.value.code is LiveCalibrationStopCode.LEDGER_INVALID

    changed_model = replace(
        PEDAGOGICAL_CALIBRATION_CALL_MATRIX[0],
        model="unapproved-model",
    )
    with pytest.raises(LiveCalibrationStop) as identity_error:
        validate_call_identity(changed_model)
    assert identity_error.value.code is LiveCalibrationStopCode.CALL_IDENTITY_MISMATCH
