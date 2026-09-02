"""Offline V5 semantic calibration integration, planning, and reporting.

This module composes the immutable V4.2 logical matrix with the provider-neutral
V5 scorer contracts.  It never resolves credentials or opens a provider transport.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from dataclasses import asdict, dataclass
from decimal import ROUND_CEILING, Decimal
from enum import StrEnum
from pathlib import Path
from typing import NoReturn, cast

from tests.calibration.pedagogical.anchor_corpus_v4 import (
    V4_ANCHOR_EXPECTATIONS,
    V4_CALIBRATION_ANCHORS,
    v4_calibration_corpus_sha256,
)
from tests.calibration.pedagogical.call_plan import (
    CalibrationCallSpec,
    CalibrationProvider,
    CalibrationRole,
    CalibrationWorkload,
    CostEstimate,
)
from tests.calibration.pedagogical.catalog import AnchorTier, scenario_by_code
from tests.calibration.pedagogical.offline_calibration_v5 import v5_contract_sha256
from tests.calibration.pedagogical.pricing import (
    MODEL_PRICE_BY_NAME,
    PRICING_SNAPSHOT_ID,
    pricing_snapshot_sha256,
)
from tests.calibration.pedagogical.protocol import CalibrationCriterionItem
from tests.calibration.pedagogical.repair_tranche_v4_2 import (
    V42_LOGICAL_CALL_MATRIX,
    CallIdentityVersion,
    call_spec_identity,
)
from tests.calibration.pedagogical.scorer_contract_v5 import (
    V5_RUBRIC_BY_CRITERION,
    V5_SCORE_SCALE_VERSION,
    V5PairwiseDecision,
    V5PairwiseObservation,
    V5PairwiseOutcome,
    V5ScorerObservation,
    V5ScorerOutcome,
    V5ScoreStatus,
    build_v5_anchor_observation,
    parse_v5_pairwise_output,
    parse_v5_score_output,
    v5_pairwise_output_schema,
    v5_pairwise_system_instructions,
    v5_score_output_schema,
    v5_scorer_system_instructions,
)

ROOT = Path(__file__).resolve().parents[3]
V5_SEMANTIC_PLAN_VERSION = "12.16-g2-v5-semantic-integration-v1"
V5_BASELINE_COMMIT_SHA = "a560d6ca1989ba3dd13c9d02eeb97ef3fff6238b"
V42_SAFE_REPORT_PATH = Path("artifacts/calibration/12.16-g2-v4-2/safe_report.json")
V42_SAFE_REPORT_SHA256 = (
    "3cbe5c7bbf5fc0a4b34f0b3810656666969355d7fde3fa643b9ae05371082c1a"
)
V5_OFFLINE_MANIFEST_PATH = Path(
    "docs/development/phase_12_16_g2_v5_scorer_contract_redesign_offline/"
    "MANIFEST_SHA256.txt"
)
V5_OFFLINE_MANIFEST_SHA256 = (
    "2b86d0de9a3da8db87a8d55a6a3bfeb60fcdb0eead46b52178bdb6a9323d74c2"
)
EXPECTED_V5_SCORER_CONTRACT_SHA256 = (
    "a79928ba0aa402ffa012f353bd1a633b50c95e34eae368885c462690ec0b3344"
)
EXPECTED_V5_MATRIX_SHA256 = (
    "3c3a9eb418cb21ac44b657a49f0a3932443a5ea5c427bf32e359d680e2bc2d7c"
)
COST_SAFETY_MARGIN = Decimal("1.25")
PAIRWISE_INPUT_UTF8_UPPER_BOUND_BYTES = 12_000
V5_SCORER_MAX_OUTPUT_TOKENS = 2_048
APPROVED_PILOT_CEILING_USD: Decimal | None = None
LIVE_PROVIDER_RECALIBRATION_AUTHORIZED = False


class V5CallContract(StrEnum):
    V42_UNCHANGED = "V42_UNCHANGED"
    V5_ABSOLUTE_SCORE = "V5_ABSOLUTE_SCORE"
    V5_DIRECT_PAIRWISE = "V5_DIRECT_PAIRWISE"


class V5DiffReason(StrEnum):
    UNCHANGED = "UNCHANGED"
    SCORER_CONTRACT_AND_PROMPT_CHANGED = "SCORER_CONTRACT_AND_PROMPT_CHANGED"
    NEW_V5_PAIRWISE_CALL = "NEW_V5_PAIRWISE_CALL"


class V5PilotVerdict(StrEnum):
    PASS = "V5_SEMANTIC_PILOT_PASS"
    FAIL = "V5_SEMANTIC_PILOT_FAIL"
    INCONCLUSIVE = "V5_SEMANTIC_PILOT_INCONCLUSIVE"


class V5IntegrationErrorCode(StrEnum):
    SOURCE_REPORT_INVALID = "SOURCE_REPORT_INVALID"
    BASELINE_MISMATCH = "BASELINE_MISMATCH"
    MATRIX_MISMATCH = "MATRIX_MISMATCH"
    PRICING_MISMATCH = "PRICING_MISMATCH"
    MANIFEST_MISMATCH = "MANIFEST_MISMATCH"
    CONTRACT_MISMATCH = "CONTRACT_MISMATCH"
    CALL_NOT_PLANNED = "CALL_NOT_PLANNED"
    CALL_ALREADY_COMPLETED = "CALL_ALREADY_COMPLETED"
    CANARY_FANOUT_FORBIDDEN = "CANARY_FANOUT_FORBIDDEN"
    APPROVED_CEILING_MISSING = "APPROVED_CEILING_MISSING"
    APPROVED_CEILING_TOO_LOW = "APPROVED_CEILING_TOO_LOW"
    LIVE_EXECUTION_FORBIDDEN = "LIVE_EXECUTION_FORBIDDEN"


class V5IntegrationError(RuntimeError):
    code: V5IntegrationErrorCode

    def __init__(self, code: V5IntegrationErrorCode) -> None:
        self.code = code
        super().__init__(code.value)


@dataclass(frozen=True, slots=True)
class V5LogicalCallSpec:
    call: CalibrationCallSpec
    contract: V5CallContract
    expected_pairwise_decision: V5PairwiseDecision | None = None


@dataclass(frozen=True, slots=True)
class V5CallSpecIdentity:
    call_id: str
    provider: str
    model: str
    model_profile_id: str
    role: str
    workload: str
    scenario_code: str
    task_kind: str
    repetition: int
    prompt_input_sha256: str
    source_dependency_sha256: str
    criterion_refs: tuple[str, ...]
    declared_input_refs: tuple[str, ...]
    max_output_tokens: int
    input_utf8_upper_bound_bytes: int
    parser_or_scorer_contract_sha256: str
    pricing_snapshot_id: str
    pricing_sha256: str

    def sha256(self) -> str:
        return _canonical_sha256(asdict(self))


@dataclass(frozen=True, slots=True)
class V42ToV5Diff:
    call_id: str
    provider_unchanged: bool
    model_unchanged: bool
    model_profile_unchanged: bool
    role_unchanged: bool
    workload_unchanged: bool
    scenario_unchanged: bool
    task_kind_unchanged: bool
    repetition_unchanged: bool
    prompt_input_unchanged: bool
    dependencies_unchanged: bool
    criterion_refs_unchanged: bool
    scorer_parser_contract_unchanged: bool
    token_budget_unchanged: bool
    declared_input_refs_unchanged: bool
    pricing_identity_unchanged: bool
    call_spec_unchanged: bool
    source_terminal_status: str
    carry_forward_eligible: bool
    reason: V5DiffReason
    v42_call_spec_sha256: str
    v5_call_spec_sha256: str


@dataclass(frozen=True, slots=True)
class V5PilotPlan:
    name: str
    calls: tuple[V5LogicalCallSpec, ...]
    canary_call_ids: tuple[str, ...]
    fanout_call_ids: tuple[str, ...]
    purpose: str
    limitation: str


@dataclass(frozen=True, slots=True)
class V5PilotBudget:
    name: str
    openai_call_count: int
    anthropic_call_count: int
    estimate: CostEstimate
    safety_margin_usd: Decimal
    proposed_pilot_ceiling_usd: Decimal
    approved_pilot_ceiling_usd: Decimal | None


@dataclass(frozen=True, slots=True)
class V5PilotReport:
    verdict: V5PilotVerdict
    matrix_sha256: str
    scorer_contract_sha256: str
    pricing_sha256: str
    scale_version: str
    carry_forward_count: int
    planned_new_call_count: int
    completed_new_call_count: int
    score_histogram: tuple[tuple[int, int], ...]
    extreme_score_count: int
    extreme_score_rate: str | None
    intermediate_score_count: int
    intermediate_score_rate: str | None
    strict_monotonicity_count: int
    covered_triplet_count: int
    inversion_count: int
    pairwise_expected_count: int
    pairwise_correct_count: int
    pairwise_decisions: tuple[tuple[str, int], ...]
    parser_schema_pass: bool
    canary_passed: bool
    provenance_intact: bool
    gate_failures: tuple[str, ...]

    def safe_payload(self) -> dict[str, object]:
        return {
            **asdict(self),
            "verdict": self.verdict.value,
            "score_histogram": [list(item) for item in self.score_histogram],
            "pairwise_decisions": [list(item) for item in self.pairwise_decisions],
            "candidate_content_included": False,
            "provider_calls_performed_by_reporter": 0,
        }


_ANCHOR_BY_ID = {item.anchor_id: item for item in V4_CALIBRATION_ANCHORS}
_TIER_BY_ANCHOR_ID = {item.anchor_id: item.tier for item in V4_ANCHOR_EXPECTATIONS}
_ANCHOR_BY_SCENARIO_TIER = {
    (_ANCHOR_BY_ID[item.anchor_id].scenario_code, item.tier): _ANCHOR_BY_ID[
        item.anchor_id
    ]
    for item in V4_ANCHOR_EXPECTATIONS
}
_V42_BY_ID = {item.call_id: item for item in V42_LOGICAL_CALL_MATRIX}


def _pairwise_call(
    *,
    call_id: str,
    scenario_code: str,
    criterion_ref: str,
    input_refs: tuple[str, str],
    expected: V5PairwiseDecision,
) -> V5LogicalCallSpec:
    scenario = scenario_by_code(scenario_code)
    return V5LogicalCallSpec(
        call=CalibrationCallSpec(
            call_id=call_id,
            provider=CalibrationProvider.ANTHROPIC,
            model="claude-sonnet-5",
            model_profile_id="anthropic.claude-sonnet-5.scorer",
            role=CalibrationRole.JUDGE,
            workload=CalibrationWorkload.SCORING,
            scenario_code=scenario_code,
            task_kind=scenario.task_kind,
            repetition=1,
            max_output_tokens=V5_SCORER_MAX_OUTPUT_TOKENS,
            input_utf8_upper_bound_bytes=PAIRWISE_INPUT_UTF8_UPPER_BOUND_BYTES,
            criterion_refs=(criterion_ref,),
            input_refs=input_refs,
        ),
        contract=V5CallContract.V5_DIRECT_PAIRWISE,
        expected_pairwise_decision=expected,
    )


def _anchor_ref(scenario_code: str, tier: AnchorTier) -> str:
    return f"anchor:{_ANCHOR_BY_SCENARIO_TIER[(scenario_code, tier)].anchor_id}"


_ANCHOR_PAIRWISE_CALLS = (
    _pairwise_call(
        call_id="cal.v5.pairwise.anchor.scn-01.strong-vs-mixed.clarity.r1",
        scenario_code="SCN-01",
        criterion_ref="scn-01.quality.clarity",
        input_refs=(
            _anchor_ref("SCN-01", AnchorTier.STRONG),
            _anchor_ref("SCN-01", AnchorTier.MIXED),
        ),
        expected=V5PairwiseDecision.A_BETTER,
    ),
    _pairwise_call(
        call_id="cal.v5.pairwise.anchor.scn-04.mixed-vs-strong.fidelity.r1",
        scenario_code="SCN-04",
        criterion_ref="scn-04.quality.fidelity",
        input_refs=(
            _anchor_ref("SCN-04", AnchorTier.MIXED),
            _anchor_ref("SCN-04", AnchorTier.STRONG),
        ),
        expected=V5PairwiseDecision.B_BETTER,
    ),
    _pairwise_call(
        call_id=(
            "cal.v5.pairwise.anchor.scn-06.strong-vs-mixed."
            "assessment-clarity.r1"
        ),
        scenario_code="SCN-06",
        criterion_ref="scn-06.quality.assessment-clarity",
        input_refs=(
            _anchor_ref("SCN-06", AnchorTier.STRONG),
            _anchor_ref("SCN-06", AnchorTier.MIXED),
        ),
        expected=V5PairwiseDecision.A_BETTER,
    ),
    _pairwise_call(
        call_id=(
            "cal.v5.pairwise.anchor.scn-06.strong-vs-mixed."
            "marking-scheme-coherence.r1"
        ),
        scenario_code="SCN-06",
        criterion_ref="scn-06.quality.marking-scheme-coherence",
        input_refs=(
            _anchor_ref("SCN-06", AnchorTier.STRONG),
            _anchor_ref("SCN-06", AnchorTier.MIXED),
        ),
        expected=V5PairwiseDecision.A_BETTER,
    ),
    _pairwise_call(
        call_id=(
            "cal.v5.pairwise.anchor.scn-08.mixed-vs-strong."
            "distractor-quality.r1"
        ),
        scenario_code="SCN-08",
        criterion_ref="scn-08.quality.distractor-quality",
        input_refs=(
            _anchor_ref("SCN-08", AnchorTier.MIXED),
            _anchor_ref("SCN-08", AnchorTier.STRONG),
        ),
        expected=V5PairwiseDecision.B_BETTER,
    ),
)

_SELECTED_OUTPUT_PAIRS = {
    "SCN-03": (
        "cal.generation.course.primary.r1",
        "cal.generation.course.fallback.r1",
    ),
    "SCN-06": (
        "cal.generation.assessment.primary.r1",
        "cal.generation.assessment.fallback.r1",
    ),
    "SCN-07": (
        "cal.correction.remediation.primary.r1",
        "cal.correction.remediation.fallback.r1",
    ),
}
_OUTPUT_PAIRWISE_CALLS = tuple(
    _pairwise_call(
        call_id=(
            f"cal.v5.pairwise.output.{scenario_code.lower()}.primary-vs-fallback."
            f"{criterion_ref.rsplit('.', 1)[-1]}.r1"
        ),
        scenario_code=scenario_code,
        criterion_ref=criterion_ref,
        input_refs=(f"output:{source_a}", f"output:{source_b}"),
        expected=V5PairwiseDecision.TIE,
    )
    for scenario_code, (source_a, source_b) in _SELECTED_OUTPUT_PAIRS.items()
    for criterion_ref in scenario_by_code(scenario_code).criterion_refs
)

V5_LOGICAL_CALL_MATRIX = tuple(
    V5LogicalCallSpec(
        call=call,
        contract=(
            V5CallContract.V42_UNCHANGED
            if call.provider is CalibrationProvider.OPENAI
            else V5CallContract.V5_ABSOLUTE_SCORE
        ),
    )
    for call in V42_LOGICAL_CALL_MATRIX
) + _ANCHOR_PAIRWISE_CALLS + _OUTPUT_PAIRWISE_CALLS
_V5_BY_ID = {item.call.call_id: item for item in V5_LOGICAL_CALL_MATRIX}

MINIMAL_PILOT_CALL_IDS = (
    "cal.score.anchor.scn-06.strong.marking-scheme-coherence.r1",
    "cal.score.anchor.scn-06.mixed.marking-scheme-coherence.r1",
    "cal.score.anchor.scn-06.weak.marking-scheme-coherence.r1",
    "cal.v5.pairwise.anchor.scn-06.strong-vs-mixed.marking-scheme-coherence.r1",
)
_ROBUST_CRITERIA = (
    ("SCN-01", "scn-01.quality.clarity"),
    ("SCN-04", "scn-04.quality.fidelity"),
    ("SCN-06", "scn-06.quality.assessment-clarity"),
    ("SCN-06", "scn-06.quality.marking-scheme-coherence"),
    ("SCN-08", "scn-08.quality.distractor-quality"),
)


def _absolute_triplet_ids(scenario_code: str, criterion_ref: str) -> tuple[str, ...]:
    criterion = criterion_ref.rsplit(".", 1)[-1]
    prefix = f"cal.score.anchor.{scenario_code.lower()}"
    return tuple(f"{prefix}.{tier}.{criterion}.r1" for tier in ("strong", "mixed", "weak"))


_ROBUST_REMAINING_ABSOLUTE_IDS = tuple(
    call_id
    for scenario_code, criterion_ref in _ROBUST_CRITERIA
    for call_id in _absolute_triplet_ids(scenario_code, criterion_ref)
    if call_id not in MINIMAL_PILOT_CALL_IDS
)
_ROBUST_REMAINING_ANCHOR_PAIRWISE_IDS = tuple(
    item.call.call_id
    for item in _ANCHOR_PAIRWISE_CALLS
    if item.call.call_id not in MINIMAL_PILOT_CALL_IDS
)
ROBUST_PILOT_CALL_IDS = (
    *MINIMAL_PILOT_CALL_IDS,
    *_ROBUST_REMAINING_ABSOLUTE_IDS,
    *_ROBUST_REMAINING_ANCHOR_PAIRWISE_IDS,
    "cal.v5.pairwise.output.scn-03.primary-vs-fallback.clarity.r1",
)


def build_minimal_pilot() -> V5PilotPlan:
    calls = tuple(_V5_BY_ID[call_id] for call_id in MINIMAL_PILOT_CALL_IDS)
    return V5PilotPlan(
        name="MINIMAL_PILOT",
        calls=calls,
        canary_call_ids=MINIMAL_PILOT_CALL_IDS,
        fanout_call_ids=(),
        purpose=(
            "One real Strong/Mixed/Weak triplet plus one direct pairwise decision "
            "tests schema, scale use, monotonicity, inversions, and pairwise behavior."
        ),
        limitation="Covers one historically inverted criterion only.",
    )


def build_robust_pilot() -> V5PilotPlan:
    calls = tuple(_V5_BY_ID[call_id] for call_id in ROBUST_PILOT_CALL_IDS)
    return V5PilotPlan(
        name="ROBUST_PILOT",
        calls=calls,
        canary_call_ids=MINIMAL_PILOT_CALL_IDS,
        fanout_call_ids=ROBUST_PILOT_CALL_IDS[len(MINIMAL_PILOT_CALL_IDS) :],
        purpose=(
            "Covers all five historical inversion criteria, both A/B pairwise "
            "winner orientations, and one near-equivalent output tie."
        ),
        limitation="Still a diagnostic pilot, not a release threshold or full rerun.",
    )


def v5_call_spec_identity(spec: V5LogicalCallSpec) -> V5CallSpecIdentity:
    call = spec.call
    historical = _V42_BY_ID.get(call.call_id)
    if spec.contract is V5CallContract.V42_UNCHANGED:
        if historical is None:
            _error(V5IntegrationErrorCode.MATRIX_MISMATCH)
        old = call_spec_identity(historical, CallIdentityVersion.V42_CORRECTIVE)
        return V5CallSpecIdentity(
            call_id=call.call_id,
            provider=call.provider.value,
            model=call.model,
            model_profile_id=call.model_profile_id,
            role=call.role.value,
            workload=call.workload.value,
            scenario_code=call.scenario_code,
            task_kind=call.task_kind,
            repetition=call.repetition,
            prompt_input_sha256=old.prompt_input_sha256,
            source_dependency_sha256=old.source_dependency_sha256,
            criterion_refs=call.criterion_refs,
            declared_input_refs=call.input_refs,
            max_output_tokens=call.max_output_tokens,
            input_utf8_upper_bound_bytes=call.input_utf8_upper_bound_bytes,
            parser_or_scorer_contract_sha256=old.parser_or_scorer_contract_sha256,
            pricing_snapshot_id=PRICING_SNAPSHOT_ID,
            pricing_sha256=pricing_snapshot_sha256(),
        )
    dependency_sha = _v5_dependency_sha256(spec)
    contract_sha = EXPECTED_V5_SCORER_CONTRACT_SHA256
    projection = {
        "contract_kind": spec.contract.value,
        "system_instructions": (
            v5_scorer_system_instructions()
            if spec.contract is V5CallContract.V5_ABSOLUTE_SCORE
            else v5_pairwise_system_instructions()
        ),
        "schema": (
            v5_score_output_schema()
            if spec.contract is V5CallContract.V5_ABSOLUTE_SCORE
            else v5_pairwise_output_schema()
        ),
        "scenario_code": call.scenario_code,
        "criterion_refs": call.criterion_refs,
        "declared_input_refs": call.input_refs,
        "source_dependency_sha256": dependency_sha,
        "max_output_tokens": call.max_output_tokens,
    }
    return V5CallSpecIdentity(
        call_id=call.call_id,
        provider=call.provider.value,
        model=call.model,
        model_profile_id=call.model_profile_id,
        role=call.role.value,
        workload=call.workload.value,
        scenario_code=call.scenario_code,
        task_kind=call.task_kind,
        repetition=call.repetition,
        prompt_input_sha256=_canonical_sha256(projection),
        source_dependency_sha256=dependency_sha,
        criterion_refs=call.criterion_refs,
        declared_input_refs=call.input_refs,
        max_output_tokens=call.max_output_tokens,
        input_utf8_upper_bound_bytes=call.input_utf8_upper_bound_bytes,
        parser_or_scorer_contract_sha256=contract_sha,
        pricing_snapshot_id=PRICING_SNAPSHOT_ID,
        pricing_sha256=pricing_snapshot_sha256(),
    )


def v5_call_spec_sha256(spec: V5LogicalCallSpec) -> str:
    if spec.contract is V5CallContract.V42_UNCHANGED:
        historical = _V42_BY_ID[spec.call.call_id]
        return call_spec_identity(
            historical, CallIdentityVersion.V42_CORRECTIVE
        ).sha256()
    return v5_call_spec_identity(spec).sha256()


def v5_logical_matrix_sha256() -> str:
    payload = {
        "plan_version": V5_SEMANTIC_PLAN_VERSION,
        "baseline_commit_sha": V5_BASELINE_COMMIT_SHA,
        "v4_corpus_sha256": v4_calibration_corpus_sha256(),
        "v5_offline_manifest_sha256": V5_OFFLINE_MANIFEST_SHA256,
        "scorer_contract_sha256": EXPECTED_V5_SCORER_CONTRACT_SHA256,
        "pricing_snapshot_id": PRICING_SNAPSHOT_ID,
        "pricing_sha256": pricing_snapshot_sha256(),
        "calls": [
            {
                "call": {
                    **asdict(spec.call),
                    "provider": spec.call.provider.value,
                    "role": spec.call.role.value,
                    "workload": spec.call.workload.value,
                },
                "contract": spec.contract.value,
                "expected_pairwise_decision": (
                    spec.expected_pairwise_decision.value
                    if spec.expected_pairwise_decision is not None
                    else None
                ),
                "call_spec_sha256": v5_call_spec_sha256(spec),
            }
            for spec in V5_LOGICAL_CALL_MATRIX
        ],
    }
    digest = _canonical_sha256(payload)
    if digest != EXPECTED_V5_MATRIX_SHA256:
        _error(V5IntegrationErrorCode.MATRIX_MISMATCH)
    return digest


def build_v42_to_v5_diff() -> tuple[V42ToV5Diff, ...]:
    statuses = _v42_terminal_statuses()
    records: list[V42ToV5Diff] = []
    for old_call in V42_LOGICAL_CALL_MATRIX:
        new_spec = _V5_BY_ID[old_call.call_id]
        new_call = new_spec.call
        old_identity = call_spec_identity(
            old_call, CallIdentityVersion.V42_CORRECTIVE
        )
        new_identity = v5_call_spec_identity(new_spec)
        fields = {
            "provider_unchanged": old_call.provider is new_call.provider,
            "model_unchanged": old_call.model == new_call.model,
            "model_profile_unchanged": (
                old_call.model_profile_id == new_call.model_profile_id
            ),
            "role_unchanged": old_call.role is new_call.role,
            "workload_unchanged": old_call.workload is new_call.workload,
            "scenario_unchanged": old_call.scenario_code == new_call.scenario_code,
            "task_kind_unchanged": old_call.task_kind == new_call.task_kind,
            "repetition_unchanged": old_call.repetition == new_call.repetition,
            "prompt_input_unchanged": (
                old_identity.prompt_input_sha256 == new_identity.prompt_input_sha256
            ),
            "dependencies_unchanged": (
                old_identity.source_dependency_sha256
                == new_identity.source_dependency_sha256
            ),
            "criterion_refs_unchanged": (
                old_call.criterion_refs == new_call.criterion_refs
            ),
            "scorer_parser_contract_unchanged": (
                old_identity.parser_or_scorer_contract_sha256
                == new_identity.parser_or_scorer_contract_sha256
            ),
            "token_budget_unchanged": (
                old_call.max_output_tokens == new_call.max_output_tokens
                and old_call.input_utf8_upper_bound_bytes
                == new_call.input_utf8_upper_bound_bytes
            ),
            "declared_input_refs_unchanged": (
                old_call.input_refs == new_call.input_refs
            ),
            "pricing_identity_unchanged": (
                old_identity.pricing_sha256 == new_identity.pricing_sha256
            ),
        }
        unchanged = all(fields.values())
        status = statuses[old_call.call_id]
        records.append(
            V42ToV5Diff(
                call_id=old_call.call_id,
                **fields,
                call_spec_unchanged=unchanged,
                source_terminal_status=status,
                carry_forward_eligible=unchanged and status == "COMPLETED",
                reason=(
                    V5DiffReason.UNCHANGED
                    if unchanged
                    else V5DiffReason.SCORER_CONTRACT_AND_PROMPT_CHANGED
                ),
                v42_call_spec_sha256=old_identity.sha256(),
                v5_call_spec_sha256=v5_call_spec_sha256(new_spec),
            )
        )
    return tuple(records)


def estimate_pilot_budget(plan: V5PilotPlan) -> V5PilotBudget:
    base_input = base_output = max_input = max_output = 0
    base_cost = Decimal("0")
    maximum_cost = Decimal("0")
    for spec in plan.calls:
        call = spec.call
        estimated_input = _ceil_div(call.input_utf8_upper_bound_bytes, 4)
        estimated_output = _ceil_div(call.max_output_tokens, 2)
        base_input += estimated_input
        base_output += estimated_output
        max_input += call.input_utf8_upper_bound_bytes
        max_output += call.max_output_tokens
        base_cost += _token_cost(estimated_input, estimated_output, call.model)
        maximum_cost += _token_cost(
            call.input_utf8_upper_bound_bytes, call.max_output_tokens, call.model
        )
    maximum_before = _money(maximum_cost)
    proposed = _money(maximum_cost * COST_SAFETY_MARGIN)
    estimate = CostEstimate(
        call_count=len(plan.calls),
        estimated_input_tokens=base_input,
        estimated_output_tokens=base_output,
        estimated_base_usd=_money(base_cost),
        maximum_input_tokens=max_input,
        maximum_output_tokens=max_output,
        estimated_maximum_before_margin_usd=maximum_before,
        estimated_maximum_with_margin_usd=proposed,
    )
    return V5PilotBudget(
        name=plan.name,
        openai_call_count=sum(
            spec.call.provider is CalibrationProvider.OPENAI for spec in plan.calls
        ),
        anthropic_call_count=sum(
            spec.call.provider is CalibrationProvider.ANTHROPIC for spec in plan.calls
        ),
        estimate=estimate,
        safety_margin_usd=_money(proposed - maximum_before),
        proposed_pilot_ceiling_usd=proposed,
        approved_pilot_ceiling_usd=APPROVED_PILOT_CEILING_USD,
    )


def validate_offline_preflight(
    *,
    observed_baseline_commit_sha: str,
    observed_matrix_sha256: str,
    observed_pricing_sha256: str,
    observed_manifest_sha256: str,
    observed_contract_sha256: str,
) -> None:
    if observed_baseline_commit_sha != V5_BASELINE_COMMIT_SHA:
        _error(V5IntegrationErrorCode.BASELINE_MISMATCH)
    if observed_matrix_sha256 != v5_logical_matrix_sha256():
        _error(V5IntegrationErrorCode.MATRIX_MISMATCH)
    if observed_pricing_sha256 != pricing_snapshot_sha256():
        _error(V5IntegrationErrorCode.PRICING_MISMATCH)
    if observed_manifest_sha256 != V5_OFFLINE_MANIFEST_SHA256:
        _error(V5IntegrationErrorCode.MANIFEST_MISMATCH)
    if observed_contract_sha256 != EXPECTED_V5_SCORER_CONTRACT_SHA256:
        _error(V5IntegrationErrorCode.CONTRACT_MISMATCH)
    if _sha256((ROOT / V5_OFFLINE_MANIFEST_PATH).read_bytes()) != (
        V5_OFFLINE_MANIFEST_SHA256
    ):
        _error(V5IntegrationErrorCode.MANIFEST_MISMATCH)
    if v5_contract_sha256() != EXPECTED_V5_SCORER_CONTRACT_SHA256:
        _error(V5IntegrationErrorCode.CONTRACT_MISMATCH)


class V5PilotBudgetGuard:
    """Fail closed before any credential or transport boundary."""

    def authorize_next(
        self,
        *,
        plan: V5PilotPlan,
        call_id: str,
        completed_call_ids: tuple[str, ...],
        canary_passed: bool,
        approved_ceiling_usd: Decimal | None,
        observed_baseline_commit_sha: str,
        observed_matrix_sha256: str,
        observed_pricing_sha256: str,
        observed_manifest_sha256: str,
        observed_contract_sha256: str,
    ) -> V5LogicalCallSpec:
        validate_offline_preflight(
            observed_baseline_commit_sha=observed_baseline_commit_sha,
            observed_matrix_sha256=observed_matrix_sha256,
            observed_pricing_sha256=observed_pricing_sha256,
            observed_manifest_sha256=observed_manifest_sha256,
            observed_contract_sha256=observed_contract_sha256,
        )
        planned = {item.call.call_id: item for item in plan.calls}
        if call_id not in planned:
            _error(V5IntegrationErrorCode.CALL_NOT_PLANNED)
        if call_id in completed_call_ids or len(completed_call_ids) != len(
            set(completed_call_ids)
        ):
            _error(V5IntegrationErrorCode.CALL_ALREADY_COMPLETED)
        if call_id in plan.fanout_call_ids and not canary_passed:
            _error(V5IntegrationErrorCode.CANARY_FANOUT_FORBIDDEN)
        if approved_ceiling_usd is None:
            _error(V5IntegrationErrorCode.APPROVED_CEILING_MISSING)
        if approved_ceiling_usd < estimate_pilot_budget(
            plan
        ).proposed_pilot_ceiling_usd:
            _error(V5IntegrationErrorCode.APPROVED_CEILING_TOO_LOW)
        if not LIVE_PROVIDER_RECALIBRATION_AUTHORIZED:
            _error(V5IntegrationErrorCode.LIVE_EXECUTION_FORBIDDEN)
        return planned[call_id]


def evaluate_canary_gate(
    outcomes: Mapping[str, V5ScorerOutcome | V5PairwiseOutcome],
) -> bool:
    if set(MINIMAL_PILOT_CALL_IDS).difference(outcomes):
        return False
    scores: list[int] = []
    for call_id in MINIMAL_PILOT_CALL_IDS[:3]:
        outcome = outcomes[call_id]
        if (
            type(outcome) is not V5ScorerOutcome
            or outcome.status is not V5ScoreStatus.SCORED
            or outcome.score_level is None
        ):
            return False
        scores.append(int(outcome.score_level))
    pairwise = outcomes[MINIMAL_PILOT_CALL_IDS[3]]
    return (
        scores[0] > scores[1] > scores[2]
        and any(level in {1, 2, 3} for level in scores)
        and type(pairwise) is V5PairwiseOutcome
        and pairwise.decision is V5PairwiseDecision.A_BETTER
    )


def build_v5_observation(
    spec: V5LogicalCallSpec,
    output_projections: Mapping[str, str] | None = None,
) -> V5ScorerObservation | V5PairwiseObservation:
    call = spec.call
    if spec.contract is V5CallContract.V42_UNCHANGED:
        raise ValueError("unchanged OpenAI calls do not use the V5 scorer observation")
    criterion_ref = call.criterion_refs[0]
    if spec.contract is V5CallContract.V5_ABSOLUTE_SCORE:
        input_ref = call.input_refs[0]
        if input_ref.startswith("anchor:"):
            anchor_id = input_ref.removeprefix("anchor:")
            return build_v5_anchor_observation(
                CalibrationCriterionItem(anchor_id, call.scenario_code, criterion_ref)
            )
        projection = _required_output_projection(input_ref, output_projections)
        return V5ScorerObservation(
            observation_id=call.call_id,
            scenario=scenario_by_code(call.scenario_code),
            rubric=V5_RUBRIC_BY_CRITERION[criterion_ref],
            candidate_projection=projection,
        )
    ref_a, ref_b = call.input_refs
    return V5PairwiseObservation(
        comparison_id=f"comparison.v5.{_sha256(call.call_id.encode('utf-8'))[:16]}",
        scenario=scenario_by_code(call.scenario_code),
        rubric=V5_RUBRIC_BY_CRITERION[criterion_ref],
        candidate_a_id=_opaque_candidate_id(ref_a, "a"),
        candidate_a_projection=_projection_for_ref(ref_a, output_projections),
        candidate_b_id=_opaque_candidate_id(ref_b, "b"),
        candidate_b_projection=_projection_for_ref(ref_b, output_projections),
    )


def parse_v5_call_result(
    spec: V5LogicalCallSpec,
    output_text: str,
) -> V5ScorerOutcome | V5PairwiseOutcome:
    if spec.contract is V5CallContract.V5_ABSOLUTE_SCORE:
        return parse_v5_score_output(output_text, spec.call.criterion_refs[0])
    if spec.contract is V5CallContract.V5_DIRECT_PAIRWISE:
        return parse_v5_pairwise_output(output_text)
    raise ValueError("unchanged OpenAI calls do not use a V5 scorer parser")


def build_semantic_pilot_report(
    plan: V5PilotPlan,
    outcomes: Mapping[str, V5ScorerOutcome | V5PairwiseOutcome],
) -> V5PilotReport:
    expected_ids = {item.call.call_id for item in plan.calls}
    completed_ids = expected_ids.intersection(outcomes)
    failures: list[str] = []
    score_histogram = {level: 0 for level in range(5)}
    pairwise_histogram = {item.value: 0 for item in V5PairwiseDecision}
    triplets: dict[tuple[str, str], dict[AnchorTier, int]] = {}
    pairwise_expected = pairwise_correct = 0
    parser_schema_pass = True
    for spec in plan.calls:
        outcome = outcomes.get(spec.call.call_id)
        if outcome is None:
            continue
        if spec.contract is V5CallContract.V5_ABSOLUTE_SCORE:
            if type(outcome) is not V5ScorerOutcome:
                parser_schema_pass = False
                continue
            if outcome.status is V5ScoreStatus.INCONCLUSIVE or outcome.score_level is None:
                failures.append(f"INCONCLUSIVE:{spec.call.call_id}")
                continue
            level = int(outcome.score_level)
            score_histogram[level] += 1
            input_ref = spec.call.input_refs[0]
            if input_ref.startswith("anchor:") and spec.call.repetition == 1:
                anchor_id = input_ref.removeprefix("anchor:")
                tier = _TIER_BY_ANCHOR_ID[anchor_id]
                key = (spec.call.scenario_code, spec.call.criterion_refs[0])
                triplets.setdefault(key, {})[tier] = level
            continue
        if type(outcome) is not V5PairwiseOutcome:
            parser_schema_pass = False
            continue
        pairwise_histogram[outcome.decision.value] += 1
        pairwise_expected += 1
        if outcome.decision is spec.expected_pairwise_decision:
            pairwise_correct += 1
        else:
            failures.append(f"PAIRWISE_MISMATCH:{spec.call.call_id}")
    complete_triplets = tuple(
        tiers
        for tiers in triplets.values()
        if set(tiers) == {
            AnchorTier.STRONG,
            AnchorTier.MIXED,
            AnchorTier.WEAK_BUT_STRUCTURALLY_VALID,
        }
    )
    strict = sum(
        tiers[AnchorTier.STRONG]
        > tiers[AnchorTier.MIXED]
        > tiers[AnchorTier.WEAK_BUT_STRUCTURALLY_VALID]
        for tiers in complete_triplets
    )
    inversions = sum(
        tiers[AnchorTier.MIXED]
        < tiers[AnchorTier.WEAK_BUT_STRUCTURALLY_VALID]
        for tiers in complete_triplets
    )
    extreme = score_histogram[0] + score_histogram[4]
    intermediate = sum(score_histogram[level] for level in (1, 2, 3))
    if complete_triplets and strict != len(complete_triplets):
        failures.append("MONOTONICITY")
    if inversions:
        failures.append("INVERSION")
    if completed_ids and intermediate == 0:
        failures.append("QUASI_BINARY_DISTRIBUTION")
    if pairwise_expected and pairwise_correct != pairwise_expected:
        failures.append("PAIRWISE_DEGENERATE")
    canary_passed = evaluate_canary_gate(outcomes)
    if completed_ids == expected_ids and not canary_passed:
        failures.append("CANARY")
    audit = build_v42_to_v5_diff()
    carry_count = sum(item.carry_forward_eligible for item in audit)
    provenance_intact = carry_count == 20 and len(audit) == 102
    if not provenance_intact:
        failures.append("PROVENANCE")
    if not parser_schema_pass:
        failures.append("PARSER_SCHEMA")
    if completed_ids != expected_ids or any(
        isinstance(outcomes.get(call_id), V5ScorerOutcome)
        and cast(V5ScorerOutcome, outcomes[call_id]).status
        is V5ScoreStatus.INCONCLUSIVE
        for call_id in completed_ids
    ):
        verdict = V5PilotVerdict.INCONCLUSIVE
    elif failures:
        verdict = V5PilotVerdict.FAIL
    else:
        verdict = V5PilotVerdict.PASS
    return V5PilotReport(
        verdict=verdict,
        matrix_sha256=v5_logical_matrix_sha256(),
        scorer_contract_sha256=EXPECTED_V5_SCORER_CONTRACT_SHA256,
        pricing_sha256=pricing_snapshot_sha256(),
        scale_version=V5_SCORE_SCALE_VERSION,
        carry_forward_count=carry_count,
        planned_new_call_count=len(plan.calls),
        completed_new_call_count=len(completed_ids),
        score_histogram=tuple(score_histogram.items()),
        extreme_score_count=extreme,
        extreme_score_rate=(
            f"{extreme}/{extreme + intermediate}"
            if extreme + intermediate
            else None
        ),
        intermediate_score_count=intermediate,
        intermediate_score_rate=(
            f"{intermediate}/{extreme + intermediate}"
            if extreme + intermediate
            else None
        ),
        strict_monotonicity_count=strict,
        covered_triplet_count=len(complete_triplets),
        inversion_count=inversions,
        pairwise_expected_count=pairwise_expected,
        pairwise_correct_count=pairwise_correct,
        pairwise_decisions=tuple(pairwise_histogram.items()),
        parser_schema_pass=parser_schema_pass,
        canary_passed=canary_passed,
        provenance_intact=provenance_intact,
        gate_failures=tuple(dict.fromkeys(failures)),
    )


def validate_offline_integration() -> None:
    if len(V5_LOGICAL_CALL_MATRIX) != 113 or len(_V5_BY_ID) != 113:
        _error(V5IntegrationErrorCode.MATRIX_MISMATCH)
    audit = build_v42_to_v5_diff()
    if len(audit) != 102 or sum(item.call_spec_unchanged for item in audit) != 20:
        _error(V5IntegrationErrorCode.MATRIX_MISMATCH)
    if sum(item.carry_forward_eligible for item in audit) != 20:
        _error(V5IntegrationErrorCode.SOURCE_REPORT_INVALID)
    minimal = estimate_pilot_budget(build_minimal_pilot())
    robust = estimate_pilot_budget(build_robust_pilot())
    if (
        minimal.proposed_pilot_ceiling_usd != Decimal("0.192400")
        or robust.proposed_pilot_ceiling_usd != Decimal("1.017600")
        or len(build_minimal_pilot().calls) != 4
        or len(build_robust_pilot().calls) != 21
    ):
        _error(V5IntegrationErrorCode.MATRIX_MISMATCH)
    validate_offline_preflight(
        observed_baseline_commit_sha=V5_BASELINE_COMMIT_SHA,
        observed_matrix_sha256=v5_logical_matrix_sha256(),
        observed_pricing_sha256=pricing_snapshot_sha256(),
        observed_manifest_sha256=V5_OFFLINE_MANIFEST_SHA256,
        observed_contract_sha256=EXPECTED_V5_SCORER_CONTRACT_SHA256,
    )


def _v5_dependency_sha256(spec: V5LogicalCallSpec) -> str:
    historical = _V42_BY_ID.get(spec.call.call_id)
    if historical is not None:
        return call_spec_identity(
            historical, CallIdentityVersion.V42_CORRECTIVE
        ).source_dependency_sha256
    dependencies: list[dict[str, str]] = []
    for input_ref in spec.call.input_refs:
        if input_ref.startswith("anchor:"):
            anchor = _ANCHOR_BY_ID.get(input_ref.removeprefix("anchor:"))
            if anchor is None:
                _error(V5IntegrationErrorCode.MATRIX_MISMATCH)
            digest = _sha256(anchor.candidate_projection().encode("utf-8"))
        elif input_ref.startswith("output:"):
            source_id = input_ref.removeprefix("output:")
            source = _V5_BY_ID.get(source_id)
            if source is None:
                _error(V5IntegrationErrorCode.MATRIX_MISMATCH)
            digest = v5_call_spec_sha256(source)
        else:
            _error(V5IntegrationErrorCode.MATRIX_MISMATCH)
        dependencies.append({"input_ref": input_ref, "sha256": digest})
    return _canonical_sha256(dependencies)


def _v42_terminal_statuses() -> dict[str, str]:
    path = ROOT / V42_SAFE_REPORT_PATH
    if _sha256(path.read_bytes()) != V42_SAFE_REPORT_SHA256:
        _error(V5IntegrationErrorCode.SOURCE_REPORT_INVALID)
    try:
        report = json.loads(path.read_text(encoding="utf-8"))
        raw_results = report["execution"]["call_results"]
    except (OSError, json.JSONDecodeError, KeyError, TypeError):
        _error(V5IntegrationErrorCode.SOURCE_REPORT_INVALID)
    if type(raw_results) is not list:
        _error(V5IntegrationErrorCode.SOURCE_REPORT_INVALID)
    statuses: dict[str, str] = {}
    for raw in raw_results:
        if type(raw) is not dict:
            _error(V5IntegrationErrorCode.SOURCE_REPORT_INVALID)
        call_id = raw.get("call_id")
        status = raw.get("terminal_status")
        if type(call_id) is not str or type(status) is not str or call_id in statuses:
            _error(V5IntegrationErrorCode.SOURCE_REPORT_INVALID)
        statuses[call_id] = status
    if set(statuses) != set(_V42_BY_ID):
        _error(V5IntegrationErrorCode.SOURCE_REPORT_INVALID)
    return statuses


def _projection_for_ref(
    input_ref: str, output_projections: Mapping[str, str] | None
) -> str:
    if input_ref.startswith("anchor:"):
        return _ANCHOR_BY_ID[
            input_ref.removeprefix("anchor:")
        ].candidate_projection()
    return _required_output_projection(input_ref, output_projections)


def _required_output_projection(
    input_ref: str, output_projections: Mapping[str, str] | None
) -> str:
    if not input_ref.startswith("output:") or output_projections is None:
        raise ValueError("an authorized minimized output projection is required")
    source_id = input_ref.removeprefix("output:")
    try:
        return output_projections[source_id]
    except KeyError:
        raise ValueError("the required output projection is missing") from None


def _opaque_candidate_id(input_ref: str, side: str) -> str:
    digest = _sha256(input_ref.encode("utf-8"))[:16]
    return f"candidate.v5.{side}.{digest}"


def _canonical_sha256(value: object) -> str:
    return _sha256(
        json.dumps(
            value, ensure_ascii=False, separators=(",", ":"), sort_keys=True
        ).encode("utf-8")
    )


def _sha256(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _ceil_div(value: int, divisor: int) -> int:
    return (value + divisor - 1) // divisor


def _token_cost(input_tokens: int, output_tokens: int, model: str) -> Decimal:
    quote = MODEL_PRICE_BY_NAME[model]
    million = Decimal(1_000_000)
    return (
        Decimal(input_tokens) * quote.input_usd_per_million_tokens
        + Decimal(output_tokens) * quote.output_usd_per_million_tokens
    ) / million


def _money(value: Decimal) -> Decimal:
    return value.quantize(Decimal("0.000001"), rounding=ROUND_CEILING)


def _error(code: V5IntegrationErrorCode) -> NoReturn:
    raise V5IntegrationError(code) from None
