"""Offline R4-R1 policy rationalization and uniform Anthropic plan owner."""

from __future__ import annotations

import hashlib
import json
import os
from collections import Counter
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from decimal import ROUND_CEILING, Decimal
from enum import StrEnum
from pathlib import Path
from typing import Never, cast

from tests.calibration.pedagogical.legacy_call_plan import (
    PEDAGOGICAL_CALIBRATION_CALL_MATRIX,
    CalibrationCallSpec,
    CalibrationProvider,
    CalibrationWorkload,
)
from tests.calibration.pedagogical.r3b_r3_plan import (
    audit_r3_consolidated_evidence,
)
from tests.providers.anthropic import AnthropicEffort, AnthropicThinkingMode

R4_LEDGER_RELATIVE_PATH = "artifacts/calibration/12.16-g2-r3b-r4/ledger.json"
R4_SUMMARY_RELATIVE_PATH = "artifacts/calibration/12.16-g2-r3b-r4/summary.json"
R4_LEDGER_SHA256 = "2163050a6dc580acadddcedbb72ec13ee5b984f0769b51593a965d2bace99c82"
R4_SUMMARY_SHA256 = "50e7c8171e97f9ba732a78ca30c6fb195e095a59ad7becaff0496cf214ac9859"
R4_FAILED_CALL_ID = "r4.cal.score.anchor.scn-01.c.organization-utility.r1"
CANARY_LOGICAL_SLOT_ID = "cal.score.anchor.scn-01.c.organization-utility.r1"
CANARY_EXECUTION_CALL_ID = "remediation.r4.scorer-policy.scn-01.c.organization-utility.canary.r1"

R2_PLAN_VERSION = "12.16-g2-r4-r2-anthropic-policy-canary-v1"
R3_PLAN_VERSION = "12.16-g2-r4-r3-anthropic-uniform-completion-v1"
R2_ARTIFACT_DIRECTORY = "artifacts/calibration/12.16-g2-r4-r2"
R3_ARTIFACT_DIRECTORY = "artifacts/calibration/12.16-g2-r4-r3"
R2_LEDGER_RELATIVE_PATH = f"{R2_ARTIFACT_DIRECTORY}/ledger.json"
R3_LEDGER_RELATIVE_PATH = f"{R3_ARTIFACT_DIRECTORY}/ledger.json"

R1_BASELINE_RELATIVE_PATH = (
    "docs/development/PHASE_12_16_G2_R3B_R4_R1_SCORER_POLICY_RATIONALIZATION.md"
)
R2_COST_MARKDOWN_RELATIVE_PATH = "docs/development/PHASE_12_16_G2_R3B_R4_R1_CANARY_COST_PLAN.md"
R2_COST_JSON_RELATIVE_PATH = "docs/development/PHASE_12_16_G2_R3B_R4_R1_CANARY_COST_PLAN.json"
R3_COST_MARKDOWN_RELATIVE_PATH = "docs/development/PHASE_12_16_G2_R3B_R4_R1_COMPLETION_COST_PLAN.md"
R3_COST_JSON_RELATIVE_PATH = "docs/development/PHASE_12_16_G2_R3B_R4_R1_COMPLETION_COST_PLAN.json"

MODEL = "claude-sonnet-5"
MODEL_PROFILE_ID = "anthropic.claude-sonnet-5.scorer"
THINKING_MODE = AnthropicThinkingMode.ADAPTIVE
EFFORT = AnthropicEffort.LOW
MAX_OUTPUT_TOKENS = 2_048
INPUT_USD_PER_MTOK = Decimal("2.00")
CACHE_HIT_USD_PER_MTOK = Decimal("0.20")
OUTPUT_USD_PER_MTOK = Decimal("10.00")
COST_MARGIN = Decimal("1.25")
R2_EXPECTED_BASE_USD = Decimal("0.036480")
R2_EXPECTED_CEILING_USD = Decimal("0.045600")
R3_EXPECTED_BASE_USD = Decimal("2.736000")
R3_EXPECTED_CEILING_USD = Decimal("3.420000")
R2_MATRIX_SHA256 = "906de866d6c5f3503a20c38f9909182f48b9e7aaf980f0138470cb25dd1a717b"
R3_MATRIX_SHA256 = "5ed0abbb6a27b0118be7045abc412216ef320a6fe407ad4d02a6076d621ccd82"

OFFICIAL_SOURCES = (
    "https://platform.claude.com/docs/en/models/sonnet-5/whats-new-sonnet-5",
    "https://platform.claude.com/docs/en/build-with-claude/effort",
    "https://platform.claude.com/docs/en/build-with-claude/adaptive-thinking",
    "https://platform.claude.com/docs/en/api/messages/create",
    "https://platform.claude.com/docs/en/about-claude/pricing",
)

EXPECTED_DIAGNOSTIC_LOGICAL_SLOTS = (
    "cal.score.anchor.scn-01.a.clarity.r1",
    "cal.score.anchor.scn-01.a.organization-utility.r1",
    "cal.score.anchor.scn-01.b.clarity.r1",
    "cal.score.anchor.scn-01.b.organization-utility.r1",
    "cal.score.anchor.scn-01.c.clarity.r1",
)


