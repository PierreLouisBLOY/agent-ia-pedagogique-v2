"""Offline-only V4.2 carry-forward audit and corrective tranche plan."""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass, replace
from decimal import ROUND_CEILING, Decimal
from enum import StrEnum
from pathlib import Path
from typing import NoReturn, cast

from tests.calibration.pedagogical.anchor_corpus_v4 import (
    V4_CALIBRATION_ANCHORS,
    v4_calibration_corpus_sha256,
)
from tests.calibration.pedagogical.call_plan import (
    CalibrationCallSpec,
    CalibrationProvider,
    CalibrationWorkload,
    CostEstimate,
)
from tests.calibration.pedagogical.call_plan_v4_1 import (
    PEDAGOGICAL_CALIBRATION_CALL_MATRIX as V41_CALL_MATRIX,
)
from tests.calibration.pedagogical.catalog import anchor_by_id, scenario_by_code
from tests.calibration.pedagogical.pricing import (
    EXPECTED_PRICING_SNAPSHOT_SHA256,
    MODEL_PRICE_BY_NAME,
    PRICING_SNAPSHOT_ID,
    pricing_snapshot_sha256,
)
from tests.calibration.pedagogical.review_contract_v4_2 import (
    COMPACT_REVIEW_MAX_OUTPUT_TOKENS,
    COMPACT_REVIEW_REASONING_EFFORT,
    build_compact_review_request,
    compact_review_contract_sha256,
    compact_review_input_bound_bytes,
    v4_2_strong_projection,
)

ROOT = Path(__file__).resolve().parents[3]
V41_BASELINE_COMMIT_SHA = "71e4258baacc1f0914cf9a9087638736c2a4ebdd"
V41_MATRIX_SHA256 = "94eb067ac7dd8498eeb2605ee506315fd0c831259f454555ecac88acbe94403a"
V41_RUN_ID = "12.16-g2-v4-1-live"
V41_SAFE_REPORT_PATH = Path(
    "artifacts/calibration/12.16-g2-v4-1/safe_report.json"
)
V41_LEDGER_PATH = Path("artifacts/calibration/12.16-g2-v4-1/ledger.json")
V41_SAFE_REPORT_SHA256 = (
    "fe25523b4c72d927c4ba71df4d789c3fafeaed8414cd82a342761cc3581eea85"
)
V41_LEDGER_SHA256 = (
    "697eb124e5a4883896e2eb17ef7fa4764b7396fdc434dbaf0022a3425a79788f"
)
V42_PLAN_VERSION = "12.16-g2-v4.2-repair-plan-v1"
V42_LEDGER_PATH = Path("artifacts/calibration/12.16-g2-v4-2/ledger.json")
COST_SAFETY_MARGIN = Decimal("1.25")
EXPECTED_CARRY_FORWARD_COUNT = 63
EXPECTED_REPAIR_TRANCHE_MAX_CALL_COUNT = 39
EXPECTED_V42_MATRIX_SHA256 = (
    "605358444f1bc9052ca7b4e55057c9d5424b3ad3b4deecc17bdde83e23c18aa5"
)
PROPOSED_REPAIR_TRANCHE_CEILING_USD = Decimal("2.111240")
APPROVED_REPAIR_TRANCHE_CEILING_USD: Decimal | None = None
LIVE_PROVIDER_RECALIBRATION_AUTHORIZED = False

_V4_ANCHOR_BY_ID = {anchor.anchor_id: anchor for anchor in V4_CALIBRATION_ANCHORS}
_V41_CALL_BY_ID = {call.call_id: call for call in V41_CALL_MATRIX}
_GENERATION_CONTRACT_PATHS = (
    "backend/adapters/outbound/generation/openai/mapping.py",
    "backend/adapters/outbound/generation/openai/adapter.py",
    "backend/adapters/outbound/openai/transport.py",
)
_V41_REVIEW_CONTRACT_PATHS = (
    "backend/adapters/outbound/review/openai/mapping.py",
    "backend/adapters/outbound/review/openai/adapter.py",
    "backend/adapters/outbound/openai/transport.py",
)
_ANTHROPIC_CONTRACT_PATHS = (
    "tests/providers/anthropic/mapping.py",
    "tests/providers/anthropic/scorer.py",
    "tests/providers/anthropic/transport.py",
)


