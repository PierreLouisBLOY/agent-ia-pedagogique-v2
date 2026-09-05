from __future__ import annotations

import hashlib
import json
import shutil
from collections import Counter
from decimal import Decimal
from pathlib import Path

import pytest

from backend.infrastructure.config.secrets.provider import EnvironmentProviderSecretResolver
from tests.calibration.pedagogical.r4_r1_policy import build_uniform_scoring_matrix
from tests.calibration.pedagogical.r4_r3_r1_recovery import (
    BASELINE_RELATIVE_PATH,
    FAILED_EXECUTION_CALL_ID,
    FAILED_LOGICAL_SLOT_ID,
    PLAN_JSON_RELATIVE_PATH,
    PLAN_MARKDOWN_RELATIVE_PATH,
    R2_LEDGER_RELATIVE_PATH,
    R2_LEDGER_SHA256,
    R2_RAW_SHA256,
    R2_SUMMARY_SHA256,
    R3_LEDGER_RELATIVE_PATH,
    R3_LEDGER_SHA256,
    R3_RAW_ORDERED_LIST_SHA256,
    R3_SUMMARY_SHA256,
    R3_TRANSFER_MANIFEST_SHA256,
    RECOVERY_LEDGER_RELATIVE_PATH,
    RECOVERY_MATRIX_SHA256,
    RECOVERY_PLAN_VERSION,
    REMEDIATION_EXECUTION_CALL_ID,
    REUSABLE_MANIFEST_RELATIVE_PATH,
    REUSABLE_MANIFEST_SHA256,
    RecoveryCategory,
    RecoveryError,
    RecoveryErrorCode,
    RecoveryLedgerStatus,
    audit_evidence,
    audit_selected_output_dependencies,
    build_recovery_ledger,
    build_recovery_matrix,
    build_reusable_manifest,
    estimate_recovery_cost,
    financial_approval_text,
    next_executable_call_id,
    pause_after_technical_failure,
    r1_payload,
    recovery_matrix_sha256,
    render_baseline_markdown,
    render_plan_json,
    render_plan_markdown,
    reusable_manifest_sha256,
    transfer_approval_text,
    validate_recovery_ledger,
    write_r1_outputs,
)
from tests.providers.anthropic import AnthropicSDKScoringTransportFactory

ROOT = Path(__file__).resolve().parents[2]


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_r2_and_r3_proofs_are_frozen_and_http503_is_closed_classification() -> None:
    evidence = audit_evidence(ROOT)
    r2 = evidence["r2"]
    r3 = evidence["r3"]

    assert _sha(ROOT / R2_LEDGER_RELATIVE_PATH) == R2_LEDGER_SHA256
    assert r2["summary"]["raw_output_sha256"] == R2_RAW_SHA256  # type: ignore[index]
    assert _sha(ROOT / "artifacts/calibration/12.16-g2-r4-r2/summary.json") == (R2_SUMMARY_SHA256)
    assert _sha(ROOT / R3_LEDGER_RELATIVE_PATH) == R3_LEDGER_SHA256
    assert _sha(ROOT / "artifacts/calibration/12.16-g2-r4-r3/summary.json") == (R3_SUMMARY_SHA256)
    assert _sha(ROOT / "artifacts/calibration/12.16-g2-r4-r3/transfer_manifest.json") == (
        R3_TRANSFER_MANIFEST_SHA256
    )
    assert r3["raw_ordered_list_sha256"] == R3_RAW_ORDERED_LIST_SHA256  # type: ignore[index]
    assert len(r3["completed"]) == 37  # type: ignore[arg-type,index]
    failed = r3["failed"]  # type: ignore[index]
    assert failed["execution_call_id"] == FAILED_EXECUTION_CALL_ID
    assert failed["original_logical_slot_id"] == FAILED_LOGICAL_SLOT_ID
    assert failed["http_status"] == 503
    assert failed["provider_error_type"] == "INTERNAL_SERVER_ERROR"
    assert failed["raw_output_sha256"] is None


def test_r3_hash_mutation_fails_closed(tmp_path: Path) -> None:
    for directory in ("12.16-g2-r4-r2", "12.16-g2-r4-r3"):
        source = ROOT / "artifacts/calibration" / directory
        target = tmp_path / "artifacts/calibration" / directory
        shutil.copytree(source, target)
    ledger = tmp_path / R3_LEDGER_RELATIVE_PATH
    ledger.write_bytes(ledger.read_bytes() + b"\n")

    with pytest.raises(RecoveryError) as raised:
        audit_evidence(tmp_path)

    assert raised.value.code is RecoveryErrorCode.R3_EVIDENCE_MISMATCH


