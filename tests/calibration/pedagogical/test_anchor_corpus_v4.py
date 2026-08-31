from __future__ import annotations

import hashlib
import json
import re
from collections import Counter
from dataclasses import replace
from pathlib import Path

from tests.calibration.pedagogical.anchor_corpus_v2 import V2_CALIBRATION_ANCHORS
from tests.calibration.pedagogical.anchor_corpus_v3 import V3_CALIBRATION_ANCHORS
from tests.calibration.pedagogical.anchor_corpus_v4 import (
    _V3_ANCHOR_BY_SCENARIO_TIER,
    _V4_ANCHOR_BY_SCENARIO_TIER,
    ADR_RELATIVE_PATH,
    BASELINE_RELATIVE_PATH,
    CALIBRATION_SEMANTICS,
    CARRIED_FORWARD_NEGATIVE_CONTROLS,
    HUMAN_SCENARIO_CARDS,
    MATRIX_RELATIVE_PATH,
    NEXT_GATE,
    OWNER_DECISION,
    PACKET_RELATIVE_PATH,
    PEDAGOGICAL_CALIBRATION_CORPUS_V4_VERSION,
    PRIMARY_CRITERION_GATE,
    PRIMARY_DELIVERY_GATE,
    PRIMARY_HUMAN_INSTRUMENT,
    RECONCILIATION_KEY_RELATIVE_PATH,
    TARGETED_NEGATIVE_CONTROLS,
    V3_ANCHOR_ACTION_EVIDENCE,
    V4_ANCHOR_EXPECTATIONS,
    V4_CALIBRATION_ANCHORS,
    V4_CRITERION_ORDERINGS,
    V4_REMEDIATION_MATRIX,
    audit_v4_corpus,
    build_human_reconciliation_key,
    render_adr,
    render_baseline,
    render_human_packet,
    render_human_reconciliation_key_json,
    render_remediation_matrix,
    v4_calibration_corpus_sha256,
    write_outputs,
)
from tests.calibration.pedagogical.catalog import (
    CALIBRATION_ANCHORS,
    CALIBRATION_SCENARIOS,
    AnchorTier,
)

ROOT = Path(__file__).resolve().parents[3]
EXPECTED_V4_CORPUS_SHA256 = (
    "9c8e262028f1d63fa50963f2f8bcb742e4c24d4e106a73244861416f826ca034"
)
EXPECTED_PACKET_SHA256 = (
    "56bc9d28b65b2e7b82a982cf36afb56d13e147ce6c0716587acaef47e4c42a1f"
)
EXPECTED_KEY_SHA256 = (
    "a5b2ed4ebed755b128d3cc163f8004bedb57f2087bd2b444f9835069609edc21"
)
EXPECTED_TARGETS = {
    ("SCN-01", AnchorTier.MIXED),
    ("SCN-04", AnchorTier.MIXED),
    ("SCN-06", AnchorTier.MIXED),
    ("SCN-07", AnchorTier.WEAK_BUT_STRUCTURALLY_VALID),
    ("SCN-08", AnchorTier.WEAK_BUT_STRUCTURALLY_VALID),
}


def test_t1_owner_semantics_and_v3_actions_are_exact() -> None:
    assert OWNER_DECISION == "ADOPT_DISPOSITION_FIRST_PAIRWISE_HUMAN_CALIBRATION"
    assert PRIMARY_HUMAN_INSTRUMENT == (
        "DELIVERABILITY_DISPOSITION_PLUS_BLIND_PAIRWISE_CRITERION_COMPARISON"
    )
    assert PRIMARY_DELIVERY_GATE == (
        "STRONG_DELIVER_AS_IS_AND_NEGATIVES_NOT_DELIVER_AS_IS"
    )
    assert PRIMARY_CRITERION_GATE == (
        "STRONG_STRICTLY_PREFERRED_TO_EACH_NEGATIVE"
    )
    assert CALIBRATION_SEMANTICS.production_content_policy == "STRONG_ONLY"
    assert CALIBRATION_SEMANTICS.strong_role == "DELIVERY_CANDIDATE"
    assert CALIBRATION_SEMANTICS.mixed_role == "NON_DELIVERABLE_NEGATIVE_CONTROL"
    assert CALIBRATION_SEMANTICS.weak_role == "NON_DELIVERABLE_NEGATIVE_CONTROL"
    assert CALIBRATION_SEMANTICS.absolute_quality_labels == "DIAGNOSTIC_ONLY"
    assert CALIBRATION_SEMANTICS.provider_recalibration_allowed is False
    assert TARGETED_NEGATIVE_CONTROLS == EXPECTED_TARGETS
    assert len(CARRIED_FORWARD_NEGATIVE_CONTROLS) == 11
    assert Counter(
        (item.tier, item.action) for item in V3_ANCHOR_ACTION_EVIDENCE
    ) == {
        ("STRONG", "aucune"): 8,
        ("MIXED", "aucune"): 3,
        ("MIXED", "révision"): 5,
        ("WEAK_BUT_STRUCTURALLY_VALID", "aucune"): 2,
        ("WEAK_BUT_STRUCTURALLY_VALID", "révision"): 4,
        ("WEAK_BUT_STRUCTURALLY_VALID", "exclusion"): 2,
    }


