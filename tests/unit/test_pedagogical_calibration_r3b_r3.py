from __future__ import annotations

import json
from collections import Counter
from dataclasses import replace
from pathlib import Path

import pytest

import tests.calibration.pedagogical.r3b_r3_plan as owner
from backend.adapters.outbound.openai import OpenAISDKResponsesTransportFactory
from backend.infrastructure.config.secrets.provider import (
    EnvironmentProviderSecretResolver,
)
from tests.calibration.pedagogical.call_plan import (
    PEDAGOGICAL_CALIBRATION_CALL_MATRIX,
    CalibrationProvider,
)
from tests.calibration.pedagogical.r3b_r3_plan import (
    FAILED_LOGICAL_SLOT_ID,
    R3B_R2_LEDGER_RELATIVE_PATH,
    R3B_R2_LEDGER_SHA256,
    R3B_R2_RAW_SHA256,
    R3B_R2_SUMMARY_SHA256,
    R4_CALL_MATRIX_SHA256,
    R4_LEDGER_RELATIVE_PATH,
    R4_MAXIMUM_BEFORE_MARGIN_USD,
    R4_PLAN_VERSION,
    R4_REQUESTED_HARD_CEILING_USD,
    R4_REUSED_EVIDENCE_MANIFEST_SHA256,
    R4_SAFETY_MARGIN_AMOUNT_USD,
    R3ConsolidationError,
    R3ConsolidationErrorCode,
    R4LedgerStatus,
    ReuseMappingClass,
    audit_r3_consolidated_evidence,
    build_r4_ledger_template,
    build_r4_remaining_call_matrix,
    consolidated_manifest_payload,
    consolidated_manifest_sha256,
    default_readiness_evidence_sha256,
    estimate_r4_cost,
    import_anthropic_readiness,
    next_executable_call_id,
    pause_after_systemic_failure,
    r3_plan_payload,
    r4_approval_text,
    r4_call_matrix_sha256,
    render_evidence_baseline_markdown,
    render_remaining_plan_json,
    render_remaining_plan_markdown,
)
from tests.providers.anthropic.transport import AnthropicSDKScoringTransportFactory

ROOT = Path(__file__).resolve().parents[2]
REQUIRES_LOCAL_EVIDENCE = pytest.mark.skipif(
    not (ROOT / R3B_R2_LEDGER_RELATIVE_PATH).exists(),
    reason="local R3B/R2 evidence is intentionally outside Git",
)


def _audit_and_calls() -> tuple[
    owner.R3ConsolidatedEvidenceAudit, tuple[owner.R4RemainingCallSpec, ...]
]:
    audit = audit_r3_consolidated_evidence(ROOT)
    calls = build_r4_remaining_call_matrix(
        tuple(item.original_logical_slot_id for item in audit.reused_mappings)
    )
    return audit, calls


@REQUIRES_LOCAL_EVIDENCE
def test_proof_sets_and_r2_canary_are_frozen_and_exactly_mapped() -> None:
    audit = audit_r3_consolidated_evidence(ROOT)

    assert audit.proof_set_sha256[R3B_R2_LEDGER_RELATIVE_PATH] == (R3B_R2_LEDGER_SHA256)
    assert R3B_R2_SUMMARY_SHA256 in audit.proof_set_sha256.values()
    assert R3B_R2_RAW_SHA256 in audit.proof_set_sha256.values()
    assert all(audit.r2_equivalence_dimensions.values())
    assert audit.r2_remediation_mapping.mapping_class is (
        ReuseMappingClass.EXACT_REMEDIATION_EQUIVALENT
    )
    assert audit.r2_remediation_mapping.original_logical_slot_id == (FAILED_LOGICAL_SLOT_ID)
    assert audit.r2_remediation_mapping.status == "SCORED"
    assert audit.r2_remediation_mapping.cost_usd == "0.005786"


def test_evidence_hash_mismatch_fails_closed(tmp_path: Path) -> None:
    relative = "artifacts/calibration/proof.json"
    path = tmp_path / relative
    path.parent.mkdir(parents=True)
    path.write_text("{}", encoding="utf-8")

    with pytest.raises(R3ConsolidationError) as mismatch:
        owner._safe_json(tmp_path, relative, "0" * 64)

    assert mismatch.value.code is R3ConsolidationErrorCode.EVIDENCE_MISMATCH


