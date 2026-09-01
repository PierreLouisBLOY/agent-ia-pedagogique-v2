from __future__ import annotations

import json
from copy import deepcopy
from dataclasses import replace
from decimal import Decimal

import pytest

import tests.calibration.pedagogical.semantic_pilot_freeze_v5 as freeze_module
from tests.calibration.pedagogical.semantic_pilot_freeze_v5 import (
    APPROVED_INTEGRATION_MANIFEST_SHA256,
    APPROVED_PILOT_CEILING_USD,
    EXPECTED_PEDAGOGICAL_TRANSFER_SCOPE_SHA256,
    EXPECTED_ROBUST_PILOT_SELECTION_SHA256,
    LIVE_PROVIDER_RECALIBRATION_AUTHORIZED,
    OWNER_SEMANTIC_PILOT_APPROVAL,
    PEDAGOGICAL_TRANSFER_AUTHORIZED,
    PILOT_MAX_CALL_COUNT,
    PILOT_MODE,
    PedagogicalTransferEnvelope,
    TransferProjectionName,
    TransferScopeError,
    TransferScopeErrorCode,
    TransferScopeGuard,
    build_pedagogical_transfer_envelopes,
    build_pedagogical_transfer_inventory,
    pedagogical_transfer_scope_payload,
    pedagogical_transfer_scope_sha256,
    robust_pilot_selection_sha256,
    validate_freeze_readiness,
    validate_post_approval_no_drift,
    validate_transfer_envelope,
)


def test_owner_approval_is_frozen_without_live_or_transfer_authority() -> None:
    assert OWNER_SEMANTIC_PILOT_APPROVAL == "APPROVED"
    assert PILOT_MODE == "ROBUST"
    assert PILOT_MAX_CALL_COUNT == 21
    assert APPROVED_PILOT_CEILING_USD == Decimal("1.017600")
    assert APPROVED_INTEGRATION_MANIFEST_SHA256 == (
        "6f7ef49bef952353787c6afa38fff38e5c36eb2b6f103bb32653707dbd56472f"
    )
    assert PEDAGOGICAL_TRANSFER_AUTHORIZED is False
    assert LIVE_PROVIDER_RECALIBRATION_AUTHORIZED is False
    validate_post_approval_no_drift()


def test_robust_selection_and_transfer_scope_hashes_are_exact_and_closed() -> None:
    assert robust_pilot_selection_sha256() == EXPECTED_ROBUST_PILOT_SELECTION_SHA256
    assert EXPECTED_PEDAGOGICAL_TRANSFER_SCOPE_SHA256 == (
        "c65e6460969d3eee4a5fb6a5d99e0a9bfbf3a253efc111ebb64e4af788df0e93"
    )
    assert (
        pedagogical_transfer_scope_sha256()
        == EXPECTED_PEDAGOGICAL_TRANSFER_SCOPE_SHA256
    )


def test_inventory_covers_all_21_payloads_and_27_projection_occurrences() -> None:
    envelopes = build_pedagogical_transfer_envelopes()
    inventory = build_pedagogical_transfer_inventory(envelopes)
    assert len(envelopes) == 21
    assert tuple(item.projection_name for item in inventory) == tuple(
        TransferProjectionName
    )
    assert tuple(item.payload_instance_count for item in inventory) == (15, 5, 1)
    assert tuple(
        item.pedagogical_projection_occurrence_count for item in inventory
    ) == (15, 10, 2)
    assert tuple(item.estimated_utf8_bytes for item in inventory) == (
        60_037,
        21_100,
        4_788,
    )
    assert all(item.provider == "anthropic" for item in inventory)
    assert all(
        not item.personal_data_present and not item.secrets_present
        for item in inventory
    )


def test_transfer_payload_allowlist_excludes_raw_files_paths_tiers_and_authority() -> None:
    envelopes = build_pedagogical_transfer_envelopes()
    for envelope in envelopes:
        validate_transfer_envelope(envelope)
        serialized = json.dumps(
            envelope.transfer_payload(), ensure_ascii=False, sort_keys=True
        ).casefold()
        assert all(
            marker not in serialized
            for marker in (
                "raw_output_path",
                "artifacts/calibration",
                "c:\\users",
                "file://",
                '"tier"',
                "expected_score",
                "expected_decision",
                '"credential"',
                '"secret"',
                "sqlite",
            )
        )
        assert set(envelope.transfer_payload()) == {
            "model",
            "max_output_tokens",
            "system",
            "input",
            "output_schema",
        }