class R4R1ErrorCode(StrEnum):
    R4_EVIDENCE_MISMATCH = "R4_EVIDENCE_MISMATCH"
    HISTORICAL_EVIDENCE_MISMATCH = "HISTORICAL_EVIDENCE_MISMATCH"
    POLICY_MATRIX_INVALID = "POLICY_MATRIX_INVALID"
    COST_INVALID = "COST_INVALID"
    LEDGER_INVALID = "LEDGER_INVALID"


class R4R1Error(RuntimeError):
    code: R4R1ErrorCode

    def __init__(self, code: R4R1ErrorCode) -> None:
        self.code = code
        super().__init__(code.value)


class PolicyLedgerStatus(StrEnum):
    PENDING = "PENDING"
    STARTED = "STARTED"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    SKIPPED_DEPENDENCY_FAILED = "SKIPPED_DEPENDENCY_FAILED"


@dataclass(frozen=True, slots=True)
class R4EvidenceAudit:
    ledger_sha256: str
    summary_sha256: str
    failed_call_id: str
    response_received: bool
    stop_reason: str
    text_block_count: int
    output_tokens: int
    max_output_tokens: int
    classification: str
    state_counts: Mapping[str, int]


@dataclass(frozen=True, slots=True)
class HistoricalDiagnosticScore:
    logical_slot_id: str
    evidence_set: str
    output_sha256: str
    status: str
    final_calibration_status: str


@dataclass(frozen=True, slots=True)
class UniformScoringCallSpec:
    execution_call_id: str
    original_logical_slot_id: str
    provider: CalibrationProvider
    model: str
    model_profile_id: str
    workload: CalibrationWorkload
    scenario_code: str
    task_kind: str
    repetition: int
    max_output_tokens: int
    input_utf8_upper_bound_bytes: int
    criterion_refs: tuple[str, ...]
    input_refs: tuple[str, ...]
    thinking_mode: AnthropicThinkingMode
    effort: AnthropicEffort
    automatic_retry_count: int


def _fail(code: R4R1ErrorCode) -> Never:
    raise R4R1Error(code) from None