def test_reusable_manifest_contains_only_38_valid_homogeneous_results() -> None:
    manifest = build_reusable_manifest(ROOT)
    results = manifest["results"]

    assert manifest["result_count"] == 38
    assert manifest["raw_content_recorded"] is False
    assert manifest["diagnostic_only_results_included"] is False
    assert len({item["logical_slot_id"] for item in results}) == 38
    assert Counter(item["proof_set"] for item in results) == {
        "R2_HOMOGENEOUS_CANARY": 1,
        "R3_COMPLETED_BEFORE_HTTP503": 37,
    }
    assert all(item["provider"] == "anthropic" for item in results)
    assert all(item["thinking_mode"] == "adaptive" for item in results)
    assert all(item["effort"] == "low" for item in results)
    assert all(item["max_output_tokens"] == 2048 for item in results)
    assert all(item["status"] == "COMPLETED" for item in results)
    assert reusable_manifest_sha256(ROOT) == REUSABLE_MANIFEST_SHA256


def test_76_minus_38_derives_one_38_call_matrix_without_loss_or_overlap() -> None:
    all_ids = {call.original_logical_slot_id for call in build_uniform_scoring_matrix()}
    reused_ids = {item["logical_slot_id"] for item in build_reusable_manifest(ROOT)["results"]}
    calls = build_recovery_matrix(ROOT)
    remaining_ids = {call.original_logical_slot_id for call in calls}

    assert len(all_ids) == 76
    assert len(reused_ids) == len(remaining_ids) == 38
    assert reused_ids.isdisjoint(remaining_ids)
    assert reused_ids | remaining_ids == all_ids
    assert Counter(call.category for call in calls) == {
        RecoveryCategory.INITIAL_ANCHOR: 10,
        RecoveryCategory.REPEATABILITY: 16,
        RecoveryCategory.SELECTED_OUTPUT: 12,
    }


def test_failed_slot_is_preserved_and_new_remediation_call_runs_first() -> None:
    calls = build_recovery_matrix(ROOT)
    historical = audit_evidence(ROOT)["r3"]["failed"]  # type: ignore[index]

    assert historical["status"] == "FAILED"
    assert historical["execution_call_id"] == FAILED_EXECUTION_CALL_ID
    assert calls[0].execution_call_id == REMEDIATION_EXECUTION_CALL_ID
    assert calls[0].original_logical_slot_id == FAILED_LOGICAL_SLOT_ID
    assert calls[0].source_r3_call_id == FAILED_EXECUTION_CALL_ID
    assert calls[0].remediation_source_failed_call_id == FAILED_EXECUTION_CALL_ID
    assert calls[0].mapping_class == "TRANSIENT_SERVER_ERROR_REMEDIATION"
    assert all(call.remediation_source_failed_call_id is None for call in calls[1:])


def test_no_historical_execution_call_id_is_reused() -> None:
    evidence = audit_evidence(ROOT)
    old_r3 = {
        item["execution_call_id"]
        for item in evidence["r3"]["records"]  # type: ignore[index]
    }
    old_r2 = evidence["r2"]["call"]["execution_call_id"]  # type: ignore[index]
    new_ids = {call.execution_call_id for call in build_recovery_matrix(ROOT)}

    assert len(new_ids) == 38
    assert new_ids.isdisjoint(old_r3)
    assert old_r2 not in new_ids


def test_selected_output_dependencies_are_six_of_six_hash_valid() -> None:
    dependencies = audit_selected_output_dependencies(ROOT)

    assert len(dependencies) == 6
    assert all(len(digest) == 64 for digest in dependencies.values())
    assert (
        sum(
            call.category is RecoveryCategory.SELECTED_OUTPUT
            for call in build_recovery_matrix(ROOT)
        )
        == 12
    )


def test_cost_and_matrix_checksums_are_frozen_from_38_specs() -> None:
    calls = build_recovery_matrix(ROOT)
    cost = estimate_recovery_cost(calls)

    assert cost["per_call_maximum_usd"] == "0.036480"
    assert cost["maximum_before_margin_usd"] == "1.386240"
    assert cost["margin_amount_usd"] == "0.346560"
    assert cost["requested_ceiling_usd"] == "1.732800"
    assert Decimal(cost["requested_ceiling_usd"]) == Decimal("1.732800")
    assert recovery_matrix_sha256(ROOT) == RECOVERY_MATRIX_SHA256


