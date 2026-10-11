from __future__ import annotations

import hashlib
import json
import shutil
from copy import deepcopy
from fractions import Fraction
from pathlib import Path

import pytest

from tests.calibration.pedagogical.metrics import (
    summarize_latency,
    summarize_rational_distribution,
)
from tests.calibration.pedagogical.r4_r3_r3_analysis import (
    BASELINE_RELATIVE_PATH,
    CONTINUATION_LEDGER_RELATIVE_PATH,
    FINAL_MANIFEST_RELATIVE_PATH,
    HUMAN_PACKET_RELATIVE_PATH,
    RECONCILIATION_RELATIVE_PATH,
    REPORT_JSON_RELATIVE_PATH,
    AnalysisError,
    AnalysisErrorCode,
    _relative_classification,
    audit_openai_results,
    build_analysis_payload,
    build_final_manifest,
    build_reconciliation_key,
    cost_accounting,
    final_manifest_sha256,
    render_baseline_markdown,
    render_human_review_packet,
    render_report_json,
    render_report_markdown,
    validate_final_manifest,
)

ROOT = Path(__file__).resolve().parents[2]


def _proof_root(tmp_path: Path) -> Path:
    for directory in ("12.16-g2-r4-r2", "12.16-g2-r4-r3", "12.16-g2-r4-r4"):
        source = ROOT / "artifacts/calibration" / directory
        target = tmp_path / "artifacts/calibration" / directory
        shutil.copytree(source, target)
    return tmp_path


def _assert_no_float(value: object) -> None:
    assert not isinstance(value, float)
    if isinstance(value, dict):
        for item in value.values():
            _assert_no_float(item)
    elif isinstance(value, list):
        for item in value:
            _assert_no_float(item)


def test_final_manifest_has_exact_uniform_76_slot_union() -> None:
    manifest = build_final_manifest(ROOT)
    results = manifest["results"]
    assert manifest["result_count"] == 76
    assert len({item["logical_slot_id"] for item in results}) == 76
    assert {item["score_status"] for item in results} == {"SCORED"}
    assert {item["thinking_mode"] for item in results} == {"adaptive"}
    assert {item["effort"] for item in results} == {"low"}
    assert {item["max_output_tokens"] for item in results} == {2048}
    assert final_manifest_sha256(ROOT) == (
        "273c5b6e9cfe36d5bebf364337a050eecb8d13077f3409c34da6c8f7f8698677"
    )


@pytest.mark.parametrize("mutation", ["duplicate", "diagnostic", "policy", "missing"])
def test_manifest_rejects_invalid_membership_or_policy(mutation: str) -> None:
    manifest = deepcopy(build_final_manifest(ROOT))
    results = manifest["results"]
    if mutation == "duplicate":
        results[1]["logical_slot_id"] = results[0]["logical_slot_id"]
    elif mutation == "diagnostic":
        results[0]["proof_set"] = "DIAGNOSTIC_ONLY"
    elif mutation == "policy":
        results[0]["max_output_tokens"] = 512
    else:
        results.pop()
    with pytest.raises(AnalysisError, match=AnalysisErrorCode.FINAL_MANIFEST_INVALID):
        validate_final_manifest(manifest)


def test_missing_continuation_ledger_stops(tmp_path: Path) -> None:
    root = _proof_root(tmp_path)
    (root / CONTINUATION_LEDGER_RELATIVE_PATH).unlink()
    with pytest.raises(
        AnalysisError,
        match=AnalysisErrorCode.FINAL_CALIBRATION_EVIDENCE_MISMATCH,
    ):
        build_final_manifest(root)


def test_tampered_continuation_raw_stops(tmp_path: Path) -> None:
    root = _proof_root(tmp_path)
    ledger = json.loads((root / CONTINUATION_LEDGER_RELATIVE_PATH).read_text("utf-8"))
    raw = root / ledger["calls"][0]["raw_output_path"]
    raw.write_bytes(raw.read_bytes() + b" ")
    with pytest.raises(
        AnalysisError,
        match=AnalysisErrorCode.FINAL_CALIBRATION_EVIDENCE_MISMATCH,
    ):
        build_final_manifest(root)


def test_exact_rational_distribution_and_latency_quantiles() -> None:
    distribution = summarize_rational_distribution(
        (Fraction(0), Fraction(1, 2), Fraction(1), Fraction(1))
    )
    assert distribution.mean == Fraction(5, 8)
    assert distribution.median == Fraction(3, 4)
    assert distribution.histogram == (
        (Fraction(0), 1),
        (Fraction(1, 2), 1),
        (Fraction(1), 2),
    )
    latency = summarize_latency(tuple(range(1, 101)))
    assert latency.median_milliseconds == Fraction(101, 2)
    assert latency.p95_milliseconds == 95
    assert summarize_latency((3, 1, 2)).median_milliseconds == Fraction(2)


