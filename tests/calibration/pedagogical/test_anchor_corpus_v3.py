from __future__ import annotations

import hashlib
import json
import re
from collections import Counter
from dataclasses import replace
from pathlib import Path

import pytest

from tests.calibration.pedagogical.anchor_corpus_v2 import (
    V2_ANCHOR_EXPECTATIONS,
    V2_CALIBRATION_ANCHORS,
)
from tests.calibration.pedagogical.anchor_corpus_v3 import (
    _V2_ANCHOR_BY_SCENARIO_TIER,
    _V3_ANCHOR_BY_SCENARIO_TIER,
    BASELINE_RELATIVE_PATH,
    CALIBRATION_SEMANTICS,
    CARRY_FORWARD_MANIFEST,
    CARRY_FORWARD_NEGATIVE_CONTROLS,
    CRITERION_DEFECT_ALIGNMENT_MATRIX,
    MATRIX_RELATIVE_PATH,
    PACKET_RELATIVE_PATH,
    PEDAGOGICAL_CALIBRATION_CORPUS_V3_VERSION,
    PRIMARY_FAILURE_TIERS_BY_CRITERION,
    RECONCILIATION_KEY_RELATIVE_PATH,
    REMEDIATED_SCENARIOS,
    REVISED_NEGATIVE_CONTROLS,
    V2_HUMAN_EVIDENCE,
    V3_ANCHOR_EXPECTATIONS,
    V3_CALIBRATION_ANCHORS,
    V3_CRITERION_ORDERINGS,
    audit_v3_corpus,
    build_delta_reconciliation_key,
    render_alignment_matrix,
    render_baseline,
    render_delta_reconciliation_key_json,
    render_human_delta_packet,
    scorer_visible_projection,
    v3_calibration_corpus_sha256,
    write_outputs,
)
from tests.calibration.pedagogical.catalog import (
    CALIBRATION_ANCHORS,
    CALIBRATION_SCENARIOS,
    AnchorTier,
)

ROOT = Path(__file__).resolve().parents[3]
EXPECTED_V3_CORPUS_SHA256 = (
    "dad8e7d08934b7d64c3f22c4c5fdf1e3ca39768854359c26f681852852ffb50c"
)
EXPECTED_DELTA_PACKET_SHA256 = (
    "0cd536bdbdca68cead009bad9ae09a1d11c514ff0774c34fbe4f14f5ae4d6477"
)
EXPECTED_DELTA_KEY_SHA256 = (
    "afe21aab0e83e2046fd5e6a26c5f3548f75ecc702550f16b5a4b6c2d7a4c6205"
)


def test_v2_evidence_derives_exact_primary_failures() -> None:
    assert len(V2_HUMAN_EVIDENCE) == 16
    assert REMEDIATED_SCENARIOS == (
        "SCN-01",
        "SCN-03",
        "SCN-04",
        "SCN-07",
        "SCN-08",
    )
    assert REVISED_NEGATIVE_CONTROLS == {
        ("SCN-01", AnchorTier.MIXED),
        ("SCN-03", AnchorTier.MIXED),
        ("SCN-03", AnchorTier.WEAK_BUT_STRUCTURALLY_VALID),
        ("SCN-04", AnchorTier.MIXED),
        ("SCN-04", AnchorTier.WEAK_BUT_STRUCTURALLY_VALID),
        ("SCN-07", AnchorTier.MIXED),
        ("SCN-08", AnchorTier.MIXED),
        ("SCN-08", AnchorTier.WEAK_BUT_STRUCTURALLY_VALID),
    }
    assert len(CARRY_FORWARD_NEGATIVE_CONTROLS) == 8
    assert Counter(
        tier
        for tiers in PRIMARY_FAILURE_TIERS_BY_CRITERION.values()
        for tier in tiers
    ) == {
        AnchorTier.MIXED: 9,
        AnchorTier.WEAK_BUT_STRUCTURALLY_VALID: 6,
    }


