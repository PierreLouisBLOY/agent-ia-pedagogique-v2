"""Offline preparation and fail-closed gates for the V5.1 semantic mini-pilot.

The module freezes a five-observation logical pilot made of one certified
micro-canary carry-forward and four new Anthropic scoring calls.  It is pure
data: it resolves no credential, opens no transport, and performs no live call.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from dataclasses import asdict, dataclass
from decimal import ROUND_CEILING, Decimal
from enum import StrEnum
from typing import NoReturn, cast

from tests.calibration.pedagogical.offline_calibration_v5 import v5_contract_sha256
from tests.calibration.pedagogical.pricing import (
    MODEL_PRICE_BY_NAME,
    pricing_snapshot_sha256,
)
from tests.calibration.pedagogical.scorer_contract_v5 import (
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

V5_1_MINI_PILOT_VERSION = "12.16-g2-v5.1-mini-pilot-v1"
MINI_PILOT_LOGICAL_OBSERVATION_COUNT = 5
MINI_PILOT_NEW_CALL_COUNT = 4
MICRO_CANARY_CARRY_FORWARD = True
PROPOSED_MINI_PILOT_CEILING_USD = Decimal("0.202400")
APPROVED_MINI_PILOT_CEILING_USD: Decimal | None = None
LIVE_PROVIDER_RECALIBRATION_AUTHORIZED = False

MINI_PILOT_NEW_CALL_IDS = (
    "cal.score.anchor.scn-06.mixed.marking-scheme-coherence.r1",
    "cal.score.anchor.scn-06.weak.marking-scheme-coherence.r1",
    (
        "cal.v5.pairwise.anchor.scn-06.strong-vs-mixed."
        "marking-scheme-coherence.r1"
    ),
    "cal.v5.pairwise.anchor.scn-01.strong-vs-mixed.clarity.r1",
)
MINI_PILOT_LOGICAL_CALL_IDS = (MICRO_CANARY_CALL_ID, *MINI_PILOT_NEW_CALL_IDS)

EXPECTED_MINI_PILOT_CALL_SPEC_SHA256_BY_ID = {
    MINI_PILOT_NEW_CALL_IDS[0]: (
        "67312b3b73f4cd872f2b6b2f0585d02149c403a29d00c44582370c3b42c93c19"
    ),
    MINI_PILOT_NEW_CALL_IDS[1]: (
        "72ccc17ccfece21b070c0ea9c19b3bb93538196b60ab0605b374069170478938"
    ),
    MINI_PILOT_NEW_CALL_IDS[2]: (
        "ded321befe1bb3f1c0402734e72be87e7ae7380f2990f22991919cb031725710"
    ),
    MINI_PILOT_NEW_CALL_IDS[3]: (
        "5f67866cd65327621d32c70e4688b58dec0bf6ee996a4376bee78f4ba0f62653"
    ),
}
EXPECTED_MINI_PILOT_TRANSFER_PROJECTION_SHA256_BY_ID = {
    MINI_PILOT_NEW_CALL_IDS[0]: (
        "67f465002c21186b552ba62289fe49ce765c75f9ccb99a8cad088ece44fa1b7a"
    ),
    MINI_PILOT_NEW_CALL_IDS[1]: (
        "8faf88c7f863294591d8ed3c47812db1d69edd8c38aafc98a1345f431f1af2dc"
    ),
    MINI_PILOT_NEW_CALL_IDS[2]: (
        "e2eba2625bc6674de898918b330abdab198faceec8f9ec90313ab68983cab0d8"
    ),
    MINI_PILOT_NEW_CALL_IDS[3]: (
        "8cfea454d79472cd04f9274f8e960db4fa7c7e69b562b7b9f9d673c01acc9b0d"
    ),
}


class V51MiniPilotVerdict(StrEnum):
    PASS = "V5_1_MINI_PILOT_PASS"
    FAIL = "V5_1_MINI_PILOT_FAIL"
    INCONCLUSIVE = "V5_1_MINI_PILOT_INCONCLUSIVE"


class V51MiniPilotGateErrorCode(StrEnum):
    BASELINE_MISMATCH = "BASELINE_MISMATCH"
    IDENTITY_MISMATCH = "IDENTITY_MISMATCH"
    CALL_NOT_PLANNED = "CALL_NOT_PLANNED"
    CALL_ORDER_INVALID = "CALL_ORDER_INVALID"
    CALL_ALREADY_COMPLETED = "CALL_ALREADY_COMPLETED"
    CARRY_FORWARD_INVALID = "CARRY_FORWARD_INVALID"
    APPROVED_CEILING_MISSING = "APPROVED_CEILING_MISSING"
    CEILING_MISMATCH = "CEILING_MISMATCH"
    PROVIDER_NOT_ALLOWED = "PROVIDER_NOT_ALLOWED"
    SEMANTIC_GATE_FAILED = "SEMANTIC_GATE_FAILED"
    LIVE_EXECUTION_FORBIDDEN = "LIVE_EXECUTION_FORBIDDEN"


class V51MiniPilotGateError(RuntimeError):
    code: V51MiniPilotGateErrorCode

    def __init__(self, code: V51MiniPilotGateErrorCode) -> None:
        self.code = code
        super().__init__(code.value)


@dataclass(frozen=True, slots=True)
class V51MiniPilotCallSpec:
    version: str
    call_id: str
    provider: str
    model: str
    source_call_spec_sha256: str
    parser_v5_1_sha256: str
    scorer_contract_sha256: str
    matrix_sha256: str
    pricing_sha256: str
    transfer_scope_sha256: str
    transfer_projection_sha256: str
    scenario_code: str
    criterion_refs: tuple[str, ...]
    input_refs: tuple[str, ...]
    expected_semantic_role: str
    expected_pairwise_decision: str | None
    max_input_tokens: int
    max_output_tokens: int

    def sha256(self) -> str:
        return _canonical_sha256(asdict(self))


@dataclass(frozen=True, slots=True)
class V51MicroCanaryCarryForwardRecord:
    call_id: str
    call_spec_sha256: str
    source_call_spec_sha256: str
    parser_v5_1_sha256: str
    scorer_contract_sha256: str
    matrix_sha256: str
    pricing_sha256: str
    transfer_scope_sha256: str
    transfer_projection_sha256: str
    scenario_code: str
    criterion_ref: str
    anchor_ref: str
    provider: str
    model: str
    max_input_tokens: int
    max_output_tokens: int
    parser_schema_status: str
    score_level: int
    raw_response_persistence: str
    live_authorization: str


@dataclass(frozen=True, slots=True)
class V51CarryForwardAudit:
    call_spec_equal: bool
    parser_equal: bool
    scorer_equal: bool
    matrix_equal: bool
    pricing_equal: bool
    transfer_scope_equal: bool
    transfer_projection_equal: bool
    criterion_anchor_equal: bool
    provider_model_equal: bool
    token_budget_equal: bool
    certified_result_valid: bool

    @property
    def eligible(self) -> bool:
        return all(asdict(self).values())


@dataclass(frozen=True, slots=True)
class V51MiniPilotBudgetItem:
    call_id: str
    maximum_input_tokens: int
    maximum_output_tokens: int
    maximum_before_margin_usd: Decimal
    proposed_ceiling_usd: Decimal


@dataclass(frozen=True, slots=True)
class V51MiniPilotBudget:
    new_call_count: int
    items: tuple[V51MiniPilotBudgetItem, ...]
    maximum_before_margin_usd: Decimal
    safety_margin_multiplier: Decimal
    safety_margin_usd: Decimal
    proposed_ceiling_usd: Decimal
    approved_ceiling_usd: Decimal | None


@dataclass(frozen=True, slots=True)
class V51MiniPilotSafeObservation:
    call_id: str
    parser_schema_pass: bool
    evidence_first_present: bool
    transfer_provenance_pass: bool
    score_level: int | None = None
    pairwise_decision: V5PairwiseDecision | None = None


@dataclass(frozen=True, slots=True)
class V51MiniPilotSemanticGateReport:
    verdict: V51MiniPilotVerdict
    failures: tuple[str, ...]
    parser_schema_pass: bool
    evidence_first_pass: bool
    transfer_provenance_pass: bool
    strict_low_mid_high: bool
    intermediate_score_present: bool
    pairwise_expected_pass: bool
    false_tie_absent: bool


@dataclass(frozen=True, slots=True)
class V51MiniPilotAuthorization:
    baseline_commit_sha: str
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


LIVE_MICRO_CANARY_CARRY_FORWARD_RECORD = V51MicroCanaryCarryForwardRecord(
    call_id=MICRO_CANARY_CALL_ID,
    call_spec_sha256=EXPECTED_MICRO_CANARY_CALL_SPEC_SHA256,
    source_call_spec_sha256=(
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
    scenario_code="SCN-06",
    criterion_ref="scn-06.quality.marking-scheme-coherence",
    anchor_ref="anchor:cal.v4.scn-06.315be9953fb2",
    provider="anthropic",
    model="claude-sonnet-5",
    max_input_tokens=8_000,
    max_output_tokens=2_048,
    parser_schema_status="PASS",
    score_level=4,
    raw_response_persistence="NONE",
    live_authorization="CONSUMED",
)


def build_mini_pilot_new_calls() -> tuple[V5LogicalCallSpec, ...]:
    robust = {item.call.call_id: item for item in build_robust_pilot().calls}
    try:
        calls = tuple(robust[call_id] for call_id in MINI_PILOT_NEW_CALL_IDS)
    except KeyError:
        _error(V51MiniPilotGateErrorCode.IDENTITY_MISMATCH)
    scenarios = {item.call.scenario_code for item in calls}
    absolute_roles = {
        _semantic_role(item)
        for item in calls
        if item.contract is V5CallContract.V5_ABSOLUTE_SCORE
    }
    pairwise_count = sum(
        item.contract is V5CallContract.V5_DIRECT_PAIRWISE for item in calls
    )
    if (
        len(calls) != MINI_PILOT_NEW_CALL_COUNT
        or len(scenarios) < 2
        or absolute_roles != {"INTERMEDIATE", "WEAK"}
        or pairwise_count != 2
    ):
        _error(V51MiniPilotGateErrorCode.IDENTITY_MISMATCH)
    return calls


def build_mini_pilot_transfer_envelopes() -> tuple[PedagogicalTransferEnvelope, ...]:
    return tuple(_envelope_for_spec(spec) for spec in build_mini_pilot_new_calls())


def build_mini_pilot_call_specs() -> tuple[V51MiniPilotCallSpec, ...]:
    envelopes = {
        item.call_id: item for item in build_mini_pilot_transfer_envelopes()
    }
    identities = tuple(
        _mini_pilot_call_spec(spec, envelopes[spec.call.call_id])
        for spec in build_mini_pilot_new_calls()
    )
    for identity in identities:
        expected = EXPECTED_MINI_PILOT_CALL_SPEC_SHA256_BY_ID[identity.call_id]
        if identity.sha256() != expected:
            _error(V51MiniPilotGateErrorCode.IDENTITY_MISMATCH)
    return identities


def micro_canary_carry_forward_audit(
    record: V51MicroCanaryCarryForwardRecord = LIVE_MICRO_CANARY_CARRY_FORWARD_RECORD,
) -> V51CarryForwardAudit:
    identity = build_micro_canary_spec()
    spec, envelope = micro_canary_source()
    call = spec.call
    return V51CarryForwardAudit(
        call_spec_equal=record.call_spec_sha256 == identity.sha256(),
        parser_equal=(
            record.parser_v5_1_sha256
            == identity.parser_v5_1_sha256
            == v5_1_parser_contract_sha256()
        ),
        scorer_equal=(
            record.scorer_contract_sha256
            == identity.scorer_contract_sha256
            == v5_contract_sha256()
        ),
        matrix_equal=(
            record.matrix_sha256
            == identity.matrix_sha256
            == v5_logical_matrix_sha256()
        ),
        pricing_equal=(
            record.pricing_sha256
            == identity.pricing_sha256
            == pricing_snapshot_sha256()
        ),
        transfer_scope_equal=(
            record.transfer_scope_sha256
            == identity.transfer_scope_sha256
            == pedagogical_transfer_scope_sha256()
        ),
        transfer_projection_equal=(
            record.transfer_projection_sha256
            == identity.transfer_projection_sha256
            == envelope.transfer_payload_sha256()
        ),
        criterion_anchor_equal=(
            record.call_id == call.call_id
            and record.scenario_code == call.scenario_code
            and (record.criterion_ref,) == call.criterion_refs
            and (record.anchor_ref,) == call.input_refs
        ),
        provider_model_equal=(
            record.provider == call.provider.value == identity.provider
            and record.model == call.model == identity.model
        ),
        token_budget_equal=(
            record.max_input_tokens
            == call.input_utf8_upper_bound_bytes
            == identity.max_input_tokens
            and record.max_output_tokens
            == call.max_output_tokens
            == identity.max_output_tokens
        ),
        certified_result_valid=(
            record.parser_schema_status == "PASS"
            and record.score_level == 4
            and record.raw_response_persistence == "NONE"
            and record.live_authorization == "CONSUMED"
        ),
    )


def estimate_mini_pilot_budget() -> V51MiniPilotBudget:
    items: list[V51MiniPilotBudgetItem] = []
    for spec in build_mini_pilot_new_calls():
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
            V51MiniPilotBudgetItem(
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
    budget = V51MiniPilotBudget(
        new_call_count=len(items),
        items=tuple(items),
        maximum_before_margin_usd=maximum_before,
        safety_margin_multiplier=COST_SAFETY_MARGIN,
        safety_margin_usd=_money(proposed - maximum_before),
        proposed_ceiling_usd=proposed,
        approved_ceiling_usd=APPROVED_MINI_PILOT_CEILING_USD,
    )
    if (
        budget.new_call_count != MINI_PILOT_NEW_CALL_COUNT
        or budget.proposed_ceiling_usd != PROPOSED_MINI_PILOT_CEILING_USD
    ):
        _error(V51MiniPilotGateErrorCode.IDENTITY_MISMATCH)
    return budget


def evaluate_mini_pilot_semantic_gates(
    observations: Mapping[str, V51MiniPilotSafeObservation],
) -> V51MiniPilotSemanticGateReport:
    expected = set(MINI_PILOT_LOGICAL_CALL_IDS)
    observed = set(observations)
    if expected != observed:
        return V51MiniPilotSemanticGateReport(
            verdict=V51MiniPilotVerdict.INCONCLUSIVE,
            failures=("OBSERVATION_SET_INCOMPLETE",),
            parser_schema_pass=False,
            evidence_first_pass=False,
            transfer_provenance_pass=False,
            strict_low_mid_high=False,
            intermediate_score_present=False,
            pairwise_expected_pass=False,
            false_tie_absent=False,
        )
    ordered = tuple(observations[call_id] for call_id in MINI_PILOT_LOGICAL_CALL_IDS)
    parser_pass = all(item.parser_schema_pass for item in ordered)
    evidence_pass = all(item.evidence_first_present for item in ordered)
    provenance_pass = all(item.transfer_provenance_pass for item in ordered)
    strong, mixed, weak = (ordered[index].score_level for index in range(3))
    valid_levels = all(type(level) is int and 0 <= level <= 4 for level in (strong, mixed, weak))
    strict_order = bool(valid_levels and cast(int, strong) > cast(int, mixed) > cast(int, weak))
    intermediate = bool(type(mixed) is int and 1 <= mixed <= 3)
    expected_decisions = (
        V5PairwiseDecision.A_BETTER,
        V5PairwiseDecision.A_BETTER,
    )
    actual_decisions = (ordered[3].pairwise_decision, ordered[4].pairwise_decision)
    pairwise_pass = actual_decisions == expected_decisions
    no_false_tie = all(item is not V5PairwiseDecision.TIE for item in actual_decisions)
    failures: list[str] = []
    if not parser_pass:
        failures.append("PARSER_SCHEMA")
    if not valid_levels:
        failures.append("SCORE_RANGE")
    if not strict_order:
        failures.append("LOW_MID_HIGH_ORDER")
    if not intermediate:
        failures.append("INTERMEDIATE_SCORE_MISSING")
    if not pairwise_pass:
        failures.append("PAIRWISE_EXPECTATION")
    if not no_false_tie:
        failures.append("FALSE_TIE")
    if not evidence_pass:
        failures.append("EVIDENCE_FIRST")
    if not provenance_pass:
        failures.append("TRANSFER_PROVENANCE")
    return V51MiniPilotSemanticGateReport(
        verdict=(V51MiniPilotVerdict.FAIL if failures else V51MiniPilotVerdict.PASS),
        failures=tuple(failures),
        parser_schema_pass=parser_pass,
        evidence_first_pass=evidence_pass,
        transfer_provenance_pass=provenance_pass,
        strict_low_mid_high=strict_order,
        intermediate_score_present=intermediate,
        pairwise_expected_pass=pairwise_pass,
        false_tie_absent=no_false_tie,
    )


class V51MiniPilotGate:
    """Pure-data, sequential gate before future credential resolution."""

    def authorize_next_before_credentials(
        self,
        *,
        observed_baseline_commit_sha: str,
        authorization: V51MiniPilotAuthorization,
        call_id: str,
        completed_new_call_ids: tuple[str, ...],
        safe_observations: Mapping[str, V51MiniPilotSafeObservation],
    ) -> V51MiniPilotCallSpec:
        identities = build_mini_pilot_call_specs()
        by_id = {item.call_id: item for item in identities}
        if observed_baseline_commit_sha != authorization.baseline_commit_sha:
            _error(V51MiniPilotGateErrorCode.BASELINE_MISMATCH)
        expected_specs = tuple((item.call_id, item.sha256()) for item in identities)
        expected_projections = tuple(
            (item.call_id, item.transfer_projection_sha256) for item in identities
        )
        if (
            authorization.parser_v5_1_sha256
            != EXPECTED_V5_1_PARSER_CONTRACT_SHA256
            or authorization.scorer_contract_sha256
            != EXPECTED_V5_SCORER_CONTRACT_SHA256
            or authorization.matrix_sha256 != EXPECTED_V5_MATRIX_SHA256
            or authorization.pricing_sha256 != pricing_snapshot_sha256()
            or authorization.transfer_scope_sha256
            != EXPECTED_PEDAGOGICAL_TRANSFER_SCOPE_SHA256
            or authorization.call_spec_sha256_by_id != expected_specs
            or authorization.transfer_projection_sha256_by_id
            != expected_projections
            or authorization.maximum_new_call_count != MINI_PILOT_NEW_CALL_COUNT
        ):
            _error(V51MiniPilotGateErrorCode.IDENTITY_MISMATCH)
        if not micro_canary_carry_forward_audit().eligible:
            _error(V51MiniPilotGateErrorCode.CARRY_FORWARD_INVALID)
        if authorization.approved_ceiling_usd is None:
            _error(V51MiniPilotGateErrorCode.APPROVED_CEILING_MISSING)
        if authorization.approved_ceiling_usd != PROPOSED_MINI_PILOT_CEILING_USD:
            _error(V51MiniPilotGateErrorCode.CEILING_MISMATCH)
        if authorization.provider != "anthropic":
            _error(V51MiniPilotGateErrorCode.PROVIDER_NOT_ALLOWED)
        if (
            authorization.live_provider_recalibration_authorized is not True
            or LIVE_PROVIDER_RECALIBRATION_AUTHORIZED is not True
        ):
            _error(V51MiniPilotGateErrorCode.LIVE_EXECUTION_FORBIDDEN)
        if call_id not in by_id:
            _error(V51MiniPilotGateErrorCode.CALL_NOT_PLANNED)
        if call_id in completed_new_call_ids or len(completed_new_call_ids) != len(
            set(completed_new_call_ids)
        ):
            _error(V51MiniPilotGateErrorCode.CALL_ALREADY_COMPLETED)
        expected_index = len(completed_new_call_ids)
        if (
            expected_index >= len(MINI_PILOT_NEW_CALL_IDS)
            or call_id != MINI_PILOT_NEW_CALL_IDS[expected_index]
            or completed_new_call_ids != MINI_PILOT_NEW_CALL_IDS[:expected_index]
        ):
            _error(V51MiniPilotGateErrorCode.CALL_ORDER_INVALID)
        if not _prior_stage_passes(expected_index, safe_observations):
            _error(V51MiniPilotGateErrorCode.SEMANTIC_GATE_FAILED)
        return by_id[call_id]


def validate_mini_pilot_preparation_offline() -> None:
    identities = build_mini_pilot_call_specs()
    envelopes = build_mini_pilot_transfer_envelopes()
    budget = estimate_mini_pilot_budget()
    if (
        not micro_canary_carry_forward_audit().eligible
        or len(identities) != MINI_PILOT_NEW_CALL_COUNT
        or len(envelopes) != MINI_PILOT_NEW_CALL_COUNT
        or len(MINI_PILOT_LOGICAL_CALL_IDS)
        != MINI_PILOT_LOGICAL_OBSERVATION_COUNT
        or budget.approved_ceiling_usd is not None
        or LIVE_PROVIDER_RECALIBRATION_AUTHORIZED is not False
    ):
        _error(V51MiniPilotGateErrorCode.IDENTITY_MISMATCH)


def _prior_stage_passes(
    expected_index: int,
    observations: Mapping[str, V51MiniPilotSafeObservation],
) -> bool:
    if expected_index == 0:
        return True
    mixed = observations.get(MINI_PILOT_NEW_CALL_IDS[0])
    if mixed is None or not _safe_observation_passes(mixed):
        return False
    if mixed.score_level is None or not 1 <= mixed.score_level <= 3:
        return False
    if expected_index == 1:
        return True
    weak = observations.get(MINI_PILOT_NEW_CALL_IDS[1])
    if weak is None or not _safe_observation_passes(weak):
        return False
    if weak.score_level is None or not 4 > mixed.score_level > weak.score_level >= 0:
        return False
    if expected_index == 2:
        return True
    pairwise = observations.get(MINI_PILOT_NEW_CALL_IDS[2])
    return bool(
        pairwise is not None
        and _safe_observation_passes(pairwise)
        and pairwise.pairwise_decision is V5PairwiseDecision.A_BETTER
    )


def _safe_observation_passes(item: V51MiniPilotSafeObservation) -> bool:
    return (
        item.parser_schema_pass
        and item.evidence_first_present
        and item.transfer_provenance_pass
    )


def _mini_pilot_call_spec(
    spec: V5LogicalCallSpec,
    envelope: PedagogicalTransferEnvelope,
) -> V51MiniPilotCallSpec:
    expected = spec.expected_pairwise_decision
    return V51MiniPilotCallSpec(
        version=V5_1_MINI_PILOT_VERSION,
        call_id=spec.call.call_id,
        provider=spec.call.provider.value,
        model=spec.call.model,
        source_call_spec_sha256=v5_call_spec_sha256(spec),
        parser_v5_1_sha256=v5_1_parser_contract_sha256(),
        scorer_contract_sha256=v5_contract_sha256(),
        matrix_sha256=v5_logical_matrix_sha256(),
        pricing_sha256=pricing_snapshot_sha256(),
        transfer_scope_sha256=pedagogical_transfer_scope_sha256(),
        transfer_projection_sha256=envelope.transfer_payload_sha256(),
        scenario_code=spec.call.scenario_code,
        criterion_refs=spec.call.criterion_refs,
        input_refs=spec.call.input_refs,
        expected_semantic_role=_semantic_role(spec),
        expected_pairwise_decision=(expected.value if expected is not None else None),
        max_input_tokens=spec.call.input_utf8_upper_bound_bytes,
        max_output_tokens=spec.call.max_output_tokens,
    )


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
        _error(V51MiniPilotGateErrorCode.IDENTITY_MISMATCH)
    envelope = PedagogicalTransferEnvelope(
        call_id=spec.call.call_id,
        projection_name=projection_name,
        model=spec.call.model,
        max_output_tokens=spec.call.max_output_tokens,
        system=system,
        input_payload=cast(dict[str, object], observation.as_payload()),
        output_schema=schema,
    )
    validate_transfer_envelope(envelope)
    expected_hash = EXPECTED_MINI_PILOT_TRANSFER_PROJECTION_SHA256_BY_ID[
        spec.call.call_id
    ]
    if envelope.transfer_payload_sha256() != expected_hash:
        _error(V51MiniPilotGateErrorCode.IDENTITY_MISMATCH)
    return envelope


def _semantic_role(spec: V5LogicalCallSpec) -> str:
    call_id = spec.call.call_id
    if ".mixed." in call_id:
        return "INTERMEDIATE"
    if ".weak." in call_id:
        return "WEAK"
    if spec.contract is V5CallContract.V5_DIRECT_PAIRWISE:
        return "PAIRWISE_KNOWN_PREFERENCE"
    _error(V51MiniPilotGateErrorCode.IDENTITY_MISMATCH)


def _canonical_sha256(value: object) -> str:
    return hashlib.sha256(
        json.dumps(
            value,
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        ).encode("utf-8")
    ).hexdigest()


def _money(value: Decimal) -> Decimal:
    return value.quantize(Decimal("0.000001"), rounding=ROUND_CEILING)


def _error(code: V51MiniPilotGateErrorCode) -> NoReturn:
    raise V51MiniPilotGateError(code) from None
