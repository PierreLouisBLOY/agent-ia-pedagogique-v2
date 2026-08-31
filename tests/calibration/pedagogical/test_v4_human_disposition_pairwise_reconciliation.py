from __future__ import annotations

import hashlib
import json
import shutil
from collections import Counter
from pathlib import Path

import pytest

from tests.calibration.pedagogical.v4_corrective_attestation_closure import (
    CORRECTED_FORM_SHA256,
)
from tests.calibration.pedagogical.v4_human_disposition_pairwise_reconciliation import (
    COMPLETED_REVIEW_RELATIVE_PATH,
    EXPECTED_CORPUS_SHA256,
    EXPECTED_PACKET_SHA256,
    EXPECTED_RECONCILIATION_KEY_SHA256,
    NEXT_GATE_FAIL,
    PACKET_RELATIVE_PATH,
    RECONCILIATION_KEY_RELATIVE_PATH,
    REPORT_RELATIVE_PATH,
    RESULT_JSON_RELATIVE_PATH,
    V4HumanReconciliationError,
    build_reconciliation_payload,
    render_report_markdown,
    render_result_json,
    write_outputs,
)

ROOT = Path(__file__).resolve().parents[3]
EXPECTED_HISTORICAL_REPORT_SHA256 = (
    "7f54427d420cf139723f60a3efa55b6f24aa2b7b2d083f630f5173e19573947e"
)
EXPECTED_HISTORICAL_RESULT_SHA256 = (
    "deefcf8078f7a182e5332587bc782ef166afff473468d4d14d4d171a7ff785db"
)
EXPECTED_CURRENT_REPORT_SHA256 = (
    "872dd091d6ba520a6b3de7660b923f57adf6fb23de37e4cd9c01d9cec8f61d78"
)
EXPECTED_CURRENT_RESULT_SHA256 = (
    "23fce7f8f76171449c1a7f89c88b5c515bb8d3c57d3576bbf23ad716908da92b"
)


def _current_payload(root: Path = ROOT) -> dict[str, object]:
    return build_reconciliation_payload(
        root,
        expected_completed_sha256=CORRECTED_FORM_SHA256,
    )


def _input_root(tmp_path: Path) -> Path:
    for relative_path in (
        PACKET_RELATIVE_PATH,
        COMPLETED_REVIEW_RELATIVE_PATH,
        RECONCILIATION_KEY_RELATIVE_PATH,
    ):
        target = tmp_path / relative_path
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(ROOT / relative_path, target)
    return tmp_path


def test_t1_owner_approved_source_proofs_and_completeness_are_exact() -> None:
    payload = _current_payload()
    proofs = payload["proofs"]
    review = payload["review"]
    assert proofs == {
        "packet_sha256": EXPECTED_PACKET_SHA256,
        "completed_v4_prevalidation_sha256": (
            CORRECTED_FORM_SHA256
        ),
        "reconciliation_key_sha256": EXPECTED_RECONCILIATION_KEY_SHA256,
        "corpus_sha256": EXPECTED_CORPUS_SHA256,
    }
    assert review["review_status"] == "COMPLETED"
    assert review["reviewer_code"] == "OWNER_HUMAN_REVIEWER"
    assert review["review_date"] == "2026-08-31"
    assert review["closure_date"] == "2026-08-31"
    assert review["review_card_count"] == 8
    assert review["disposition_count"] == 24
    assert review["pairwise_ranking_count"] == 16
    assert len(review["cards"]) == 8
    assert all(card["justification"] for card in review["cards"])


def test_t1_disposition_distribution_and_gate_a_are_exact() -> None:
    payload = _current_payload()
    assert payload["distribution_by_tier"] == {
        "STRONG": {
            "DELIVER_AS_IS": 8,
            "REVISE_BEFORE_DELIVERY": 0,
            "REJECT": 0,
            "NON_EVALUABLE": 0,
        },
        "MIXED": {
            "DELIVER_AS_IS": 0,
            "REVISE_BEFORE_DELIVERY": 6,
            "REJECT": 2,
            "NON_EVALUABLE": 0,
        },
        "WEAK_BUT_STRUCTURALLY_VALID": {
            "DELIVER_AS_IS": 0,
            "REVISE_BEFORE_DELIVERY": 2,
            "REJECT": 6,
            "NON_EVALUABLE": 0,
        },
    }
    assert payload["gate_a"] == {
        "strong_deliver_as_is": 8,
        "mixed_deliver_as_is": 0,
        "weak_deliver_as_is": 0,
        "non_evaluable_dispositions": 0,
        "status": "PASS",
    }
    assert payload["disposition_diagnostic"] == {
        "mixed_revise": 6,
        "mixed_reject": 2,
        "weak_revise": 2,
        "weak_reject": 6,
    }


