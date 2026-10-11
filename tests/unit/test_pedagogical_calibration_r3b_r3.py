from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

import pytest

import tests.calibration.pedagogical.r3b_r3_plan as owner
from backend.adapters.outbound.openai import OpenAISDKResponsesTransportFactory
from backend.infrastructure.config.secrets.provider import (
    EnvironmentProviderSecretResolver,
)
from tests.calibration.pedagogical.legacy_call_plan import (
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
    R4_REUSED_EVIDENCE_MANIFEST_SHA256,
    R3ConsolidationError,
    R3ConsolidationErrorCode,
    R4LedgerStatus,
    ReuseMappingClass,
    audit_r3_consolidated_evidence,
    build_r4_ledger_template,
    build_r4_remaining_call_matrix,
    consolidated_manifest_sha256,
    default_readiness_evidence_sha256,
    import_anthropic_readiness,
    next_executable_call_id,
    pause_after_systemic_failure,
    r3_plan_payload,
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
def test_consolidated_manifest_has_twenty_five_unique_hash_only_results(tmp_path: Path) -> None:
    from tests.support.historical_calibration_replay import replay_historical_report

    result = replay_historical_report(ROOT, tmp_path, "tests/unit/test_pedagogical_calibration_r3b_r3.py::test_consolidated_manifest_has_twenty_five_unique_hash_only_results")
    assert result.returncode == 0, result.stdout.decode("utf-8", errors="replace")
    assert b"1 passed" in result.stdout


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
def test_new_ids_order_and_frozen_checksum_are_deterministic(tmp_path: Path) -> None:
    from tests.support.historical_calibration_replay import replay_historical_report

    result = replay_historical_report(ROOT, tmp_path, "tests/unit/test_pedagogical_calibration_r3b_r3.py::test_new_ids_order_and_frozen_checksum_are_deterministic")
    assert result.returncode == 0, result.stdout.decode("utf-8", errors="replace")
    assert b"1 passed" in result.stdout


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
def test_cost_ceiling_and_exact_approval_are_frozen_and_mutation_sensitive(tmp_path: Path) -> None:
    from tests.support.historical_calibration_replay import replay_historical_report

    result = replay_historical_report(ROOT, tmp_path, "tests/unit/test_pedagogical_calibration_r3b_r3.py::test_cost_ceiling_and_exact_approval_are_frozen_and_mutation_sensitive")
    assert result.returncode == 0, result.stdout.decode("utf-8", errors="replace")
    assert b"1 passed" in result.stdout


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
def test_generated_reports_and_ignored_ledger_match_deterministic_renderers(tmp_path: Path) -> None:
    from tests.support.historical_calibration_replay import replay_historical_report

    result = replay_historical_report(ROOT, tmp_path, "tests/unit/test_pedagogical_calibration_r3b_r3.py::test_generated_reports_and_ignored_ledger_match_deterministic_renderers")
    assert result.returncode == 0, result.stdout.decode("utf-8", errors="replace")
    assert b"1 passed" in result.stdout


@REQUIRES_LOCAL_EVIDENCE
def test_current_revalidation_checksums_do_not_reauthorize_historical_plan() -> None:
    audit, calls = _audit_and_calls()
    current_manifest = consolidated_manifest_sha256(audit)
    current_matrix = r4_call_matrix_sha256(calls, manifest_sha256=current_manifest)
    assert R4_REUSED_EVIDENCE_MANIFEST_SHA256 == "b9eb583ccf5c6fcbc6b7b5d4491dd74a53889ffd92521b3270f9984f61d12aa9"
    assert R4_CALL_MATRIX_SHA256 == "0298e4672f03def781bf7217b37567a456d6865aa35c157c4d956111962c7d8d"
    assert current_manifest == "63e983cb3c3229139698c65b4d7a711d798ca0a4754ab7b82d0cdaafbed91ce1"
    assert current_matrix == "861693f6f3217012ad1c3ab0623ca6bd1398903d6875fabeb3752d33f9f4d75c"
    assert current_manifest != R4_REUSED_EVIDENCE_MANIFEST_SHA256
    assert current_matrix != R4_CALL_MATRIX_SHA256
    assert current_matrix in r3_plan_payload(audit)["approval_text"]
    assert R4_CALL_MATRIX_SHA256 not in r3_plan_payload(audit)["approval_text"]


@pytest.mark.parametrize("target", ["", "../outside.py::test", "backend/unknown.py::test", "tests/unit/test_r5_scope_guard.py::test"])
def test_historical_calibration_unknown_target_is_refused_before_files(tmp_path, target):
    from tests.support.historical_calibration_replay import replay_historical_report

    with pytest.raises(ValueError, match="HISTORICAL_CALIBRATION_TARGET_REJECTED"):
        replay_historical_report(tmp_path, tmp_path, target)


def test_historical_calibration_missing_private_evidence_is_not_hidden(tmp_path):
    from tests.support.historical_calibration_replay import replay_historical_report

    with pytest.raises(ValueError, match="HISTORICAL_CALIBRATION_321_PRIVATE_FILES_REQUIRED"):
        replay_historical_report(tmp_path, tmp_path)


def test_unknown_historical_fabrication_is_refused_before_git(tmp_path):
    from tests.support.historical_guard_fixture import materialize_historical_guard_sources

    target = tmp_path / "not-created"
    with pytest.raises(ValueError, match="HISTORICAL_FABRICATION_REJECTED"):
        materialize_historical_guard_sources(target, "0" * 40)
    assert not target.exists()