def _sha256(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _canonical_sha256(payload: object) -> str:
    return _sha256(
        json.dumps(
            payload,
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        ).encode("utf-8")
    )


def _money(value: Decimal) -> Decimal:
    return value.quantize(Decimal("0.000001"), rounding=ROUND_CEILING)


def _read_frozen_json(
    root: Path,
    relative_path: str,
    expected_sha256: str,
) -> dict[str, object]:
    path = (root / relative_path).resolve()
    artifact_root = (root / "artifacts/calibration").resolve()
    if artifact_root not in path.parents:
        _fail(R4R1ErrorCode.R4_EVIDENCE_MISMATCH)
    try:
        payload = path.read_bytes()
        decoded = json.loads(payload)
    except (OSError, UnicodeError, json.JSONDecodeError):
        _fail(R4R1ErrorCode.R4_EVIDENCE_MISMATCH)
    if _sha256(payload) != expected_sha256 or type(decoded) is not dict:
        _fail(R4R1ErrorCode.R4_EVIDENCE_MISMATCH)
    return cast(dict[str, object], decoded)


def audit_r4_evidence(root: Path) -> R4EvidenceAudit:
    ledger = _read_frozen_json(root, R4_LEDGER_RELATIVE_PATH, R4_LEDGER_SHA256)
    summary = _read_frozen_json(root, R4_SUMMARY_RELATIVE_PATH, R4_SUMMARY_SHA256)
    raw_calls = ledger.get("calls")
    if type(raw_calls) is not list or len(raw_calls) != 71:
        _fail(R4R1ErrorCode.R4_EVIDENCE_MISMATCH)
    records = [cast(dict[str, object], item) for item in raw_calls if type(item) is dict]
    if len(records) != 71:
        _fail(R4R1ErrorCode.R4_EVIDENCE_MISMATCH)
    counts = Counter(cast(str, item.get("status")) for item in records)
    failed = [item for item in records if item.get("status") == "FAILED"]
    if len(failed) != 1:
        _fail(R4R1ErrorCode.R4_EVIDENCE_MISMATCH)
    record = failed[0]
    expected_counts = {
        "COMPLETED": 0,
        "FAILED": 1,
        "PENDING": 70,
        "SKIPPED_DEPENDENCY_FAILED": 0,
        "STARTED": 0,
    }
    if (
        {key: counts.get(key, 0) for key in expected_counts} != expected_counts
        or ledger.get("run_status") != "PAUSED_SYSTEMIC_FAILURE"
        or ledger.get("provider_calls_attempted") != 1
        or ledger.get("automatic_retry_count") != 0
        or ledger.get("automatic_rerun_count") != 0
        or record.get("r4_call_id") != R4_FAILED_CALL_ID
        or record.get("response_received") is not True
        or record.get("stop_reason") != "max_tokens"
        or record.get("text_block_count") != 0
        or record.get("output_tokens") != 512
        or record.get("max_output_tokens") != 512
        or record.get("raw_output_path") is not None
        or record.get("raw_output_sha256") is not None
        or summary.get("r4_status") != "PAUSED_SYSTEMIC_FAILURE"
        or summary.get("provider_calls_attempted") != 1
        or summary.get("duplicate_r4_call_ids") != []
        or summary.get("raw_output_count") != 0
    ):
        _fail(R4R1ErrorCode.R4_EVIDENCE_MISMATCH)
    return R4EvidenceAudit(
        ledger_sha256=R4_LEDGER_SHA256,
        summary_sha256=R4_SUMMARY_SHA256,
        failed_call_id=R4_FAILED_CALL_ID,
        response_received=True,
        stop_reason="max_tokens",
        text_block_count=0,
        output_tokens=512,
        max_output_tokens=512,
        classification="MAX_TOKENS_EXHAUSTED_BEFORE_TEXT",
        state_counts=expected_counts,
    )


def audit_historical_anthropic_scores(
    root: Path,
) -> tuple[tuple[HistoricalDiagnosticScore, ...], int]:
    audit = audit_r3_consolidated_evidence(root)
    anthropic = tuple(item for item in audit.reused_mappings if item.provider == "anthropic")
    openai = tuple(item for item in audit.reused_mappings if item.provider == "openai")
    by_id = {item.original_logical_slot_id: item for item in anthropic}
    if (
        len(anthropic) != 5
        or len(openai) != 20
        or set(by_id) != set(EXPECTED_DIAGNOSTIC_LOGICAL_SLOTS)
    ):
        _fail(R4R1ErrorCode.HISTORICAL_EVIDENCE_MISMATCH)
    diagnostics = tuple(
        HistoricalDiagnosticScore(
            logical_slot_id=logical_slot_id,
            evidence_set=by_id[logical_slot_id].evidence_set,
            output_sha256=by_id[logical_slot_id].output_sha256,
            status=by_id[logical_slot_id].status,
            final_calibration_status="DIAGNOSTIC_ONLY_NOT_FINAL_CALIBRATION",
        )
        for logical_slot_id in EXPECTED_DIAGNOSTIC_LOGICAL_SLOTS
    )
    return diagnostics, len(openai)


def _policy_call(
    original: CalibrationCallSpec,
    *,
    execution_call_id: str,
) -> UniformScoringCallSpec:
    return UniformScoringCallSpec(
        execution_call_id=execution_call_id,
        original_logical_slot_id=original.call_id,
        provider=original.provider,
        model=original.model,
        model_profile_id=original.model_profile_id,
        workload=original.workload,
        scenario_code=original.scenario_code,
        task_kind=original.task_kind,
        repetition=original.repetition,
        max_output_tokens=MAX_OUTPUT_TOKENS,
        input_utf8_upper_bound_bytes=original.input_utf8_upper_bound_bytes,
        criterion_refs=original.criterion_refs,
        input_refs=original.input_refs,
        thinking_mode=THINKING_MODE,
        effort=EFFORT,
        automatic_retry_count=0,
    )


def build_uniform_scoring_matrix() -> tuple[UniformScoringCallSpec, ...]:
    originals = tuple(
        call
        for call in PEDAGOGICAL_CALIBRATION_CALL_MATRIX
        if call.provider is CalibrationProvider.ANTHROPIC
    )
    initial = tuple(
        call
        for call in originals
        if call.call_id.startswith("cal.score.anchor.") and call.repetition == 1
    )
    repeats = tuple(
        call
        for call in originals
        if call.call_id.startswith("cal.score.anchor.") and call.repetition == 2
    )
    outputs = tuple(call for call in originals if call.call_id.startswith("cal.score.output."))
    ordered = (*initial, *repeats, *outputs)
    if (
        len(originals) != 76
        or len(initial) != 48
        or len(repeats) != 16
        or len(outputs) != 12
        or len({call.call_id for call in originals}) != 76
        or {call.call_id for call in originals} != {call.call_id for call in ordered}
    ):
        _fail(R4R1ErrorCode.POLICY_MATRIX_INVALID)
    result = tuple(
        _policy_call(
            call,
            execution_call_id=(
                CANARY_EXECUTION_CALL_ID
                if call.call_id == CANARY_LOGICAL_SLOT_ID
                else f"uniform.r4.scorer-policy.{call.call_id}"
            ),
        )
        for call in ordered
    )
    if (
        len({call.execution_call_id for call in result}) != 76
        or any(call.provider is not CalibrationProvider.ANTHROPIC for call in result)
        or any(call.model != MODEL for call in result)
        or any(call.model_profile_id != MODEL_PROFILE_ID for call in result)
        or any(call.workload is not CalibrationWorkload.SCORING for call in result)
        or any(call.thinking_mode is not THINKING_MODE for call in result)
        or any(call.effort is not EFFORT for call in result)
        or any(call.max_output_tokens != MAX_OUTPUT_TOKENS for call in result)
        or any(call.automatic_retry_count != 0 for call in result)
    ):
        _fail(R4R1ErrorCode.POLICY_MATRIX_INVALID)
    return result


def build_r2_canary_matrix() -> tuple[UniformScoringCallSpec, ...]:
    matches = tuple(
        call
        for call in build_uniform_scoring_matrix()
        if call.original_logical_slot_id == CANARY_LOGICAL_SLOT_ID
    )
    if len(matches) != 1 or matches[0].execution_call_id != CANARY_EXECUTION_CALL_ID:
        _fail(R4R1ErrorCode.POLICY_MATRIX_INVALID)
    return matches


def build_r3_completion_matrix() -> tuple[UniformScoringCallSpec, ...]:
    calls = tuple(
        call
        for call in build_uniform_scoring_matrix()
        if call.original_logical_slot_id != CANARY_LOGICAL_SLOT_ID
    )
    split = (
        sum(
            call.original_logical_slot_id.startswith("cal.score.anchor.") and call.repetition == 1
            for call in calls
        ),
        sum(
            call.original_logical_slot_id.startswith("cal.score.anchor.") and call.repetition == 2
            for call in calls
        ),
        sum(call.original_logical_slot_id.startswith("cal.score.output.") for call in calls),
    )
    if len(calls) != 75 or split != (47, 16, 12):
        _fail(R4R1ErrorCode.POLICY_MATRIX_INVALID)
    return calls


def _call_payload(call: UniformScoringCallSpec) -> dict[str, object]:
    return {
        "execution_call_id": call.execution_call_id,
        "original_logical_slot_id": call.original_logical_slot_id,
        "provider": call.provider.value,
        "model": call.model,
        "model_profile_id": call.model_profile_id,
        "workload": call.workload.value,
        "scenario_code": call.scenario_code,
        "task_kind": call.task_kind,
        "repetition": call.repetition,
        "max_output_tokens": call.max_output_tokens,
        "input_utf8_upper_bound_bytes": call.input_utf8_upper_bound_bytes,
        "criterion_refs": list(call.criterion_refs),
        "input_refs": list(call.input_refs),
        "thinking_mode": call.thinking_mode.value,
        "effort": call.effort.value,
        "automatic_retry_count": call.automatic_retry_count,
    }


def estimate_policy_cost(
    calls: Sequence[UniformScoringCallSpec],
) -> dict[str, object]:
    per_call = tuple(
        _money(
            (
                Decimal(call.input_utf8_upper_bound_bytes) * INPUT_USD_PER_MTOK
                + Decimal(call.max_output_tokens) * OUTPUT_USD_PER_MTOK
            )
            / Decimal(1_000_000)
        )
        for call in calls
    )
    maximum = _money(sum(per_call, start=Decimal("0")))
    ceiling = _money(maximum * COST_MARGIN)
    margin = _money(ceiling - maximum)
    if any(value != Decimal("0.036480") for value in per_call):
        _fail(R4R1ErrorCode.COST_INVALID)
    return {
        "call_count": len(calls),
        "input_max_per_call": 8_000,
        "output_max_per_call": MAX_OUTPUT_TOKENS,
        "per_call_maximum_usd": "0.036480",
        "maximum_before_margin_usd": str(maximum),
        "margin_multiplier": str(COST_MARGIN),
        "margin_amount_usd": str(margin),
        "requested_ceiling_usd": str(ceiling),
        "pricing": {
            "input_usd_per_mtok": str(INPUT_USD_PER_MTOK),
            "cache_hit_usd_per_mtok": str(CACHE_HIT_USD_PER_MTOK),
            "output_usd_per_mtok": str(OUTPUT_USD_PER_MTOK),
        },
    }


def policy_matrix_sha256(
    version: str,
    calls: Sequence[UniformScoringCallSpec],
    *,
    prerequisite: Mapping[str, object],
) -> str:
    return _canonical_sha256(
        {
            "version": version,
            "calls": [_call_payload(call) for call in calls],
            "cost": estimate_policy_cost(calls),
            "prerequisite": dict(prerequisite),
            "automatic_retry_count": 0,
            "automatic_rerun_count": 0,
            "stop_on_first_technical_failure": True,
            "policy": {
                "thinking_mode": THINKING_MODE.value,
                "effort": EFFORT.value,
                "max_output_tokens": MAX_OUTPUT_TOKENS,
                "uniform_final_population": True,
            },
        }
    )


def r2_matrix_sha256() -> str:
    return policy_matrix_sha256(
        R2_PLAN_VERSION,
        build_r2_canary_matrix(),
        prerequisite={
            "r4_ledger_sha256": R4_LEDGER_SHA256,
            "r4_summary_sha256": R4_SUMMARY_SHA256,
            "explicit_financial_approval_required": True,
            "explicit_transfer_approval_required": True,
        },
    )


def r3_matrix_sha256() -> str:
    return policy_matrix_sha256(
        R3_PLAN_VERSION,
        build_r3_completion_matrix(),
        prerequisite={
            "r2_canary_plan_version": R2_PLAN_VERSION,
            "r2_canary_matrix_sha256": r2_matrix_sha256(),
            "r2_canary_status": "PASS_HASH_VALID_REQUIRED",
            "explicit_financial_approval_required": True,
            "explicit_transfer_approval_required": True,
        },
    )


def _validate_frozen_checksums() -> None:
    if R2_MATRIX_SHA256 and r2_matrix_sha256() != R2_MATRIX_SHA256:
        _fail(R4R1ErrorCode.POLICY_MATRIX_INVALID)
    if R3_MATRIX_SHA256 and r3_matrix_sha256() != R3_MATRIX_SHA256:
        _fail(R4R1ErrorCode.POLICY_MATRIX_INVALID)


def build_policy_ledger(
    *,
    version: str,
    matrix_sha256: str,
    calls: Sequence[UniformScoringCallSpec],
    requested_ceiling_usd: str,
    prerequisite: Mapping[str, object],
) -> dict[str, object]:
    return {
        "plan_version": version,
        "matrix_sha256": matrix_sha256,
        "approved_ceiling_usd": None,
        "requested_ceiling_usd": requested_ceiling_usd,
        "financial_approval_required": True,
        "external_transfer_approval_required": True,
        "prerequisite": dict(prerequisite),
        "provider_calls_attempted": 0,
        "automatic_retry_count": 0,
        "automatic_rerun_count": 0,
        "total_cost_usd": "0.000000",
        "run_status": "AWAITING_EXPLICIT_APPROVAL",
        "calls": [
            {
                **_call_payload(call),
                "status": PolicyLedgerStatus.PENDING.value,
                "started_at": None,
                "completed_at": None,
                "closed_error_code": None,
                "thinking_block_count": None,
                "thinking_tokens": None,
                "text_block_count": None,
                "input_tokens": 0,
                "cached_input_tokens": 0,
                "output_tokens": 0,
                "total_tokens": 0,
                "latency_milliseconds": 0,
                "cost_usd": "0.000000",
                "raw_output_path": None,
                "raw_output_sha256": None,
            }
            for call in calls
        ],
    }


def next_executable_call_id(ledger: Mapping[str, object]) -> str | None:
    raw = ledger.get("calls")
    if type(raw) is not list:
        _fail(R4R1ErrorCode.LEDGER_INVALID)
    records = [cast(dict[str, object], item) for item in raw if type(item) is dict]
    if len(records) != len(raw):
        _fail(R4R1ErrorCode.LEDGER_INVALID)
    if any(item.get("status") == PolicyLedgerStatus.STARTED.value for item in records):
        _fail(R4R1ErrorCode.LEDGER_INVALID)
    allowed = {item.value for item in PolicyLedgerStatus}
    for item in records:
        status = item.get("status")
        if status not in allowed:
            _fail(R4R1ErrorCode.LEDGER_INVALID)
        if status == PolicyLedgerStatus.PENDING.value:
            call_id = item.get("execution_call_id")
            if type(call_id) is not str:
                _fail(R4R1ErrorCode.LEDGER_INVALID)
            return call_id
    return None


def r2_financial_approval_text(matrix_sha256: str) -> str:
    return "\n".join(
        (
            "J'approuve exclusivement l'exécution de la matrice",
            f"{R2_PLAN_VERSION},",
            f"checksum {matrix_sha256},",
            (
                "1 appel maximum (Anthropic Scorer claude-sonnet-5, "
                "thinking adaptive, effort low, max_output_tokens 2048),"
            ),
            "plafond 0.045600 USD,",
            "aucun retry et arrêt immédiat après ce canary quel que soit le résultat.",
        )
    )


def r2_transfer_approval_text(matrix_sha256: str) -> str:
    return "\n".join(
        (
            "J'autorise explicitement l'envoi à l'API Anthropic, exclusivement pour",
            f"la matrice {R2_PLAN_VERSION},",
            f"checksum {matrix_sha256},",
            "d'un anchor synthétique G1 strictement nécessaire au canary.",
            "Aucune base SQLite, aucun output historique et aucun secret supplémentaire.",
        )
    )


def r3_financial_approval_text(matrix_sha256: str) -> str:
    return "\n".join(
        (
            "J'approuve exclusivement l'exécution conditionnelle de la matrice",
            f"{R3_PLAN_VERSION},",
            f"checksum {matrix_sha256},",
            (
                "75 appels maximum (75 Anthropic Scorer claude-sonnet-5, "
                "thinking adaptive, effort low, max_output_tokens 2048),"
            ),
            "plafond 3.420000 USD,",
            "aucun retry et arrêt immédiat au premier échec technique.",
        )
    )


def r3_transfer_approval_text(matrix_sha256: str) -> str:
    return "\n".join(
        (
            "J'autorise explicitement l'envoi à l'API Anthropic, exclusivement pour",
            f"la matrice conditionnelle {R3_PLAN_VERSION},",
            f"checksum {matrix_sha256},",
            (
                "des anchors synthétiques G1 et des projections pédagogiques autorisées "
                "des six productions historiques strictement nécessaires."
            ),
            "Aucune base SQLite et aucun secret supplémentaire.",
        )
    )


def _historical_payload(
    diagnostics: Sequence[HistoricalDiagnosticScore],
) -> list[dict[str, object]]:
    return [
        {
            "logical_slot_id": item.logical_slot_id,
            "evidence_set": item.evidence_set,
            "output_sha256": item.output_sha256,
            "status": item.status,
            "final_calibration_status": item.final_calibration_status,
        }
        for item in diagnostics
    ]


def r1_payload(root: Path) -> dict[str, object]:
    evidence = audit_r4_evidence(root)
    diagnostics, openai_reusable_count = audit_historical_anthropic_scores(root)
    r2_calls = build_r2_canary_matrix()
    r3_calls = build_r3_completion_matrix()
    r2_hash = r2_matrix_sha256()
    r3_hash = r3_matrix_sha256()
    _validate_frozen_checksums()
    r2_cost = estimate_policy_cost(r2_calls)
    r3_cost = estimate_policy_cost(r3_calls)
    if (
        Decimal(cast(str, r2_cost["maximum_before_margin_usd"])) != R2_EXPECTED_BASE_USD
        or Decimal(cast(str, r2_cost["requested_ceiling_usd"])) != R2_EXPECTED_CEILING_USD
        or Decimal(cast(str, r3_cost["maximum_before_margin_usd"])) != R3_EXPECTED_BASE_USD
        or Decimal(cast(str, r3_cost["requested_ceiling_usd"])) != R3_EXPECTED_CEILING_USD
    ):
        _fail(R4R1ErrorCode.COST_INVALID)
    return {
        "phase": "12.16-G2-R3B-R4-R1",
        "status": "PASS_CLOSED",
        "refs": {
            "branch": "phase12/12-16-provider-model-calibration",
            "entry_head": "12685070a3c7cccd2c1a6ab0a429d1881ac58465",
            "entry_parent": "186c388772e66a99bb402c6e03ec6e469757ea1b",
            "entry_main": "7ae02ee109bcc6399ec0f71616da6aef07abda81",
        },
        "r4_evidence": {
            "ledger_sha256": evidence.ledger_sha256,
            "summary_sha256": evidence.summary_sha256,
            "failed_call_id": evidence.failed_call_id,
            "state_counts": dict(evidence.state_counts),
            "response_received": evidence.response_received,
            "stop_reason": evidence.stop_reason,
            "text_block_count": evidence.text_block_count,
            "output_tokens": evidence.output_tokens,
            "max_output_tokens": evidence.max_output_tokens,
            "classification": evidence.classification,
            "overclaim_thinking_tokens": False,
        },
        "transport_audit_before_r1": {
            "thinking_parameter_absent": True,
            "effort_parameter_absent": True,
            "thinking_blocks_not_counted": True,
            "thinking_tokens_not_retained": True,
            "text_blocks_only": True,
            "max_retries_zero": True,
        },
        "official_revalidation": {
            "adaptive_thinking_default": True,
            "default_effort": "high",
            "explicit_disabled_supported": True,
            "explicit_low_supported": True,
            "effort_request_field": "output_config.effort",
            "max_tokens_includes_thinking_and_text": True,
            "thinking_usage_field": "usage.output_tokens_details.thinking_tokens",
            "sources": list(OFFICIAL_SOURCES),
        },
        "policy_decision": {
            "selected": "B",
            "policy": "EXPLICIT_ADAPTIVE_LOW_2048",
            "thinking_mode": THINKING_MODE.value,
            "effort": EFFORT.value,
            "max_output_tokens": MAX_OUTPUT_TOKENS,
            "option_a": "REJECTED_METHODOLOGICAL_CHANGE",
            "option_b": "SELECTED_BOUNDED_REASONING_HEADROOM_X4",
            "option_c": "REJECTED_IMPLICIT_HIGH_TOO_COSTLY",
            "public_harness_contract_delta": "NONE",
        },
        "historical_anthropic_scores": _historical_payload(diagnostics),
        "historical_anthropic_score_count": len(diagnostics),
        "historical_anthropic_final_calibration_status": ("DIAGNOSTIC_ONLY_NOT_FINAL_CALIBRATION"),
        "openai_selected_output_projection_reuse_count": openai_reusable_count,
        "uniform_final_scoring_population": {
            "initial_anchor_scoring": 48,
            "repeatability": 16,
            "selected_outputs": 12,
            "total": 76,
        },
        "r2_canary": {
            "version": R2_PLAN_VERSION,
            "matrix_sha256": r2_hash,
            "logical_slot_id": CANARY_LOGICAL_SLOT_ID,
            "execution_call_id": CANARY_EXECUTION_CALL_ID,
            "calls": [_call_payload(call) for call in r2_calls],
            "cost": r2_cost,
            "financial_approval_text": r2_financial_approval_text(r2_hash),
            "transfer_approval_text": r2_transfer_approval_text(r2_hash),
            "ledger_relative_path": R2_LEDGER_RELATIVE_PATH,
            "already_approved": False,
        },
        "r3_completion": {
            "version": R3_PLAN_VERSION,
            "matrix_sha256": r3_hash,
            "calls": [_call_payload(call) for call in r3_calls],
            "split": {
                "initial_anchor_scoring": 47,
                "repeatability": 16,
                "selected_outputs": 12,
            },
            "cost": r3_cost,
            "financial_approval_text": r3_financial_approval_text(r3_hash),
            "transfer_approval_text": r3_transfer_approval_text(r3_hash),
            "ledger_relative_path": R3_LEDGER_RELATIVE_PATH,
            "prerequisite": "R2_CANARY_PASS_HASH_VALID_AND_NEW_APPROVALS",
            "already_approved": False,
        },
        "r1_live_provider_calls": 0,
        "r1_provider_cost_usd": "0.000000",
        "adr": "ADR-P12-064",
        "next_gate": "12.16-G2-R3B-R4-R2_READY_AFTER_EXPLICIT_APPROVAL",
    }


def _markdown_table_diagnostics(payload: Mapping[str, object]) -> list[str]:
    raw = cast(list[dict[str, object]], payload["historical_anthropic_scores"])
    lines = [
        "| Logical slot | Proof | Output SHA-256 | Final status |",
        "| --- | --- | --- | --- |",
    ]
    lines.extend(
        (
            f"| `{item['logical_slot_id']}` | `{item['evidence_set']}` | "
            f"`{item['output_sha256']}` | `{item['final_calibration_status']}` |"
        )
        for item in raw
    )
    return lines


def render_r1_baseline_markdown(root: Path) -> str:
    payload = r1_payload(root)
    r4 = cast(dict[str, object], payload["r4_evidence"])
    official = cast(dict[str, object], payload["official_revalidation"])
    policy = cast(dict[str, object], payload["policy_decision"])
    r2 = cast(dict[str, object], payload["r2_canary"])
    r3 = cast(dict[str, object], payload["r3_completion"])
    lines = [
        "# Phase 12.16-G2-R3B-R4-R1 — Rationalisation de la policy Anthropic Scorer",
        "",
        "## Preuve R4 préservée",
        "",
        f"- Ledger : `{r4['ledger_sha256']}`.",
        f"- Summary : `{r4['summary_sha256']}`.",
        (
            "- Classification : `MAX_TOKENS_EXHAUSTED_BEFORE_TEXT` : réponse reçue, "
            "`stop_reason=max_tokens`, `0` text block et `512/512` output tokens."
        ),
        "- R1 ne prétend pas que les 512 tokens sont tous des thinking tokens.",
        "",
        "## Audit du transport avant R1",
        "",
        "- Aucun `thinking` ni `output_config.effort` explicite.",
        "- Thinking blocks et `usage.output_tokens_details.thinking_tokens` non capturés.",
        "- Seuls les text blocks étaient comptés ; `max_retries=0` était déjà actif.",
        "",
        "## Revalidation officielle Anthropic",
        "",
        "- Sonnet 5 active l'adaptive thinking par défaut ; l'effort API par défaut est `high`.",
        "- Thinking peut être désactivé ; `low` est supporté via `output_config.effort`.",
        "- `max_tokens` couvre thinking + texte ; les thinking tokens sont exposés dans "
        "`usage.output_tokens_details.thinking_tokens`.",
        "- Sources officielles :",
        *(f"  - {source}" for source in cast(list[str], official["sources"])),
        "",
        "## Décision",
        "",
        "- Option A `disabled/512` rejetée : changement méthodologique trop fort.",
        "- Option B retenue : `adaptive/low/2048`, raisonnement conservé et headroom x4.",
        "- Option C rejetée : effort `high` implicite trop consommateur et non explicite.",
        f"- Policy : `{policy['policy']}` ; delta des ports publics : `NONE`.",
        "- La télémétrie conserve uniquement les counts et tokens, jamais le thinking brut.",
        "",
        "## Scores Anthropic historiques",
        "",
        *_markdown_table_diagnostics(payload),
        "",
        "Les cinq preuves restent intactes mais ne comptent plus dans la calibration finale.",
        "Les `20` résultats OpenAI restent réutilisables pour les projections selected-output.",
        "",
        "## Nouvelle population homogène",
        "",
        "- `48` anchors initiaux + `16` répétabilités + `12` selected-output = `76` slots.",
        "- Aucun ancien score Anthropic n'est soustrait.",
        "",
        "## Plans gelés",
        "",
        f"- R2 one-shot : `{r2['version']}` / `{r2['matrix_sha256']}`.",
        f"- R3 conditionnel : `{r3['version']}` / `{r3['matrix_sha256']}`.",
        "- Les anciennes approbations ne valent pas pour ces nouveaux checksums.",
        "",
        "## Preuve offline",
        "",
        "- `LIVE_PROVIDER_CALLS_R1 = 0`.",
        "- `LIVE_PROVIDER_COST_R1 = 0.000000 USD`.",
        "- R4 ledger/summary non modifiés ; R2/R3 non exécutés.",
    ]
    return "\n".join(lines)


def _render_cost_markdown(root: Path, *, r2: bool) -> str:
    payload = r1_payload(root)
    key = "r2_canary" if r2 else "r3_completion"
    plan = cast(dict[str, object], payload[key])
    cost = cast(dict[str, object], plan["cost"])
    title = "Canary R2" if r2 else "Completion conditionnelle R3"
    calls = "1" if r2 else "75"
    lines = [
        f"# Phase 12.16-G2-R3B-R4-R1 — {title}",
        "",
        f"- Version : `{plan['version']}`.",
        f"- Checksum : `{plan['matrix_sha256']}`.",
        f"- Appels : `{calls}` ; policy : `adaptive/low/2048` ; retry/rerun : `0/0`.",
        "- Borne par appel : `8000` input, `2048` output.",
        f"- Maximum avant marge : `{cost['maximum_before_margin_usd']} USD`.",
        f"- Plafond avec marge 25 % : `{cost['requested_ceiling_usd']} USD`.",
        "",
        "## Approbation financière requise",
        "",
        "```text",
        cast(str, plan["financial_approval_text"]),
        "```",
        "",
        "## Autorisation de transfert externe requise",
        "",
        "```text",
        cast(str, plan["transfer_approval_text"]),
        "```",
        "",
        "Ce texte est un modèle d'approbation et n'est pas déjà approuvé.",
    ]
    return "\n".join(lines)


def render_r2_cost_markdown(root: Path) -> str:
    return _render_cost_markdown(root, r2=True)


def render_r3_cost_markdown(root: Path) -> str:
    return _render_cost_markdown(root, r2=False)


def _render_cost_json(root: Path, *, r2: bool) -> str:
    payload = r1_payload(root)
    key = "r2_canary" if r2 else "r3_completion"
    return json.dumps(payload[key], ensure_ascii=False, indent=2, sort_keys=True) + "\n"


def render_r2_cost_json(root: Path) -> str:
    return _render_cost_json(root, r2=True)


def render_r3_cost_json(root: Path) -> str:
    return _render_cost_json(root, r2=False)


def _atomic_write(path: Path, payload: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    try:
        with temporary.open("wb") as stream:
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        if temporary.exists():
            temporary.unlink()


def write_r1_outputs(root: Path) -> None:
    payload = r1_payload(root)
    r2 = cast(dict[str, object], payload["r2_canary"])
    r3 = cast(dict[str, object], payload["r3_completion"])
    r2_calls = build_r2_canary_matrix()
    r3_calls = build_r3_completion_matrix()
    r2_cost = cast(dict[str, object], r2["cost"])
    r3_cost = cast(dict[str, object], r3["cost"])
    r2_ledger = build_policy_ledger(
        version=R2_PLAN_VERSION,
        matrix_sha256=cast(str, r2["matrix_sha256"]),
        calls=r2_calls,
        requested_ceiling_usd=cast(str, r2_cost["requested_ceiling_usd"]),
        prerequisite={
            "r4_ledger_sha256": R4_LEDGER_SHA256,
            "r4_summary_sha256": R4_SUMMARY_SHA256,
        },
    )
    r3_ledger = build_policy_ledger(
        version=R3_PLAN_VERSION,
        matrix_sha256=cast(str, r3["matrix_sha256"]),
        calls=r3_calls,
        requested_ceiling_usd=cast(str, r3_cost["requested_ceiling_usd"]),
        prerequisite={
            "r2_canary_plan_version": R2_PLAN_VERSION,
            "r2_canary_matrix_sha256": cast(str, r2["matrix_sha256"]),
            "r2_canary_status": "PASS_HASH_VALID_REQUIRED",
        },
    )
    outputs = {
        R1_BASELINE_RELATIVE_PATH: render_r1_baseline_markdown(root) + "\n",
        R2_COST_MARKDOWN_RELATIVE_PATH: render_r2_cost_markdown(root) + "\n",
        R2_COST_JSON_RELATIVE_PATH: render_r2_cost_json(root),
        R3_COST_MARKDOWN_RELATIVE_PATH: render_r3_cost_markdown(root) + "\n",
        R3_COST_JSON_RELATIVE_PATH: render_r3_cost_json(root),
        R2_LEDGER_RELATIVE_PATH: (
            json.dumps(r2_ledger, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
        ),
        R3_LEDGER_RELATIVE_PATH: (
            json.dumps(r3_ledger, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
        ),
    }
    for relative_path, content in outputs.items():
        _atomic_write(root / relative_path, content.encode("utf-8"))
