"""Offline-only compatibility helpers for the V5.2.2 pairwise runner.

This module never resolves credentials or opens a provider transport.  It reads the
already-authorized canonical nested pairwise payload only after transfer-envelope
validation and projection-hash verification.
"""

from __future__ import annotations

import hashlib
from collections.abc import Mapping
from dataclasses import dataclass
from decimal import Decimal
from enum import StrEnum
from typing import NoReturn

from tests.calibration.pedagogical import semantic_gate_v5_2 as gate_v5_2
from tests.calibration.pedagogical.pricing import EXPECTED_PRICING_SNAPSHOT_SHA256
from tests.calibration.pedagogical.semantic_gate_v5_2 import (
    EXPECTED_V5_2_CALL_SPEC_SHA256_BY_ID,
    EXPECTED_V5_2_GATE_CONTRACT_SHA256,
    EXPECTED_V5_2_TRANSFER_PROJECTION_SHA256_BY_ID,
    SCN_01_PAIRWISE_CALL_ID,
    SCN_06_PAIRWISE_CALL_ID,
    V5_2_EXPECTATION_BY_CALL_ID,
    WEAK_CALL_ID,
    build_v5_2_call_specs,
    estimate_v5_2_budget,
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
    PedagogicalTransferEnvelope,
    TransferProjectionName,
    validate_transfer_envelope,
)

V5_2_2_PAIRWISE_RUNNER_VERSION = "12.16-g2-v5.2.2-pairwise-runner-v1"
V5_2_2_LOGICAL_OBSERVATION_COUNT = 5
V5_2_2_CARRY_FORWARD_COUNT = 3
V5_2_2_NEW_CALL_COUNT = 2
V5_2_2_NEW_CALL_IDS = (SCN_06_PAIRWISE_CALL_ID, SCN_01_PAIRWISE_CALL_ID)
PROPOSED_V5_2_2_CEILING_USD = Decimal("0.111200")
APPROVED_V5_2_2_CEILING_USD: Decimal | None = None
V5_2_INCONCLUSIVE_BASELINE = "e26d0d44f9d5e3c253623bb80fe357ec08ac3812"

_CANONICAL_PAIRWISE_FIELDS = {
    "contract_version",
    "comparison_id",
    "scenario",
    "criterion",
    "candidate_a",
    "candidate_b",
}
_CANDIDATE_FIELDS = {"candidate_id", "projection"}
_LEGACY_FLAT_FIELDS = {
    "candidate_a_id",
    "candidate_a_projection",
    "candidate_b_id",
    "candidate_b_projection",
}


class PairwiseRunnerErrorCode(StrEnum):
    NOT_PAIRWISE = "NOT_PAIRWISE"
    PROJECTION_HASH_MISMATCH = "PROJECTION_HASH_MISMATCH"
    AMBIGUOUS_NESTED_AND_FLAT = "AMBIGUOUS_NESTED_AND_FLAT"
    LEGACY_FLAT_UNSUPPORTED = "LEGACY_FLAT_UNSUPPORTED"
    PAYLOAD_FIELDS_INVALID = "PAYLOAD_FIELDS_INVALID"
    COMPARISON_ID_INVALID = "COMPARISON_ID_INVALID"
    CANDIDATE_FIELDS_INVALID = "CANDIDATE_FIELDS_INVALID"
    CANDIDATE_VALUE_INVALID = "CANDIDATE_VALUE_INVALID"
    CANDIDATE_IDS_DUPLICATE = "CANDIDATE_IDS_DUPLICATE"
    CARRY_FORWARD_INVALID = "CARRY_FORWARD_INVALID"
    BUDGET_IDENTITY_INVALID = "BUDGET_IDENTITY_INVALID"


class PairwiseRunnerError(RuntimeError):
    code: PairwiseRunnerErrorCode

    def __init__(self, code: PairwiseRunnerErrorCode) -> None:
        self.code = code
        super().__init__(code.value)


@dataclass(frozen=True, slots=True)
class PairwiseProjectionMetadata:
    comparison_id: str
    source_projection_ids: tuple[str, str]
    source_projection_sha256: tuple[str, str]

    def as_safe_record(self) -> dict[str, object]:
        return {
            "comparison_id": self.comparison_id,
            "source_projection_ids": list(self.source_projection_ids),
            "source_projection_sha256": list(self.source_projection_sha256),
        }