def test_v3_identity_cardinality_and_ids_are_new() -> None:
    assert PEDAGOGICAL_CALIBRATION_CORPUS_V3_VERSION == "12.16-g1-v3"
    assert v3_calibration_corpus_sha256() == EXPECTED_V3_CORPUS_SHA256
    assert len(V3_CALIBRATION_ANCHORS) == 24
    assert len(V3_ANCHOR_EXPECTATIONS) == 24
    assert len(V3_CRITERION_ORDERINGS) == 16
    assert len(CALIBRATION_SCENARIOS) == 8
    assert len(V3_CALIBRATION_ANCHORS) * 2 == 48
    v3_ids = {anchor.anchor_id for anchor in V3_CALIBRATION_ANCHORS}
    legacy_ids = {
        anchor.anchor_id for anchor in (*CALIBRATION_ANCHORS, *V2_CALIBRATION_ANCHORS)
    }
    assert len(v3_ids) == 24
    assert not v3_ids & legacy_ids
    assert all(anchor_id.startswith("cal.v3.scn-") for anchor_id in v3_ids)


def test_all_strong_contents_are_byte_equivalent_to_v2() -> None:
    for scenario in CALIBRATION_SCENARIOS:
        key = (scenario.scenario_code, AnchorTier.STRONG)
        v2_anchor = _V2_ANCHOR_BY_SCENARIO_TIER[key]
        v3_anchor = _V3_ANCHOR_BY_SCENARIO_TIER[key]
        assert v3_anchor.sections == v2_anchor.sections
        assert v3_anchor.candidate_projection().encode() == (
            v2_anchor.candidate_projection().encode()
        )


def test_negative_controls_are_carried_or_revised_exactly_as_derived() -> None:
    revised = 0
    carried = 0
    for scenario in CALIBRATION_SCENARIOS:
        for tier in (
            AnchorTier.MIXED,
            AnchorTier.WEAK_BUT_STRUCTURALLY_VALID,
        ):
            key = (scenario.scenario_code, tier)
            identical = (
                _V3_ANCHOR_BY_SCENARIO_TIER[key].sections
                == _V2_ANCHOR_BY_SCENARIO_TIER[key].sections
            )
            if key in REVISED_NEGATIVE_CONTROLS:
                revised += 1
                assert identical is False
            else:
                carried += 1
                assert identical is True
    assert (carried, revised) == (8, 8)


def test_sections_structure_static_audit_and_primary_distinction() -> None:
    assert audit_v3_corpus() == ()
    tier_by_anchor = {
        expectation.anchor_id: expectation.tier
        for expectation in V3_ANCHOR_EXPECTATIONS
    }
    for anchor in V3_CALIBRATION_ANCHORS:
        scenario = next(
            item
            for item in CALIBRATION_SCENARIOS
            if item.scenario_code == anchor.scenario_code
        )
        assert tuple(code for code, _ in anchor.sections) == scenario.required_sections
        assert all(text and text == text.strip() for _, text in anchor.sections)
        tier = tier_by_anchor[anchor.anchor_id]
        if tier is not AnchorTier.STRONG:
            strong = _V3_ANCHOR_BY_SCENARIO_TIER[
                (anchor.scenario_code, AnchorTier.STRONG)
            ]
            assert anchor.candidate_projection() != strong.candidate_projection()


@pytest.mark.parametrize("mutation", ["strong", "carried", "revised"])
def test_static_audit_detects_bounded_mutations(mutation: str) -> None:
    anchors = list(V3_CALIBRATION_ANCHORS)
    if mutation == "strong":
        key = ("SCN-01", AnchorTier.STRONG)
        target = _V3_ANCHOR_BY_SCENARIO_TIER[key]
        index = anchors.index(target)
        anchors[index] = replace(
            target,
            sections=((target.sections[0][0], "Contenu altéré."), *target.sections[1:]),
        )
        expected = "v3.strong-byte-equivalent"
    elif mutation == "carried":
        key = ("SCN-02", AnchorTier.MIXED)
        target = _V3_ANCHOR_BY_SCENARIO_TIER[key]
        index = anchors.index(target)
        anchors[index] = replace(
            target,
            sections=((target.sections[0][0], "Contenu altéré."), *target.sections[1:]),
        )
        expected = "v3.carry-forward-exact"
    else:
        key = ("SCN-01", AnchorTier.MIXED)
        target = _V3_ANCHOR_BY_SCENARIO_TIER[key]
        index = anchors.index(target)
        anchors[index] = replace(
            target,
            sections=_V2_ANCHOR_BY_SCENARIO_TIER[key].sections,
        )
        expected = "v3.revisions-bounded-by-v2-evidence"
    assert expected in {issue.rule_id for issue in audit_v3_corpus(tuple(anchors))}


