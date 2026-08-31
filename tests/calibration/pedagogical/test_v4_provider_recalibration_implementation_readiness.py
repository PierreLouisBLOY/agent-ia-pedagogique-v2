from __future__ import annotations

import ast
from decimal import Decimal

from tests.calibration.pedagogical.v4_provider_recalibration_implementation_readiness import (
    ROOT,
    build_implementation_readiness_payload,
)

OWNER = (
    ROOT
    / "tests/calibration/pedagogical/"
    "v4_provider_recalibration_implementation_readiness.py"
)


def test_t1_all_implementation_gates_pass_offline() -> None:
    payload = build_implementation_readiness_payload(ROOT)
    assert payload["bundle_manifest_integrity"] == "PASS"
    assert payload["gates"] == {
        "v4_anchor_matrix": "PASS",
        "v4_baseline_guard": "PASS",
        "canary_integration": "PASS",
        "pricing_consistency": "PASS",
        "v4_reporting_pairwise": "PASS",
        "owner_configuration_binding": "PASS",
    }


def test_t1_matrix_pricing_and_pairwise_projection_are_exact() -> None:
    payload = build_implementation_readiness_payload(ROOT)
    assert payload["matrix"] == {
        "version": "12.16-g2-v4-plan-v1",
        "sha256": "f159f200bf45d9df631007dd742e6ea9cc44a3e487ed76180f92c1392cd6245e",
        "call_count": 102,
        "openai_call_count": 20,
        "anthropic_call_count": 82,
        "v4_anchor_count": 24,
        "legacy_anchor_count": 0,
        "anchor_score_call_count": 48,
        "strong_repeat_call_count": 16,
        "output_score_call_count": 18,
        "pairwise_comparison_count": 6,
    }
    pricing = payload["pricing"]
    assert pricing["snapshot_id"] == "official-2026-08-31-v4"  # type: ignore[index]
    assert pricing["snapshot_sha256"] == (  # type: ignore[index]
        "31f2a9287845da8986448f62abe312b2290af5e9578ff61643d1cb0045bfe1b8"
    )
    assert Decimal(pricing["proposed_technical_ceiling_usd"]) == Decimal(  # type: ignore[index]
        "3.251640"
    )
    assert Decimal(pricing["approved_hard_ceiling_usd"]) == Decimal(  # type: ignore[index]
        "3.251640"
    )


def test_t1_owner_configuration_is_approved_but_never_authorizes_live() -> None:
    payload = build_implementation_readiness_payload(ROOT)
    assert payload["owner_configuration"] == {
        "approval": "APPROVED",
        "matrix_sha256": (
            "f159f200bf45d9df631007dd742e6ea9cc44a3e487ed76180f92c1392cd6245e"
        ),
        "pricing_sha256": (
            "31f2a9287845da8986448f62abe312b2290af5e9578ff61643d1cb0045bfe1b8"
        ),
        "max_call_count": 102,
        "approved_hard_ceiling_usd": "3.251640",
        "live_provider_recalibration_authorized": False,
    }
    assert payload["implementation_live_readiness"] == (
        "READY_CONFIG_APPROVED_LIVE_NOT_AUTHORIZED"
    )
    assert payload["live_provider_recalibration_authorized"] is False
    assert payload["provider_calls"] == 0
    assert payload["credentials_resolved"] is False
    assert payload["transport_constructed"] is False
    assert payload["runtime_route_change"] == "NONE"
    assert payload["corpus_change"] == "NONE"
    assert payload["attestation_change"] == "NONE"
    assert payload["commit"] == "NONE"
    assert payload["push"] == "NONE"


def test_t1_readiness_owner_has_no_provider_or_runtime_import() -> None:
    tree = ast.parse(OWNER.read_text(encoding="utf-8"))
    imports: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imports.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imports.add(node.module)
    assert not any(name == "backend" or name.startswith("backend.") for name in imports)
    source = OWNER.read_text(encoding="utf-8")
    assert "run_live_calibration(" not in source
    assert "RealCalibrationExecutor(" not in source