def test_new_ledger_is_distinct_pending_retry_free_and_hash_valid() -> None:
    ledger = build_recovery_ledger(ROOT)

    validate_recovery_ledger(ledger, ROOT)
    assert RECOVERY_LEDGER_RELATIVE_PATH != R3_LEDGER_RELATIVE_PATH
    assert ledger["approved_ceiling_usd"] is None
    assert ledger["provider_calls_attempted"] == 0
    assert ledger["automatic_retry_count"] == ledger["automatic_rerun_count"] == 0
    assert ledger["run_status"] == "AWAITING_EXPLICIT_APPROVAL"
    assert all(item["status"] == RecoveryLedgerStatus.PENDING.value for item in ledger["calls"])
    assert ledger["allowed_states"] == [status.value for status in RecoveryLedgerStatus]
    assert next_executable_call_id(ledger, ROOT) == REMEDIATION_EXECUTION_CALL_ID


def test_canary_failure_blocks_calls_two_through_38_before_provider() -> None:
    ledger = build_recovery_ledger(ROOT)
    ledger["calls"][0]["status"] = RecoveryLedgerStatus.STARTED.value
    ledger["run_status"] = "RUNNING"

    paused = pause_after_technical_failure(ledger, REMEDIATION_EXECUTION_CALL_ID, ROOT)

    assert paused["calls"][0]["status"] == RecoveryLedgerStatus.FAILED.value
    assert all(
        item["status"] == RecoveryLedgerStatus.BLOCKED_BY_CANARY.value
        for item in paused["calls"][1:]
    )
    assert paused["run_status"] == "PAUSED_CANARY_FAILURE"
    assert next_executable_call_id(paused, ROOT) is None


def test_successful_canary_allows_call_two_and_later_failure_pauses() -> None:
    ledger = build_recovery_ledger(ROOT)
    for record in ledger["calls"][:5]:
        record["status"] = RecoveryLedgerStatus.COMPLETED.value
    failed_id = ledger["calls"][5]["execution_call_id"]
    ledger["calls"][5]["status"] = RecoveryLedgerStatus.STARTED.value
    ledger["run_status"] = "RUNNING"

    paused = pause_after_technical_failure(ledger, failed_id, ROOT)

    assert paused["calls"][5]["status"] == RecoveryLedgerStatus.FAILED.value
    assert all(item["status"] == RecoveryLedgerStatus.PENDING.value for item in paused["calls"][6:])
    assert paused["run_status"] == "PAUSED_SYSTEMIC_FAILURE"
    assert next_executable_call_id(paused, ROOT) is None


def test_ambiguous_started_call_stops_and_terminal_calls_are_not_recalled() -> None:
    ledger = build_recovery_ledger(ROOT)
    ledger["calls"][0]["status"] = RecoveryLedgerStatus.STARTED.value
    with pytest.raises(RecoveryError) as raised:
        next_executable_call_id(ledger, ROOT)
    assert raised.value.code is RecoveryErrorCode.LEDGER_INVALID

    ledger["calls"][0]["status"] = RecoveryLedgerStatus.COMPLETED.value
    ledger["run_status"] = "RUNNING"
    assert next_executable_call_id(ledger, ROOT) == ledger["calls"][1]["execution_call_id"]


def test_approval_texts_bind_exact_plan_checksum_and_invalidate_on_change() -> None:
    financial = financial_approval_text(RECOVERY_MATRIX_SHA256)
    transfer = transfer_approval_text(RECOVERY_MATRIX_SHA256)

    assert RECOVERY_PLAN_VERSION in financial and RECOVERY_MATRIX_SHA256 in financial
    assert "38 appels maximum" in financial
    assert "1.732800 USD" in financial
    assert "canary en premier" in financial
    assert RECOVERY_PLAN_VERSION in transfer and RECOVERY_MATRIX_SHA256 in transfer
    assert "six outputs historiques" in transfer
    assert "Aucune base SQLite" in transfer
    assert financial != financial_approval_text("0" * 64)
    assert transfer != transfer_approval_text("0" * 64)