@REQUIRES_LOCAL_EVIDENCE
def test_r2_mapping_mutation_is_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    original = owner._safe_json

    def mutated(
        root: Path,
        relative_path: str,
        expected_sha256: str,
    ) -> tuple[dict[str, object], bytes]:
        value, payload = original(root, relative_path, expected_sha256)
        if relative_path == R3B_R2_LEDGER_RELATIVE_PATH:
            value = json.loads(json.dumps(value))
            value["calls"][0]["max_output_tokens"] = 511  # type: ignore[index]
        return value, payload

    monkeypatch.setattr(owner, "_safe_json", mutated)

    with pytest.raises(R3ConsolidationError) as mismatch:
        owner._audit_r3b_r2(ROOT)

    assert mismatch.value.code is R3ConsolidationErrorCode.MAPPING_MISMATCH


@REQUIRES_LOCAL_EVIDENCE
def test_nine_r3b_successes_are_reusable_and_failed_record_is_preserved() -> None:
    audit = audit_r3_consolidated_evidence(ROOT)

    assert len(audit.r3b_completed_mappings) == 9
    assert Counter(item.provider for item in audit.r3b_completed_mappings) == {
        "openai": 6,
        "anthropic": 3,
    }
    assert audit.original_failed_record_preserved is True
    assert all(item.status != "FAILED" for item in audit.reused_mappings)
    failed_slot = [
        item
        for item in audit.reused_mappings
        if item.original_logical_slot_id == FAILED_LOGICAL_SLOT_ID
    ]
    assert len(failed_slot) == 1
    assert failed_slot[0].evidence_set == "R3B-R2"


@REQUIRES_LOCAL_EVIDENCE
def test_consolidated_manifest_has_twenty_five_unique_hash_only_results() -> None:
    audit = audit_r3_consolidated_evidence(ROOT)
    manifest = consolidated_manifest_payload(audit)

    assert manifest["mapping_count"] == 25
    assert manifest["logical_slot_count"] == 25
    assert len(manifest["mappings"]) == 25  # type: ignore[arg-type]
    assert consolidated_manifest_sha256(audit) == (R4_REUSED_EVIDENCE_MANIFEST_SHA256)
    rendered = json.dumps(manifest, sort_keys=True)
    assert "raw_output_path" not in rendered
    assert "raw_output_text" not in rendered


@REQUIRES_LOCAL_EVIDENCE
def test_set_subtraction_derives_96_to_25_plus_71_without_collision() -> None:
    audit, calls = _audit_and_calls()
    original = {call.call_id for call in PEDAGOGICAL_CALIBRATION_CALL_MATRIX}
    reused = {item.original_logical_slot_id for item in audit.reused_mappings}
    remaining = {item.original_logical_slot_id for item in calls}

    assert len(original) == 96
    assert len(reused) == 25
    assert len(remaining) == 71
    assert reused.isdisjoint(remaining)
    assert reused | remaining == original


