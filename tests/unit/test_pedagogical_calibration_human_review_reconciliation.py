from __future__ import annotations

import json
import re
import shutil
from collections import Counter
from pathlib import Path

import pytest

from tests.calibration.pedagogical.human_review_reconciliation import (
    BASELINE_RELATIVE_PATH,
    COMPLETED_REVIEW_RELATIVE_PATH,
    PACKET_RELATIVE_PATH,
    RECONCILIATION_KEY_RELATIVE_PATH,
    REPORT_JSON_RELATIVE_PATH,
    REPORT_MD_RELATIVE_PATH,
    HumanReviewError,
    HumanReviewErrorCode,
    build_reconciliation_payload,
    classify_exposure,
    render_baseline_markdown,
    render_report_json,
    render_report_markdown,
    write_outputs,
)

ROOT = Path(__file__).resolve().parents[2]


def _review_root(tmp_path: Path) -> Path:
    for relative_path in (
        PACKET_RELATIVE_PATH,
        COMPLETED_REVIEW_RELATIVE_PATH,
        RECONCILIATION_KEY_RELATIVE_PATH,
    ):
        source = ROOT / relative_path
        target = tmp_path / relative_path
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)
    return tmp_path


def _mutate_review(root: Path, transform: object) -> None:
    path = root / COMPLETED_REVIEW_RELATIVE_PATH
    text = path.read_text(encoding="utf-8")
    if callable(transform):
        text = transform(text)
    else:
        raise TypeError("transform must be callable")
    path.write_text(text, encoding="utf-8")


def test_incomplete_review_stops_before_reconciliation_key_access(tmp_path: Path) -> None:
    root = _review_root(tmp_path)
    _mutate_review(
        root,
        lambda text: text.replace("REVIEW_STATUS : COMPLETED", "REVIEW_STATUS : IN_PROGRESS"),
    )
    key_accessed = False

    def forbidden_key_loader(_: Path) -> dict[str, object]:
        nonlocal key_accessed
        key_accessed = True
        raise AssertionError("the reconciliation key must remain unopened")

    with pytest.raises(
        HumanReviewError,
        match=HumanReviewErrorCode.HUMAN_REVIEW_INCOMPLETE.value,
    ):
        build_reconciliation_payload(root, key_loader=forbidden_key_loader)
    assert key_accessed is False


@pytest.mark.parametrize("mutation", ["invalid_label", "invalid_action", "placeholder"])
def test_invalid_or_incomplete_human_fields_stop_before_key(
    tmp_path: Path,
    mutation: str,
) -> None:
    root = _review_root(tmp_path)
    if mutation == "invalid_label":
        _mutate_review(
            root,
            lambda text: re.sub(
                r"(?m)(^- Appréciation humaine — `[^`]+`\s*:\s*)\S+",
                r"\1EXCELLENT",
                text,
                count=1,
            ),
        )
        expected = HumanReviewErrorCode.HUMAN_REVIEW_INVALID
    elif mutation == "invalid_action":
        _mutate_review(
            root,
            lambda text: re.sub(
                r"(?m)^- Action demandée :.*$",
                "- Action demandée : [x] aucune [x] révision [ ] exclusion",
                text,
                count=1,
            ),
        )
        expected = HumanReviewErrorCode.HUMAN_REVIEW_INCOMPLETE
    else:
        _mutate_review(
            root,
            lambda text: re.sub(
                r"(?m)^- Limites de la revue :.*$",
                "- Limites de la revue : <description honnête>",
                text,
                count=1,
            ),
        )
        expected = HumanReviewErrorCode.HUMAN_REVIEW_INCOMPLETE

    accessed = False

    def forbidden_key_loader(_: Path) -> dict[str, object]:
        nonlocal accessed
        accessed = True
        return {}

    with pytest.raises(HumanReviewError, match=expected.value):
        build_reconciliation_payload(root, key_loader=forbidden_key_loader)
    assert accessed is False