def test_r1_never_resolves_credentials_or_builds_provider_transport(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        EnvironmentProviderSecretResolver,
        "resolve",
        lambda *_: pytest.fail("R1 must not resolve a provider credential"),
    )
    monkeypatch.setattr(
        AnthropicSDKScoringTransportFactory,
        "build",
        lambda *_args, **_kwargs: pytest.fail("R1 must not build a provider transport"),
    )

    payload = r1_payload(ROOT)
    assert payload["offline_execution"] == {
        "openai_calls": 0,
        "anthropic_calls": 0,
        "provider_cost_usd": "0.000000",
        "credentials_resolved": False,
        "provider_transport_constructed": False,
        "prior_ledgers_mutated": False,
    }


def test_renderers_are_raw_free_path_free_and_deterministic() -> None:
    first = "\n".join(
        (render_baseline_markdown(ROOT), render_plan_markdown(ROOT), render_plan_json(ROOT))
    )
    second = "\n".join(
        (render_baseline_markdown(ROOT), render_plan_markdown(ROOT), render_plan_json(ROOT))
    )

    assert first == second
    for forbidden in (
        "ANTHROPIC_API_KEY",
        "OPENAI_API_KEY",
        "C:\\Users\\",
        "G:\\Mon Drive\\",
        ".sqlite",
        "request-id",
        '"authorization"',
        "candidate-projection",
    ):
        assert forbidden.casefold() not in first.casefold()


def test_generated_documents_and_ignored_artifacts_match_renderers() -> None:
    assert (ROOT / BASELINE_RELATIVE_PATH).read_text(encoding="utf-8") == (
        render_baseline_markdown(ROOT) + "\n"
    )
    assert (ROOT / PLAN_MARKDOWN_RELATIVE_PATH).read_text(encoding="utf-8") == (
        render_plan_markdown(ROOT) + "\n"
    )
    assert (ROOT / PLAN_JSON_RELATIVE_PATH).read_text(encoding="utf-8") == render_plan_json(ROOT)
    assert json.loads((ROOT / REUSABLE_MANIFEST_RELATIVE_PATH).read_text(encoding="utf-8")) == (
        build_reusable_manifest(ROOT)
    )
    recovery_path = ROOT / RECOVERY_LEDGER_RELATIVE_PATH
    recovery = json.loads(recovery_path.read_text(encoding="utf-8"))
    validate_recovery_ledger(recovery, ROOT)
    if recovery["run_status"] == "AWAITING_EXPLICIT_APPROVAL":
        assert recovery == build_recovery_ledger(ROOT)
    else:
        summary = json.loads(
            (
                ROOT / "artifacts/calibration/12.16-g2-r4-r4/summary.json"
            ).read_text(encoding="utf-8")
        )
        assert _sha(recovery_path) == summary["ledger_final_sha256"]


def test_writing_r1_outputs_does_not_mutate_historical_proofs(tmp_path: Path) -> None:
    for directory in ("12.16-g2", "12.16-g2-r4-r2", "12.16-g2-r4-r3", "12.16-g2-r4-r4"):
        shutil.copytree(
            ROOT / "artifacts/calibration" / directory,
            tmp_path / "artifacts/calibration" / directory,
        )
    protected = (
        tmp_path / R2_LEDGER_RELATIVE_PATH,
        tmp_path / R3_LEDGER_RELATIVE_PATH,
        tmp_path / "artifacts/calibration/12.16-g2-r4-r2/summary.json",
        tmp_path / "artifacts/calibration/12.16-g2-r4-r3/summary.json",
        tmp_path / "artifacts/calibration/12.16-g2-r4-r3/transfer_manifest.json",
        tmp_path / RECOVERY_LEDGER_RELATIVE_PATH,
    )
    before = {path: _sha(path) for path in protected}
    original_paths = (
        ROOT / BASELINE_RELATIVE_PATH,
        ROOT / PLAN_MARKDOWN_RELATIVE_PATH,
        ROOT / PLAN_JSON_RELATIVE_PATH,
        ROOT / REUSABLE_MANIFEST_RELATIVE_PATH,
        *(ROOT / path.relative_to(tmp_path) for path in protected),
    )
    original_before = {path: (_sha(path), path.stat().st_mtime_ns) for path in original_paths}

    write_r1_outputs(tmp_path)

    assert {path: _sha(path) for path in protected} == before
    assert {path: (_sha(path), path.stat().st_mtime_ns) for path in original_paths} == original_before
    assert json.loads((tmp_path / REUSABLE_MANIFEST_RELATIVE_PATH).read_text(encoding="utf-8")) == (
        build_reusable_manifest(tmp_path)
    )