class CallIdentityVersion(StrEnum):
    V41_EXECUTED = "V41_EXECUTED"
    V42_CORRECTIVE = "V42_CORRECTIVE"


class CarryForwardReason(StrEnum):
    EQUIVALENT = "EQUIVALENT"
    SOURCE_NOT_COMPLETED = "SOURCE_NOT_COMPLETED"
    SOURCE_PROJECTION_CHANGED = "SOURCE_PROJECTION_CHANGED"
    REVIEW_CONTRACT_CHANGED = "REVIEW_CONTRACT_CHANGED"
    UPSTREAM_CALL_SPEC_CHANGED = "UPSTREAM_CALL_SPEC_CHANGED"
    OTHER_CALL_SPEC_CHANGED = "OTHER_CALL_SPEC_CHANGED"


class RepairPlanErrorCode(StrEnum):
    SOURCE_REPORT_INVALID = "SOURCE_REPORT_INVALID"
    MATRIX_MISMATCH = "MATRIX_MISMATCH"
    CALL_NOT_PLANNED = "CALL_NOT_PLANNED"
    CALL_COUNT_EXCEEDED = "CALL_COUNT_EXCEEDED"
    APPROVED_CEILING_MISSING = "APPROVED_CEILING_MISSING"
    APPROVED_CEILING_TOO_LOW = "APPROVED_CEILING_TOO_LOW"
    LIVE_AUTHORIZATION_REQUIRED = "LIVE_AUTHORIZATION_REQUIRED"
    CANARY_ORDER_INVALID = "CANARY_ORDER_INVALID"
    CARRY_FORWARD_UNSAFE = "CARRY_FORWARD_UNSAFE"


class RepairPlanError(RuntimeError):
    code: RepairPlanErrorCode

    def __init__(self, code: RepairPlanErrorCode) -> None:
        self.code = code
        super().__init__(code.value)


@dataclass(frozen=True, slots=True)
class CallSpecIdentity:
    call_id: str
    provider: str
    model: str
    workload_family: str
    prompt_input_sha256: str
    source_dependency_sha256: str
    criterion_refs: tuple[str, ...]
    declared_input_refs: tuple[str, ...]
    execution_parameters: tuple[tuple[str, object], ...]
    parser_or_scorer_contract_sha256: str
    pricing_sha256: str

    def sha256(self) -> str:
        return _sha256(_canonical_json(asdict(self)).encode("utf-8"))


@dataclass(frozen=True, slots=True)
class CarryForwardDecision:
    call_id: str
    source_terminal_status: str
    v41_call_spec_sha256: str
    v42_call_spec_sha256: str
    eligible: bool
    reason: CarryForwardReason


@dataclass(frozen=True, slots=True)
class RepairRuntimeAuthorization:
    effective: bool = False
    authorized_baseline_commit_sha: str | None = None
    authorized_matrix_sha256: str | None = None
    authorized_pricing_sha256: str | None = None
    authorized_max_call_count: int | None = None
    authorized_hard_ceiling_usd: Decimal | None = None


def _v42_call(call: CalibrationCallSpec) -> CalibrationCallSpec:
    input_refs = tuple(
        ref.replace("12.16-g2-v4.1-plan-v1", V42_PLAN_VERSION)
        for ref in call.input_refs
    )
    if call.workload is not CalibrationWorkload.REVIEW:
        return replace(call, input_refs=input_refs)
    return replace(
        call,
        max_output_tokens=COMPACT_REVIEW_MAX_OUTPUT_TOKENS,
        input_utf8_upper_bound_bytes=compact_review_input_bound_bytes(call),
        input_refs=input_refs,
    )