@pytest.mark.parametrize("mutation", ["duplicate", "missing"])
def test_duplicate_or_missing_review_ids_stop_before_key(
    tmp_path: Path,
    mutation: str,
) -> None:
    root = _review_root(tmp_path)
    if mutation == "duplicate":
        _mutate_review(
            root,
            lambda text: text.replace("## REV-024", "## REV-023", 1),
        )
    else:
        _mutate_review(
            root,
            lambda text: re.sub(
                r"(?ms)^## REV-024\s*.*?(?=^## Synthèse)",
                "",
                text,
                count=1,
            ),
        )
    accessed = False

    def forbidden_key_loader(_: Path) -> dict[str, object]:
        nonlocal accessed
        accessed = True
        return {}

    with pytest.raises(
        HumanReviewError,
        match=HumanReviewErrorCode.HUMAN_REVIEW_INVALID.value,
    ):
        build_reconciliation_payload(root, key_loader=forbidden_key_loader)
    assert accessed is False


@pytest.mark.parametrize(
    ("declaration", "expected"),
    [
        ("NON — aucun résultat machine consulté", "FULLY_BLIND"),
        ("OUI — agrégats globaux consultés", "AGGREGATE_RESULTS_EXPOSED"),
        ("OUI — certains détails par critère consultés", "DETAILED_RESULTS_EXPOSED"),
        ("information indisponible", "UNDECLARED"),
    ],
)
def test_exposure_classification_is_closed(declaration: str, expected: str) -> None:
    assert classify_exposure(declaration) == expected


def test_key_integrity_corpus_and_per_item_sha_are_verified() -> None:
    payload = build_reconciliation_payload(ROOT)
    assert payload["key_integrity"] == {
        "item_count": 24,
        "unique_review_item_count": 24,
        "unique_anchor_count": 24,
        "per_item_sha256_valid_count": 24,
        "content_repeated": False,
        "catalog_corpus_match": True,
    }
    assert payload["source_proofs"]["corpus_version"] == "12.16-g1-v1"
    assert payload["source_proofs"]["corpus_sha256"] == (
        "abeec0b4e5e1f60f2974ec1c19de34a5307e1b7d92e11c7b811e338d3b2e626d"
    )


def test_tampered_key_item_sha_stops_reconciliation(tmp_path: Path) -> None:
    root = _review_root(tmp_path)
    key_path = root / RECONCILIATION_KEY_RELATIVE_PATH
    key = json.loads(key_path.read_text(encoding="utf-8"))
    key["items"][0]["expected_tier"] = "MIXED"
    key_path.write_text(json.dumps(key), encoding="utf-8")
    with pytest.raises(
        HumanReviewError,
        match=HumanReviewErrorCode.RECONCILIATION_KEY_INVALID.value,
    ):
        build_reconciliation_payload(root)


def test_human_order_and_expected_tier_aggregates_are_exact() -> None:
    payload = build_reconciliation_payload(ROOT)
    assert payload["human_ordering"]["metrics"] == {
        "criterion_count": 16,
        "strict_ordering_count": 0,
        "weak_ordering_count": 16,
        "tied_pair_count": 28,
        "inverted_pair_count": 0,
        "non_evaluable_relation_count": 0,
        "human_distinction_count": 4,
    }
    expected = payload["expected_tier_comparison"]
    assert expected["human_label_counts_by_tier"] == {
        "STRONG": {
            "TRES_SATISFAISANT": 4,
            "SATISFAISANT": 12,
            "FRAGILE": 0,
            "INSUFFISANT": 0,
            "NON_EVALUABLE": 0,
        },
        "MIXED": {
            "TRES_SATISFAISANT": 0,
            "SATISFAISANT": 16,
            "FRAGILE": 0,
            "INSUFFISANT": 0,
            "NON_EVALUABLE": 0,
        },
        "WEAK_BUT_STRUCTURALLY_VALID": {
            "TRES_SATISFAISANT": 0,
            "SATISFAISANT": 16,
            "FRAGILE": 0,
            "INSUFFISANT": 0,
            "NON_EVALUABLE": 0,
        },
    }
    assert expected["structural_invalid_count_by_tier"] == {
        "STRONG": 0,
        "MIXED": 1,
        "WEAK_BUT_STRUCTURALLY_VALID": 0,
    }
    assert {
        tier: counts["révision"]
        for tier, counts in expected["action_counts_by_tier"].items()
    } == {"STRONG": 1, "MIXED": 1, "WEAK_BUT_STRUCTURALLY_VALID": 3}


