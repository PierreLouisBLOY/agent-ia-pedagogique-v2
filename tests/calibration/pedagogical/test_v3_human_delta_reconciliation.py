from __future__ import annotations

import hashlib
import json
import shutil
from pathlib import Path

import pytest

from tests.calibration.pedagogical.anchor_corpus_v3 import (
    build_delta_reconciliation_key,
)
from tests.calibration.pedagogical.v2_human_prevalidation_reconciliation import (
    COMPLETED_PREVALIDATION_RELATIVE_PATH as V2_COMPLETED_RELATIVE_PATH,
)
from tests.calibration.pedagogical.v2_human_prevalidation_reconciliation import (
    PACKET_RELATIVE_PATH as V2_PACKET_RELATIVE_PATH,
)
from tests.calibration.pedagogical.v2_human_prevalidation_reconciliation import (
    RECONCILIATION_KEY_RELATIVE_PATH as V2_KEY_RELATIVE_PATH,
)
from tests.calibration.pedagogical.v3_human_delta_reconciliation import (
    COMPLETED_DELTA_PREVALIDATION_RELATIVE_PATH,
    EXPECTED_COMPLETED_DELTA_PREVALIDATION_SHA256,
    EXPECTED_CORPUS_SHA256,
    EXPECTED_PACKET_SHA256,
    EXPECTED_RECONCILIATION_KEY_SHA256,
    PACKET_RELATIVE_PATH,
    RECONCILIATION_KEY_RELATIVE_PATH,
    REPORT_RELATIVE_PATH,
    RESULT_JSON_RELATIVE_PATH,
    V2_CARRY_FORWARD_SCENARIOS,
    V3_DELTA_SCENARIOS,
    V3HumanDeltaError,
    V3HumanDeltaErrorCode,
    build_reconciliation_payload,
    render_report_markdown,
    render_result_json,
    write_outputs,
)

ROOT = Path(__file__).resolve().parents[3]


def _delta_root(tmp_path: Path, *, include_v2: bool = False) -> Path:
    paths = [
        PACKET_RELATIVE_PATH,
        COMPLETED_DELTA_PREVALIDATION_RELATIVE_PATH,
        RECONCILIATION_KEY_RELATIVE_PATH,
    ]
    if include_v2:
        paths.extend(
            (
                V2_PACKET_RELATIVE_PATH,
                V2_COMPLETED_RELATIVE_PATH,
                V2_KEY_RELATIVE_PATH,
            )
        )
    for relative_path in paths:
        source = ROOT / relative_path
        target = tmp_path / relative_path
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)
    return tmp_path


def test_owner_approved_delta_source_proofs_are_exact() -> None:
    payload = build_reconciliation_payload(ROOT)
    proofs = payload["source_proofs"]
    assert proofs["completed_delta_prevalidation_sha256"] == (
        EXPECTED_COMPLETED_DELTA_PREVALIDATION_SHA256
    )
    assert proofs["packet_sha256"] == EXPECTED_PACKET_SHA256
    assert proofs["reconciliation_key_sha256"] == EXPECTED_RECONCILIATION_KEY_SHA256
    assert proofs["corpus_sha256"] == EXPECTED_CORPUS_SHA256
    assert proofs["owner_checksum_override"] == "APPROVED"
    assert payload["review_metadata"] == {
        "review_status": "COMPLETED",
        "reviewer_code": "OWNER_HUMAN_REVIEWER",
        "review_date": "2026-08-30",
        "closure_date_declared": "30/08/26",
        "responsible_code": "OWNER",
        "grid_version": "human-delta-prevalidation-v3",
        "item_count": 15,
        "structure_decision_count": 15,
        "criterion_appreciation_count": 30,
        "action_decision_count": 15,
        "global_opinion": "RÉVISIONS_REQUISES",
        "exposure_declaration": (
            "OUI — revue v2 effectuée, résultats v2 connus et décision STRONG_ONLY "
            "connue ; aucun mapping HPV3D→tier, aucune clé locale v3 et aucun "
            "résultat fournisseur v3 consultés pendant cette revue."
        ),
        "exposure_class": "V2_RESULTS_EXPOSED_V3_MAPPING_AND_RESULTS_BLIND",
    }