V42_LOGICAL_CALL_MATRIX = tuple(_v42_call(call) for call in V41_CALL_MATRIX)
_V42_CALL_BY_ID = {call.call_id: call for call in V42_LOGICAL_CALL_MATRIX}


def call_spec_identity(
    call: CalibrationCallSpec,
    version: CallIdentityVersion,
) -> CallSpecIdentity:
    source_dependency_sha256 = _source_dependency_sha256(call, version)
    contract_sha256 = _contract_sha256(call, version)
    declared_refs = (
        _V41_CALL_BY_ID[call.call_id].input_refs
        if version is CallIdentityVersion.V41_EXECUTED
        else _V42_CALL_BY_ID[call.call_id].input_refs
    )
    execution_parameters = _execution_parameters(call, version)
    prompt_projection = {
        "call_id": call.call_id,
        "scenario": _scenario_projection(call.scenario_code),
        "task_kind": call.task_kind,
        "workload": call.workload.value,
        "source_dependency_sha256": source_dependency_sha256,
        "declared_input_refs": declared_refs,
        "criterion_refs": call.criterion_refs,
        "contract_sha256": contract_sha256,
        "execution_parameters": execution_parameters,
    }
    if (
        version is CallIdentityVersion.V42_CORRECTIVE
        and call.workload is CalibrationWorkload.REVIEW
    ):
        request = build_compact_review_request(_V42_CALL_BY_ID[call.call_id])
        prompt_projection["provider_input_json_sha256"] = _sha256(
            request.input_json.encode("utf-8")
        )
        prompt_projection["provider_schema_sha256"] = _sha256(
            _canonical_json(request.output_schema).encode("utf-8")
        )
    return CallSpecIdentity(
        call_id=call.call_id,
        provider=call.provider.value,
        model=call.model,
        workload_family=_workload_family(call),
        prompt_input_sha256=_sha256(
            _canonical_json(prompt_projection).encode("utf-8")
        ),
        source_dependency_sha256=source_dependency_sha256,
        criterion_refs=call.criterion_refs,
        declared_input_refs=declared_refs,
        execution_parameters=execution_parameters,
        parser_or_scorer_contract_sha256=contract_sha256,
        pricing_sha256=pricing_snapshot_sha256(),
    )


def call_spec_sha256(call: CalibrationCallSpec, version: CallIdentityVersion) -> str:
    return call_spec_identity(call, version).sha256()


def logical_matrix_sha256() -> str:
    projection = {
        "plan_version": V42_PLAN_VERSION,
        "corpus_sha256": v4_calibration_corpus_sha256(),
        "pricing_snapshot_id": PRICING_SNAPSHOT_ID,
        "pricing_sha256": pricing_snapshot_sha256(),
        "review_contract_sha256": compact_review_contract_sha256(),
        "calls": [
            {
                **asdict(call),
                "provider": call.provider.value,
                "role": call.role.value,
                "workload": call.workload.value,
                "call_spec_sha256": call_spec_sha256(
                    call, CallIdentityVersion.V42_CORRECTIVE
                ),
            }
            for call in V42_LOGICAL_CALL_MATRIX
        ],
    }
    digest = _sha256(_canonical_json(projection).encode("utf-8"))
    if digest != EXPECTED_V42_MATRIX_SHA256:
        _error(RepairPlanErrorCode.MATRIX_MISMATCH)
    return digest


