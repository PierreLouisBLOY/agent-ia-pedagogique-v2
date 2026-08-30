from __future__ import annotations

import hashlib
import json
import re
from dataclasses import FrozenInstanceError, replace
from pathlib import Path

import pytest

from tests.calibration.pedagogical.anchor_corpus_v2 import (
    BASELINE_RELATIVE_PATH,
    CONTROLLED_DIFFERENTIATION_MATRIX,
    HUMAN_LABELS,
    MATRIX_RELATIVE_PATH,
    PACKET_RELATIVE_PATH,
    PEDAGOGICAL_CALIBRATION_CORPUS_V1_SHA256,
    PEDAGOGICAL_CALIBRATION_CORPUS_V2_VERSION,
    RECONCILIATION_KEY_RELATIVE_PATH,
    STATIC_DIFFERENTIATION_RULE_IDS,
    V2_ANCHOR_EXPECTATIONS,
    V2_CALIBRATION_ANCHORS,
    V2_CALIBRATION_CRITERION_ITEMS,
    V2_CRITERION_ORDERINGS,
    V2_HUMAN_ACCEPTANCE_GATE,
    ControlledDifferentiation,
    audit_v2_corpus,
    build_reconciliation_key,
    render_baseline,
    render_differentiation_matrix,
    render_human_prevalidation_packet,
    render_reconciliation_key_json,
    scorer_visible_projection,
    v2_calibration_corpus_sha256,
    write_outputs,
)
from tests.calibration.pedagogical.catalog import (
    CALIBRATION_ANCHORS,
    CALIBRATION_SCENARIOS,
    AnchorTier,
    calibration_corpus_sha256,
)

ROOT = Path(__file__).resolve().parents[2]

EXPECTED_V2_SHA256 = "4fe17f4286eb1a713a3d41a95b99260ef470ba32cadf33c2267dfc4dbaada427"
EXPECTED_PACKET_SHA256 = "81bca8cc998e866c7b08f22af65c009714b5e4d5068fb0c19b2ba6598a7d48c9"
EXPECTED_KEY_SHA256 = "eb20fe93ae76215218fea3958bd44d6e2c0d7d5c476cec4350e6eb6146084ef0"


def test_v1_is_frozen_and_v2_has_a_distinct_identity() -> None:
    assert calibration_corpus_sha256() == PEDAGOGICAL_CALIBRATION_CORPUS_V1_SHA256
    assert PEDAGOGICAL_CALIBRATION_CORPUS_V2_VERSION == "12.16-g1-v2"
    assert len(V2_CALIBRATION_ANCHORS) == 24
    assert len({anchor.anchor_id for anchor in V2_CALIBRATION_ANCHORS}) == 24
    assert {anchor.anchor_id for anchor in V2_CALIBRATION_ANCHORS}.isdisjoint(
        anchor.anchor_id for anchor in CALIBRATION_ANCHORS
    )
    assert all(anchor.anchor_id.startswith("cal.v2.scn-") for anchor in V2_CALIBRATION_ANCHORS)
    assert v2_calibration_corpus_sha256() == EXPECTED_V2_SHA256
    assert v2_calibration_corpus_sha256() != calibration_corpus_sha256()


def test_v2_cardinality_structure_and_immutability_are_exact() -> None:
    assert len(CALIBRATION_SCENARIOS) == 8
    assert len({scenario.level_code for scenario in CALIBRATION_SCENARIOS}) == 4
    assert len({scenario.task_kind for scenario in CALIBRATION_SCENARIOS}) == 8
    assert len(V2_CALIBRATION_CRITERION_ITEMS) == 48
    assert len(V2_CRITERION_ORDERINGS) == 16
    assert len(V2_ANCHOR_EXPECTATIONS) == 24
    assert {
        tier: sum(expectation.tier is tier for expectation in V2_ANCHOR_EXPECTATIONS)
        for tier in AnchorTier
    } == {tier: 8 for tier in AnchorTier}
    scenario_by_code = {scenario.scenario_code: scenario for scenario in CALIBRATION_SCENARIOS}
    for anchor in V2_CALIBRATION_ANCHORS:
        assert tuple(code for code, _ in anchor.sections) == scenario_by_code[
            anchor.scenario_code
        ].required_sections
        assert len(anchor.candidate_projection()) <= 2_500
    with pytest.raises(FrozenInstanceError):
        V2_CALIBRATION_ANCHORS[0].anchor_id = "changed"  # type: ignore[misc]


def test_controlled_differentiation_matrix_and_static_gates_are_complete() -> None:
    assert len(CONTROLLED_DIFFERENTIATION_MATRIX) == 16
    assert len(
        {(item.scenario_code, item.criterion_ref) for item in CONTROLLED_DIFFERENTIATION_MATRIX}
    ) == 16
    assert all(
        len({item.strong_intent, item.mixed_defect, item.weak_defect}) == 3
        for item in CONTROLLED_DIFFERENTIATION_MATRIX
    )
    assert len(STATIC_DIFFERENTIATION_RULE_IDS) == 9
    assert audit_v2_corpus() == ()


