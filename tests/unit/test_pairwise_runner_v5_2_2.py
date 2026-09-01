from __future__ import annotations

import hashlib
from copy import deepcopy
from decimal import Decimal

import pytest

from tests.calibration.pedagogical import semantic_gate_v5_2 as gate_v5_2
from tests.calibration.pedagogical.pairwise_runner_v5_2_2 import (
    APPROVED_V5_2_2_CEILING_USD,
    PROPOSED_V5_2_2_CEILING_USD,
    V5_2_2_CARRY_FORWARD_COUNT,
    V5_2_2_LOGICAL_OBSERVATION_COUNT,
    V5_2_2_NEW_CALL_COUNT,
    V5_2_2_NEW_CALL_IDS,
    PairwiseRunnerError,
    PairwiseRunnerErrorCode,
    audit_weak_carry_forward_v5_2_2,
    build_minimal_pairwise_pilot_v5_2_2,
    extract_authorized_pairwise_projection_metadata,
    extract_pairwise_projection_metadata,
)
from tests.calibration.pedagogical.pricing import EXPECTED_PRICING_SNAPSHOT_SHA256
from tests.calibration.pedagogical.semantic_gate_v5_2 import (
    EXPECTED_V5_2_CALL_SPEC_SHA256_BY_ID,
    EXPECTED_V5_2_GATE_CONTRACT_SHA256,
    EXPECTED_V5_2_TRANSFER_PROJECTION_SHA256_BY_ID,
    SCN_01_PAIRWISE_CALL_ID,
    SCN_06_PAIRWISE_CALL_ID,
    WEAK_CALL_ID,
    build_v5_2_call_specs,
    build_v5_2_transfer_envelopes,
    mixed_carry_forward_audit,
    strong_carry_forward_audit,
)
from tests.calibration.pedagogical.semantic_integration_v5 import (
    EXPECTED_V5_MATRIX_SHA256,
    EXPECTED_V5_SCORER_CONTRACT_SHA256,
)
from tests.calibration.pedagogical.semantic_parser_adapter_v5_1 import (
    EXPECTED_V5_1_PARSER_CONTRACT_SHA256,
)
from tests.calibration.pedagogical.semantic_pilot_freeze_v5 import (
    EXPECTED_PEDAGOGICAL_TRANSFER_SCOPE_SHA256,
)


def _legacy_flat_reader(payload: dict[str, object]) -> tuple[str, str, str, str, str]:
    values = (
        payload.get("comparison_id"),
        payload.get("candidate_a_id"),
        payload.get("candidate_a_projection"),
        payload.get("candidate_b_id"),
        payload.get("candidate_b_projection"),
    )
    if not all(type(value) is str for value in values):
        raise RuntimeError("PAIRWISE_PROJECTION_INVALID")
    comparison_id, candidate_a_id, candidate_a, candidate_b_id, candidate_b = values
    assert type(comparison_id) is str
    assert type(candidate_a_id) is str
    assert type(candidate_a) is str
    assert type(candidate_b_id) is str
    assert type(candidate_b) is str
    return comparison_id, candidate_a_id, candidate_a, candidate_b_id, candidate_b


def _safe_weak_records() -> tuple[dict[str, object], dict[str, object]]:
    report: dict[str, object] = {
        "baseline_commit_sha": "e26d0d44f9d5e3c253623bb80fe357ec08ac3812",
        "parser_v5_1_sha256": EXPECTED_V5_1_PARSER_CONTRACT_SHA256,
        "scorer_contract_sha256": EXPECTED_V5_SCORER_CONTRACT_SHA256,
        "matrix_sha256": EXPECTED_V5_MATRIX_SHA256,
        "pricing_sha256": EXPECTED_PRICING_SNAPSHOT_SHA256,
        "gate_contract_sha256": EXPECTED_V5_2_GATE_CONTRACT_SHA256,
        "pedagogical_transfer_scope_sha256": (
            EXPECTED_PEDAGOGICAL_TRANSFER_SCOPE_SHA256
        ),
        "weak_score": 1,
        "raw_response_persistence": "NONE",
        "live_authorization": "CONSUMED",
        "attempted": 1,
        "completed": 1,
        "rerun_count": 0,
    }
    ledger: dict[str, object] = {
        "live_authorization": "CONSUMED",
        "calls": [
            {
                "call_id": WEAK_CALL_ID,
                "call_spec_sha256": EXPECTED_V5_2_CALL_SPEC_SHA256_BY_ID[WEAK_CALL_ID],
                "transfer_payload_sha256": (
                    EXPECTED_V5_2_TRANSFER_PROJECTION_SHA256_BY_ID[WEAK_CALL_ID]
                ),
                "safe_response_record": {
                    "parser_schema_status": "PASS",
                    "terminal_status": "COMPLETED",
                    "score_level": 1,
                    "raw_response_persisted": False,
                },
                "semantic_safe_record": {
                    "evidence_first_present": True,
                    "transfer_provenance_pass": True,
                },
            }
        ],
    }
    return report, ledger


def test_exact_pairwise_payloads_reproduce_previous_flat_reader_mismatch() -> None:
    pairwise = build_v5_2_transfer_envelopes()[1:]
    assert tuple(item.call_id for item in pairwise) == V5_2_2_NEW_CALL_IDS
    for envelope in pairwise:
        with pytest.raises(RuntimeError, match="PAIRWISE_PROJECTION_INVALID"):
            _legacy_flat_reader(envelope.input_payload)