def build_carry_forward_audit(
    report_path: Path = V41_SAFE_REPORT_PATH,
) -> tuple[CarryForwardDecision, ...]:
    resolved_report = ROOT / report_path
    if (
        report_path == V41_SAFE_REPORT_PATH
        and _sha256(resolved_report.read_bytes()) != V41_SAFE_REPORT_SHA256
    ):
        _error(RepairPlanErrorCode.SOURCE_REPORT_INVALID)
    report = _read_json_object(resolved_report)
    if report.get("decision") != "CALIBRATION_INCONCLUSIVE":
        _error(RepairPlanErrorCode.SOURCE_REPORT_INVALID)
    execution = report.get("execution")
    if type(execution) is not dict:
        _error(RepairPlanErrorCode.SOURCE_REPORT_INVALID)
    raw_results = cast(dict[str, object], execution).get("call_results")
    if type(raw_results) is not list:
        _error(RepairPlanErrorCode.SOURCE_REPORT_INVALID)
    statuses: dict[str, str] = {}
    for raw in cast(list[object], raw_results):
        if type(raw) is not dict:
            _error(RepairPlanErrorCode.SOURCE_REPORT_INVALID)
        call_id = raw.get("call_id")
        status = raw.get("terminal_status")
        if type(call_id) is not str or type(status) is not str or call_id in statuses:
            _error(RepairPlanErrorCode.SOURCE_REPORT_INVALID)
        statuses[call_id] = status
    if set(statuses) != set(_V41_CALL_BY_ID):
        _error(RepairPlanErrorCode.SOURCE_REPORT_INVALID)
    decisions: list[CarryForwardDecision] = []
    for v41_call in V41_CALL_MATRIX:
        v42_call = _V42_CALL_BY_ID[v41_call.call_id]
        v41_sha = call_spec_sha256(v41_call, CallIdentityVersion.V41_EXECUTED)
        v42_sha = call_spec_sha256(v42_call, CallIdentityVersion.V42_CORRECTIVE)
        status = statuses[v41_call.call_id]
        eligible = status == "COMPLETED" and v41_sha == v42_sha
        decisions.append(
            CarryForwardDecision(
                call_id=v41_call.call_id,
                source_terminal_status=status,
                v41_call_spec_sha256=v41_sha,
                v42_call_spec_sha256=v42_sha,
                eligible=eligible,
                reason=_carry_forward_reason(v41_call, status, v41_sha == v42_sha),
            )
        )
    return tuple(decisions)


def repair_call_matrix(
    audit: tuple[CarryForwardDecision, ...],
) -> tuple[CalibrationCallSpec, ...]:
    ineligible = {item.call_id for item in audit if not item.eligible}
    calls = tuple(call for call in V42_LOGICAL_CALL_MATRIX if call.call_id in ineligible)
    _validate_canary_order(calls)
    return calls


def estimate_repair_tranche_cost(
    calls: tuple[CalibrationCallSpec, ...],
) -> CostEstimate:
    base_input = base_output = maximum_input = maximum_output = 0
    base_cost = Decimal("0")
    maximum_cost = Decimal("0")
    for call in calls:
        quote = MODEL_PRICE_BY_NAME[call.model]
        estimated_input = _ceil_div(call.input_utf8_upper_bound_bytes, 4)
        estimated_output = _ceil_div(call.max_output_tokens, 2)
        base_input += estimated_input
        base_output += estimated_output
        maximum_input += call.input_utf8_upper_bound_bytes
        maximum_output += call.max_output_tokens
        base_cost += _token_cost(estimated_input, estimated_output, call.model)
        maximum_cost += _token_cost(
            call.input_utf8_upper_bound_bytes,
            call.max_output_tokens,
            call.model,
        )
        if quote.model != call.model:
            _error(RepairPlanErrorCode.MATRIX_MISMATCH)
    return CostEstimate(
        call_count=len(calls),
        estimated_input_tokens=base_input,
        estimated_output_tokens=base_output,
        estimated_base_usd=_money(base_cost),
        maximum_input_tokens=maximum_input,
        maximum_output_tokens=maximum_output,
        estimated_maximum_before_margin_usd=_money(maximum_cost),
        estimated_maximum_with_margin_usd=_money(maximum_cost * COST_SAFETY_MARGIN),
    )