def test_static_gates_detect_duplicate_trivial_cosmetic_and_section_identity() -> None:
    anchors = list(V2_CALIBRATION_ANCHORS)
    anchors[1] = replace(anchors[1], sections=anchors[0].sections)
    rules = {issue.rule_id for issue in audit_v2_corpus(tuple(anchors))}
    assert {
        "v2.anchors-distinct",
        "v2.tier-sections-distinct",
        "v2.non-trivial-textual-distance",
        "v2.not-cosmetic-only",
    } <= rules


@pytest.mark.parametrize(
    ("mutation", "expected_rule"),
    [
        ("missing-section", "v2.required-sections-exact"),
        ("empty-section", "v2.structurally-valid"),
        ("unsafe", "v2.safe-synthetic-content"),
        ("weak-too-long", "v2.weak-not-more-detailed-than-strong"),
        ("missing-matrix-row", "v2.controlled-defect-declared"),
    ],
)
def test_static_gates_detect_bounded_invalid_mutations(
    mutation: str,
    expected_rule: str,
) -> None:
    anchors = list(V2_CALIBRATION_ANCHORS)
    matrix: tuple[ControlledDifferentiation, ...] = CONTROLLED_DIFFERENTIATION_MATRIX
    if mutation == "missing-section":
        anchors[0] = replace(anchors[0], sections=anchors[0].sections[:-1])
    elif mutation == "empty-section":
        sections = list(anchors[0].sections)
        sections[0] = (sections[0][0], "")
        anchors[0] = replace(anchors[0], sections=tuple(sections))
    elif mutation == "unsafe":
        sections = list(anchors[0].sections)
        sections[0] = (sections[0][0], "https://invalid.example")
        anchors[0] = replace(anchors[0], sections=tuple(sections))
    elif mutation == "weak-too-long":
        sections = list(anchors[2].sections)
        sections[-1] = (sections[-1][0], sections[-1][1] + " Explication détaillée." * 40)
        anchors[2] = replace(anchors[2], sections=tuple(sections))
    else:
        matrix = matrix[:-1]
    rules = {issue.rule_id for issue in audit_v2_corpus(tuple(anchors), matrix)}
    assert expected_rule in rules


def test_scorer_visible_projection_is_provider_and_tier_blind() -> None:
    scenario_by_code = {scenario.scenario_code: scenario for scenario in CALIBRATION_SCENARIOS}
    for item in V2_CALIBRATION_CRITERION_ITEMS:
        anchor = next(
            anchor for anchor in V2_CALIBRATION_ANCHORS if anchor.anchor_id == item.anchor_id
        )
        projection = scorer_visible_projection(anchor, item.criterion_ref)
        assert tuple(projection) == (
            "criterion",
            "scenario",
            "pedagogical-level",
            "task-kind",
            "candidate-projection",
            "reference-constraints",
            "required-sections",
        )
        assert projection["required-sections"] == scenario_by_code[
            item.scenario_code
        ].required_sections
        serialized = json.dumps(projection, ensure_ascii=False).casefold()
        assert item.anchor_id.casefold() not in serialized
        assert "strong" not in serialized
        assert "mixed" not in serialized
        assert "weak_but_structurally_valid" not in serialized
        assert "openai" not in serialized
        assert "anthropic" not in serialized
        assert "provider" not in serialized
        assert "model_id" not in serialized
        assert "credential" not in serialized
        assert "sqlite" not in serialized
        assert "://" not in serialized
        assert ":\\" not in serialized


def test_blind_packet_is_new_unfilled_safe_and_deterministic() -> None:
    packet = render_human_prevalidation_packet()
    assert packet == render_human_prevalidation_packet()
    assert hashlib.sha256(packet.encode("utf-8")).hexdigest() == EXPECTED_PACKET_SHA256
    review_ids = re.findall(r"(?m)^## (HPV2-\d{3})$", packet)
    assert len(review_ids) == len(set(review_ids)) == 24
    assert review_ids == [f"HPV2-{index:03d}" for index in range(1, 25)]
    assert "REVIEW_STATUS : `NOT_COMPLETED`" in packet
    assert "[x]" not in packet.casefold()
    assert packet.count("- Appréciation humaine —") == 48
    assert all(anchor.anchor_id not in packet for anchor in V2_CALIBRATION_ANCHORS)
    assert "## REV-" not in packet
    assert "STRONG" not in packet
    assert "MIXED" not in packet
    assert "WEAK_BUT_STRUCTURALLY_VALID" not in packet
    assert "score_numerator" not in packet
    assert "score_denominator" not in packet
    assert "1/16" not in packet
    assert "28 égalités" not in packet
    assert all(label in packet for label in HUMAN_LABELS)