@dataclass(frozen=True, slots=True)
class WeakCarryForwardAuditV522:
    identity_contracts_equal: bool
    call_spec_equal: bool
    projection_equal: bool
    parser_schema_pass: bool
    score_equal: bool
    evidence_first_present: bool
    transfer_provenance_pass: bool
    response_raw_absent: bool
    authorization_consumed: bool
    single_emission_only: bool

    @property
    def eligible(self) -> bool:
        return all(
            (
                self.identity_contracts_equal,
                self.call_spec_equal,
                self.projection_equal,
                self.parser_schema_pass,
                self.score_equal,
                self.evidence_first_present,
                self.transfer_provenance_pass,
                self.response_raw_absent,
                self.authorization_consumed,
                self.single_emission_only,
            )
        )


@dataclass(frozen=True, slots=True)
class MinimalPairwisePilotV522:
    logical_observation_count: int
    carry_forward_count: int
    new_call_count: int
    new_call_ids: tuple[str, str]
    proposed_ceiling_usd: Decimal
    approved_ceiling_usd: Decimal | None
    live_provider_recalibration_authorized: bool


def extract_pairwise_projection_metadata(
    payload: Mapping[str, object],
) -> PairwiseProjectionMetadata:
    """Extract safe metadata from the exact canonical nested pairwise payload."""

    keys = set(payload)
    nested_present = "candidate_a" in keys or "candidate_b" in keys
    flat_present = bool(keys.intersection(_LEGACY_FLAT_FIELDS))
    if nested_present and flat_present:
        _error(PairwiseRunnerErrorCode.AMBIGUOUS_NESTED_AND_FLAT)
    if flat_present:
        _error(PairwiseRunnerErrorCode.LEGACY_FLAT_UNSUPPORTED)
    if keys != _CANONICAL_PAIRWISE_FIELDS:
        _error(PairwiseRunnerErrorCode.PAYLOAD_FIELDS_INVALID)
    comparison_id = payload.get("comparison_id")
    if type(comparison_id) is not str or not comparison_id:
        _error(PairwiseRunnerErrorCode.COMPARISON_ID_INVALID)
    candidate_a = _candidate(payload.get("candidate_a"))
    candidate_b = _candidate(payload.get("candidate_b"))
    if candidate_a[0] == candidate_b[0]:
        _error(PairwiseRunnerErrorCode.CANDIDATE_IDS_DUPLICATE)
    return PairwiseProjectionMetadata(
        comparison_id=comparison_id,
        source_projection_ids=(candidate_a[0], candidate_b[0]),
        source_projection_sha256=(
            _sha256_text(candidate_a[1]),
            _sha256_text(candidate_b[1]),
        ),
    )


def extract_authorized_pairwise_projection_metadata(
    envelope: PedagogicalTransferEnvelope,
    *,
    authorized_projection_sha256: str,
) -> PairwiseProjectionMetadata:
    """Validate scope and identity before reading nested A/B metadata."""

    if envelope.projection_name is not TransferProjectionName.PAIRWISE_ANCHOR:
        _error(PairwiseRunnerErrorCode.NOT_PAIRWISE)
    validate_transfer_envelope(envelope)
    if envelope.transfer_payload_sha256() != authorized_projection_sha256:
        _error(PairwiseRunnerErrorCode.PROJECTION_HASH_MISMATCH)
    return extract_pairwise_projection_metadata(envelope.input_payload)