def test_t1_v4_identity_cardinality_and_opaque_ids_are_new() -> None:
    assert PEDAGOGICAL_CALIBRATION_CORPUS_V4_VERSION == "12.16-g1-v4"
    assert v4_calibration_corpus_sha256() == EXPECTED_V4_CORPUS_SHA256
    assert len(CALIBRATION_SCENARIOS) == 8
    assert len(V4_CALIBRATION_ANCHORS) == 24
    assert len(V4_ANCHOR_EXPECTATIONS) == 24
    assert len(V4_CRITERION_ORDERINGS) == 16
    assert len(V4_CALIBRATION_ANCHORS) * 2 == 48
    v4_ids = {anchor.anchor_id for anchor in V4_CALIBRATION_ANCHORS}
    legacy_ids = {
        anchor.anchor_id
        for anchor in (
            *CALIBRATION_ANCHORS,
            *V2_CALIBRATION_ANCHORS,
            *V3_CALIBRATION_ANCHORS,
        )
    }
    assert len(v4_ids) == 24
    assert not v4_ids & legacy_ids
    assert all(re.fullmatch(r"cal\.v4\.scn-\d{2}\.[0-9a-f]{12}", item) for item in v4_ids)


def test_t1_carry_forward_and_five_revisions_are_byte_exact() -> None:
    strong_carried = 0
    negative_carried = 0
    negative_revised = 0
    for scenario in CALIBRATION_SCENARIOS:
        for tier in (
            AnchorTier.STRONG,
            AnchorTier.MIXED,
            AnchorTier.WEAK_BUT_STRUCTURALLY_VALID,
        ):
            key = (scenario.scenario_code, tier)
            v3 = _V3_ANCHOR_BY_SCENARIO_TIER[key]
            v4 = _V4_ANCHOR_BY_SCENARIO_TIER[key]
            byte_equivalent = (
                v3.candidate_projection().encode()
                == v4.candidate_projection().encode()
            )
            assert tuple(code for code, _ in v4.sections) == scenario.required_sections
            if tier is AnchorTier.STRONG:
                strong_carried += 1
                assert byte_equivalent
            elif key in EXPECTED_TARGETS:
                negative_revised += 1
                assert not byte_equivalent
            else:
                negative_carried += 1
                assert byte_equivalent
    assert (strong_carried, negative_carried, negative_revised) == (8, 11, 5)
    assert audit_v4_corpus() == ()


def test_t1_remediation_matrix_has_complete_bounded_proof() -> None:
    assert len(V4_REMEDIATION_MATRIX) == 5
    actual = {
        (item.scenario_code, AnchorTier(item.tier)) for item in V4_REMEDIATION_MATRIX
    }
    assert actual == EXPECTED_TARGETS
    for item in V4_REMEDIATION_MATRIX:
        assert item.v3_action == "aucune"
        assert len(item.v3_content_hash) == 64
        assert len(item.v4_content_hash) == 64
        assert item.v3_content_hash != item.v4_content_hash
        assert "action=aucune" in item.why_v3_was_deliverable
        assert item.v4_controlled_defect
        assert item.criterion_alignment.count("scn-") == 2
        assert item.expected_disposition == "REVISE_BEFORE_DELIVERY"