class RepairTrancheBudgetGuard:
    def authorize_next(
        self,
        *,
        call_id: str,
        matrix_sha256: str,
        calls: tuple[CalibrationCallSpec, ...],
        approved_ceiling_usd: Decimal | None,
        completed_call_ids: tuple[str, ...],
        actual_cost_usd: Decimal,
    ) -> CalibrationCallSpec:
        if matrix_sha256 != logical_matrix_sha256():
            _error(RepairPlanErrorCode.MATRIX_MISMATCH)
        if approved_ceiling_usd is None:
            _error(RepairPlanErrorCode.APPROVED_CEILING_MISSING)
        proposed = estimate_repair_tranche_cost(calls).estimated_maximum_with_margin_usd
        if approved_ceiling_usd < proposed:
            _error(RepairPlanErrorCode.APPROVED_CEILING_TOO_LOW)
        if actual_cost_usd > approved_ceiling_usd:
            _error(RepairPlanErrorCode.APPROVED_CEILING_TOO_LOW)
        if len(completed_call_ids) != len(set(completed_call_ids)):
            _error(RepairPlanErrorCode.CALL_COUNT_EXCEEDED)
        planned = {call.call_id: call for call in calls}
        if call_id not in planned:
            _error(RepairPlanErrorCode.CALL_NOT_PLANNED)
        if call_id in completed_call_ids:
            _error(RepairPlanErrorCode.CALL_COUNT_EXCEEDED)
        return planned[call_id]


def validate_live_authorization(authorization: RepairRuntimeAuthorization) -> None:
    if (
        LIVE_PROVIDER_RECALIBRATION_AUTHORIZED is not True
        or APPROVED_REPAIR_TRANCHE_CEILING_USD is None
        or not authorization.effective
    ):
        _error(RepairPlanErrorCode.LIVE_AUTHORIZATION_REQUIRED)


def build_offline_provenance_aggregate(
    audit: tuple[CarryForwardDecision, ...],
    newly_executed: dict[str, str] | None = None,
) -> dict[str, object]:
    new_statuses = newly_executed or {}
    records: list[dict[str, object]] = []
    for decision in audit:
        if decision.eligible:
            records.append(
                {
                    "call_id": decision.call_id,
                    "source_run_id": V41_RUN_ID,
                    "source_baseline_commit": V41_BASELINE_COMMIT_SHA,
                    "call_spec_sha256": decision.v41_call_spec_sha256,
                    "disposition": "CARRY_FORWARD",
                    "terminal_status": decision.source_terminal_status,
                    "ledger_source": V41_LEDGER_PATH.as_posix(),
                }
            )
            continue
        executed_status = new_statuses.get(decision.call_id)
        records.append(
            {
                "call_id": decision.call_id,
                "source_run_id": (
                    "12.16-g2-v4-2-live" if executed_status is not None else None
                ),
                "source_baseline_commit": None,
                "call_spec_sha256": decision.v42_call_spec_sha256,
                "disposition": (
                    "NEWLY_EXECUTED"
                    if executed_status is not None
                    else "PENDING_NEW_EXECUTION"
                ),
                "terminal_status": executed_status or "PENDING",
                "ledger_source": V42_LEDGER_PATH.as_posix(),
            }
        )
    return {
        "logical_matrix_sha256": logical_matrix_sha256(),
        "logical_matrix_call_count": len(V42_LOGICAL_CALL_MATRIX),
        "carry_forward_count": sum(item.eligible for item in audit),
        "repair_tranche_max_call_count": sum(not item.eligible for item in audit),
        "records": records,
        "cross_run_provenance_preserved": True,
    }