def test_relation_comparison_cause_classes_and_dispositions_are_exact() -> None:
    payload = build_reconciliation_payload(ROOT)
    assert payload["human_model_relation_comparison"]["metrics"] == {
        "relation_agreement_count": 0,
        "human_only_distinction_count": 4,
        "model_only_distinction_count": 12,
        "shared_tie_count": 16,
        "disagreement_count": 0,
        "non_assessable_count": 0,
        "relation_count": 32,
    }
    details = payload["criterion_dispositions"]
    assert Counter(item["cause_class"] for item in details) == {
        "STRUCTURAL_ANCHOR_DEFECT": 2,
        "ANCHORS_TOO_SIMILAR_FOR_HUMAN_AND_MODEL": 3,
        "MODEL_UNDER_DISCRIMINATES_HUMAN_CLEARLY_DISTINGUISHES": 1,
        "INSUFFICIENT_EVIDENCE": 10,
    }
    assert Counter(item["disposition"] for item in details) == {
        "REVISE_ANCHORS": 9,
        "OWNER_DECISION_REQUIRED": 7,
    }
    assert payload["decision"] == {
        "HUMAN_REVIEW_COMPLETE": True,
        "HUMAN_ANCHOR_EVIDENCE": "PARTIAL",
        "JUDGE_CALIBRATION_DISPOSITION": "ANCHOR_REVISION_REQUIRED",
        "CALIBRATION_CONFIDENCE": "PROVISIONAL_REVIEW_EXPOSURE_LIMITED",
        "RELEASE_THRESHOLD_ADOPTION": "NOT_ALLOWED",
        "PROVIDER_ROUTE_CHANGE": "NONE",
    }
    assert payload["validation"] == {
        "targeted_calibration_regression": "PASS_131",
        "global_pytest": "PASS_4316_SKIPPED_3_EXPLICIT_GATES",
        "ruff_global": "PASS",
        "mypy_backend_and_evaluation_harness": "PASS_689_SOURCE_FILES",
        "compileall_backend_harness_calibration": "PASS",
    }


def test_reports_are_minimized_deterministic_and_match_tracked_files() -> None:
    json_a = render_report_json(ROOT)
    json_b = render_report_json(ROOT)
    markdown_a = render_report_markdown(ROOT)
    markdown_b = render_report_markdown(ROOT)
    baseline_a = render_baseline_markdown(ROOT)
    baseline_b = render_baseline_markdown(ROOT)
    assert (json_a, markdown_a, baseline_a) == (json_b, markdown_b, baseline_b)
    assert json_a == (ROOT / REPORT_JSON_RELATIVE_PATH).read_text(encoding="utf-8")
    assert markdown_a == (ROOT / REPORT_MD_RELATIVE_PATH).read_text(encoding="utf-8")
    assert baseline_a == (ROOT / BASELINE_RELATIVE_PATH).read_text(encoding="utf-8")

    lowered = (json_a + markdown_a + baseline_a).casefold()
    assert "c:\\users\\" not in lowered
    assert "api_key" not in lowered
    assert "request_id" not in lowered
    assert "rev-001" not in lowered
    assert "cal.scn-" not in lowered
    assert "plb" not in lowered
    assert "ajouter des ressources associées" not in lowered
    assert "justification pédagogique courte" not in lowered
    assert "numerator" not in lowered
    assert "denominator" not in lowered
    assert "human_ordinal_rank" not in lowered


def test_outputs_are_byte_stable_when_regenerated(tmp_path: Path) -> None:
    root = _review_root(tmp_path)
    write_outputs(root)
    first = tuple(
        (root / relative_path).read_bytes()
        for relative_path in (
            REPORT_MD_RELATIVE_PATH,
            REPORT_JSON_RELATIVE_PATH,
            BASELINE_RELATIVE_PATH,
        )
    )
    write_outputs(root)
    second = tuple(
        (root / relative_path).read_bytes()
        for relative_path in (
            REPORT_MD_RELATIVE_PATH,
            REPORT_JSON_RELATIVE_PATH,
            BASELINE_RELATIVE_PATH,
        )
    )
    assert first == second