def test_t2_human_packet_is_blind_complete_and_deterministic() -> None:
    packet = render_human_packet()
    assert packet == render_human_packet()
    assert hashlib.sha256(packet.encode()).hexdigest() == EXPECTED_PACKET_SHA256
    assert re.findall(r"(?m)^## (V4H-\d{3}) — SCN-\d{2}$", packet) == [
        f"V4H-{index:03d}" for index in range(1, 9)
    ]
    assert packet.count("### Candidat `CAND-") == 24
    assert packet.count("Disposition :") == 24
    for disposition in (
        "DELIVER_AS_IS",
        "REVISE_BEFORE_DELIVERY",
        "REJECT",
        "NON_EVALUABLE",
    ):
        assert packet.count(f"- [ ] {disposition}") == 24
    assert packet.count("- Classement relatif —") == 16
    assert packet.count("- Justification pédagogique courte de la carte :") == 8
    assert "[x]" not in packet.casefold()
    assert "REVIEW_STATUS : `NOT_COMPLETED`" in packet
    forbidden = (
        "STRONG",
        "MIXED",
        "WEAK_BUT_STRUCTURALLY_VALID",
        "expected_tier",
        "V2_CARRY_FORWARD",
        "V3_DELTA",
        "provider",
        "model",
    )
    assert all(marker.casefold() not in packet.casefold() for marker in forbidden)
    assert all(anchor.anchor_id not in packet for anchor in V4_CALIBRATION_ANCHORS)


def test_t2_local_key_maps_all_candidates_and_shuffles_deterministically() -> None:
    key = build_human_reconciliation_key()
    rendered = render_human_reconciliation_key_json()
    assert rendered == render_human_reconciliation_key_json()
    assert hashlib.sha256(rendered.encode()).hexdigest() == EXPECTED_KEY_SHA256
    assert key["card_count"] == 8
    assert key["candidate_count"] == 24
    assert key["criterion_ranking_count"] == 16
    assert len(HUMAN_SCENARIO_CARDS) == 8
    cards = key["cards"]
    sequences = []
    candidate_ids = set()
    for card in cards:
        candidates = card["candidates"]
        assert len(candidates) == 3
        sequences.append(tuple(candidate["expected_tier"] for candidate in candidates))
        candidate_ids.update(candidate["blinded_candidate_id"] for candidate in candidates)
        proof = card["reconciliation_sha256"]
        projection = {name: value for name, value in card.items() if name != "reconciliation_sha256"}
        encoded = json.dumps(
            projection,
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        ).encode()
        assert proof == hashlib.sha256(encoded).hexdigest()
    assert len(candidate_ids) == 24
    assert len(set(sequences)) > 1


def test_t2_static_audit_detects_carry_forward_mutation() -> None:
    anchors = list(V4_CALIBRATION_ANCHORS)
    target = _V4_ANCHOR_BY_SCENARIO_TIER[("SCN-02", AnchorTier.MIXED)]
    index = anchors.index(target)
    anchors[index] = replace(
        target,
        sections=((target.sections[0][0], "Contenu altéré."), *target.sections[1:]),
    )
    assert "v4.negative-carry-forward-exact" in {
        issue.rule_id for issue in audit_v4_corpus(tuple(anchors))
    }


def test_t2_generated_outputs_match_and_are_byte_stable(tmp_path: Path) -> None:
    expected = {
        ADR_RELATIVE_PATH: render_adr(),
        MATRIX_RELATIVE_PATH: render_remediation_matrix(),
        PACKET_RELATIVE_PATH: render_human_packet(),
        BASELINE_RELATIVE_PATH: render_baseline(),
    }
    for relative_path, rendered in expected.items():
        assert (ROOT / relative_path).read_text(encoding="utf-8") == rendered
    write_outputs(tmp_path)
    first = {
        relative_path: (tmp_path / relative_path).read_bytes()
        for relative_path in (*expected, RECONCILIATION_KEY_RELATIVE_PATH)
    }
    write_outputs(tmp_path)
    second = {
        relative_path: (tmp_path / relative_path).read_bytes()
        for relative_path in (*expected, RECONCILIATION_KEY_RELATIVE_PATH)
    }
    assert first == second
    assert NEXT_GATE == (
        "12.16-G2-V4-HUMAN-DISPOSITION-PAIRWISE-PREVALIDATION_READY"
    )
