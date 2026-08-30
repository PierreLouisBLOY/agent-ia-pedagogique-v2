from __future__ import annotations

import json
import shutil
from decimal import Decimal
from pathlib import Path

import pytest

from backend.infrastructure.config.secrets.provider import (
    EnvironmentProviderSecretResolver,
)
from evaluation_harness import ScorerOutcome
from tests.calibration.pedagogical.r4_r1_policy import (
    CANARY_EXECUTION_CALL_ID,
    CANARY_LOGICAL_SLOT_ID,
    EXPECTED_DIAGNOSTIC_LOGICAL_SLOTS,
    MAX_OUTPUT_TOKENS,
    R1_BASELINE_RELATIVE_PATH,
    R2_COST_JSON_RELATIVE_PATH,
    R2_COST_MARKDOWN_RELATIVE_PATH,
    R2_EXPECTED_BASE_USD,
    R2_EXPECTED_CEILING_USD,
    R2_LEDGER_RELATIVE_PATH,
    R2_MATRIX_SHA256,
    R2_PLAN_VERSION,
    R3_COST_JSON_RELATIVE_PATH,
    R3_COST_MARKDOWN_RELATIVE_PATH,
    R3_EXPECTED_BASE_USD,
    R3_EXPECTED_CEILING_USD,
    R3_LEDGER_RELATIVE_PATH,
    R3_MATRIX_SHA256,
    R3_PLAN_VERSION,
    R4_LEDGER_RELATIVE_PATH,
    R4_LEDGER_SHA256,
    R4_SUMMARY_RELATIVE_PATH,
    R4_SUMMARY_SHA256,
    PolicyLedgerStatus,
    R4R1Error,
    R4R1ErrorCode,
    audit_historical_anthropic_scores,
    audit_r4_evidence,
    build_policy_ledger,
    build_r2_canary_matrix,
    build_r3_completion_matrix,
    build_uniform_scoring_matrix,
    estimate_policy_cost,
    next_executable_call_id,
    r1_payload,
    r2_financial_approval_text,
    r2_matrix_sha256,
    r2_transfer_approval_text,
    r3_financial_approval_text,
    r3_matrix_sha256,
    r3_transfer_approval_text,
    render_r1_baseline_markdown,
    render_r2_cost_json,
    render_r2_cost_markdown,
    render_r3_cost_json,
    render_r3_cost_markdown,
)
from tests.providers.anthropic import (
    AnthropicEffort,
    AnthropicSDKScoringTransportFactory,
    AnthropicThinkingMode,
)

ROOT = Path(__file__).resolve().parents[2]


def test_r4_failure_evidence_is_frozen_and_classified_without_overclaim() -> None:
    audit = audit_r4_evidence(ROOT)

    assert audit.ledger_sha256 == R4_LEDGER_SHA256
    assert audit.summary_sha256 == R4_SUMMARY_SHA256
    assert audit.failed_call_id == ("r4.cal.score.anchor.scn-01.c.organization-utility.r1")
    assert audit.response_received is True
    assert audit.stop_reason == "max_tokens"
    assert audit.text_block_count == 0
    assert audit.output_tokens == audit.max_output_tokens == 512
    assert audit.classification == "MAX_TOKENS_EXHAUSTED_BEFORE_TEXT"
    assert audit.state_counts == {
        "COMPLETED": 0,
        "FAILED": 1,
        "PENDING": 70,
        "SKIPPED_DEPENDENCY_FAILED": 0,
        "STARTED": 0,
    }
    assert r1_payload(ROOT)["r4_evidence"]["overclaim_thinking_tokens"] is False  # type: ignore[index]


def test_r4_hash_mutation_fails_closed(tmp_path: Path) -> None:
    for relative_path in (R4_LEDGER_RELATIVE_PATH, R4_SUMMARY_RELATIVE_PATH):
        source = ROOT / relative_path
        target = tmp_path / relative_path
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)
    ledger = tmp_path / R4_LEDGER_RELATIVE_PATH
    ledger.write_bytes(ledger.read_bytes() + b"\n")

    with pytest.raises(R4R1Error) as raised:
        audit_r4_evidence(tmp_path)

    assert raised.value.code is R4R1ErrorCode.R4_EVIDENCE_MISMATCH


def test_five_historical_anthropic_scores_are_retained_as_diagnostic_only() -> None:
    scores, openai_count = audit_historical_anthropic_scores(ROOT)

    assert len(scores) == 5
    assert tuple(item.logical_slot_id for item in scores) == (EXPECTED_DIAGNOSTIC_LOGICAL_SLOTS)
    assert all(item.output_sha256 for item in scores)
    assert all(
        item.final_calibration_status == "DIAGNOSTIC_ONLY_NOT_FINAL_CALIBRATION" for item in scores
    )
    assert openai_count == 20