@pytest.mark.parametrize("mutation", ["action", "label", "content"])
def test_invalid_delta_stops_before_key_access(
    tmp_path: Path,
    mutation: str,
) -> None:
    root = _delta_root(tmp_path)
    review_path = root / COMPLETED_DELTA_PREVALIDATION_RELATIVE_PATH
    text = review_path.read_text(encoding="utf-8")
    if mutation == "action":
        text = text.replace(
            "- Action demandée : [x] aucune [ ] révision [ ] exclusion",
            "- Action demandée : [x] aucune [x] révision [ ] exclusion",
            1,
        )
        expected_error = V3HumanDeltaErrorCode.DELTA_REVIEW_INCOMPLETE
    elif mutation == "label":
        text = text.replace(":SATISFAISANT", ":EXCELLENT", 1)
        expected_error = V3HumanDeltaErrorCode.DELTA_REVIEW_INCOMPLETE
    else:
        text = text.replace(
            "Une ressource synthétique de management indique un titre",
            "Une ressource synthétique de management mentionne un titre",
            1,
        )
        expected_error = V3HumanDeltaErrorCode.DELTA_REVIEW_TEMPLATE_MUTATED
    review_path.write_text(text, encoding="utf-8")
    expected_sha256 = hashlib.sha256(review_path.read_bytes()).hexdigest()

    key_accessed = False

    def forbidden_key_loader(_: Path) -> dict[str, object]:
        nonlocal key_accessed
        key_accessed = True
        raise AssertionError("blind key must remain unopened")

    with pytest.raises(V3HumanDeltaError, match=expected_error.value):
        build_reconciliation_payload(
            root,
            key_loader=forbidden_key_loader,
            expected_completed_sha256=expected_sha256,
        )
    assert key_accessed is False


def test_unapproved_completed_checksum_stops_reconciliation() -> None:
    with pytest.raises(
        V3HumanDeltaError,
        match=V3HumanDeltaErrorCode.COMPLETED_DELTA_SHA256_MISMATCH.value,
    ):
        build_reconciliation_payload(ROOT, expected_completed_sha256="0" * 64)


def test_tampered_key_stops_reconciliation() -> None:
    key = build_delta_reconciliation_key()
    key["items"][0]["expected_tier"] = "STRONG"

    with pytest.raises(
        V3HumanDeltaError,
        match=V3HumanDeltaErrorCode.RECONCILIATION_KEY_INVALID.value,
    ):
        build_reconciliation_payload(ROOT, key_loader=lambda _: key)


def test_full_human_proof_uses_exactly_one_source_per_scenario() -> None:
    payload = build_reconciliation_payload(ROOT)
    proof = payload["full_human_proof"]
    assert proof["scenario_count"] == 8
    assert proof["criterion_count"] == 16
    assert proof["anchor_count"] == 24
    assert proof["label_count"] == 48
    assert tuple(proof["v2_carry_forward_scenarios"]) == V2_CARRY_FORWARD_SCENARIOS
    assert tuple(proof["v3_delta_scenarios"]) == V3_DELTA_SCENARIOS
    assert proof["v2_carry_forward_anchor_count"] == 9
    assert proof["v3_delta_anchor_count"] == 15
    assert len(proof["carry_forward_proofs"]) == 9
    assert all(
        item["byte_equivalent"]
        and item["v2_content_sha256"] == item["v3_content_sha256"]
        for item in proof["carry_forward_proofs"]
    )

    source_by_scenario: dict[str, set[str]] = {}
    for item in payload["criterion_details"]:
        source_by_scenario.setdefault(item["scenario_code"], set()).add(item["source"])
    assert source_by_scenario == {
        "SCN-01": {"V3_DELTA"},
        "SCN-02": {"V2_CARRY_FORWARD"},
        "SCN-03": {"V3_DELTA"},
        "SCN-04": {"V3_DELTA"},
        "SCN-05": {"V2_CARRY_FORWARD"},
        "SCN-06": {"V2_CARRY_FORWARD"},
        "SCN-07": {"V3_DELTA"},
        "SCN-08": {"V3_DELTA"},
    }