def test_selected_output_closed_relative_classification() -> None:
    assert _relative_classification(Fraction(1), Fraction(1), Fraction(1, 2), Fraction(0)) == "EQUAL_STRONG"
    assert _relative_classification(Fraction(3, 4), Fraction(1), Fraction(1, 2), Fraction(0)) == "BETWEEN_STRONG_AND_MIXED"
    assert _relative_classification(Fraction(1, 4), Fraction(1), Fraction(1, 2), Fraction(0)) == "BETWEEN_MIXED_AND_WEAK"
    assert _relative_classification(Fraction(0), Fraction(1), Fraction(1, 2), Fraction(0)) == "EQUAL_WEAK"
    assert _relative_classification(Fraction(1, 2), Fraction(1), Fraction(1), Fraction(0)) == "UNCLASSIFIABLE_NON_MONOTONIC_ANCHORS"


def test_analysis_metrics_and_cost_accounting_are_bounded() -> None:
    payload = build_analysis_payload(ROOT)
    orderings = payload["anchor_orderings"]["metrics"]
    repeatability = payload["repeatability"]["metrics"]
    technical = payload["anthropic_technical"]
    costs = payload["cost_accounting"]
    assert orderings == {
        "criterion_count": 16,
        "strict_ordering_count": 1,
        "weak_ordering_count": 16,
        "tied_pair_count": 20,
        "inverted_pair_count": 0,
        "inconclusive_count": 0,
    }
    assert repeatability["exact_agreement_count"] == 14
    assert repeatability["maximum_spread"] == {"numerator": 1, "denominator": 1}
    assert repeatability["mean_absolute_rational_delta"] == {
        "numerator": 9,
        "denominator": 80,
    }
    assert technical["usage"] == {
        "input_tokens": 79273,
        "cached_input_tokens": 0,
        "output_tokens": 5016,
        "thinking_tokens": 2789,
        "total_tokens": 84289,
    }
    assert costs["A_FINAL_USEFUL_OPENAI_EXECUTION_COST"] == "0.211738"
    assert costs["B_FINAL_UNIFORM_ANTHROPIC_SCORING_COST"] == "0.208706"
    assert costs["C_DIAGNOSTIC_AND_REMEDIATION_MEASURED_COST"] == "0.054800"
    assert costs["D_CONSERVATIVE_RESERVES_NOT_PROVEN_AS_BILLED"] == "1.957696"
    assert costs["no_double_counting"] is True


def test_twenty_openai_results_are_post_validated_without_new_calls() -> None:
    results = audit_openai_results(ROOT)
    assert len(results) == 20
    assert len({item["logical_slot_id"] for item in results}) == 20
    assert {item["post_validation_status"] for item in results} == {
        "COMPLETED",
        "PARTIAL",
        "SUCCEEDED",
    }
    assert sum(Fraction(item["measured_cost_usd"]) for item in results) == Fraction(
        105869, 500000
    )


def test_blind_packet_is_unfilled_and_reconciliation_is_separate() -> None:
    packet = render_human_review_packet()
    assert packet.count("## REV-") == 24
    assert "REVIEW_STATUS : `NOT_COMPLETED`" in packet
    assert "cal.scn-" not in packet
    assert "STRONG" not in packet
    assert "MIXED" not in packet
    assert "WEAK" not in packet
    assert "score_numerator" not in packet
    reconciliation = build_reconciliation_key(build_final_manifest(ROOT))
    assert reconciliation["item_count"] == 24
    assert reconciliation["content_repeated"] is False


def test_reports_are_safe_float_free_and_byte_reproducible(tmp_path: Path) -> None:
    from tests.support.historical_calibration_replay import replay_historical_report

    result = replay_historical_report(ROOT, tmp_path)
    assert result.returncode == 0, result.stdout.decode("utf-8", errors="replace")
    assert b"1 passed" in result.stdout


def test_current_report_revalidation_is_deterministic_and_separate_from_history() -> None:
    json_a = render_report_json(ROOT)
    json_b = render_report_json(ROOT)
    markdown_a = render_report_markdown(ROOT)
    markdown_b = render_report_markdown(ROOT)
    assert json_a == json_b
    assert markdown_a == markdown_b
    parsed = json.loads(json_a)
    _assert_no_float(parsed)
    lowered = (json_a + markdown_a).lower()
    assert "c:\\users\\" not in lowered
    assert "api_key" not in lowered
    assert "request_id" not in lowered
    assert "candidate_projection" not in lowered
    assert hashlib.sha256((ROOT / REPORT_JSON_RELATIVE_PATH).read_bytes()).hexdigest() == (
        "f08fad954918f82e690a539b35f02a88ce3d08818a95f6c18df982f4c3d7c272"
    )
    assert hashlib.sha256(json_a.encode()).hexdigest() == (
        "15281ec06c3fbcb9ebf00b6ddf595ac5fb33fbc8b2972603040a6668cd80abf9"
    )
    assert render_baseline_markdown(ROOT) == (ROOT / BASELINE_RELATIVE_PATH).read_text("utf-8")
    assert render_human_review_packet() == (ROOT / HUMAN_PACKET_RELATIVE_PATH).read_text("utf-8")


def test_machine_artifacts_are_ignored_and_regenerated() -> None:
    assert (ROOT / FINAL_MANIFEST_RELATIVE_PATH).is_file()
    assert (ROOT / RECONCILIATION_RELATIVE_PATH).is_file()
    assert cost_accounting(
        ROOT,
        final_openai=audit_openai_results(ROOT),
        final_anthropic=tuple(build_final_manifest(ROOT)["results"]),
    )["experimental_measured_cost_usd"] == "0.475244"