def test_nested_payload_extracts_exact_a_and_b_without_mutation() -> None:
    for envelope in build_v5_2_transfer_envelopes()[1:]:
        before = deepcopy(envelope.input_payload)
        metadata = extract_pairwise_projection_metadata(envelope.input_payload)
        candidate_a = envelope.input_payload["candidate_a"]
        candidate_b = envelope.input_payload["candidate_b"]
        assert type(candidate_a) is dict
        assert type(candidate_b) is dict
        assert metadata.comparison_id == envelope.input_payload["comparison_id"]
        assert metadata.source_projection_ids == (
            candidate_a["candidate_id"],
            candidate_b["candidate_id"],
        )
        assert metadata.source_projection_sha256 == (
            hashlib.sha256(candidate_a["projection"].encode("utf-8")).hexdigest(),
            hashlib.sha256(candidate_b["projection"].encode("utf-8")).hexdigest(),
        )
        assert envelope.input_payload == before


def test_authorized_extraction_preserves_both_pairwise_identities() -> None:
    for envelope in build_v5_2_transfer_envelopes()[1:]:
        before = deepcopy(envelope.input_payload)
        metadata = extract_authorized_pairwise_projection_metadata(
            envelope,
            authorized_projection_sha256=(
                EXPECTED_V5_2_TRANSFER_PROJECTION_SHA256_BY_ID[envelope.call_id]
            ),
        )
        assert metadata.source_projection_ids
        assert envelope.transfer_payload_sha256() == (
            EXPECTED_V5_2_TRANSFER_PROJECTION_SHA256_BY_ID[envelope.call_id]
        )
        assert envelope.input_payload == before


def test_malformed_nested_payload_fails_closed() -> None:
    cases: tuple[tuple[dict[str, object], PairwiseRunnerErrorCode], ...] = (
        ({"candidate_a": None}, PairwiseRunnerErrorCode.CANDIDATE_FIELDS_INVALID),
        (
            {"candidate_a": {"candidate_id": "a"}},
            PairwiseRunnerErrorCode.CANDIDATE_FIELDS_INVALID,
        ),
        (
            {"candidate_a": {"candidate_id": "", "projection": "value"}},
            PairwiseRunnerErrorCode.CANDIDATE_VALUE_INVALID,
        ),
    )
    for mutation, expected in cases:
        payload = deepcopy(build_v5_2_transfer_envelopes()[1].input_payload)
        payload.update(mutation)
        with pytest.raises(PairwiseRunnerError) as captured:
            extract_pairwise_projection_metadata(payload)
        assert captured.value.code is expected


def test_nested_and_legacy_flat_ambiguity_fails_closed() -> None:
    payload = deepcopy(build_v5_2_transfer_envelopes()[1].input_payload)
    payload["candidate_a_id"] = "legacy-a"
    payload["candidate_a_projection"] = "legacy projection"
    with pytest.raises(PairwiseRunnerError) as captured:
        extract_pairwise_projection_metadata(payload)
    assert captured.value.code is PairwiseRunnerErrorCode.AMBIGUOUS_NESTED_AND_FLAT


def test_projection_hash_drift_fails_before_extraction() -> None:
    envelope = build_v5_2_transfer_envelopes()[1]
    with pytest.raises(PairwiseRunnerError) as captured:
        extract_authorized_pairwise_projection_metadata(
            envelope,
            authorized_projection_sha256="0" * 64,
        )
    assert captured.value.code is PairwiseRunnerErrorCode.PROJECTION_HASH_MISMATCH


def test_call_specs_and_projection_hashes_remain_unchanged() -> None:
    identities = {
        item.call_id: item
        for item in build_v5_2_call_specs()
        if item.call_id in V5_2_2_NEW_CALL_IDS
    }
    assert set(identities) == {SCN_06_PAIRWISE_CALL_ID, SCN_01_PAIRWISE_CALL_ID}
    for call_id, identity in identities.items():
        assert identity.sha256() == EXPECTED_V5_2_CALL_SPEC_SHA256_BY_ID[call_id]
        assert identity.transfer_projection_sha256 == (
            EXPECTED_V5_2_TRANSFER_PROJECTION_SHA256_BY_ID[call_id]
        )


def test_three_carry_forwards_and_exact_minimal_budget_are_ready() -> None:
    report, ledger = _safe_weak_records()
    weak = audit_weak_carry_forward_v5_2_2(report, ledger)
    plan = build_minimal_pairwise_pilot_v5_2_2(weak)
    assert strong_carry_forward_audit().eligible is True
    assert mixed_carry_forward_audit().eligible is True
    assert weak.eligible is True
    assert plan.logical_observation_count == V5_2_2_LOGICAL_OBSERVATION_COUNT == 5
    assert plan.carry_forward_count == V5_2_2_CARRY_FORWARD_COUNT == 3
    assert plan.new_call_count == V5_2_2_NEW_CALL_COUNT == 2
    assert plan.new_call_ids == V5_2_2_NEW_CALL_IDS
    assert plan.proposed_ceiling_usd == PROPOSED_V5_2_2_CEILING_USD == Decimal(
        "0.111200"
    )
    assert plan.approved_ceiling_usd is APPROVED_V5_2_2_CEILING_USD is None
    assert plan.live_provider_recalibration_authorized is False


def test_weak_carry_forward_fails_closed_on_provenance_drift() -> None:
    report, ledger = _safe_weak_records()
    calls = ledger["calls"]
    assert type(calls) is list
    call = calls[0]
    assert type(call) is dict
    semantic = call["semantic_safe_record"]
    assert type(semantic) is dict
    semantic["transfer_provenance_pass"] = False
    assert audit_weak_carry_forward_v5_2_2(report, ledger).eligible is False


def test_live_remains_closed() -> None:
    assert gate_v5_2.LIVE_PROVIDER_RECALIBRATION_AUTHORIZED is False