def test_distributions_primary_gate_and_secondary_diagnostic_are_exact() -> None:
    payload = build_reconciliation_payload(ROOT)
    assert payload["human_distributions"] == {
        "labels_by_tier": {
            "STRONG": {
                "TRES_SATISFAISANT": 16,
                "SATISFAISANT": 0,
                "FRAGILE": 0,
                "INSUFFISANT": 0,
                "NON_EVALUABLE": 0,
            },
            "MIXED": {
                "TRES_SATISFAISANT": 6,
                "SATISFAISANT": 7,
                "FRAGILE": 3,
                "INSUFFISANT": 0,
                "NON_EVALUABLE": 0,
            },
            "WEAK_BUT_STRUCTURALLY_VALID": {
                "TRES_SATISFAISANT": 6,
                "SATISFAISANT": 2,
                "FRAGILE": 8,
                "INSUFFISANT": 0,
                "NON_EVALUABLE": 0,
            },
        },
        "actions_by_tier": {
            "STRONG": {"aucune": 8, "révision": 0, "exclusion": 0},
            "MIXED": {"aucune": 3, "révision": 5, "exclusion": 0},
            "WEAK_BUT_STRUCTURALLY_VALID": {
                "aucune": 2,
                "révision": 4,
                "exclusion": 2,
            },
        },
        "structural_invalid_by_tier": {
            "STRONG": 0,
            "MIXED": 0,
            "WEAK_BUT_STRUCTURALLY_VALID": 0,
        },
    }
    assert payload["primary_gate"] == {
        "structures_valid": "24/24",
        "non_evaluable": "0/48",
        "strong_dominates_mixed": "10/16",
        "strong_dominates_weak": "10/16",
        "strong_vs_non_strong_differentiation": "6/16",
        "passed": False,
    }
    assert payload["secondary_diagnostic"] == {
        "trinary_strict_order_count": 4,
        "trinary_weak_order_count": 12,
        "mixed_vs_weak_tie_count": 4,
        "mixed_vs_weak_inversion_count": 4,
        "blocking": False,
    }


def test_action_diagnostic_is_non_blocking_and_decision_is_fail() -> None:
    payload = build_reconciliation_payload(ROOT)
    diagnostic = payload["action_alignment_diagnostic"]
    assert diagnostic["owner_followup_required"] is True
    assert diagnostic["blocking"] is False
    assert {
        (item["scenario_code"], item["tier"]) for item in diagnostic["conflicts"]
    } == {
        ("SCN-01", "MIXED"),
        ("SCN-04", "MIXED"),
        ("SCN-07", "WEAK_BUT_STRUCTURALLY_VALID"),
        ("SCN-08", "WEAK_BUT_STRUCTURALLY_VALID"),
    }
    assert payload["decision"] == {
        "HUMAN_DELTA_PREVALIDATION": "FAIL",
        "PROVIDER_RECALIBRATION_ALLOWED": "FALSE",
        "RELEASE_THRESHOLD_ADOPTION": "NOT_ALLOWED",
        "RUNTIME_ROUTE_CHANGE": "NONE",
        "NEXT_GATE": "12.16-G2-V3-ANCHOR-REVISION_REQUIRED",
    }
    assert payload["offline_execution"] == {
        "openai_calls": 0,
        "anthropic_calls": 0,
        "provider_cost_usd": "0.000000",
        "credentials_resolved": False,
        "provider_transport_constructed": False,
        "source_packet_mutated": False,
        "completed_delta_mutated_during_reconciliation": False,
        "reconciliation_key_mutated": False,
        "runtime_routes_mutated": False,
    }


def test_outputs_are_deterministic_minimized_and_byte_stable(tmp_path: Path) -> None:
    report_a = render_report_markdown(ROOT)
    report_b = render_report_markdown(ROOT)
    result_a = render_result_json(ROOT)
    result_b = render_result_json(ROOT)
    assert report_a == report_b
    assert result_a == result_b
    assert report_a == (ROOT / REPORT_RELATIVE_PATH).read_text(encoding="utf-8")
    assert result_a == (ROOT / RESULT_JSON_RELATIVE_PATH).read_text(encoding="utf-8")

    lowered_report = report_a.casefold()
    assert "hpv3d-" not in lowered_report
    assert "cal.v3.scn-" not in lowered_report
    assert "c:\\users\\" not in lowered_report
    assert "api_key" not in lowered_report
    assert "justification pédagogique courte" not in lowered_report
    assert "provider_calls = `0`" in lowered_report
    assert '"openai_calls": 0' in result_a
    assert '"anthropic_calls": 0' in result_a
    json.loads(result_a)

    root = _delta_root(tmp_path, include_v2=True)
    write_outputs(root)
    first = tuple(
        (root / relative_path).read_bytes()
        for relative_path in (REPORT_RELATIVE_PATH, RESULT_JSON_RELATIVE_PATH)
    )
    write_outputs(root)
    second = tuple(
        (root / relative_path).read_bytes()
        for relative_path in (REPORT_RELATIVE_PATH, RESULT_JSON_RELATIVE_PATH)
    )
    assert first == second