def validate_offline_readiness(audit: tuple[CarryForwardDecision, ...]) -> None:
    if _sha256((ROOT / V41_LEDGER_PATH).read_bytes()) != V41_LEDGER_SHA256:
        _error(RepairPlanErrorCode.SOURCE_REPORT_INVALID)
    if len(V42_LOGICAL_CALL_MATRIX) != 102 or pricing_snapshot_sha256() != (
        EXPECTED_PRICING_SNAPSHOT_SHA256
    ):
        _error(RepairPlanErrorCode.MATRIX_MISMATCH)
    carry_count = sum(item.eligible for item in audit)
    calls = repair_call_matrix(audit)
    if carry_count != EXPECTED_CARRY_FORWARD_COUNT:
        _error(RepairPlanErrorCode.CARRY_FORWARD_UNSAFE)
    if len(calls) != EXPECTED_REPAIR_TRANCHE_MAX_CALL_COUNT:
        _error(RepairPlanErrorCode.CARRY_FORWARD_UNSAFE)
    if (
        estimate_repair_tranche_cost(calls).estimated_maximum_with_margin_usd
        != PROPOSED_REPAIR_TRANCHE_CEILING_USD
    ):
        _error(RepairPlanErrorCode.MATRIX_MISMATCH)
    if any(call.call_id in {item.call_id for item in audit if item.eligible} for call in calls):
        _error(RepairPlanErrorCode.CARRY_FORWARD_UNSAFE)


def _carry_forward_reason(
    call: CalibrationCallSpec,
    source_status: str,
    equivalent: bool,
) -> CarryForwardReason:
    if source_status != "COMPLETED":
        return CarryForwardReason.SOURCE_NOT_COMPLETED
    if equivalent:
        return CarryForwardReason.EQUIVALENT
    if call.workload is CalibrationWorkload.REVIEW:
        return CarryForwardReason.REVIEW_CONTRACT_CHANGED
    if call.provider is CalibrationProvider.OPENAI:
        return CarryForwardReason.SOURCE_PROJECTION_CHANGED
    if call.input_refs[0].startswith("output:"):
        return CarryForwardReason.UPSTREAM_CALL_SPEC_CHANGED
    return CarryForwardReason.OTHER_CALL_SPEC_CHANGED


def _source_dependency_sha256(
    call: CalibrationCallSpec,
    version: CallIdentityVersion,
) -> str:
    input_ref = call.input_refs[0]
    if call.provider is CalibrationProvider.OPENAI:
        projection = (
            anchor_by_id(f"cal.{call.scenario_code.lower()}.a").candidate_projection()
            if version is CallIdentityVersion.V41_EXECUTED
            else v4_2_strong_projection(call.scenario_code)
        )
        return _sha256(projection.encode("utf-8"))
    if input_ref.startswith("anchor:"):
        anchor_id = input_ref.removeprefix("anchor:")
        anchor = _V4_ANCHOR_BY_ID.get(anchor_id)
        if anchor is None:
            _error(RepairPlanErrorCode.MATRIX_MISMATCH)
        return _sha256(anchor.candidate_projection().encode("utf-8"))
    if not input_ref.startswith("output:"):
        _error(RepairPlanErrorCode.MATRIX_MISMATCH)
    dependency_id = input_ref.removeprefix("output:")
    dependency_call = (
        _V41_CALL_BY_ID.get(dependency_id)
        if version is CallIdentityVersion.V41_EXECUTED
        else _V42_CALL_BY_ID.get(dependency_id)
    )
    if dependency_call is None:
        _error(RepairPlanErrorCode.MATRIX_MISMATCH)
    return call_spec_sha256(dependency_call, version)


def _contract_sha256(
    call: CalibrationCallSpec,
    version: CallIdentityVersion,
) -> str:
    if call.workload is CalibrationWorkload.REVIEW:
        return (
            _bundle_sha256(_V41_REVIEW_CONTRACT_PATHS)
            if version is CallIdentityVersion.V41_EXECUTED
            else compact_review_contract_sha256()
        )
    if call.provider is CalibrationProvider.OPENAI:
        return _bundle_sha256(_GENERATION_CONTRACT_PATHS)
    return _bundle_sha256(_ANTHROPIC_CONTRACT_PATHS)


