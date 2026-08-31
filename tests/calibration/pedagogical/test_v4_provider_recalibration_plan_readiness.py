from __future__ import annotations

import ast
import hashlib

from tests.calibration.pedagogical.v4_provider_recalibration_plan_readiness import (
    APPROVED_HARD_CEILING_USD,
    CORRECTED_FORM_SHA256,
    ENTRY_HEAD,
    EXPECTED_MATRIX_SHA256,
    EXPECTED_V4_CORPUS_SHA256,
    LIVE_BLOCKERS,
    ROOT,
    RUNNER_REVALIDATED_CEILING_USD,
    build_readiness_payload,
)

OWNER = (
    ROOT
    / "tests/calibration/pedagogical/"
    "v4_provider_recalibration_plan_readiness.py"
)


def test_t1_v4_baseline_and_corrective_closure_are_immutable() -> None:
    payload = build_readiness_payload(ROOT)
    baseline = payload["baseline"]
    assert baseline == {
        "branch": "phase12/12-16-provider-model-calibration",
        "head": ENTRY_HEAD,
        "main": "7ae02ee109bcc6399ec0f71616da6aef07abda81",
        "corrected_form_sha256": CORRECTED_FORM_SHA256,
        "corpus_version": "12.16-g1-v4",
        "corpus_sha256": EXPECTED_V4_CORPUS_SHA256,
        "closure": "PASS",
        "trace": "PASS",
        "gate_a": "PASS",
        "gate_b": "PASS",
        "status": "PASS",
    }


def test_t1_static_matrix_inventory_is_exact_and_secret_free() -> None:
    matrix = build_readiness_payload(ROOT)["matrix"]
    assert matrix["plan_version"] == "12.16-g2-v4-plan-v1"
    assert matrix["matrix_sha256"] == EXPECTED_MATRIX_SHA256
    assert matrix["matrix_sha256_expected"] == EXPECTED_MATRIX_SHA256
    assert matrix["call_count"] == 102
    assert matrix["openai_call_count"] == 20
    assert matrix["anthropic_call_count"] == 82
    assert matrix["duplicate_call_id_count"] == 0
    assert matrix["models"] == {
        "claude-sonnet-5": 82,
        "gpt-5.6-sol": 10,
        "gpt-5.6-terra": 10,
    }
    assert matrix["raw_output_directory"] == "artifacts/calibration/12.16-g2/raw"
    assert matrix["estimated_maximum_with_margin_usd"] == "3.251640"
    assert matrix["contains_secret_marker"] is False


def test_t1_matrix_is_bound_to_the_v4_anchor_corpus() -> None:
    matrix = build_readiness_payload(ROOT)["matrix"]
    assert matrix["anchor_scoring_ref_count"] == 24
    assert matrix["v4_anchor_count"] == 24
    assert matrix["v4_anchor_ref_intersection_count"] == 24
    assert matrix["v4_anchor_binding"] is True


def test_t1_pricing_is_consistent_and_still_requires_owner_approval() -> None:
    pricing = build_readiness_payload(ROOT)["pricing"]
    assert pricing["matrix"]["claude-sonnet-5"] == {
        "provider": "anthropic",
        "input_usd_per_million_tokens": "2.00",
        "cached_input_usd_per_million_tokens": "0.20",
        "output_usd_per_million_tokens": "10.00",
    }
    assert pricing["runner"]["claude-sonnet-5"] == {
        "provider": "anthropic",
        "input_usd_per_million_tokens": "2.00",
        "cached_input_usd_per_million_tokens": "0.20",
        "output_usd_per_million_tokens": "10.00",
    }
    assert pricing["consistent"] is True
    assert pricing["matrix_ceiling_usd"] == str(APPROVED_HARD_CEILING_USD)
    assert pricing["runner_ceiling_usd"] == str(RUNNER_REVALIDATED_CEILING_USD)