def audit_weak_carry_forward_v5_2_2(
    safe_report: Mapping[str, object],
    ledger: Mapping[str, object],
) -> WeakCarryForwardAuditV522:
    """Audit only the safe V5.2 closure records; never read raw provider output."""

    calls = ledger.get("calls")
    call = calls[0] if type(calls) is list and len(calls) == 1 else None
    response = call.get("safe_response_record") if type(call) is dict else None
    semantic = call.get("semantic_safe_record") if type(call) is dict else None
    identity_contracts_equal = all(
        (
            safe_report.get("baseline_commit_sha") == V5_2_INCONCLUSIVE_BASELINE,
            safe_report.get("parser_v5_1_sha256")
            == EXPECTED_V5_1_PARSER_CONTRACT_SHA256,
            safe_report.get("scorer_contract_sha256")
            == EXPECTED_V5_SCORER_CONTRACT_SHA256,
            safe_report.get("matrix_sha256") == EXPECTED_V5_MATRIX_SHA256,
            safe_report.get("pricing_sha256") == EXPECTED_PRICING_SNAPSHOT_SHA256,
            safe_report.get("gate_contract_sha256")
            == EXPECTED_V5_2_GATE_CONTRACT_SHA256,
            safe_report.get("pedagogical_transfer_scope_sha256")
            == EXPECTED_PEDAGOGICAL_TRANSFER_SCOPE_SHA256,
        )
    )
    return WeakCarryForwardAuditV522(
        identity_contracts_equal=identity_contracts_equal,
        call_spec_equal=(
            type(call) is dict
            and call.get("call_id") == WEAK_CALL_ID
            and call.get("call_spec_sha256")
            == EXPECTED_V5_2_CALL_SPEC_SHA256_BY_ID[WEAK_CALL_ID]
        ),
        projection_equal=(
            type(call) is dict
            and call.get("transfer_payload_sha256")
            == EXPECTED_V5_2_TRANSFER_PROJECTION_SHA256_BY_ID[WEAK_CALL_ID]
        ),
        parser_schema_pass=(
            type(response) is dict
            and response.get("parser_schema_status") == "PASS"
            and response.get("terminal_status") == "COMPLETED"
        ),
        score_equal=(
            safe_report.get("weak_score") == 1
            and type(response) is dict
            and response.get("score_level") == 1
            and len(V5_2_EXPECTATION_BY_CALL_ID[WEAK_CALL_ID].expected_semantic_checks)
            == 1
        ),
        evidence_first_present=(
            type(semantic) is dict and semantic.get("evidence_first_present") is True
        ),
        transfer_provenance_pass=(
            type(semantic) is dict and semantic.get("transfer_provenance_pass") is True
        ),
        response_raw_absent=(
            safe_report.get("raw_response_persistence") == "NONE"
            and type(response) is dict
            and response.get("raw_response_persisted") is False
            and "output_text" not in response
        ),
        authorization_consumed=(
            safe_report.get("live_authorization") == "CONSUMED"
            and ledger.get("live_authorization") == "CONSUMED"
        ),
        single_emission_only=(
            safe_report.get("attempted") == 1
            and safe_report.get("completed") == 1
            and safe_report.get("rerun_count") == 0
            and type(calls) is list
            and len(calls) == 1
        ),
    )


def build_minimal_pairwise_pilot_v5_2_2(
    weak_audit: WeakCarryForwardAuditV522,
) -> MinimalPairwisePilotV522:
    """Build the two-call continuation plan from unchanged V5.2 identities."""

    if not (
        strong_carry_forward_audit().eligible
        and mixed_carry_forward_audit().eligible
        and weak_audit.eligible
    ):
        _error(PairwiseRunnerErrorCode.CARRY_FORWARD_INVALID)
    identities = build_v5_2_call_specs()
    pairwise_identities = tuple(
        item for item in identities if item.call_id in V5_2_2_NEW_CALL_IDS
    )
    budget = estimate_v5_2_budget()
    proposed = sum(
        (
            item.proposed_ceiling_usd
            for item in budget.items
            if item.call_id in V5_2_2_NEW_CALL_IDS
        ),
        Decimal("0"),
    )
    if (
        tuple(item.call_id for item in pairwise_identities) != V5_2_2_NEW_CALL_IDS
        or any(
            item.sha256() != EXPECTED_V5_2_CALL_SPEC_SHA256_BY_ID[item.call_id]
            or item.transfer_projection_sha256
            != EXPECTED_V5_2_TRANSFER_PROJECTION_SHA256_BY_ID[item.call_id]
            for item in pairwise_identities
        )
        or proposed != PROPOSED_V5_2_2_CEILING_USD
        or gate_v5_2.LIVE_PROVIDER_RECALIBRATION_AUTHORIZED is not False
    ):
        _error(PairwiseRunnerErrorCode.BUDGET_IDENTITY_INVALID)
    return MinimalPairwisePilotV522(
        logical_observation_count=V5_2_2_LOGICAL_OBSERVATION_COUNT,
        carry_forward_count=V5_2_2_CARRY_FORWARD_COUNT,
        new_call_count=V5_2_2_NEW_CALL_COUNT,
        new_call_ids=V5_2_2_NEW_CALL_IDS,
        proposed_ceiling_usd=proposed,
        approved_ceiling_usd=APPROVED_V5_2_2_CEILING_USD,
        live_provider_recalibration_authorized=False,
    )


def _candidate(value: object) -> tuple[str, str]:
    if type(value) is not dict or set(value) != _CANDIDATE_FIELDS:
        _error(PairwiseRunnerErrorCode.CANDIDATE_FIELDS_INVALID)
    candidate_id = value.get("candidate_id")
    projection = value.get("projection")
    if (
        type(candidate_id) is not str
        or not candidate_id
        or type(projection) is not str
        or not projection
    ):
        _error(PairwiseRunnerErrorCode.CANDIDATE_VALUE_INVALID)
    return candidate_id, projection


def _sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _error(code: PairwiseRunnerErrorCode) -> NoReturn:
    raise PairwiseRunnerError(code)