def test_t1_pairwise_relations_gate_b_and_secondary_diagnostic_are_exact() -> None:
    payload = _current_payload()
    rankings = payload["criterion_rankings"]
    assert len(rankings) == 16
    assert payload["gate_b"] == {
        "strong_gt_mixed": 16,
        "strong_gt_weak": 16,
        "non_evaluable_rankings": 0,
        "status": "PASS",
    }
    assert payload["mixed_weak_diagnostic"] == {
        "mixed_gt_weak": 10,
        "mixed_eq_weak": 4,
        "mixed_lt_weak": 2,
        "trinary_strict_order_count": 10,
        "blocking": False,
    }
    assert all(item["strong_vs_mixed"] == "GT" for item in rankings)
    assert all(item["strong_vs_weak"] == "GT" for item in rankings)
    assert Counter(item["mixed_vs_weak"] for item in rankings) == {
        "GT": 10,
        "EQ": 4,
        "LT": 2,
    }


def test_t1_final_decision_is_fail_without_provider_or_runtime_authority() -> None:
    payload = _current_payload()
    assert payload["decision"] == "PASS"
    assert payload["human_v4_prevalidation"] == "PASS"
    assert payload["provider_recalibration_allowed"] == "READY_FOR_OFFLINE_PLAN_ONLY"
    assert payload["provider_calls"] == 0
    assert payload["provider_cost"] == 0
    assert payload["credentials_resolved"] is False
    assert payload["provider_transport_constructed"] is False
    assert payload["runtime_route_change"] == "NONE"
    assert payload["release_threshold_adoption"] == "NOT_ALLOWED"
    assert payload["next_gate"] != NEXT_GATE_FAIL
    assert set(payload["authority_separation"].values()) == {False}


def test_t2_unapproved_completed_checksum_stops_before_reconciliation() -> None:
    with pytest.raises(
        V4HumanReconciliationError,
        match="COMPLETED_V4_PREVALIDATION_SHA256_MISMATCH",
    ):
        build_reconciliation_payload(ROOT, expected_completed_sha256="0" * 64)


def test_t2_invalid_ranking_grammar_is_not_corrected_or_reinterpreted(
    tmp_path: Path,
) -> None:
    root = _input_root(tmp_path)
    completed = root / COMPLETED_REVIEW_RELATIVE_PATH
    text = completed.read_text(encoding="utf-8")
    text = text.replace(
        "CAND-2E26645B8E  > CAND-9873A63D8B = CAND-01ADA7FABC",
        "CAND-9873A63D8B = CAND-01ADA7FABC < CAND-2E26645B8E",
        1,
    )
    completed.write_text(text, encoding="utf-8", newline="")
    mutated_sha256 = hashlib.sha256(completed.read_bytes()).hexdigest()
    with pytest.raises(
        V4HumanReconciliationError,
        match="V4_REVIEW_INVALID:.*RANKING_GRAMMAR",
    ):
        build_reconciliation_payload(
            root,
            expected_completed_sha256=mutated_sha256,
        )


def test_t2_tampered_key_content_stops_reconciliation() -> None:
    original = json.loads(
        (ROOT / RECONCILIATION_KEY_RELATIVE_PATH).read_text(encoding="utf-8")
    )
    original["cards"][0]["candidates"][0]["expected_tier"] = "STRONG"

    def tampered_loader(_path: Path) -> object:
        return original

    with pytest.raises(
        V4HumanReconciliationError,
        match="V4_RECONCILIATION_KEY_INVALID:CANONICAL_CONTENT",
    ):
        build_reconciliation_payload(
            ROOT,
            expected_completed_sha256=CORRECTED_FORM_SHA256,
            key_loader=tampered_loader,
        )


def test_t2_current_outputs_are_deterministic_and_historical_proofs_remain_stable(
    tmp_path: Path,
) -> None:
    report = render_report_markdown(
        ROOT,
        expected_completed_sha256=CORRECTED_FORM_SHA256,
    )
    result = render_result_json(
        ROOT,
        expected_completed_sha256=CORRECTED_FORM_SHA256,
    )
    assert report == render_report_markdown(
        ROOT,
        expected_completed_sha256=CORRECTED_FORM_SHA256,
    )
    assert result == render_result_json(
        ROOT,
        expected_completed_sha256=CORRECTED_FORM_SHA256,
    )
    assert hashlib.sha256(report.encode()).hexdigest() == (
        EXPECTED_CURRENT_REPORT_SHA256
    )
    assert hashlib.sha256(result.encode()).hexdigest() == (
        EXPECTED_CURRENT_RESULT_SHA256
    )
    historical_report = (ROOT / REPORT_RELATIVE_PATH).read_bytes()
    historical_result = (ROOT / RESULT_JSON_RELATIVE_PATH).read_bytes()
    assert hashlib.sha256(historical_report).hexdigest() == (
        EXPECTED_HISTORICAL_REPORT_SHA256
    )
    assert hashlib.sha256(historical_result).hexdigest() == (
        EXPECTED_HISTORICAL_RESULT_SHA256
    )
    assert historical_report != report.encode()
    assert historical_result != result.encode()

    root = _input_root(tmp_path)
    write_outputs(root, expected_completed_sha256=CORRECTED_FORM_SHA256)
    first = (
        (root / REPORT_RELATIVE_PATH).read_bytes(),
        (root / RESULT_JSON_RELATIVE_PATH).read_bytes(),
    )
    write_outputs(root, expected_completed_sha256=CORRECTED_FORM_SHA256)
    second = (
        (root / REPORT_RELATIVE_PATH).read_bytes(),
        (root / RESULT_JSON_RELATIVE_PATH).read_bytes(),
    )
    assert first == second