def test_selected_output_payload_contains_only_two_minimized_projections() -> None:
    envelope = next(
        item
        for item in build_pedagogical_transfer_envelopes()
        if item.projection_name
        is TransferProjectionName.PAIRWISE_SELECTED_OUTPUT
    )
    payload = envelope.input_payload
    assert set(payload) == {
        "contract_version",
        "comparison_id",
        "scenario",
        "criterion",
        "candidate_a",
        "candidate_b",
    }
    for key in ("candidate_a", "candidate_b"):
        candidate = payload[key]
        assert type(candidate) is dict
        projection = candidate["projection"]
        assert type(projection) is str
        assert 0 < len(projection) <= 2_500
        assert "[objective]" in projection
    serialized = json.dumps(payload, ensure_ascii=False).casefold()
    assert all(
        marker not in serialized
        for marker in ("warnings", "uncertainties", "outcome", "raw_output")
    )


def test_scope_payload_changes_with_every_record_content_and_field() -> None:
    canonical = pedagogical_transfer_scope_payload()
    records = canonical["records"]
    assert type(records) is list and len(records) == 21
    first = deepcopy(records[0])
    assert type(first) is dict
    transfer = first["transfer_payload"]
    assert type(transfer) is dict
    transfer["unapproved_field"] = "not allowed"
    assert first != records[0]


def test_transfer_envelope_rejects_unapproved_field_before_transport() -> None:
    envelope = build_pedagogical_transfer_envelopes()[0]
    changed_input = deepcopy(envelope.input_payload)
    changed_input["local_path"] = "C:\\Users\\example\\source.txt"
    changed = replace(envelope, input_payload=changed_input)
    with pytest.raises(TransferScopeError) as error:
        validate_transfer_envelope(changed)
    assert error.value.code is TransferScopeErrorCode.TRANSFER_FIELD_FORBIDDEN


def test_transfer_guard_rejects_scope_mismatch_missing_authority_and_live(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    guard = TransferScopeGuard()
    envelopes = build_pedagogical_transfer_envelopes()
    with pytest.raises(TransferScopeError) as mismatch:
        guard.authorize_before_transport(
            envelopes=envelopes,
            authorized_transfer_scope_sha256="0" * 64,
        )
    assert mismatch.value.code is TransferScopeErrorCode.TRANSFER_SCOPE_MISMATCH

    with pytest.raises(TransferScopeError) as missing:
        guard.authorize_before_transport(
            envelopes=envelopes,
            authorized_transfer_scope_sha256=None,
        )
    assert (
        missing.value.code
        is TransferScopeErrorCode.TRANSFER_SCOPE_AUTHORIZATION_REQUIRED
    )

    with pytest.raises(TransferScopeError) as transfer_closed:
        guard.authorize_before_transport(
            envelopes=envelopes,
            authorized_transfer_scope_sha256=(
                EXPECTED_PEDAGOGICAL_TRANSFER_SCOPE_SHA256
            ),
        )
    assert (
        transfer_closed.value.code
        is TransferScopeErrorCode.TRANSFER_SCOPE_AUTHORIZATION_REQUIRED
    )

    monkeypatch.setattr(freeze_module, "PEDAGOGICAL_TRANSFER_AUTHORIZED", True)
    with pytest.raises(TransferScopeError) as live_closed:
        guard.authorize_before_transport(
            envelopes=envelopes,
            authorized_transfer_scope_sha256=(
                EXPECTED_PEDAGOGICAL_TRANSFER_SCOPE_SHA256
            ),
        )
    assert live_closed.value.code is TransferScopeErrorCode.LIVE_EXECUTION_FORBIDDEN


def test_transfer_guard_rejects_reordered_or_mutated_pilot_payloads() -> None:
    guard = TransferScopeGuard()
    envelopes = build_pedagogical_transfer_envelopes()
    reordered = (envelopes[1], envelopes[0], *envelopes[2:])
    with pytest.raises(TransferScopeError) as order_error:
        guard.authorize_before_transport(
            envelopes=reordered,
            authorized_transfer_scope_sha256=(
                EXPECTED_PEDAGOGICAL_TRANSFER_SCOPE_SHA256
            ),
        )
    assert order_error.value.code is TransferScopeErrorCode.TRANSFER_SCOPE_MISMATCH

    first = envelopes[0]
    changed_input = deepcopy(first.input_payload)
    changed_input["candidate_projection"] = "[summary] Changed content."
    changed: tuple[PedagogicalTransferEnvelope, ...] = (
        replace(first, input_payload=changed_input),
        *envelopes[1:],
    )
    with pytest.raises(TransferScopeError) as content_error:
        guard.authorize_before_transport(
            envelopes=changed,
            authorized_transfer_scope_sha256=(
                EXPECTED_PEDAGOGICAL_TRANSFER_SCOPE_SHA256
            ),
        )
    assert content_error.value.code is TransferScopeErrorCode.TRANSFER_SCOPE_MISMATCH


def test_freeze_readiness_is_offline_and_fail_closed() -> None:
    validate_freeze_readiness()
    assert PEDAGOGICAL_TRANSFER_AUTHORIZED is False
    assert LIVE_PROVIDER_RECALIBRATION_AUTHORIZED is False
