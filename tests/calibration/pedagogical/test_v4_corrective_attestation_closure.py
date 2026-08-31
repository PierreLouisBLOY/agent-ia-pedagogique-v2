from __future__ import annotations

import ast
import hashlib
from pathlib import Path

from tests.calibration.pedagogical.anchor_corpus_v4 import (
    v4_calibration_corpus_sha256,
)
from tests.calibration.pedagogical.v4_corrective_attestation_closure import (
    CORRECTED_FORM_SHA256,
    EXPECTED_PRE_CORRECTION_FORM_SHA256,
    EXPECTED_PRE_CORRECTION_RESULT_SHA256,
    PRE_CORRECTION_RESULT_RELATIVE_PATH,
    REPORT_RELATIVE_PATH,
    build_closure_payload,
    render_report_markdown,
)
from tests.calibration.pedagogical.v4_human_disposition_pairwise_reconciliation import (
    COMPLETED_REVIEW_RELATIVE_PATH,
)

ROOT = Path(__file__).resolve().parents[3]
OWNER = (
    ROOT
    / "tests/calibration/pedagogical/"
    "v4_corrective_attestation_closure.py"
)
EXPECTED_CORPUS_SHA256 = (
    "9c8e262028f1d63fa50963f2f8bcb742e4c24d4e106a73244861416f826ca034"
)
EXPECTED_V4_OWNER_SHA256 = (
    "b0a86640502db4ab1d0b623e50faffa45178d9e93b0a24976df3312d460662be"
)
EXPECTED_REPORT_SHA256 = (
    "6b81546a054334a9f33738d37b9e2fd4a0dbf5ec918694fb1e7a767073d66a79"
)


def test_t1_corrected_and_pre_correction_hash_proofs_are_exact() -> None:
    assert hashlib.sha256(
        (ROOT / COMPLETED_REVIEW_RELATIVE_PATH).read_bytes()
    ).hexdigest() == CORRECTED_FORM_SHA256
    assert hashlib.sha256(
        (ROOT / PRE_CORRECTION_RESULT_RELATIVE_PATH).read_bytes()
    ).hexdigest() == EXPECTED_PRE_CORRECTION_RESULT_SHA256
    payload = build_closure_payload(ROOT)
    assert payload["pre_correction_form_sha256"] == (
        EXPECTED_PRE_CORRECTION_FORM_SHA256
    )
    assert payload["corrected_form_sha256"] == CORRECTED_FORM_SHA256
    assert payload["corpus_changed"] is False
    assert v4_calibration_corpus_sha256() == EXPECTED_CORPUS_SHA256
    assert hashlib.sha256(
        (ROOT / "tests/calibration/pedagogical/anchor_corpus_v4.py").read_bytes()
    ).hexdigest() == EXPECTED_V4_OWNER_SHA256


def test_t1_semantic_diff_is_not_bounded_to_attested_scn05_scope() -> None:
    payload = build_closure_payload(ROOT)
    assert payload["attested_corrected_scope"] == "SCN-05 TWO PAIRWISE RANKINGS"
    assert payload["changed_scenarios"] == ["SCN-01", "SCN-06"]
    assert payload["changed_pairwise_rankings"] == 3
    assert payload["changed_dispositions"] == 1
    assert payload["changed_justifications"] == 0
    assert payload["changed_other_fields"] == 0
    assert payload["trace_correction_check"] == "FAIL"
    assert [
        (item["scenario"], item["kind"], item["ref"])
        for item in payload["semantic_changes"]
    ] == [
        ("SCN-01", "pairwise_ranking", "scn-01.quality.clarity"),
        ("SCN-06", "disposition", "candidate_position_2"),
        (
            "SCN-06",
            "pairwise_ranking",
            "scn-06.quality.assessment-clarity",
        ),
        (
            "SCN-06",
            "pairwise_ranking",
            "scn-06.quality.marking-scheme-coherence",
        ),
    ]


def test_t1_mechanical_gates_pass_but_methodological_closure_is_partial() -> None:
    payload = build_closure_payload(ROOT)
    assert payload["gate_a"] == {
        "strong_deliver_as_is": 8,
        "mixed_deliver_as_is": 0,
        "weak_deliver_as_is": 0,
        "non_evaluable_dispositions": 0,
        "status": "PASS",
    }
    assert payload["gate_b"] == {
        "strong_gt_mixed": 16,
        "strong_gt_weak": 16,
        "non_evaluable_rankings": 0,
        "status": "PASS",
    }
    assert payload["human_v4_prevalidation"] == "PARTIAL"
    assert payload["methodological_status"] == "PARTIAL"
    assert payload["provider_recalibration_allowed"] == "FALSE"
    assert payload["provider_calls"] == 0
    assert payload["runtime_route_change"] == "NONE"
    assert payload["next_gate"] == "12.16-G2-V4-OWNER_DECISION_REQUIRED"


def test_t1_public_report_is_deterministic_and_does_not_expose_key_mapping() -> None:
    report = render_report_markdown(ROOT)
    assert report == render_report_markdown(ROOT)
    assert hashlib.sha256(report.encode()).hexdigest() == EXPECTED_REPORT_SHA256
    assert (ROOT / REPORT_RELATIVE_PATH).read_text(encoding="utf-8") == report
    assert "CAND-" not in report
    assert "cal.v4.scn-" not in report
    assert "TRACE_CORRECTION_CHECK = `FAIL`" in report
    assert "HUMAN_V4_PREVALIDATION = `PARTIAL`" in report
    assert "PROVIDER_RECALIBRATION_ALLOWED = `FALSE`" in report


def test_t1_owner_has_no_provider_or_runtime_dependency() -> None:
    tree = ast.parse(OWNER.read_text(encoding="utf-8"))
    imports: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imports.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imports.add(node.module)
    assert not any(name == "backend" or name.startswith("backend.") for name in imports)
    assert not any(name == "openai" or name.startswith("openai.") for name in imports)
    assert not any(name == "anthropic" or name.startswith("anthropic.") for name in imports)
    source = OWNER.read_text(encoding="utf-8")
    forbidden = (
        "OPENAI_API_KEY",
        "ANTHROPIC_API_KEY",
        "os.environ",
        ".responses.create(",
        ".messages.create(",
    )
    assert all(marker not in source for marker in forbidden)