def test_t1_runner_guards_are_reported_without_overstating_readiness() -> None:
    runner = build_readiness_payload(ROOT)["runner"]
    assert runner["matrix_checksum_guard"] is True
    assert runner["credential_presence_guard"] is True
    assert runner["explicit_live_flag_guard"] is True
    assert runner["raw_output_path_guard"] is True
    assert runner["approved_ceiling_guard"] is True
    assert runner["gitignore_guard"] is True
    assert runner["atomic_ledger_present"] is True
    assert runner["call_identity_guard"] is True
    assert runner["report_redaction_guard"] is True
    assert runner["canary_breaker_present"] is True
    assert runner["canary_breaker_instantiations"] == 1
    assert runner["canary_integrated_in_run"] is True
    assert runner["v4_baseline_guard"] is True
    assert runner["pricing_consistency_guard"] is True
    assert runner["v4_metrics_bound"] is True
    assert runner["legacy_report_entry_head"] is False
    assert runner["legacy_human_review_status"] is False
    assert runner["pairwise_selected_output_implemented"] is True


def test_t1_plan_is_ready_for_owner_approval_but_live_remains_false() -> None:
    payload = build_readiness_payload(ROOT)
    assert payload["static_matrix_audit"] == "PASS"
    assert payload["provider_recalibration_plan_ready"] == "PASS"
    assert payload["implementation_live_readiness"] == (
        "READY_CONFIG_APPROVED_LIVE_NOT_AUTHORIZED"
    )
    assert payload["live_provider_recalibration_authorized"] is False
    assert tuple(payload["live_blockers"]) == LIVE_BLOCKERS
    assert not any(payload["live_blocker_evidence"].values())
    assert payload["remaining_live_blockers"] == (
        "EXPLICIT_LIVE_OWNER_AUTHORIZATION",
    )
    assert payload["provider_calls"] == 0
    assert payload["provider_cost_usd"] == "0"
    assert payload["credential_resolution"] == "NOT_PERFORMED"
    assert payload["transport_construction"] == "NOT_PERFORMED"
    assert payload["runtime_route_change"] == "NONE"
    assert payload["corpus_change"] == "NONE"
    assert payload["attestation_change"] == "NONE"


def test_t1_audit_owner_cannot_construct_or_call_provider_clients() -> None:
    source = OWNER.read_text(encoding="utf-8")
    tree = ast.parse(source)
    imports: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imports.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imports.add(node.module)
    assert not any(name == "backend" or name.startswith("backend.") for name in imports)
    assert not any(name == "openai" or name.startswith("openai.") for name in imports)
    assert not any(name == "anthropic" or name.startswith("anthropic.") for name in imports)
    forbidden_calls = (
        "run_live_calibration(",
        "RealCalibrationExecutor(",
        "OpenAIResponsesTransportFactory(",
        "AnthropicMessagesTransportFactory(",
    )
    assert all(marker not in source for marker in forbidden_calls)


def test_t1_handoff_manifest_and_decision_are_exact() -> None:
    directory = (
        ROOT
        / "docs/development/"
        "phase_12_16_g2_v4_provider_recalibration_plan_ready"
    )
    manifest = (directory / "MANIFEST_SHA256.txt").read_text(
        encoding="utf-8"
    )
    entries = tuple(line.split("  ", 1) for line in manifest.splitlines())
    assert len(entries) == 10
    for expected_sha256, relative_path in entries:
        assert hashlib.sha256((ROOT / relative_path).read_bytes()).hexdigest() == (
            expected_sha256
        )
    handoff = (directory / "06_FINAL_HANDOFF.md").read_text(encoding="utf-8")
    assert "PROVIDER_RECALIBRATION_PLAN_READY = PASS" in handoff
    assert "IMPLEMENTATION_LIVE_READINESS = NO_GO" in handoff
    assert "LIVE_PROVIDER_RECALIBRATION_AUTHORIZED = FALSE" in handoff
    assert "PROVIDER_CALLS = 0" in handoff
    assert all(blocker in handoff for blocker in LIVE_BLOCKERS)