def _execution_parameters(
    call: CalibrationCallSpec,
    version: CallIdentityVersion,
) -> tuple[tuple[str, object], ...]:
    effective = (
        _V41_CALL_BY_ID[call.call_id]
        if version is CallIdentityVersion.V41_EXECUTED
        else _V42_CALL_BY_ID[call.call_id]
    )
    parameters: dict[str, object] = {
        "automatic_retries": 0,
        "max_output_tokens": effective.max_output_tokens,
        "structured_output_required": True,
    }
    if effective.workload is CalibrationWorkload.REVIEW:
        parameters["reasoning_effort"] = (
            None
            if version is CallIdentityVersion.V41_EXECUTED
            else COMPACT_REVIEW_REASONING_EFFORT.value
        )
    if effective.provider is CalibrationProvider.ANTHROPIC:
        parameters.update({"thinking_mode": "adaptive", "effort": "low"})
    return tuple(sorted(parameters.items()))


def _scenario_projection(scenario_code: str) -> dict[str, object]:
    scenario = scenario_by_code(scenario_code)
    return {
        "scenario_code": scenario.scenario_code,
        "level_code": scenario.level_code,
        "task_kind": scenario.task_kind,
        "criterion_refs": scenario.criterion_refs,
        "reference_constraints": scenario.reference_constraints,
        "required_sections": scenario.required_sections,
    }


def _workload_family(call: CalibrationCallSpec) -> str:
    if call.provider is CalibrationProvider.ANTHROPIC:
        return "ANTHROPIC_SCORER"
    if call.workload is CalibrationWorkload.REVIEW:
        return "OPENAI_REVIEW"
    return "OPENAI_GENERATION_CORRECTION"


def _validate_canary_order(calls: tuple[CalibrationCallSpec, ...]) -> None:
    families = {
        "OPENAI_GENERATION_CORRECTION": "cal.generation.course.primary.r1",
        "OPENAI_REVIEW": "cal.review.exercise.primary.r1",
        "ANTHROPIC_SCORER": "cal.score.anchor.scn-08.strong.feedback-quality.r2",
    }
    for family, canary_id in families.items():
        family_calls = tuple(call for call in calls if _workload_family(call) == family)
        if not family_calls or family_calls[0].call_id != canary_id:
            _error(RepairPlanErrorCode.CANARY_ORDER_INVALID)


def _bundle_sha256(paths: tuple[str, ...]) -> str:
    digest = hashlib.sha256()
    for path in paths:
        raw = (ROOT / path).read_bytes()
        digest.update(path.encode("utf-8"))
        digest.update(b"\0")
        digest.update(hashlib.sha256(raw).digest())
    return digest.hexdigest()


def _read_json_object(path: Path) -> dict[str, object]:
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        _error(RepairPlanErrorCode.SOURCE_REPORT_INVALID)
    if type(raw) is not dict:
        _error(RepairPlanErrorCode.SOURCE_REPORT_INVALID)
    return cast(dict[str, object], raw)


def _canonical_json(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"), sort_keys=True)


def _sha256(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _ceil_div(value: int, divisor: int) -> int:
    return (value + divisor - 1) // divisor


def _token_cost(input_tokens: int, output_tokens: int, model: str) -> Decimal:
    quote = MODEL_PRICE_BY_NAME[model]
    return cast(
        Decimal,
        (
            Decimal(input_tokens) * quote.input_usd_per_million_tokens
            + Decimal(output_tokens) * quote.output_usd_per_million_tokens
        )
        / Decimal(1_000_000),
    )


def _money(value: Decimal) -> Decimal:
    return value.quantize(Decimal("0.000001"), rounding=ROUND_CEILING)


def _error(code: RepairPlanErrorCode) -> NoReturn:
    raise RepairPlanError(code) from None