def test_scorer_projection_is_tier_blind_and_contains_no_authority() -> None:
    forbidden_keys = {
        "anchor_id",
        "tier",
        "expected_tier",
        "provider",
        "model",
        "expected_score",
        "runtime_outcome",
        "delivery_approval",
    }
    for ordering in V3_CRITERION_ORDERINGS:
        for anchor_id in ordering.ordered_anchor_ids:
            anchor = next(
                item for item in V3_CALIBRATION_ANCHORS if item.anchor_id == anchor_id
            )
            projection = scorer_visible_projection(anchor, ordering.criterion_ref)
            assert forbidden_keys.isdisjoint(projection)
            serialized = json.dumps(projection, ensure_ascii=False)
            assert anchor.anchor_id not in serialized
            assert "DELIVERY_CANDIDATE" not in serialized
            assert "NON_DELIVERABLE_NEGATIVE_CONTROL" not in serialized
            assert "STRONG_VS_NON_STRONG" not in serialized


def test_primary_gate_and_secondary_diagnostic_are_separate() -> None:
    assert CALIBRATION_SEMANTICS.production_content_policy == "STRONG_ONLY"
    assert CALIBRATION_SEMANTICS.primary_separation == "STRONG_VS_NON_STRONG"
    assert CALIBRATION_SEMANTICS.strong_role == "DELIVERY_CANDIDATE"
    assert CALIBRATION_SEMANTICS.mixed_role == (
        "NON_DELIVERABLE_NEGATIVE_CONTROL"
    )
    assert CALIBRATION_SEMANTICS.weak_role == (
        "NON_DELIVERABLE_NEGATIVE_CONTROL"
    )
    assert CALIBRATION_SEMANTICS.secondary_diagnostic == (
        "MIXED_VS_WEAK_ORDERING_NON_BLOCKING"
    )
    assert CALIBRATION_SEMANTICS.trinary_strict_ordering_target == (
        "DIAGNOSTIC_ONLY"
    )
    assert CALIBRATION_SEMANTICS.provider_recalibration_allowed is False


def test_alignment_matrix_and_carry_forward_manifest_are_complete() -> None:
    assert len(CRITERION_DEFECT_ALIGNMENT_MATRIX) == 16
    assert Counter(item.v3_action for item in CRITERION_DEFECT_ALIGNMENT_MATRIX) == {
        "REVISE_NEGATIVE_CONTROLS": 10,
        "CARRY_FORWARD": 6,
    }
    assert all(item.strong_intent for item in CRITERION_DEFECT_ALIGNMENT_MATRIX)
    assert all(
        item.primary_deliverability_expectation
        == "STRONG > MIXED AND STRONG > WEAK"
        for item in CRITERION_DEFECT_ALIGNMENT_MATRIX
    )
    assert all(
        item.secondary_mixed_weak_expectation == "DIAGNOSTIC_ONLY_NON_BLOCKING"
        for item in CRITERION_DEFECT_ALIGNMENT_MATRIX
    )
    assert len(CARRY_FORWARD_MANIFEST) == 48
    assert Counter(item.reuse_allowed for item in CARRY_FORWARD_MANIFEST) == {
        True: 32,
        False: 16,
    }
    for item in CARRY_FORWARD_MANIFEST:
        assert item.reuse_allowed == (
            item.v2_content_fingerprint == item.v3_content_fingerprint
        )
        assert len(item.v2_content_fingerprint) == 64
        assert len(item.v3_content_fingerprint) == 64