def test_uniform_population_is_76_original_anthropic_slots_under_one_policy() -> None:
    calls = build_uniform_scoring_matrix()
    selected_outputs = tuple(
        call for call in calls if call.original_logical_slot_id.startswith("cal.score.output.")
    )

    assert len(calls) == 76
    assert len({call.original_logical_slot_id for call in calls}) == 76
    assert len({call.execution_call_id for call in calls}) == 76
    assert (
        sum(
            call.original_logical_slot_id.startswith("cal.score.anchor.") and call.repetition == 1
            for call in calls
        )
        == 48
    )
    assert (
        sum(
            call.original_logical_slot_id.startswith("cal.score.anchor.") and call.repetition == 2
            for call in calls
        )
        == 16
    )
    assert (
        sum(call.original_logical_slot_id.startswith("cal.score.output.") for call in calls) == 12
    )
    assert {call.input_refs[0] for call in selected_outputs} == {
        "output:cal.generation.course.primary.r1",
        "output:cal.transformation.resource.primary.r1",
        "output:cal.generation.exercise.primary.r1",
        "output:cal.generation.assessment.primary.r1",
        "output:cal.correction.remediation.primary.r1",
        "output:cal.generation.qcm.primary.r1",
    }
    assert all(
        sum(candidate.input_refs == call.input_refs for candidate in selected_outputs) == 2
        for call in selected_outputs
    )
    assert all(call.thinking_mode is AnthropicThinkingMode.ADAPTIVE for call in calls)
    assert all(call.effort is AnthropicEffort.LOW for call in calls)
    assert all(call.max_output_tokens == MAX_OUTPUT_TOKENS for call in calls)
    assert all(call.automatic_retry_count == 0 for call in calls)


def test_r2_canary_is_one_exact_slot_with_frozen_checksum_and_cost() -> None:
    calls = build_r2_canary_matrix()
    cost = estimate_policy_cost(calls)

    assert len(calls) == 1
    assert calls[0].original_logical_slot_id == CANARY_LOGICAL_SLOT_ID
    assert calls[0].execution_call_id == CANARY_EXECUTION_CALL_ID
    assert r2_matrix_sha256() == R2_MATRIX_SHA256
    assert Decimal(cost["maximum_before_margin_usd"]) == R2_EXPECTED_BASE_USD
    assert Decimal(cost["requested_ceiling_usd"]) == R2_EXPECTED_CEILING_USD
    assert cost["input_max_per_call"] == 8_000
    assert cost["output_max_per_call"] == 2_048


def test_r3_completion_is_conditional_75_with_no_overlap_or_loss() -> None:
    canary = build_r2_canary_matrix()
    completion = build_r3_completion_matrix()
    uniform = build_uniform_scoring_matrix()
    cost = estimate_policy_cost(completion)
    canary_ids = {call.original_logical_slot_id for call in canary}
    completion_ids = {call.original_logical_slot_id for call in completion}

    assert len(completion) == 75
    assert canary_ids.isdisjoint(completion_ids)
    assert canary_ids | completion_ids == {call.original_logical_slot_id for call in uniform}
    assert (
        sum(
            call.original_logical_slot_id.startswith("cal.score.anchor.") and call.repetition == 1
            for call in completion
        )
        == 47
    )
    assert sum(call.repetition == 2 for call in completion) == 16
    assert (
        sum(call.original_logical_slot_id.startswith("cal.score.output.") for call in completion)
        == 12
    )
    assert r3_matrix_sha256() == R3_MATRIX_SHA256
    assert Decimal(cost["maximum_before_margin_usd"]) == R3_EXPECTED_BASE_USD
    assert Decimal(cost["requested_ceiling_usd"]) == R3_EXPECTED_CEILING_USD