def test_blind_packet_order_differs_from_v1_review_order() -> None:
    packet = render_human_prevalidation_packet()
    v2_scenarios = tuple(re.findall(r"(?m)^- Scénario : `(SCN-\d{2})`$", packet))
    v1_scenarios = (
        "SCN-02",
        "SCN-03",
        "SCN-05",
        "SCN-05",
        "SCN-02",
        "SCN-05",
        "SCN-08",
        "SCN-07",
        "SCN-01",
        "SCN-07",
        "SCN-06",
        "SCN-08",
        "SCN-03",
        "SCN-04",
        "SCN-02",
        "SCN-06",
        "SCN-08",
        "SCN-01",
        "SCN-03",
        "SCN-06",
        "SCN-04",
        "SCN-01",
        "SCN-04",
        "SCN-07",
    )
    assert len(v2_scenarios) == 24
    assert v2_scenarios != v1_scenarios


def test_reconciliation_key_is_complete_content_free_and_deterministic() -> None:
    key = build_reconciliation_key()
    assert key["review_status"] == "NOT_COMPLETED"
    assert key["corpus_version"] == PEDAGOGICAL_CALIBRATION_CORPUS_V2_VERSION
    assert key["corpus_sha256"] == EXPECTED_V2_SHA256
    assert key["packet_sha256"] == EXPECTED_PACKET_SHA256
    assert key["content_repeated"] is False
    assert key["item_count"] == 24
    items = key["items"]
    assert len({item["review_item_id"] for item in items}) == 24
    assert len({item["anchor_id"] for item in items}) == 24
    for item in items:
        proof = item["reconciliation_sha256"]
        projection = {
            name: value for name, value in item.items() if name != "reconciliation_sha256"
        }
        canonical = json.dumps(
            projection,
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        ).encode("utf-8")
        assert proof == hashlib.sha256(canonical).hexdigest()
        assert "sections" not in item
        assert "content" not in item
    key_json = render_reconciliation_key_json()
    assert key_json == render_reconciliation_key_json()
    assert hashlib.sha256(key_json.encode("utf-8")).hexdigest() == EXPECTED_KEY_SHA256


def test_human_acceptance_gate_is_predeclared_without_release_threshold() -> None:
    assert V2_HUMAN_ACCEPTANCE_GATE == {
        "structurally_valid_anchor_count": 24,
        "weak_ordering_count": 16,
        "inversion_count": 0,
        "non_evaluable_relation_count": 0,
        "perceptibly_differentiated_criterion_count": 16,
        "design_target_strict_ordering_count": 16,
        "remaining_tie_requires_explicit_disposition": True,
        "product_release_threshold_created": False,
    }


def test_generated_tracked_outputs_match_and_regenerate_byte_identically(tmp_path: Path) -> None:
    assert render_human_prevalidation_packet() == (ROOT / PACKET_RELATIVE_PATH).read_text(
        encoding="utf-8"
    )
    assert render_differentiation_matrix() == (ROOT / MATRIX_RELATIVE_PATH).read_text(
        encoding="utf-8"
    )
    assert render_baseline() == (ROOT / BASELINE_RELATIVE_PATH).read_text(encoding="utf-8")
    assert render_reconciliation_key_json() == (
        ROOT / RECONCILIATION_KEY_RELATIVE_PATH
    ).read_text(encoding="utf-8")

    write_outputs(tmp_path)
    first = tuple(
        (tmp_path / relative_path).read_bytes()
        for relative_path in (
            PACKET_RELATIVE_PATH,
            MATRIX_RELATIVE_PATH,
            BASELINE_RELATIVE_PATH,
            RECONCILIATION_KEY_RELATIVE_PATH,
        )
    )
    write_outputs(tmp_path)
    second = tuple(
        (tmp_path / relative_path).read_bytes()
        for relative_path in (
            PACKET_RELATIVE_PATH,
            MATRIX_RELATIVE_PATH,
            BASELINE_RELATIVE_PATH,
            RECONCILIATION_KEY_RELATIVE_PATH,
        )
    )
    assert first == second


def test_v1_owner_and_reports_remain_byte_exact() -> None:
    expected = {
        "tests/calibration/pedagogical/catalog.py": (
            "53da2068fa6585086fe955b633a1d8e173cf770c8b5cb5e71f6cc8cc474e7317"
        ),
        "docs/development/PHASE_12_16_G2_FINAL_CALIBRATION_ANALYSIS_REPORT.json": (
            "f08fad954918f82e690a539b35f02a88ce3d08818a95f6c18df982f4c3d7c272"
        ),
        "docs/development/PHASE_12_16_G2_HUMAN_REVIEW_RECONCILIATION_REPORT.json": (
            "568e810af5a3cee9e46a56696300066db421d2dfc330f721718318be85a8b6cd"
        ),
    }
    actual = {
        relative_path: hashlib.sha256((ROOT / relative_path).read_bytes()).hexdigest()
        for relative_path in expected
    }
    assert actual == expected
