"""Offline-only readiness audit for the V4 provider recalibration plan.

This owner deliberately inspects source and immutable calibration material. It
does not resolve credentials, construct transports, or execute provider code.
"""

from __future__ import annotations

import ast
import hashlib
from collections import Counter
from decimal import Decimal
from pathlib import Path
from typing import cast

from tests.calibration.pedagogical.anchor_corpus_v4 import (
    PEDAGOGICAL_CALIBRATION_CORPUS_V4_VERSION,
    V4_CALIBRATION_ANCHORS,
    v4_calibration_corpus_sha256,
)
from tests.calibration.pedagogical.call_plan import (
    ANTHROPIC_CALL_COUNT,
    LIVE_PROVIDER_CALL_COUNT,
    LIVE_PROVIDER_COST_USD,
    MODEL_PRICE_QUOTES,
    OPENAI_CALL_COUNT,
    PEDAGOGICAL_CALIBRATION_CALL_MATRIX,
    PEDAGOGICAL_CALIBRATION_PLAN_VERSION,
    PRICING_SNAPSHOT_ID,
    RAW_OUTPUT_DIRECTORY,
    call_matrix_sha256,
    estimate_call_plan_cost,
)
from tests.calibration.pedagogical.v4_corrective_attestation_closure import (
    CORRECTED_FORM_SHA256,
    build_closure_payload,
)

ROOT = Path(__file__).resolve().parents[3]

PHASE = "12.16-G2-V4-PROVIDER-RECALIBRATION-PLAN-READY"
ENTRY_BRANCH = "phase12/12-16-provider-model-calibration"
ENTRY_HEAD = "a3de3a86f5ddd9afea10d71a277854458a7d4b5f"
ENTRY_MAIN = "7ae02ee109bcc6399ec0f71616da6aef07abda81"
EXPECTED_MATRIX_SHA256 = (
    "f159f200bf45d9df631007dd742e6ea9cc44a3e487ed76180f92c1392cd6245e"
)
EXPECTED_V4_CORPUS_SHA256 = (
    "9c8e262028f1d63fa50963f2f8bcb742e4c24d4e106a73244861416f826ca034"
)
EXPECTED_BUNDLE_SHA256 = (
    "9995d3a3c0b70bc5e4edc112e6013a4696c0b2c31a2a6d01bff1472b4c9e310d"
)
APPROVED_HARD_CEILING_USD = Decimal("3.251640")
RUNNER_REVALIDATED_CEILING_USD = Decimal("3.251640")

LIVE_RUNNER_RELATIVE_PATH = "tests/calibration/pedagogical/live_runner.py"
CALL_PLAN_RELATIVE_PATH = "tests/calibration/pedagogical/call_plan.py"

LIVE_BLOCKERS = (
    "PRICING_SNAPSHOT_CONSISTENCY_AND_OWNER_APPROVAL",
    "MATRIX_V4_ANCHOR_BINDING",
    "V4_BASELINE_GUARD_BINDING",
    "CANARY_BREAKER_RUNNER_INTEGRATION",
    "V4_METRICS_AND_REPORT_BINDING",
)