@REQUIRES_LOCAL_EVIDENCE
def test_remaining_matrix_is_anthropic_only_with_exact_category_split() -> None:
    _, calls = _audit_and_calls()

    assert Counter(call.provider for call in calls) == {CalibrationProvider.ANTHROPIC: 71}
    assert (
        sum(
            call.original_logical_slot_id.startswith("cal.score.anchor.") and call.repetition == 1
            for call in calls
        )
        == 43
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
    assert all(call.model == "claude-sonnet-5" for call in calls)
    assert all(call.max_output_tokens == 512 for call in calls)
    assert all(call.automatic_retry_count == 0 for call in calls)


@REQUIRES_LOCAL_EVIDENCE
def test_new_ids_order_and_frozen_checksum_are_deterministic() -> None:
    audit, calls = _audit_and_calls()
    manifest_sha256 = consolidated_manifest_sha256(audit)
    logical = [call.original_logical_slot_id for call in calls]

    assert len({call.r4_call_id for call in calls}) == 71
    assert all(
        call.r4_call_id == f"r4.{call.original_logical_slot_id}"
        and call.source_r3_call_id == f"r3.{call.original_logical_slot_id}"
        for call in calls
    )
    assert all(item.startswith("cal.score.anchor.") for item in logical[:59])
    assert all(item.startswith("cal.score.output.") for item in logical[59:])
    assert r4_call_matrix_sha256(calls, manifest_sha256=manifest_sha256) == (R4_CALL_MATRIX_SHA256)
    mutated = (replace(calls[0], r4_call_id="r4.mutated"), *calls[1:])
    assert r4_call_matrix_sha256(mutated, manifest_sha256=manifest_sha256) != (
        R4_CALL_MATRIX_SHA256
    )


@REQUIRES_LOCAL_EVIDENCE
def test_selected_output_dependencies_remain_six_for_twelve_scores() -> None:
    audit, calls = _audit_and_calls()

    assert len(audit.selected_output_dependencies) == 6
    assert (
        sum(call.original_logical_slot_id.startswith("cal.score.output.") for call in calls) == 12
    )


def test_readiness_is_imported_only_from_exact_hashes() -> None:
    evidence = default_readiness_evidence_sha256()

    assert import_anthropic_readiness(evidence) == "PASSED"
    changed = dict(evidence)
    changed["r3b_r2_raw"] = "0" * 64
    with pytest.raises(R3ConsolidationError) as mismatch:
        import_anthropic_readiness(changed)
    assert mismatch.value.code is R3ConsolidationErrorCode.READINESS_INVALID


@REQUIRES_LOCAL_EVIDENCE
def test_ledger_is_distinct_pending_approval_raw_free_and_retry_free() -> None:
    audit, calls = _audit_and_calls()
    ledger = build_r4_ledger_template(
        calls,
        manifest_sha256=consolidated_manifest_sha256(audit),
        matrix_sha256=R4_CALL_MATRIX_SHA256,
    )
    records = ledger["calls"]

    assert R4_LEDGER_RELATIVE_PATH == ("artifacts/calibration/12.16-g2-r3b-r4/ledger.json")
    assert ledger["approved_ceiling_usd"] is None
    assert ledger["approval_required"] is True
    assert ledger["provider_calls_attempted"] == 0
    assert ledger["automatic_retry_count"] == 0
    assert ledger["automatic_rerun_count"] == 0
    assert len(records) == 71  # type: ignore[arg-type]
    assert all(item["status"] == R4LedgerStatus.PENDING.value for item in records)  # type: ignore[union-attr]
    assert next_executable_call_id(ledger) is None
    rendered = json.dumps(ledger, sort_keys=True)
    for forbidden in (
        "raw_output_text",
        "OPENAI_API_KEY",
        "ANTHROPIC_API_KEY",
        "C:\\Users\\",
    ):
        assert forbidden not in rendered


@REQUIRES_LOCAL_EVIDENCE
def test_started_is_ambiguous_and_terminal_records_are_never_recalled() -> None:
    audit, calls = _audit_and_calls()
    ledger = build_r4_ledger_template(
        calls,
        manifest_sha256=consolidated_manifest_sha256(audit),
        matrix_sha256=R4_CALL_MATRIX_SHA256,
    )
    ledger["run_status"] = "RUNNING"
    records = ledger["calls"]
    first_id = records[0]["r4_call_id"]  # type: ignore[index]
    assert next_executable_call_id(ledger) == first_id

    records[0]["status"] = R4LedgerStatus.STARTED.value  # type: ignore[index]
    with pytest.raises(R3ConsolidationError) as started:
        next_executable_call_id(ledger)
    assert started.value.code is R3ConsolidationErrorCode.STARTED_CALL_AMBIGUOUS

    records[0]["status"] = R4LedgerStatus.COMPLETED.value  # type: ignore[index]
    assert next_executable_call_id(ledger) == records[1]["r4_call_id"]  # type: ignore[index]


@REQUIRES_LOCAL_EVIDENCE
def test_systemic_failure_pauses_and_leaves_all_future_calls_pending() -> None:
    audit, calls = _audit_and_calls()
    ledger = build_r4_ledger_template(
        calls,
        manifest_sha256=consolidated_manifest_sha256(audit),
        matrix_sha256=R4_CALL_MATRIX_SHA256,
    )
    ledger["run_status"] = "RUNNING"
    records = ledger["calls"]
    records[0]["status"] = R4LedgerStatus.STARTED.value  # type: ignore[index]
    failed_id = records[0]["r4_call_id"]  # type: ignore[index]

    paused = pause_after_systemic_failure(
        ledger,
        failed_call_id=failed_id,
        failure_code="OVERLOADED",
    )
    paused_records = paused["calls"]

    assert paused["run_status"] == "PAUSED_SYSTEMIC_FAILURE"
    assert paused["automatic_retry_count"] == 0
    assert paused_records[0]["status"] == R4LedgerStatus.FAILED.value  # type: ignore[index]
    assert all(item["status"] == R4LedgerStatus.PENDING.value for item in paused_records[1:])  # type: ignore[index]
    assert next_executable_call_id(paused) is None


@REQUIRES_LOCAL_EVIDENCE
def test_cost_ceiling_and_exact_approval_are_frozen_and_mutation_sensitive() -> None:
    audit, calls = _audit_and_calls()
    cost = estimate_r4_cost(calls)
    approval = r4_approval_text(matrix_sha256=R4_CALL_MATRIX_SHA256)

    assert cost["maximum_before_margin_usd"] == str(R4_MAXIMUM_BEFORE_MARGIN_USD)
    assert cost["safety_margin_amount_usd"] == str(R4_SAFETY_MARGIN_AMOUNT_USD)
    assert cost["requested_hard_ceiling_usd"] == str(R4_REQUESTED_HARD_CEILING_USD)
    assert R4_PLAN_VERSION in approval
    assert R4_CALL_MATRIX_SHA256 in approval
    assert "1.874400 USD" in approval
    assert r4_approval_text(matrix_sha256="0" * 64) != approval
    assert r3_plan_payload(audit)["approval_text"] == approval


@REQUIRES_LOCAL_EVIDENCE
def test_r3_rendering_never_resolves_credentials_or_builds_transport(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        EnvironmentProviderSecretResolver,
        "resolve",
        lambda *_: pytest.fail("R3 must not resolve credentials"),
    )
    monkeypatch.setattr(
        AnthropicSDKScoringTransportFactory,
        "build",
        lambda *_args, **_kwargs: pytest.fail("R3 must not build Anthropic transport"),
    )
    monkeypatch.setattr(
        OpenAISDKResponsesTransportFactory,
        "build",
        lambda *_args, **_kwargs: pytest.fail("R3 must not build OpenAI transport"),
    )

    audit = audit_r3_consolidated_evidence(ROOT)
    rendered = "\n".join(
        (
            render_evidence_baseline_markdown(audit),
            render_remaining_plan_markdown(audit),
            render_remaining_plan_json(audit),
        )
    )

    for forbidden in (
        "raw_output_text",
        "OPENAI_API_KEY",
        "ANTHROPIC_API_KEY",
        "C:\\Users\\",
        "/Users/",
        "authorization",
        "request-id",
    ):
        assert forbidden.casefold() not in rendered.casefold()
    source = (ROOT / "tests/calibration/pedagogical/r3b_r3_plan.py").read_text(encoding="utf-8")
    assert "RealCalibrationExecutor" not in source


@REQUIRES_LOCAL_EVIDENCE
def test_generated_reports_and_ignored_ledger_match_deterministic_renderers() -> None:
    audit, calls = _audit_and_calls()
    manifest_sha256 = consolidated_manifest_sha256(audit)

    assert (ROOT / owner.R3_EVIDENCE_REPORT_RELATIVE_PATH).read_text(
        encoding="utf-8"
    ) == render_evidence_baseline_markdown(audit) + "\n"
    assert (ROOT / owner.R3_PLAN_MARKDOWN_RELATIVE_PATH).read_text(
        encoding="utf-8"
    ) == render_remaining_plan_markdown(audit) + "\n"
    assert (ROOT / owner.R3_PLAN_JSON_RELATIVE_PATH).read_text(
        encoding="utf-8"
    ) == render_remaining_plan_json(audit)
    ledger = json.loads((ROOT / R4_LEDGER_RELATIVE_PATH).read_text(encoding="utf-8"))
    template = build_r4_ledger_template(
        calls,
        manifest_sha256=manifest_sha256,
        matrix_sha256=R4_CALL_MATRIX_SHA256,
    )
    immutable_ledger_keys = {
        "plan_version",
        "matrix_sha256",
        "requested_hard_ceiling_usd",
        "reused_evidence_manifest_sha256",
        "reused_slot_count",
        "anthropic_readiness",
        "anthropic_readiness_evidence_sha256",
        "automatic_retry_count",
        "automatic_rerun_count",
        "stop_on_first_systemic_failure",
        "systemic_failure_codes",
    }
    assert {key: ledger[key] for key in immutable_ledger_keys} == {
        key: template[key] for key in immutable_ledger_keys
    }
    mutable_call_keys = {
        "status",
        "started_at",
        "completed_at",
        "closed_error_code",
        "cost_usd",
        "raw_output_path",
        "raw_output_sha256",
    }
    for actual, planned in zip(ledger["calls"], template["calls"], strict=True):
        immutable_call_keys = set(planned) - mutable_call_keys
        assert {key: actual[key] for key in immutable_call_keys} == {
            key: planned[key] for key in immutable_call_keys
        }