def test_delta_packet_is_blind_unfilled_bounded_and_deterministic() -> None:
    packet = render_human_delta_packet()
    assert packet == render_human_delta_packet()
    assert hashlib.sha256(packet.encode()).hexdigest() == EXPECTED_DELTA_PACKET_SHA256
    review_ids = re.findall(r"(?m)^## (HPV3D-\d{3})$", packet)
    assert review_ids == [f"HPV3D-{index:03d}" for index in range(1, 16)]
    assert len(set(review_ids)) == 15
    assert packet.count("- Appréciation humaine —") == 30
    assert packet.count("- Structure valide : [ ] oui [ ] non") == 15
    assert "[x]" not in packet.casefold()
    assert "REVIEW_STATUS : `NOT_COMPLETED`" in packet
    assert all(anchor.anchor_id not in packet for anchor in V3_CALIBRATION_ANCHORS)
    forbidden = (
        "STRONG",
        "MIXED",
        "WEAK_BUT_STRUCTURALLY_VALID",
        "expected_tier",
        "changed",
        "unchanged",
        "résultat v2",
        "score fournisseur",
    )
    assert all(marker not in packet for marker in forbidden)
    scenarios = re.findall(r"(?m)^- Scénario : `(SCN-\d{2})`$", packet)
    assert Counter(scenarios) == {scenario: 3 for scenario in REMEDIATED_SCENARIOS}


def test_delta_key_is_local_complete_and_deterministic() -> None:
    key = build_delta_reconciliation_key()
    rendered = render_delta_reconciliation_key_json()
    assert rendered == render_delta_reconciliation_key_json()
    assert hashlib.sha256(rendered.encode()).hexdigest() == EXPECTED_DELTA_KEY_SHA256
    assert key["item_count"] == 15
    assert key["remediated_scenario_count"] == 5
    items = key["items"]
    assert len(items) == 15
    assert len({item["review_item_id"] for item in items}) == 15
    assert len({item["anchor_id"] for item in items}) == 15
    assert Counter(item["expected_tier"] for item in items) == {
        "STRONG": 5,
        "MIXED": 5,
        "WEAK_BUT_STRUCTURALLY_VALID": 5,
    }
    for item in items:
        proof = item["reconciliation_sha256"]
        projected = {
            name: value
            for name, value in item.items()
            if name != "reconciliation_sha256"
        }
        encoded = json.dumps(
            projected,
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        ).encode()
        assert proof == hashlib.sha256(encoded).hexdigest()


def test_generated_documents_are_deterministic_and_match_tracked_outputs(
    tmp_path: Path,
) -> None:
    matrix = render_alignment_matrix()
    packet = render_human_delta_packet()
    baseline = render_baseline()
    assert matrix == (ROOT / MATRIX_RELATIVE_PATH).read_text(encoding="utf-8")
    assert packet == (ROOT / PACKET_RELATIVE_PATH).read_text(encoding="utf-8")
    assert baseline == (ROOT / BASELINE_RELATIVE_PATH).read_text(encoding="utf-8")
    write_outputs(tmp_path)
    first = tuple(
        (tmp_path / relative_path).read_bytes()
        for relative_path in (
            MATRIX_RELATIVE_PATH,
            PACKET_RELATIVE_PATH,
            BASELINE_RELATIVE_PATH,
            RECONCILIATION_KEY_RELATIVE_PATH,
        )
    )
    write_outputs(tmp_path)
    second = tuple(
        (tmp_path / relative_path).read_bytes()
        for relative_path in (
            MATRIX_RELATIVE_PATH,
            PACKET_RELATIVE_PATH,
            BASELINE_RELATIVE_PATH,
            RECONCILIATION_KEY_RELATIVE_PATH,
        )
    )
    assert first == second


def test_v1_v2_anchor_ids_remain_distinct_and_v2_tiers_stable() -> None:
    assert len({item.anchor_id for item in V2_ANCHOR_EXPECTATIONS}) == 24
    assert not {
        item.anchor_id for item in V2_ANCHOR_EXPECTATIONS
    } & {item.anchor_id for item in V3_ANCHOR_EXPECTATIONS}