def test_ledgers_are_distinct_pending_approval_retry_free_and_resumable() -> None:
    r2_calls = build_r2_canary_matrix()
    r3_calls = build_r3_completion_matrix()
    r2 = build_policy_ledger(
        version=R2_PLAN_VERSION,
        matrix_sha256=R2_MATRIX_SHA256,
        calls=r2_calls,
        requested_ceiling_usd="0.045600",
        prerequisite={"r4_ledger_sha256": R4_LEDGER_SHA256},
    )
    r3 = build_policy_ledger(
        version=R3_PLAN_VERSION,
        matrix_sha256=R3_MATRIX_SHA256,
        calls=r3_calls,
        requested_ceiling_usd="3.420000",
        prerequisite={"r2_canary_status": "PASS_HASH_VALID_REQUIRED"},
    )

    assert R2_LEDGER_RELATIVE_PATH != R3_LEDGER_RELATIVE_PATH
    assert r2["approved_ceiling_usd"] is None
    assert r3["approved_ceiling_usd"] is None
    assert r2["financial_approval_required"] is True
    assert r2["external_transfer_approval_required"] is True
    assert r2["automatic_retry_count"] == r2["automatic_rerun_count"] == 0
    assert r3["automatic_retry_count"] == r3["automatic_rerun_count"] == 0
    assert all(item["status"] == "PENDING" for item in r2["calls"])
    assert all(item["status"] == "PENDING" for item in r3["calls"])
    assert next_executable_call_id(r2) == CANARY_EXECUTION_CALL_ID

    r2["calls"][0]["status"] = PolicyLedgerStatus.STARTED.value  # type: ignore[index]
    with pytest.raises(R4R1Error):
        next_executable_call_id(r2)


def test_new_financial_and_transfer_approvals_are_distinct_and_not_inherited() -> None:
    r2_financial = r2_financial_approval_text(R2_MATRIX_SHA256)
    r2_transfer = r2_transfer_approval_text(R2_MATRIX_SHA256)
    r3_financial = r3_financial_approval_text(R3_MATRIX_SHA256)
    r3_transfer = r3_transfer_approval_text(R3_MATRIX_SHA256)

    assert R2_MATRIX_SHA256 in r2_financial and "0.045600" in r2_financial
    assert "un anchor synthétique G1" in r2_transfer
    assert "Aucune base SQLite" in r2_transfer
    assert "output historique" in r2_transfer
    assert R3_MATRIX_SHA256 in r3_financial and "3.420000" in r3_financial
    assert "six productions historiques" in r3_transfer
    assert "Aucune base SQLite" in r3_transfer
    assert r2_financial != r3_financial
    assert r2_transfer != r3_transfer
    payload = r1_payload(ROOT)
    assert payload["r2_canary"]["already_approved"] is False  # type: ignore[index]
    assert payload["r3_completion"]["already_approved"] is False  # type: ignore[index]


def test_r1_rendering_is_offline_raw_free_and_never_builds_provider(
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
        lambda *_args, **_kwargs: pytest.fail("R1 must not build transport"),
    )
    rendered = "\n".join(
        (
            render_r1_baseline_markdown(ROOT),
            render_r2_cost_markdown(ROOT),
            render_r2_cost_json(ROOT),
            render_r3_cost_markdown(ROOT),
            render_r3_cost_json(ROOT),
        )
    )

    for forbidden in (
        "ANTHROPIC_API_KEY",
        "OPENAI_API_KEY",
        "C:\\Users\\",
        "/Users/",
        "raw_output_text",
        "request-id",
        "authorization",
    ):
        assert forbidden.casefold() not in rendered.casefold()
    assert "LIVE_PROVIDER_CALLS_R1 = 0" in rendered
    assert ScorerOutcome.__module__ == "evaluation_harness.contracts.scoring"


def test_generated_docs_and_ignored_ledgers_match_deterministic_renderers() -> None:
    expected = {
        R1_BASELINE_RELATIVE_PATH: render_r1_baseline_markdown(ROOT) + "\n",
        R2_COST_MARKDOWN_RELATIVE_PATH: render_r2_cost_markdown(ROOT) + "\n",
        R2_COST_JSON_RELATIVE_PATH: render_r2_cost_json(ROOT),
        R3_COST_MARKDOWN_RELATIVE_PATH: render_r3_cost_markdown(ROOT) + "\n",
        R3_COST_JSON_RELATIVE_PATH: render_r3_cost_json(ROOT),
    }
    for relative_path, content in expected.items():
        assert (ROOT / relative_path).read_text(encoding="utf-8") == content

    r2_ledger = json.loads((ROOT / R2_LEDGER_RELATIVE_PATH).read_text(encoding="utf-8"))
    r3_ledger = json.loads((ROOT / R3_LEDGER_RELATIVE_PATH).read_text(encoding="utf-8"))
    assert len(r2_ledger["calls"]) == 1
    assert len(r3_ledger["calls"]) == 75
    assert r2_ledger["matrix_sha256"] == R2_MATRIX_SHA256
    assert r3_ledger["matrix_sha256"] == R3_MATRIX_SHA256