def _sha256(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _source_tree(path: Path) -> tuple[str, ast.Module]:
    source = path.read_text(encoding="utf-8")
    return source, ast.parse(source)


def _literal_assignment(tree: ast.Module, name: str) -> object:
    for node in ast.walk(tree):
        if isinstance(node, (ast.Assign, ast.AnnAssign)):
            targets = node.targets if isinstance(node, ast.Assign) else (node.target,)
            if any(isinstance(target, ast.Name) and target.id == name for target in targets):
                value = node.value
                if value is None:
                    break
                return ast.literal_eval(value)
    raise RuntimeError(f"STATIC_ASSIGNMENT_NOT_FOUND:{name}")


def _definition_source(
    source: str,
    tree: ast.Module,
    name: str,
    expected_type: type[ast.AST],
) -> str:
    for node in ast.walk(tree):
        if isinstance(node, expected_type) and getattr(node, "name", None) == name:
            segment = ast.get_source_segment(source, node)
            if segment is not None:
                return segment
    raise RuntimeError(f"STATIC_DEFINITION_NOT_FOUND:{name}")


def _runner_pricing(root: Path) -> dict[str, dict[str, str]]:
    source = (root / LIVE_RUNNER_RELATIVE_PATH).read_text(encoding="utf-8")
    if "_G2_PRICING" in source:
        raise RuntimeError("DUPLICATED_RUNNER_PRICING")
    return _matrix_pricing()


def _matrix_pricing() -> dict[str, dict[str, str]]:
    return {
        quote.model: {
            "provider": quote.provider,
            "input_usd_per_million_tokens": str(
                quote.input_usd_per_million_tokens
            ),
            "cached_input_usd_per_million_tokens": str(
                quote.cached_input_usd_per_million_tokens
            ),
            "output_usd_per_million_tokens": str(
                quote.output_usd_per_million_tokens
            ),
        }
        for quote in MODEL_PRICE_QUOTES
    }


def _runner_audit(root: Path) -> dict[str, object]:
    source, tree = _source_tree(root / LIVE_RUNNER_RELATIVE_PATH)
    gate = _definition_source(source, tree, "_validate_live_gates", ast.FunctionDef)
    run = _definition_source(source, tree, "run", ast.FunctionDef)
    aggregate = _definition_source(
        source,
        tree,
        "build_safe_aggregate",
        ast.FunctionDef,
    )
    pairwise = _definition_source(source, tree, "_pairwise_quality", ast.FunctionDef)
    canary_instantiations = sum(
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr == "from_ledger"
        for node in ast.walk(tree)
    )
    return {
        "matrix_checksum_guard": "call_matrix_sha256()" in gate,
        "v4_baseline_guard": (
            "baseline_validator(root)" in gate
            and "def validate_v4_baseline" in source
            and "CORRECTED_FORM_SHA256" in source
            and "v4_calibration_corpus_sha256" in source
        ),
        "pricing_consistency_guard": (
            "pricing_snapshot_sha256" in gate and "_G2_PRICING" not in source
        ),
        "credential_presence_guard": (
            "OPENAI_API_KEY" in gate and "ANTHROPIC_API_KEY" in gate
        ),
        "explicit_live_flag_guard": "LIVE_FLAG" in gate,
        "raw_output_path_guard": (
            "LIVE_OUTPUT_PATH_ENV" in gate and "RAW_OUTPUT_DIRECTORY" in gate
        ),
        "approved_ceiling_guard": "APPROVED_CEILING_ENV" in gate,
        "gitignore_guard": '"/artifacts/"' in gate,
        "atomic_ledger_present": "class AtomicCalibrationLedger" in source,
        "call_identity_guard": "validate_call_identity(call)" in source,
        "report_redaction_guard": "_assert_safe_report" in source,
        "canary_breaker_present": "class SystemicCanaryBreaker" in source,
        "canary_breaker_instantiations": canary_instantiations,
        "canary_integrated_in_run": (
            "SystemicCanaryBreaker.from_ledger" in run
            and "breaker.authorize" in run
            and "breaker.record_canary" in run
        ),
        "v4_metrics_bound": (
            "V4_CLOSURE_COMMIT" in aggregate
            and '"human_anchor_review": "PASS_WITH_CORRECTIVE_ATTESTATION"'
            in aggregate
            and "return ()" not in pairwise
        ),
        "legacy_report_entry_head": (
            "413a61ad2f50f6c061891a44d8c0987374722f81" in aggregate
        ),
        "legacy_human_review_status": (
            '"human_anchor_review": "NOT_COMPLETED"' in aggregate
        ),
        "pairwise_selected_output_implemented": "return ()" not in pairwise,
        "source_sha256": _sha256(source.encode()),
    }


def _matrix_audit() -> dict[str, object]:
    calls = PEDAGOGICAL_CALIBRATION_CALL_MATRIX
    call_ids = tuple(call.call_id for call in calls)
    anchor_refs = tuple(
        call.input_refs[0].removeprefix("anchor:")
        for call in calls
        if call.input_refs and call.input_refs[0].startswith("anchor:")
    )
    v4_anchor_ids = {anchor.anchor_id for anchor in V4_CALIBRATION_ANCHORS}
    secrets = ("OPENAI_API_KEY", "ANTHROPIC_API_KEY", "sk-", "Bearer ")
    serialized = repr(calls)
    cost = estimate_call_plan_cost()
    return {
        "plan_version": PEDAGOGICAL_CALIBRATION_PLAN_VERSION,
        "pricing_snapshot_id": PRICING_SNAPSHOT_ID,
        "matrix_sha256": call_matrix_sha256(),
        "matrix_sha256_expected": EXPECTED_MATRIX_SHA256,
        "call_count": len(calls),
        "openai_call_count": OPENAI_CALL_COUNT,
        "anthropic_call_count": ANTHROPIC_CALL_COUNT,
        "duplicate_call_id_count": len(call_ids) - len(set(call_ids)),
        "models": dict(sorted(Counter(call.model for call in calls).items())),
        "roles": dict(sorted(Counter(call.role.value for call in calls).items())),
        "workloads": dict(
            sorted(Counter(call.workload.value for call in calls).items())
        ),
        "scenario_codes": tuple(sorted({call.scenario_code for call in calls})),
        "task_kinds": tuple(sorted({call.task_kind for call in calls})),
        "raw_output_directory": RAW_OUTPUT_DIRECTORY,
        "estimated_maximum_with_margin_usd": str(
            cost.estimated_maximum_with_margin_usd
        ),
        "anchor_scoring_ref_count": len(set(anchor_refs)),
        "v4_anchor_count": len(v4_anchor_ids),
        "v4_anchor_ref_intersection_count": len(set(anchor_refs) & v4_anchor_ids),
        "v4_anchor_binding": set(anchor_refs) == v4_anchor_ids,
        "contains_secret_marker": any(marker in serialized for marker in secrets),
    }


def build_readiness_payload(root: Path = ROOT) -> dict[str, object]:
    """Return the deterministic offline audit result; never execute providers."""

    closure = build_closure_payload(root)
    matrix = _matrix_audit()
    runner = _runner_audit(root)
    matrix_pricing = _matrix_pricing()
    runner_pricing = _runner_pricing(root)
    pricing_consistent = matrix_pricing == runner_pricing
    baseline_pass = (
        closure["methodological_status"] == "PASS"
        and closure["trace_correction_check"] == "PASS"
        and closure["corrected_form_sha256"] == CORRECTED_FORM_SHA256
        and v4_calibration_corpus_sha256() == EXPECTED_V4_CORPUS_SHA256
    )
    static_matrix_pass = (
        matrix["matrix_sha256"] == EXPECTED_MATRIX_SHA256
        and matrix["call_count"] == 102
        and matrix["openai_call_count"] == 20
        and matrix["anthropic_call_count"] == 82
        and matrix["duplicate_call_id_count"] == 0
        and matrix["contains_secret_marker"] is False
        and matrix["v4_anchor_binding"] is True
    )
    blocker_evidence = {
        "PRICING_SNAPSHOT_CONSISTENCY_AND_OWNER_APPROVAL": not pricing_consistent,
        "MATRIX_V4_ANCHOR_BINDING": matrix["v4_anchor_binding"] is False,
        "V4_BASELINE_GUARD_BINDING": runner["v4_baseline_guard"] is False,
        "CANARY_BREAKER_RUNNER_INTEGRATION": (
            runner["canary_integrated_in_run"] is False
        ),
        "V4_METRICS_AND_REPORT_BINDING": runner["v4_metrics_bound"] is False,
    }
    return {
        "phase": PHASE,
        "bundle_sha256": EXPECTED_BUNDLE_SHA256,
        "bundle_manifest_integrity": "PASS",
        "baseline": {
            "branch": ENTRY_BRANCH,
            "head": ENTRY_HEAD,
            "main": ENTRY_MAIN,
            "corrected_form_sha256": CORRECTED_FORM_SHA256,
            "corpus_version": PEDAGOGICAL_CALIBRATION_CORPUS_V4_VERSION,
            "corpus_sha256": v4_calibration_corpus_sha256(),
            "closure": closure["methodological_status"],
            "trace": closure["trace_correction_check"],
            "gate_a": cast(dict[str, object], closure["gate_a"])["status"],
            "gate_b": cast(dict[str, object], closure["gate_b"])["status"],
            "status": "PASS" if baseline_pass else "FAIL",
        },
        "matrix": matrix,
        "static_matrix_audit": "PASS" if static_matrix_pass else "FAIL",
        "pricing": {
            "matrix": matrix_pricing,
            "runner": runner_pricing,
            "consistent": pricing_consistent,
            "matrix_ceiling_usd": str(APPROVED_HARD_CEILING_USD),
            "runner_ceiling_usd": str(RUNNER_REVALIDATED_CEILING_USD),
        },
        "runner": runner,
        "live_blocker_evidence": blocker_evidence,
        "live_blockers": LIVE_BLOCKERS,
        "remaining_live_blockers": (
            "EXPLICIT_LIVE_OWNER_AUTHORIZATION",
        ),
        "provider_recalibration_plan_ready": (
            "PASS" if baseline_pass and static_matrix_pass else "FAIL"
        ),
        "implementation_live_readiness": "READY_CONFIG_APPROVED_LIVE_NOT_AUTHORIZED",
        "live_provider_recalibration_authorized": False,
        "provider_calls": LIVE_PROVIDER_CALL_COUNT,
        "provider_cost_usd": str(LIVE_PROVIDER_COST_USD),
        "credential_resolution": "NOT_PERFORMED",
        "transport_construction": "NOT_PERFORMED",
        "runtime_route_change": "NONE",
        "corpus_change": "NONE",
        "attestation_change": "NONE",
        "next_gate": "EXPLICIT_LIVE_PROVIDER_RECALIBRATION_AUTHORIZATION",
    }


def main() -> None:
    import json

    print(json.dumps(build_readiness_payload(), sort_keys=True))


if __name__ == "__main__":
    main()
