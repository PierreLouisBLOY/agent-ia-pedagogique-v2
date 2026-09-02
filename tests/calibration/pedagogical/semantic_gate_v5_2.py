"""Explicit, check-derived semantic gates for the offline V5.2 mini-pilot.

This module changes acceptance logic only.  It never resolves credentials, opens a
provider transport, mutates a historical anchor, or authorizes a live execution.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from dataclasses import asdict, dataclass
from decimal import ROUND_CEILING, Decimal
from enum import StrEnum
from typing import NoReturn

from tests.calibration.pedagogical.offline_calibration_v5 import v5_contract_sha256
from tests.calibration.pedagogical.pricing import (
    MODEL_PRICE_BY_NAME,
    pricing_snapshot_sha256,
)
from tests.calibration.pedagogical.scorer_contract_v5 import (
    V5_RUBRIC_BY_CRITERION,
    V5PairwiseDecision,
    V5PairwiseObservation,
    V5ScorerObservation,
    v5_pairwise_output_schema,
    v5_pairwise_system_instructions,
    v5_score_output_schema,
    v5_scorer_system_instructions,
)
from tests.calibration.pedagogical.semantic_integration_v5 import (
    COST_SAFETY_MARGIN,
    EXPECTED_V5_MATRIX_SHA256,
    EXPECTED_V5_SCORER_CONTRACT_SHA256,
    V5CallContract,
    V5LogicalCallSpec,
    build_robust_pilot,
    build_v5_observation,
    v5_call_spec_sha256,
    v5_logical_matrix_sha256,
)
from tests.calibration.pedagogical.semantic_micro_canary_v5_1 import (
    EXPECTED_MICRO_CANARY_CALL_SPEC_SHA256,
    EXPECTED_MICRO_CANARY_TRANSFER_PROJECTION_SHA256,
    MICRO_CANARY_CALL_ID,
    build_micro_canary_spec,
    micro_canary_source,
)
from tests.calibration.pedagogical.semantic_mini_pilot_v5_1 import (
    build_mini_pilot_call_specs,
    build_mini_pilot_transfer_envelopes,
)
from tests.calibration.pedagogical.semantic_parser_adapter_v5_1 import (
    EXPECTED_V5_1_PARSER_CONTRACT_SHA256,
    v5_1_parser_contract_sha256,
)
from tests.calibration.pedagogical.semantic_pilot_freeze_v5 import (
    EXPECTED_PEDAGOGICAL_TRANSFER_SCOPE_SHA256,
    PedagogicalTransferEnvelope,
    TransferProjectionName,
    pedagogical_transfer_scope_sha256,
    validate_transfer_envelope,
)

V5_2_GATE_VERSION = "12.16-g2-v5.2-semantic-gate-v1"
V5_2_MINI_PILOT_VERSION = "12.16-g2-v5.2-mini-pilot-v1"
V5_2_CARRY_FORWARD_COMPATIBILITY_VERSION = (
    "12.16-g2-v5.2-gate-only-carry-forward-v1"
)
V5_2_INTERMEDIATE_PROPOSAL_VERSION = (
    "12.16-g2-v5.2-intermediate-proposal-v1"
)
LIVE_PROVIDER_RECALIBRATION_AUTHORIZED = False
APPROVED_V5_2_MINI_PILOT_CEILING_USD: Decimal | None = None
PROPOSED_V5_2_MINI_PILOT_CEILING_USD = Decimal("0.156800")

SCN_06_CRITERION = "scn-06.quality.marking-scheme-coherence"
SCN_01_CRITERION = "scn-01.quality.clarity"
SCN_06_STRONG_ANCHOR_ID = "cal.v4.scn-06.315be9953fb2"
SCN_06_MIXED_ANCHOR_ID = "cal.v4.scn-06.a74ef2a40cb1"
SCN_06_WEAK_ANCHOR_ID = "cal.v4.scn-06.74ba8e9a9af4"
SCN_01_STRONG_ANCHOR_ID = "cal.v4.scn-01.dd7633bf2991"
SCN_01_MIXED_ANCHOR_ID = "cal.v4.scn-01.a865078efdc4"

MIXED_CALL_ID = "cal.score.anchor.scn-06.mixed.marking-scheme-coherence.r1"
WEAK_CALL_ID = "cal.score.anchor.scn-06.weak.marking-scheme-coherence.r1"
SCN_06_PAIRWISE_CALL_ID = (
    "cal.v5.pairwise.anchor.scn-06.strong-vs-mixed."
    "marking-scheme-coherence.r1"
)
SCN_01_PAIRWISE_CALL_ID = (
    "cal.v5.pairwise.anchor.scn-01.strong-vs-mixed.clarity.r1"
)

V5_2_CARRY_FORWARD_CALL_IDS = (MICRO_CANARY_CALL_ID, MIXED_CALL_ID)
V5_2_NEW_CALL_IDS = (
    WEAK_CALL_ID,
    SCN_06_PAIRWISE_CALL_ID,
    SCN_01_PAIRWISE_CALL_ID,
)
V5_2_LOGICAL_CALL_IDS = (*V5_2_CARRY_FORWARD_CALL_IDS, *V5_2_NEW_CALL_IDS)
V5_2_LOGICAL_OBSERVATION_COUNT = 5
V5_2_CARRY_FORWARD_COUNT = 2
V5_2_NEW_CALL_COUNT = 3
INTERMEDIATE_ANCHOR_AVAILABLE = False

EXPECTED_V5_2_TRANSFER_PROJECTION_SHA256_BY_ID = {
    WEAK_CALL_ID: "8faf88c7f863294591d8ed3c47812db1d69edd8c38aafc98a1345f431f1af2dc",
    SCN_06_PAIRWISE_CALL_ID: (
        "e2eba2625bc6674de898918b330abdab198faceec8f9ec90313ab68983cab0d8"
    ),
    SCN_01_PAIRWISE_CALL_ID: (
        "8cfea454d79472cd04f9274f8e960db4fa7c7e69b562b7b9f9d673c01acc9b0d"
    ),
}

# Frozen after construction.  The values are deliberately explicit and validated
# by the targeted tests; changing any expectation or call identity requires a new
# version and new owner review.
EXPECTED_V5_2_GATE_CONTRACT_SHA256 = (
    "8dc0bdb7ca57c586ac8db887fcb7078e16377e1f8ae30f2d153096ce630c7eea"
)
EXPECTED_V5_2_CALL_SPEC_SHA256_BY_ID = {
    WEAK_CALL_ID: "a3646f66bd0d274cf30daf3024bbad5d204bb0d8182963460107243a0d81b707",
    SCN_06_PAIRWISE_CALL_ID: (
        "691794a224c1f440225dca29dddf34aff90c6556210c583263b006607509c196"
    ),
    SCN_01_PAIRWISE_CALL_ID: (
        "d4143eca0ac6ba40152eecdc5c37cfa7c2f74b3cda39774db79feec54689c0ca"
    ),
}

_SCN_06_CHECK_IDS = tuple(
    item.check_id for item in V5_RUBRIC_BY_CRITERION[SCN_06_CRITERION].checks
)
_V5_1_RUBRIC_AUDIT_SOURCE = (
    "docs/development/phase_12_16_g2_v5_1_mixed_semantic_"
    "discrepancy_analysis/02_STRONG_MIXED_WEAK_RUBRIC_AUDIT.md"
)
_V5_1_RUBRIC_AUDIT_SHA256 = (
    "f89bca46054f09eb48770274ae0851a37e18040b1d16095ba9b0805f1b42ef77"
)
_V4_HUMAN_SOURCE = (
    "artifacts/calibration/12.16-g2-anchor-corpus-v4/"
    "completed_human_disposition_pairwise.md"
)
_V4_HUMAN_SOURCE_SHA256 = (
    "5748b0f223b3039b463f975de8d99772a9f18ad729535a73bd27dfcfc27042a6"
)


class V52AnchorRole(StrEnum):
    DELIVERY_CANDIDATE = "DELIVERY_CANDIDATE"
    NON_DELIVERABLE_NEGATIVE_CONTROL = "NON_DELIVERABLE_NEGATIVE_CONTROL"
    BLIND_PAIRWISE_PREVALIDATED = "BLIND_PAIRWISE_PREVALIDATED"


class V52ExpectationKind(StrEnum):
    ABSOLUTE = "ABSOLUTE"
    PAIRWISE = "PAIRWISE"


class V52Verdict(StrEnum):
    PASS = "V5_2_MINI_PILOT_PASS"
    FAIL = "V5_2_MINI_PILOT_FAIL"
    INCONCLUSIVE = "V5_2_MINI_PILOT_INCONCLUSIVE"


class V52GateErrorCode(StrEnum):
    BASELINE_MISMATCH = "BASELINE_MISMATCH"
    IDENTITY_MISMATCH = "IDENTITY_MISMATCH"
    CARRY_FORWARD_INVALID = "CARRY_FORWARD_INVALID"
    APPROVED_CEILING_MISSING = "APPROVED_CEILING_MISSING"
    CEILING_MISMATCH = "CEILING_MISMATCH"
    PROVIDER_NOT_ALLOWED = "PROVIDER_NOT_ALLOWED"
    LIVE_EXECUTION_FORBIDDEN = "LIVE_EXECUTION_FORBIDDEN"
    CALL_NOT_PLANNED = "CALL_NOT_PLANNED"
    CALL_ALREADY_COMPLETED = "CALL_ALREADY_COMPLETED"
    CALL_ORDER_INVALID = "CALL_ORDER_INVALID"
    SEMANTIC_GATE_FAILED = "SEMANTIC_GATE_FAILED"


class V52GateError(RuntimeError):
    code: V52GateErrorCode

    def __init__(self, code: V52GateErrorCode) -> None:
        self.code = code
        super().__init__(code.value)


@dataclass(frozen=True, slots=True)
class V52PrevalidationSource:
    path: str
    sha256: str


@dataclass(frozen=True, slots=True)
class V52ExpectedScoreRange:
    minimum: int
    maximum: int

    def __post_init__(self) -> None:
        if not (0 <= self.minimum <= self.maximum <= 4):
            raise ValueError("expected score range must stay inside 0..4")

    @property
    def exact(self) -> int | None:
        return self.minimum if self.minimum == self.maximum else None


@dataclass(frozen=True, slots=True)
class V52ExpectedPairwiseRelation:
    candidate_a_id: str
    candidate_b_id: str
    decision: V5PairwiseDecision


@dataclass(frozen=True, slots=True)
class V52SemanticExpectation:
    version: str
    call_id: str
    kind: V52ExpectationKind
    anchor_ids: tuple[str, ...]
    scenario_code: str
    criterion_ref: str
    anchor_role: V52AnchorRole
    expected_semantic_checks: tuple[str, ...]
    expected_score_range: V52ExpectedScoreRange | None
    expected_pairwise_relations: tuple[V52ExpectedPairwiseRelation, ...]
    human_prevalidation_sources: tuple[V52PrevalidationSource, ...]

    def __post_init__(self) -> None:
        if self.version != V5_2_GATE_VERSION:
            raise ValueError("expectation version mismatch")
        if not self.anchor_ids or not self.human_prevalidation_sources:
            raise ValueError("expectation provenance is required")
        if self.kind is V52ExpectationKind.ABSOLUTE:
            if (
                len(self.anchor_ids) != 1
                or self.expected_score_range is None
                or self.expected_pairwise_relations
            ):
                raise ValueError("absolute expectation shape is invalid")
        elif (
            len(self.anchor_ids) != 2
            or self.expected_score_range is not None
            or len(self.expected_pairwise_relations) != 1
        ):
            raise ValueError("pairwise expectation shape is invalid")

    def sha256(self) -> str:
        return _canonical_sha256(asdict(self))


def _absolute_expectation(
    *,
    call_id: str,
    anchor_id: str,
    role: V52AnchorRole,
    expected_checks: tuple[str, ...],
    expected_score: int,
) -> V52SemanticExpectation:
    return V52SemanticExpectation(
        version=V5_2_GATE_VERSION,
        call_id=call_id,
        kind=V52ExpectationKind.ABSOLUTE,
        anchor_ids=(anchor_id,),
        scenario_code="SCN-06",
        criterion_ref=SCN_06_CRITERION,
        anchor_role=role,
        expected_semantic_checks=expected_checks,
        expected_score_range=V52ExpectedScoreRange(expected_score, expected_score),
        expected_pairwise_relations=(),
        human_prevalidation_sources=(
            V52PrevalidationSource(
                _V5_1_RUBRIC_AUDIT_SOURCE,
                _V5_1_RUBRIC_AUDIT_SHA256,
            ),
            V52PrevalidationSource(_V4_HUMAN_SOURCE, _V4_HUMAN_SOURCE_SHA256),
        ),
    )


def _pairwise_expectation(
    *,
    call_id: str,
    scenario_code: str,
    criterion_ref: str,
    candidate_a_id: str,
    candidate_b_id: str,
) -> V52SemanticExpectation:
    return V52SemanticExpectation(
        version=V5_2_GATE_VERSION,
        call_id=call_id,
        kind=V52ExpectationKind.PAIRWISE,
        anchor_ids=(candidate_a_id, candidate_b_id),
        scenario_code=scenario_code,
        criterion_ref=criterion_ref,
        anchor_role=V52AnchorRole.BLIND_PAIRWISE_PREVALIDATED,
        expected_semantic_checks=(),
        expected_score_range=None,
        expected_pairwise_relations=(
            V52ExpectedPairwiseRelation(
                candidate_a_id,
                candidate_b_id,
                V5PairwiseDecision.A_BETTER,
            ),
        ),
        human_prevalidation_sources=(
            V52PrevalidationSource(_V4_HUMAN_SOURCE, _V4_HUMAN_SOURCE_SHA256),
        ),
    )


V5_2_SEMANTIC_EXPECTATIONS = (
    _absolute_expectation(
        call_id=MICRO_CANARY_CALL_ID,
        anchor_id=SCN_06_STRONG_ANCHOR_ID,
        role=V52AnchorRole.DELIVERY_CANDIDATE,
        expected_checks=_SCN_06_CHECK_IDS,
        expected_score=4,
    ),
    _absolute_expectation(
        call_id=MIXED_CALL_ID,
        anchor_id=SCN_06_MIXED_ANCHOR_ID,
        role=V52AnchorRole.NON_DELIVERABLE_NEGATIVE_CONTROL,
        expected_checks=(),
        expected_score=0,
    ),
    _absolute_expectation(
        call_id=WEAK_CALL_ID,
        anchor_id=SCN_06_WEAK_ANCHOR_ID,
        role=V52AnchorRole.NON_DELIVERABLE_NEGATIVE_CONTROL,
        expected_checks=(_SCN_06_CHECK_IDS[0],),
        expected_score=1,
    ),
    _pairwise_expectation(
        call_id=SCN_06_PAIRWISE_CALL_ID,
        scenario_code="SCN-06",
        criterion_ref=SCN_06_CRITERION,
        candidate_a_id=SCN_06_STRONG_ANCHOR_ID,
        candidate_b_id=SCN_06_MIXED_ANCHOR_ID,
    ),
    _pairwise_expectation(
        call_id=SCN_01_PAIRWISE_CALL_ID,
        scenario_code="SCN-01",
        criterion_ref=SCN_01_CRITERION,
        candidate_a_id=SCN_01_STRONG_ANCHOR_ID,
        candidate_b_id=SCN_01_MIXED_ANCHOR_ID,
    ),
)
V5_2_EXPECTATION_BY_CALL_ID = {
    item.call_id: item for item in V5_2_SEMANTIC_EXPECTATIONS
}


def expected_score_from_checks(expectation: V52SemanticExpectation) -> int:
    """Derive an exact absolute level from explicit checks, never from a tier name."""

    if expectation.kind is not V52ExpectationKind.ABSOLUTE:
        raise ValueError("pairwise expectations have no absolute score")
    expected = expectation.expected_score_range
    if expected is None or expected.exact is None:
        raise ValueError("an exact prevalidated range is required")
    if expected.exact != len(expectation.expected_semantic_checks):
        raise ValueError("score must equal the number of prevalidated checks")
    return expected.exact


def v5_2_gate_contract_sha256() -> str:
    payload = {
        "version": V5_2_GATE_VERSION,
        "expectations": [asdict(item) for item in V5_2_SEMANTIC_EXPECTATIONS],
        "score_derivation": "EXPLICIT_PREVALIDATED_CHECK_COUNT",
        "tier_name_inference": "FORBIDDEN",
        "intermediate_policy": "REQUIRE_ONLY_IF_PREVALIDATED_AVAILABLE",
        "distribution_policy": "AT_LEAST_TWO_DISTINCT_ABSOLUTE_LEVELS",
        "carry_forward_compatibility": V5_2_CARRY_FORWARD_COMPATIBILITY_VERSION,
    }
    return _canonical_sha256(payload)


@dataclass(frozen=True, slots=True)
class V52IntermediateAnchorProposal:
    version: str
    proposal_id: str
    scenario_code: str
    criterion_ref: str
    sections: tuple[tuple[str, str], ...]
    target_semantic_checks: tuple[str, ...]
    target_score: int
    status: str

    def projection(self) -> str:
        return "\n".join(f"[{code}] {text}" for code, text in self.sections)

    def projection_sha256(self) -> str:
        return hashlib.sha256(self.projection().encode()).hexdigest()


@dataclass(frozen=True, slots=True)
class V52IntermediateAnchorAudit:
    available: bool
    reviewed_historical_anchor_count: int
    human_check_validated_intermediate_anchor_ids: tuple[str, ...]
    reason: str
    proposal: V52IntermediateAnchorProposal


V5_2_INTERMEDIATE_ANCHOR_PROPOSAL = V52IntermediateAnchorProposal(
    version=V5_2_INTERMEDIATE_PROPOSAL_VERSION,
    proposal_id="cal.v5.2.proposed.scn-06.marking-scheme-coherence.intermediate-v1",
    scenario_code="SCN-06",
    criterion_ref=SCN_06_CRITERION,
    sections=(
        (
            "instructions",
            "Présenter la formule et le résultat de chaque question.",
        ),
        (
            "questions",
            "1. Calculer la TVA sur 200 unités hors taxe à 20 %. "
            "2. Calculer le montant TTC.",
        ),
        (
            "marking-scheme",
            "Question 1 : formule 1 point et résultat 2 points. "
            "Question 2 : formule 1 point et résultat 2 points. "
            "Aucun point séparé pour l'application numérique, l'unité ou la vérification.",
        ),
    ),
    target_semantic_checks=_SCN_06_CHECK_IDS[:2],
    target_score=2,
    status="PROPOSED_REQUIRES_HUMAN_PREVALIDATION",
)


def audit_intermediate_anchor_availability() -> V52IntermediateAnchorAudit:
    return V52IntermediateAnchorAudit(
        available=INTERMEDIATE_ANCHOR_AVAILABLE,
        reviewed_historical_anchor_count=24,
        human_check_validated_intermediate_anchor_ids=(),
        reason=(
            "The V4 human instrument records disposition and pairwise order, not an "
            "explicit V5 check set proving level 2 or 3. Synthetic V5 fixtures are "
            "not human-prevalidated historical anchors."
        ),
        proposal=V5_2_INTERMEDIATE_ANCHOR_PROPOSAL,
    )


def build_v5_2_new_calls() -> tuple[V5LogicalCallSpec, ...]:
    robust = {item.call.call_id: item for item in build_robust_pilot().calls}
    try:
        calls = tuple(robust[call_id] for call_id in V5_2_NEW_CALL_IDS)
    except KeyError:
        _error(V52GateErrorCode.IDENTITY_MISMATCH)
    if (
        len(calls) != V5_2_NEW_CALL_COUNT
        or {item.call.scenario_code for item in calls} != {"SCN-01", "SCN-06"}
        or sum(item.contract is V5CallContract.V5_ABSOLUTE_SCORE for item in calls) != 1
        or sum(item.contract is V5CallContract.V5_DIRECT_PAIRWISE for item in calls) != 2
        or V5_2_INTERMEDIATE_ANCHOR_PROPOSAL.proposal_id
        in {item.call.call_id for item in calls}
    ):
        _error(V52GateErrorCode.IDENTITY_MISMATCH)
    return calls


def _envelope_for_spec(spec: V5LogicalCallSpec) -> PedagogicalTransferEnvelope:
    observation = build_v5_observation(spec)
    if type(observation) is V5ScorerObservation:
        projection_name = TransferProjectionName.ABSOLUTE_ANCHOR
        system = v5_scorer_system_instructions()
        schema = v5_score_output_schema()
    elif type(observation) is V5PairwiseObservation:
        projection_name = TransferProjectionName.PAIRWISE_ANCHOR
        system = v5_pairwise_system_instructions()
        schema = v5_pairwise_output_schema()
    else:
        _error(V52GateErrorCode.IDENTITY_MISMATCH)
    envelope = PedagogicalTransferEnvelope(
        call_id=spec.call.call_id,
        projection_name=projection_name,
        model=spec.call.model,
        max_output_tokens=spec.call.max_output_tokens,
        system=system,
        input_payload=observation.as_payload(),
        output_schema=schema,
    )
    validate_transfer_envelope(envelope)
    return envelope


def build_v5_2_transfer_envelopes() -> tuple[PedagogicalTransferEnvelope, ...]:
    envelopes = tuple(_envelope_for_spec(spec) for spec in build_v5_2_new_calls())
    observed = {item.call_id: item.transfer_payload_sha256() for item in envelopes}
    if observed != EXPECTED_V5_2_TRANSFER_PROJECTION_SHA256_BY_ID:
        _error(V52GateErrorCode.IDENTITY_MISMATCH)
    return envelopes


@dataclass(frozen=True, slots=True)
class V52MiniPilotCallSpec:
    version: str
    call_id: str
    provider: str
    model: str
    provider_call_spec_sha256: str
    gate_contract_sha256: str
    expectation_sha256: str
    parser_v5_1_sha256: str
    scorer_contract_sha256: str
    matrix_sha256: str
    pricing_sha256: str
    transfer_scope_sha256: str
    transfer_projection_sha256: str
    scenario_code: str
    criterion_refs: tuple[str, ...]
    input_refs: tuple[str, ...]
    max_input_tokens: int
    max_output_tokens: int

    def sha256(self) -> str:
        return _canonical_sha256(asdict(self))


def build_v5_2_call_specs() -> tuple[V52MiniPilotCallSpec, ...]:
    envelopes = {item.call_id: item for item in build_v5_2_transfer_envelopes()}
    identities = tuple(
        V52MiniPilotCallSpec(
            version=V5_2_MINI_PILOT_VERSION,
            call_id=spec.call.call_id,
            provider=spec.call.provider.value,
            model=spec.call.model,
            provider_call_spec_sha256=v5_call_spec_sha256(spec),
            gate_contract_sha256=v5_2_gate_contract_sha256(),
            expectation_sha256=V5_2_EXPECTATION_BY_CALL_ID[
                spec.call.call_id
            ].sha256(),
            parser_v5_1_sha256=v5_1_parser_contract_sha256(),
            scorer_contract_sha256=v5_contract_sha256(),
            matrix_sha256=v5_logical_matrix_sha256(),
            pricing_sha256=pricing_snapshot_sha256(),
            transfer_scope_sha256=pedagogical_transfer_scope_sha256(),
            transfer_projection_sha256=envelopes[
                spec.call.call_id
            ].transfer_payload_sha256(),
            scenario_code=spec.call.scenario_code,
            criterion_refs=spec.call.criterion_refs,
            input_refs=spec.call.input_refs,
            max_input_tokens=spec.call.input_utf8_upper_bound_bytes,
            max_output_tokens=spec.call.max_output_tokens,
        )
        for spec in build_v5_2_new_calls()
    )
    expected = EXPECTED_V5_2_CALL_SPEC_SHA256_BY_ID
    if {
        item.call_id: item.sha256() for item in identities
    } != expected:
        _error(V52GateErrorCode.IDENTITY_MISMATCH)
    return identities


@dataclass(frozen=True, slots=True)
class V52BudgetItem:
    call_id: str
    maximum_input_tokens: int
    maximum_output_tokens: int
    maximum_before_margin_usd: Decimal
    proposed_ceiling_usd: Decimal


@dataclass(frozen=True, slots=True)
class V52Budget:
    new_call_count: int
    items: tuple[V52BudgetItem, ...]
    maximum_before_margin_usd: Decimal
    safety_margin_multiplier: Decimal
    safety_margin_usd: Decimal
    proposed_ceiling_usd: Decimal
    approved_ceiling_usd: Decimal | None


def estimate_v5_2_budget() -> V52Budget:
    items: list[V52BudgetItem] = []
    for spec in build_v5_2_new_calls():
        call = spec.call
        quote = MODEL_PRICE_BY_NAME[call.model]
        maximum = _money(
            (
                Decimal(call.input_utf8_upper_bound_bytes)
                * quote.input_usd_per_million_tokens
                + Decimal(call.max_output_tokens)
                * quote.output_usd_per_million_tokens
            )
            / Decimal(1_000_000)
        )
        items.append(
            V52BudgetItem(
                call_id=call.call_id,
                maximum_input_tokens=call.input_utf8_upper_bound_bytes,
                maximum_output_tokens=call.max_output_tokens,
                maximum_before_margin_usd=maximum,
                proposed_ceiling_usd=_money(maximum * COST_SAFETY_MARGIN),
            )
        )
    maximum_before = _money(
        sum((item.maximum_before_margin_usd for item in items), Decimal("0"))
    )
    proposed = _money(
        sum((item.proposed_ceiling_usd for item in items), Decimal("0"))
    )
    budget = V52Budget(
        new_call_count=len(items),
        items=tuple(items),
        maximum_before_margin_usd=maximum_before,
        safety_margin_multiplier=COST_SAFETY_MARGIN,
        safety_margin_usd=_money(proposed - maximum_before),
        proposed_ceiling_usd=proposed,
        approved_ceiling_usd=APPROVED_V5_2_MINI_PILOT_CEILING_USD,
    )
    if (
        budget.new_call_count != V5_2_NEW_CALL_COUNT
        or budget.proposed_ceiling_usd != PROPOSED_V5_2_MINI_PILOT_CEILING_USD
    ):
        _error(V52GateErrorCode.IDENTITY_MISMATCH)
    return budget


@dataclass(frozen=True, slots=True)
class V52HistoricalResultRecord:
    call_id: str
    historical_wrapper_call_spec_sha256: str
    provider_call_spec_sha256: str
    parser_v5_1_sha256: str
    scorer_contract_sha256: str
    matrix_sha256: str
    pricing_sha256: str
    transfer_scope_sha256: str
    transfer_projection_sha256: str
    provider: str
    model: str
    max_input_tokens: int
    max_output_tokens: int
    parser_schema_status: str
    score_level: int
    evidence_first_present: bool
    transfer_provenance_pass: bool
    raw_response_persistence: str
    live_authorization: str


STRONG_HISTORICAL_RESULT = V52HistoricalResultRecord(
    call_id=MICRO_CANARY_CALL_ID,
    historical_wrapper_call_spec_sha256=EXPECTED_MICRO_CANARY_CALL_SPEC_SHA256,
    provider_call_spec_sha256=(
        "f897bee689581b1ed126b90dc17b6ff0f5912137d3baffe6980469accc76806e"
    ),
    parser_v5_1_sha256=EXPECTED_V5_1_PARSER_CONTRACT_SHA256,
    scorer_contract_sha256=EXPECTED_V5_SCORER_CONTRACT_SHA256,
    matrix_sha256=EXPECTED_V5_MATRIX_SHA256,
    pricing_sha256=(
        "31f2a9287845da8986448f62abe312b2290af5e9578ff61643d1cb0045bfe1b8"
    ),
    transfer_scope_sha256=EXPECTED_PEDAGOGICAL_TRANSFER_SCOPE_SHA256,
    transfer_projection_sha256=EXPECTED_MICRO_CANARY_TRANSFER_PROJECTION_SHA256,
    provider="anthropic",
    model="claude-sonnet-5",
    max_input_tokens=8_000,
    max_output_tokens=2_048,
    parser_schema_status="PASS",
    score_level=4,
    evidence_first_present=True,
    transfer_provenance_pass=True,
    raw_response_persistence="NONE",
    live_authorization="CONSUMED",
)

MIXED_HISTORICAL_RESULT = V52HistoricalResultRecord(
    call_id=MIXED_CALL_ID,
    historical_wrapper_call_spec_sha256=(
        "67312b3b73f4cd872f2b6b2f0585d02149c403a29d00c44582370c3b42c93c19"
    ),
    provider_call_spec_sha256=(
        "d55351eadd12cab8da5bdc7c2fd8331198c132f95089df1bb753392bbf2a3361"
    ),
    parser_v5_1_sha256=EXPECTED_V5_1_PARSER_CONTRACT_SHA256,
    scorer_contract_sha256=EXPECTED_V5_SCORER_CONTRACT_SHA256,
    matrix_sha256=EXPECTED_V5_MATRIX_SHA256,
    pricing_sha256=(
        "31f2a9287845da8986448f62abe312b2290af5e9578ff61643d1cb0045bfe1b8"
    ),
    transfer_scope_sha256=EXPECTED_PEDAGOGICAL_TRANSFER_SCOPE_SHA256,
    transfer_projection_sha256=(
        "67f465002c21186b552ba62289fe49ce765c75f9ccb99a8cad088ece44fa1b7a"
    ),
    provider="anthropic",
    model="claude-sonnet-5",
    max_input_tokens=8_000,
    max_output_tokens=2_048,
    parser_schema_status="PASS",
    score_level=0,
    evidence_first_present=True,
    transfer_provenance_pass=True,
    raw_response_persistence="NONE",
    live_authorization="CONSUMED",
)


@dataclass(frozen=True, slots=True)
class V52CanonicalSourceIdentity:
    call_id: str
    historical_wrapper_call_spec_sha256: str
    provider_call_spec_sha256: str
    parser_v5_1_sha256: str
    scorer_contract_sha256: str
    matrix_sha256: str
    pricing_sha256: str
    transfer_scope_sha256: str
    transfer_projection_sha256: str
    provider: str
    model: str
    max_input_tokens: int
    max_output_tokens: int


def _canonical_source_identity(call_id: str) -> V52CanonicalSourceIdentity:
    if call_id == MICRO_CANARY_CALL_ID:
        identity = build_micro_canary_spec()
        spec, envelope = micro_canary_source()
    elif call_id == MIXED_CALL_ID:
        identities = {item.call_id: item for item in build_mini_pilot_call_specs()}
        envelopes = {
            item.call_id: item for item in build_mini_pilot_transfer_envelopes()
        }
        identity = identities[call_id]
        robust = {item.call.call_id: item for item in build_robust_pilot().calls}
        spec = robust[call_id]
        envelope = envelopes[call_id]
    else:
        raise ValueError("call is not a V5.2 carry-forward source")
    call = spec.call
    return V52CanonicalSourceIdentity(
        call_id=call_id,
        historical_wrapper_call_spec_sha256=identity.sha256(),
        provider_call_spec_sha256=v5_call_spec_sha256(spec),
        parser_v5_1_sha256=identity.parser_v5_1_sha256,
        scorer_contract_sha256=identity.scorer_contract_sha256,
        matrix_sha256=identity.matrix_sha256,
        pricing_sha256=identity.pricing_sha256,
        transfer_scope_sha256=identity.transfer_scope_sha256,
        transfer_projection_sha256=envelope.transfer_payload_sha256(),
        provider=call.provider.value,
        model=call.model,
        max_input_tokens=call.input_utf8_upper_bound_bytes,
        max_output_tokens=call.max_output_tokens,
    )


@dataclass(frozen=True, slots=True)
class V52CarryForwardAudit:
    call_id: str
    historical_call_spec_identical_to_v5_2_gate_identity: bool
    versioned_compatibility: bool
    compatibility_version: str
    provider_call_spec_equal: bool
    parser_equal: bool
    scorer_equal: bool
    matrix_equal: bool
    pricing_equal: bool
    transfer_scope_equal: bool
    transfer_projection_equal: bool
    provider_model_equal: bool
    token_budget_equal: bool
    expected_score_match: bool
    expected_check_count_match: bool
    provenance_intact: bool
    certified_result_valid: bool

    @property
    def eligible(self) -> bool:
        identity_compatible = (
            self.historical_call_spec_identical_to_v5_2_gate_identity
            or self.versioned_compatibility
        )
        checks = (
            self.provider_call_spec_equal,
            self.parser_equal,
            self.scorer_equal,
            self.matrix_equal,
            self.pricing_equal,
            self.transfer_scope_equal,
            self.transfer_projection_equal,
            self.provider_model_equal,
            self.token_budget_equal,
            self.expected_score_match,
            self.expected_check_count_match,
            self.provenance_intact,
            self.certified_result_valid,
        )
        return identity_compatible and all(checks)


def carry_forward_audit(
    record: V52HistoricalResultRecord,
) -> V52CarryForwardAudit:
    source = _canonical_source_identity(record.call_id)
    expectation = V5_2_EXPECTATION_BY_CALL_ID[record.call_id]
    expected_score = expected_score_from_checks(expectation)
    v5_2_gate_identity = _canonical_sha256(
        {
            "version": V5_2_CARRY_FORWARD_COMPATIBILITY_VERSION,
            "source_call_spec_sha256": source.provider_call_spec_sha256,
            "gate_contract_sha256": v5_2_gate_contract_sha256(),
            "expectation_sha256": expectation.sha256(),
        }
    )
    return V52CarryForwardAudit(
        call_id=record.call_id,
        historical_call_spec_identical_to_v5_2_gate_identity=(
            record.historical_wrapper_call_spec_sha256 == v5_2_gate_identity
        ),
        versioned_compatibility=(
            V5_2_CARRY_FORWARD_COMPATIBILITY_VERSION.endswith("carry-forward-v1")
            and record.historical_wrapper_call_spec_sha256
            == source.historical_wrapper_call_spec_sha256
        ),
        compatibility_version=V5_2_CARRY_FORWARD_COMPATIBILITY_VERSION,
        provider_call_spec_equal=(
            record.provider_call_spec_sha256 == source.provider_call_spec_sha256
        ),
        parser_equal=(
            record.parser_v5_1_sha256
            == source.parser_v5_1_sha256
            == v5_1_parser_contract_sha256()
        ),
        scorer_equal=(
            record.scorer_contract_sha256
            == source.scorer_contract_sha256
            == v5_contract_sha256()
        ),
        matrix_equal=(
            record.matrix_sha256
            == source.matrix_sha256
            == v5_logical_matrix_sha256()
        ),
        pricing_equal=(
            record.pricing_sha256
            == source.pricing_sha256
            == pricing_snapshot_sha256()
        ),
        transfer_scope_equal=(
            record.transfer_scope_sha256
            == source.transfer_scope_sha256
            == pedagogical_transfer_scope_sha256()
        ),
        transfer_projection_equal=(
            record.transfer_projection_sha256 == source.transfer_projection_sha256
        ),
        provider_model_equal=(
            record.provider == source.provider == "anthropic"
            and record.model == source.model == "claude-sonnet-5"
        ),
        token_budget_equal=(
            record.max_input_tokens == source.max_input_tokens
            and record.max_output_tokens == source.max_output_tokens
        ),
        expected_score_match=(record.score_level == expected_score),
        expected_check_count_match=(
            record.score_level == len(expectation.expected_semantic_checks)
        ),
        provenance_intact=record.transfer_provenance_pass,
        certified_result_valid=(
            record.parser_schema_status == "PASS"
            and record.evidence_first_present
            and record.raw_response_persistence == "NONE"
            and record.live_authorization == "CONSUMED"
        ),
    )


def strong_carry_forward_audit() -> V52CarryForwardAudit:
    return carry_forward_audit(STRONG_HISTORICAL_RESULT)


def mixed_carry_forward_audit() -> V52CarryForwardAudit:
    return carry_forward_audit(MIXED_HISTORICAL_RESULT)


@dataclass(frozen=True, slots=True)
class V52SafeObservation:
    call_id: str
    parser_schema_pass: bool
    evidence_first_present: bool
    transfer_provenance_pass: bool
    satisfied_check_ids: tuple[str, ...] = ()
    score_level: int | None = None
    pairwise_decision: V5PairwiseDecision | None = None


def carry_forward_observations() -> dict[str, V52SafeObservation]:
    result: dict[str, V52SafeObservation] = {}
    for record in (STRONG_HISTORICAL_RESULT, MIXED_HISTORICAL_RESULT):
        if not carry_forward_audit(record).eligible:
            _error(V52GateErrorCode.CARRY_FORWARD_INVALID)
        expectation = V5_2_EXPECTATION_BY_CALL_ID[record.call_id]
        result[record.call_id] = V52SafeObservation(
            call_id=record.call_id,
            parser_schema_pass=True,
            evidence_first_present=True,
            transfer_provenance_pass=True,
            satisfied_check_ids=expectation.expected_semantic_checks,
            score_level=record.score_level,
        )
    return result


@dataclass(frozen=True, slots=True)
class V52SemanticGateReport:
    verdict: V52Verdict
    failures: tuple[str, ...]
    parser_schema_pass: bool
    semantic_checks_pass: bool
    score_expectations_pass: bool
    pairwise_expectations_pass: bool
    intermediate_anchor_required: bool
    intermediate_score_present: bool
    distribution_non_degenerate: bool
    evidence_first_pass: bool
    transfer_provenance_pass: bool


def _observation_matches_expectation(
    observation: V52SafeObservation,
    expectation: V52SemanticExpectation,
) -> bool:
    if expectation.kind is V52ExpectationKind.ABSOLUTE:
        expected_range = expectation.expected_score_range
        return bool(
            expected_range is not None
            and type(observation.score_level) is int
            and expected_range.minimum
            <= observation.score_level
            <= expected_range.maximum
            and observation.satisfied_check_ids
            == expectation.expected_semantic_checks
            and observation.pairwise_decision is None
        )
    relation = expectation.expected_pairwise_relations[0]
    return bool(
        observation.score_level is None
        and not observation.satisfied_check_ids
        and observation.pairwise_decision is relation.decision
    )


def evaluate_v5_2_semantic_gate(
    observations: Mapping[str, V52SafeObservation],
) -> V52SemanticGateReport:
    expected_ids = set(V5_2_LOGICAL_CALL_IDS)
    if set(observations) != expected_ids:
        return V52SemanticGateReport(
            verdict=V52Verdict.INCONCLUSIVE,
            failures=("OBSERVATION_SET_INCOMPLETE",),
            parser_schema_pass=False,
            semantic_checks_pass=False,
            score_expectations_pass=False,
            pairwise_expectations_pass=False,
            intermediate_anchor_required=INTERMEDIATE_ANCHOR_AVAILABLE,
            intermediate_score_present=False,
            distribution_non_degenerate=False,
            evidence_first_pass=False,
            transfer_provenance_pass=False,
        )
    ordered = tuple(observations[call_id] for call_id in V5_2_LOGICAL_CALL_IDS)
    parser_pass = all(item.parser_schema_pass for item in ordered)
    evidence_pass = all(item.evidence_first_present for item in ordered)
    provenance_pass = all(item.transfer_provenance_pass for item in ordered)
    absolute_ids = tuple(
        item.call_id
        for item in V5_2_SEMANTIC_EXPECTATIONS
        if item.kind is V52ExpectationKind.ABSOLUTE
    )
    pairwise_ids = tuple(
        item.call_id
        for item in V5_2_SEMANTIC_EXPECTATIONS
        if item.kind is V52ExpectationKind.PAIRWISE
    )
    absolute_match = all(
        _observation_matches_expectation(
            observations[call_id], V5_2_EXPECTATION_BY_CALL_ID[call_id]
        )
        for call_id in absolute_ids
    )
    pairwise_match = all(
        _observation_matches_expectation(
            observations[call_id], V5_2_EXPECTATION_BY_CALL_ID[call_id]
        )
        for call_id in pairwise_ids
    )
    checks_pass = all(
        observations[call_id].satisfied_check_ids
        == V5_2_EXPECTATION_BY_CALL_ID[call_id].expected_semantic_checks
        for call_id in absolute_ids
    )
    scores = tuple(observations[call_id].score_level for call_id in absolute_ids)
    valid_scores = all(type(score) is int and 0 <= score <= 4 for score in scores)
    distribution = bool(valid_scores and len(set(scores)) >= 2)
    intermediate_present = any(
        type(score) is int and 2 <= score <= 3 for score in scores
    )
    intermediate_pass = (
        intermediate_present if INTERMEDIATE_ANCHOR_AVAILABLE else True
    )
    failures: list[str] = []
    if not parser_pass:
        failures.append("PARSER_SCHEMA")
    if not checks_pass:
        failures.append("SEMANTIC_CHECKS")
    if not absolute_match:
        failures.append("ABSOLUTE_EXPECTATIONS")
    if not pairwise_match:
        failures.append("PAIRWISE_EXPECTATIONS")
    if not intermediate_pass:
        failures.append("PREVALIDATED_INTERMEDIATE_MISSING")
    if not distribution:
        failures.append("DEGENERATE_DISTRIBUTION")
    if not evidence_pass:
        failures.append("EVIDENCE_FIRST")
    if not provenance_pass:
        failures.append("TRANSFER_PROVENANCE")
    return V52SemanticGateReport(
        verdict=V52Verdict.FAIL if failures else V52Verdict.PASS,
        failures=tuple(failures),
        parser_schema_pass=parser_pass,
        semantic_checks_pass=checks_pass,
        score_expectations_pass=absolute_match,
        pairwise_expectations_pass=pairwise_match,
        intermediate_anchor_required=INTERMEDIATE_ANCHOR_AVAILABLE,
        intermediate_score_present=intermediate_present,
        distribution_non_degenerate=distribution,
        evidence_first_pass=evidence_pass,
        transfer_provenance_pass=provenance_pass,
    )


@dataclass(frozen=True, slots=True)
class V52Authorization:
    baseline_commit_sha: str
    gate_contract_sha256: str
    parser_v5_1_sha256: str
    scorer_contract_sha256: str
    matrix_sha256: str
    pricing_sha256: str
    transfer_scope_sha256: str
    call_spec_sha256_by_id: tuple[tuple[str, str], ...]
    transfer_projection_sha256_by_id: tuple[tuple[str, str], ...]
    approved_ceiling_usd: Decimal | None
    maximum_new_call_count: int
    provider: str
    live_provider_recalibration_authorized: bool


class V52MiniPilotGate:
    """Sequential fail-closed gate driven only by explicit expectations."""

    def authorize_next_before_credentials(
        self,
        *,
        observed_baseline_commit_sha: str,
        authorization: V52Authorization,
        call_id: str,
        completed_new_call_ids: tuple[str, ...],
        new_observations: Mapping[str, V52SafeObservation],
    ) -> V52MiniPilotCallSpec:
        identities = build_v5_2_call_specs()
        by_id = {item.call_id: item for item in identities}
        if observed_baseline_commit_sha != authorization.baseline_commit_sha:
            _error(V52GateErrorCode.BASELINE_MISMATCH)
        if (
            authorization.gate_contract_sha256 != v5_2_gate_contract_sha256()
            or authorization.parser_v5_1_sha256
            != EXPECTED_V5_1_PARSER_CONTRACT_SHA256
            or authorization.scorer_contract_sha256
            != EXPECTED_V5_SCORER_CONTRACT_SHA256
            or authorization.matrix_sha256 != EXPECTED_V5_MATRIX_SHA256
            or authorization.pricing_sha256 != pricing_snapshot_sha256()
            or authorization.transfer_scope_sha256
            != EXPECTED_PEDAGOGICAL_TRANSFER_SCOPE_SHA256
            or authorization.call_spec_sha256_by_id
            != tuple((item.call_id, item.sha256()) for item in identities)
            or authorization.transfer_projection_sha256_by_id
            != tuple(
                (item.call_id, item.transfer_projection_sha256)
                for item in identities
            )
            or authorization.maximum_new_call_count != V5_2_NEW_CALL_COUNT
        ):
            _error(V52GateErrorCode.IDENTITY_MISMATCH)
        if not (
            strong_carry_forward_audit().eligible
            and mixed_carry_forward_audit().eligible
        ):
            _error(V52GateErrorCode.CARRY_FORWARD_INVALID)
        if authorization.approved_ceiling_usd is None:
            _error(V52GateErrorCode.APPROVED_CEILING_MISSING)
        if (
            authorization.approved_ceiling_usd
            != PROPOSED_V5_2_MINI_PILOT_CEILING_USD
        ):
            _error(V52GateErrorCode.CEILING_MISMATCH)
        if authorization.provider != "anthropic":
            _error(V52GateErrorCode.PROVIDER_NOT_ALLOWED)
        if (
            authorization.live_provider_recalibration_authorized is not True
            or LIVE_PROVIDER_RECALIBRATION_AUTHORIZED is not True
        ):
            _error(V52GateErrorCode.LIVE_EXECUTION_FORBIDDEN)
        if call_id not in by_id:
            _error(V52GateErrorCode.CALL_NOT_PLANNED)
        if call_id in completed_new_call_ids or len(completed_new_call_ids) != len(
            set(completed_new_call_ids)
        ):
            _error(V52GateErrorCode.CALL_ALREADY_COMPLETED)
        expected_index = len(completed_new_call_ids)
        if (
            expected_index >= len(V5_2_NEW_CALL_IDS)
            or call_id != V5_2_NEW_CALL_IDS[expected_index]
            or completed_new_call_ids != V5_2_NEW_CALL_IDS[:expected_index]
        ):
            _error(V52GateErrorCode.CALL_ORDER_INVALID)
        for completed_id in completed_new_call_ids:
            observation = new_observations.get(completed_id)
            if observation is None or not _observation_matches_expectation(
                observation,
                V5_2_EXPECTATION_BY_CALL_ID[completed_id],
            ):
                _error(V52GateErrorCode.SEMANTIC_GATE_FAILED)
        return by_id[call_id]


def validate_v5_2_preparation_offline() -> None:
    audit = audit_intermediate_anchor_availability()
    identities = build_v5_2_call_specs()
    envelopes = build_v5_2_transfer_envelopes()
    budget = estimate_v5_2_budget()
    if (
        v5_2_gate_contract_sha256() != EXPECTED_V5_2_GATE_CONTRACT_SHA256
        or {item.call_id: item.sha256() for item in identities}
        != EXPECTED_V5_2_CALL_SPEC_SHA256_BY_ID
        or len(V5_2_SEMANTIC_EXPECTATIONS) != V5_2_LOGICAL_OBSERVATION_COUNT
        or len(identities) != V5_2_NEW_CALL_COUNT
        or len(envelopes) != V5_2_NEW_CALL_COUNT
        or not strong_carry_forward_audit().eligible
        or not mixed_carry_forward_audit().eligible
        or audit.available
        or audit.proposal.status != "PROPOSED_REQUIRES_HUMAN_PREVALIDATION"
        or budget.approved_ceiling_usd is not None
        or LIVE_PROVIDER_RECALIBRATION_AUTHORIZED is not False
    ):
        _error(V52GateErrorCode.IDENTITY_MISMATCH)


def _canonical_sha256(value: object) -> str:
    return hashlib.sha256(
        json.dumps(
            value,
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        ).encode()
    ).hexdigest()


def _money(value: Decimal) -> Decimal:
    return value.quantize(Decimal("0.000001"), rounding=ROUND_CEILING)


def _error(code: V52GateErrorCode) -> NoReturn:
    raise V52GateError(code)
