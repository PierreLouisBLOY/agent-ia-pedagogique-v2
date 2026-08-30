"""Offline owner for the Anthropic HTTP 503 calibration recovery plan."""

from __future__ import annotations

import hashlib
import json
import os
from collections import Counter
from collections.abc import Mapping, Sequence
from copy import deepcopy
from dataclasses import asdict, dataclass
from decimal import ROUND_CEILING, Decimal
from enum import StrEnum
from fractions import Fraction
from pathlib import Path
from typing import Never, cast

from tests.calibration.pedagogical.r4_r1_policy import (
    CANARY_LOGICAL_SLOT_ID,
    EFFORT,
    INPUT_USD_PER_MTOK,
    MAX_OUTPUT_TOKENS,
    MODEL,
    MODEL_PROFILE_ID,
    OUTPUT_USD_PER_MTOK,
    THINKING_MODE,
    UniformScoringCallSpec,
    build_uniform_scoring_matrix,
)
from tests.providers.anthropic.mapping import score_output_schema
from tests.providers.anthropic.transport import transform_anthropic_provider_schema

ROOT = Path(__file__).resolve().parents[3]

R2_LEDGER_RELATIVE_PATH = "artifacts/calibration/12.16-g2-r4-r2/ledger.json"
R2_SUMMARY_RELATIVE_PATH = "artifacts/calibration/12.16-g2-r4-r2/summary.json"
R2_RAW_RELATIVE_PATH = (
    "artifacts/calibration/12.16-g2-r4-r2/raw/"
    "remediation.r4.scorer-policy.scn-01.c.organization-utility.canary.r1.json"
)
R3_LEDGER_RELATIVE_PATH = "artifacts/calibration/12.16-g2-r4-r3/ledger.json"
R3_SUMMARY_RELATIVE_PATH = "artifacts/calibration/12.16-g2-r4-r3/summary.json"
R3_TRANSFER_MANIFEST_RELATIVE_PATH = "artifacts/calibration/12.16-g2-r4-r3/transfer_manifest.json"
G2_LEDGER_RELATIVE_PATH = "artifacts/calibration/12.16-g2/ledger.json"

RECOVERY_ARTIFACT_DIRECTORY = "artifacts/calibration/12.16-g2-r4-r4"
RECOVERY_LEDGER_RELATIVE_PATH = f"{RECOVERY_ARTIFACT_DIRECTORY}/ledger.json"
REUSABLE_MANIFEST_RELATIVE_PATH = f"{RECOVERY_ARTIFACT_DIRECTORY}/reusable_results_manifest.json"

BASELINE_RELATIVE_PATH = "docs/development/PHASE_12_16_G2_R3B_R4_R3_R1_HTTP503_RECOVERY_BASELINE.md"
PLAN_MARKDOWN_RELATIVE_PATH = "docs/development/PHASE_12_16_G2_R3B_R4_R3_R1_CONTINUATION_PLAN.md"
PLAN_JSON_RELATIVE_PATH = "docs/development/PHASE_12_16_G2_R3B_R4_R3_R1_CONTINUATION_PLAN.json"

R2_LEDGER_SHA256 = "ef694ad8174a28079db030086d83d0ffb8d02d7aed598092961b821b3fdd2a31"
R2_SUMMARY_SHA256 = "ec88b72b616793bd4d215ec1f4a5e24a03b458691e1b00ce7491b4f6486d5948"
R2_RAW_SHA256 = "a16287401cc87863d23dc170b76cf2983ccae1909374d2a3b6af8226642f6053"
R3_LEDGER_SHA256 = "bd4f9272730c225a7e1a309137cf937bcb0b8a9603446cc76c8d94871a029c99"
R3_SUMMARY_SHA256 = "c3052b33193bf6542cd96a2ff1706c8d210e297c736d1d3ffa101676c9405729"
R3_TRANSFER_MANIFEST_SHA256 = "c8742f5e4a46215a34141e93b17b36a730c6ab6136b3c92ad3eba073be1e905a"
R3_RAW_ORDERED_LIST_SHA256 = "f39d83334eda6b0f87b4ecf363e9f432d818b298d55defa6c1076ec766a34c52"

FAILED_LOGICAL_SLOT_ID = "cal.score.anchor.scn-07.b.correction-quality.r1"
FAILED_EXECUTION_CALL_ID = (
    "uniform.r4.scorer-policy.cal.score.anchor.scn-07.b.correction-quality.r1"
)
REMEDIATION_EXECUTION_CALL_ID = "remediation.r4-r3.http503.scn-07.b.correction-quality.canary.r1"

REUSABLE_MANIFEST_VERSION = "12.16-g2-r4-r3-r1-reusable-uniform-results-v1"
RECOVERY_PLAN_VERSION = "12.16-g2-r4-r4-anthropic-recovery-completion-v1"
REUSABLE_MANIFEST_SHA256 = "555486d2fe968d347e72ab378b4b0370dac48bb40921756993699f1fbf412566"
RECOVERY_MATRIX_SHA256 = "8cdc7c5b1ed6eaeb02606b2130db43d398bdbe51d99116d97014cb014e8b3526"

INPUT_UTF8_UPPER_BOUND_BYTES = 8_000
CACHE_HIT_USD_PER_MTOK = Decimal("0.20")
COST_MARGIN = Decimal("1.25")
EXPECTED_MAXIMUM_BEFORE_MARGIN_USD = Decimal("1.386240")
EXPECTED_REQUESTED_CEILING_USD = Decimal("1.732800")

ENTRY_BRANCH = "phase12/12-16-provider-model-calibration"
ENTRY_HEAD = "a736c707f9903ead7f5a72a1690ff9432a742f0d"
ENTRY_MAIN = "7ae02ee109bcc6399ec0f71616da6aef07abda81"

OFFICIAL_SOURCES = (
    "https://platform.claude.com/docs/en/models/sonnet-5/whats-new-sonnet-5",
    "https://platform.claude.com/docs/en/build-with-claude/effort",
    "https://platform.claude.com/docs/en/build-with-claude/structured-outputs",
    "https://platform.claude.com/docs/en/api/messages/create",
    "https://platform.claude.com/docs/en/about-claude/pricing",
)


class RecoveryErrorCode(StrEnum):
    R2_EVIDENCE_MISMATCH = "R2_EVIDENCE_MISMATCH"
    R3_EVIDENCE_MISMATCH = "R3_EVIDENCE_MISMATCH"
    REUSABLE_RESULT_INVALID = "REUSABLE_RESULT_INVALID"
    SLOT_SUBTRACTION_INVALID = "SLOT_SUBTRACTION_INVALID"
    SELECTED_OUTPUT_DEPENDENCY_FAILED = "SELECTED_OUTPUT_DEPENDENCY_FAILED"
    RECOVERY_MATRIX_INVALID = "RECOVERY_MATRIX_INVALID"
    COST_INVALID = "COST_INVALID"
    LEDGER_INVALID = "LEDGER_INVALID"


class RecoveryError(RuntimeError):
    code: RecoveryErrorCode

    def __init__(self, code: RecoveryErrorCode) -> None:
        self.code = code
        super().__init__(code.value)


class RecoveryCategory(StrEnum):
    INITIAL_ANCHOR = "INITIAL_ANCHOR"
    REPEATABILITY = "REPEATABILITY"
    SELECTED_OUTPUT = "SELECTED_OUTPUT"


class RecoveryLedgerStatus(StrEnum):
    PENDING = "PENDING"
    STARTED = "STARTED"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    SKIPPED_DEPENDENCY_FAILED = "SKIPPED_DEPENDENCY_FAILED"
    BLOCKED_BY_CANARY = "BLOCKED_BY_CANARY"


@dataclass(frozen=True, slots=True)
class RecoveryCallSpec:
    execution_call_id: str
    original_logical_slot_id: str
    source_r3_call_id: str
    remediation_source_failed_call_id: str | None
    mapping_class: str
    category: RecoveryCategory
    provider: str
    model: str
    model_profile_id: str
    workload: str
    scenario_code: str
    task_kind: str
    repetition: int
    max_output_tokens: int
    input_utf8_upper_bound_bytes: int
    criterion_refs: tuple[str, ...]
    input_refs: tuple[str, ...]
    thinking_mode: str
    effort: str
    automatic_retry_count: int
    automatic_rerun_count: int


def _fail(code: RecoveryErrorCode) -> Never:
    raise RecoveryError(code) from None


def _sha256(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _canonical_bytes(payload: object) -> bytes:
    return json.dumps(
        payload,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")


def _canonical_sha256(payload: object) -> str:
    return _sha256(_canonical_bytes(payload))


def _pretty_json(payload: object) -> str:
    return json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n"


def _money(value: Decimal) -> Decimal:
    return value.quantize(Decimal("0.000001"), rounding=ROUND_CEILING)


def _artifact_path(root: Path, relative_path: str) -> Path:
    path = (root / relative_path).resolve()
    artifact_root = (root / "artifacts/calibration").resolve()
    if artifact_root not in path.parents:
        raise ValueError("artifact path escaped calibration directory")
    return path


def _read_frozen_json(
    root: Path,
    relative_path: str,
    expected_sha256: str,
    error_code: RecoveryErrorCode,
) -> dict[str, object]:
    path = _artifact_path(root, relative_path)
    try:
        raw = path.read_bytes()
        value = json.loads(raw.decode("utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        _fail(error_code)
    if _sha256(raw) != expected_sha256 or type(value) is not dict:
        _fail(error_code)
    return cast(dict[str, object], value)


def _records(
    ledger: Mapping[str, object], error_code: RecoveryErrorCode
) -> list[dict[str, object]]:
    raw = ledger.get("calls")
    if type(raw) is not list or any(type(item) is not dict for item in raw):
        _fail(error_code)
    return cast(list[dict[str, object]], raw)


def _provider_schema_sha256() -> str:
    return _canonical_sha256(transform_anthropic_provider_schema(score_output_schema()))


def _validate_score_raw(
    root: Path,
    record: Mapping[str, object],
    *,
    raw_root_relative: str,
) -> None:
    relative = record.get("raw_output_path")
    expected_hash = record.get("raw_output_sha256")
    expected_bytes = record.get("raw_output_utf8_bytes")
    if (
        type(relative) is not str
        or type(expected_hash) is not str
        or type(expected_bytes) is not int
    ):
        _fail(RecoveryErrorCode.REUSABLE_RESULT_INVALID)
    path = _artifact_path(root, relative)
    raw_root = _artifact_path(root, raw_root_relative)
    if raw_root not in path.parents:
        _fail(RecoveryErrorCode.REUSABLE_RESULT_INVALID)
    try:
        raw = path.read_bytes()
        payload = json.loads(raw.decode("utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        _fail(RecoveryErrorCode.REUSABLE_RESULT_INVALID)
    if (
        _sha256(raw) != expected_hash
        or len(raw) != expected_bytes
        or type(payload) is not dict
        or set(payload) != {"status", "score_numerator", "score_denominator"}
    ):
        _fail(RecoveryErrorCode.REUSABLE_RESULT_INVALID)
    status = payload.get("status")
    numerator = payload.get("score_numerator")
    denominator = payload.get("score_denominator")
    if status == "INCONCLUSIVE":
        if numerator is not None or denominator is not None:
            _fail(RecoveryErrorCode.REUSABLE_RESULT_INVALID)
        if record.get("score_status") != "INCONCLUSIVE":
            _fail(RecoveryErrorCode.REUSABLE_RESULT_INVALID)
        return
    if (
        status != "SCORED"
        or type(numerator) is not int
        or type(denominator) is not int
        or denominator <= 0
    ):
        _fail(RecoveryErrorCode.REUSABLE_RESULT_INVALID)
    try:
        score = Fraction(numerator, denominator)
    except (TypeError, ValueError, ZeroDivisionError):
        _fail(RecoveryErrorCode.REUSABLE_RESULT_INVALID)
    if not 0 <= score <= 1:
        _fail(RecoveryErrorCode.REUSABLE_RESULT_INVALID)
    if record.get("score_status") != "SCORED" or record.get("rational_score") != (
        f"{numerator}/{denominator}"
    ):
        _fail(RecoveryErrorCode.REUSABLE_RESULT_INVALID)


def audit_evidence(root: Path = ROOT) -> dict[str, object]:
    r2_ledger = _read_frozen_json(
        root,
        R2_LEDGER_RELATIVE_PATH,
        R2_LEDGER_SHA256,
        RecoveryErrorCode.R2_EVIDENCE_MISMATCH,
    )
    r2_summary = _read_frozen_json(
        root,
        R2_SUMMARY_RELATIVE_PATH,
        R2_SUMMARY_SHA256,
        RecoveryErrorCode.R2_EVIDENCE_MISMATCH,
    )
    r2_raw_path = _artifact_path(root, R2_RAW_RELATIVE_PATH)
    try:
        r2_raw = r2_raw_path.read_bytes()
    except OSError:
        _fail(RecoveryErrorCode.R2_EVIDENCE_MISMATCH)
    r2_records = _records(r2_ledger, RecoveryErrorCode.R2_EVIDENCE_MISMATCH)
    if len(r2_records) != 1:
        _fail(RecoveryErrorCode.R2_EVIDENCE_MISMATCH)
    r2_call = r2_records[0]
    if (
        _sha256(r2_raw) != R2_RAW_SHA256
        or len(r2_raw) != 61
        or r2_call.get("original_logical_slot_id") != CANARY_LOGICAL_SLOT_ID
        or r2_call.get("status") != "COMPLETED"
        or r2_call.get("score_status") != "SCORED"
        or r2_call.get("thinking_mode") != THINKING_MODE.value
        or r2_call.get("effort") != EFFORT.value
        or r2_call.get("max_output_tokens") != MAX_OUTPUT_TOKENS
        or r2_summary.get("provider_schema_sha256") != _provider_schema_sha256()
    ):
        _fail(RecoveryErrorCode.R2_EVIDENCE_MISMATCH)
    _validate_score_raw(
        root,
        r2_call,
        raw_root_relative="artifacts/calibration/12.16-g2-r4-r2/raw",
    )

    r3_ledger = _read_frozen_json(
        root,
        R3_LEDGER_RELATIVE_PATH,
        R3_LEDGER_SHA256,
        RecoveryErrorCode.R3_EVIDENCE_MISMATCH,
    )
    r3_summary = _read_frozen_json(
        root,
        R3_SUMMARY_RELATIVE_PATH,
        R3_SUMMARY_SHA256,
        RecoveryErrorCode.R3_EVIDENCE_MISMATCH,
    )
    r3_manifest = _read_frozen_json(
        root,
        R3_TRANSFER_MANIFEST_RELATIVE_PATH,
        R3_TRANSFER_MANIFEST_SHA256,
        RecoveryErrorCode.R3_EVIDENCE_MISMATCH,
    )
    r3_records = _records(r3_ledger, RecoveryErrorCode.R3_EVIDENCE_MISMATCH)
    counts = Counter(cast(str, item.get("status")) for item in r3_records)
    if (
        len(r3_records) != 75
        or counts != {"COMPLETED": 37, "FAILED": 1, "PENDING": 37}
        or r3_ledger.get("provider_calls_attempted") != 38
        or r3_ledger.get("automatic_retry_count") != 0
        or r3_ledger.get("automatic_rerun_count") != 0
        or r3_summary.get("ledger_final_sha256") != R3_LEDGER_SHA256
        or r3_summary.get("status_counts") != {"COMPLETED": 37, "FAILED": 1, "PENDING": 37}
    ):
        _fail(RecoveryErrorCode.R3_EVIDENCE_MISMATCH)
    failed = [item for item in r3_records if item.get("status") == "FAILED"]
    if len(failed) != 1:
        _fail(RecoveryErrorCode.R3_EVIDENCE_MISMATCH)
    failed_record = failed[0]
    if (
        failed_record.get("execution_call_id") != FAILED_EXECUTION_CALL_ID
        or failed_record.get("original_logical_slot_id") != FAILED_LOGICAL_SLOT_ID
        or failed_record.get("http_status") != 503
        or failed_record.get("provider_error_type") != "INTERNAL_SERVER_ERROR"
        or failed_record.get("raw_output_path") is not None
        or failed_record.get("raw_output_sha256") is not None
        or failed_record.get("response_received") is not True
        or failed_record.get("closed_error_code") != "ANTHROPIC_SCORER_TRANSPORT_SERVER"
    ):
        _fail(RecoveryErrorCode.R3_EVIDENCE_MISMATCH)
    completed = [item for item in r3_records if item.get("status") == "COMPLETED"]
    completed_logical_ids: set[str] = set()
    raw_hashes: list[str] = []
    for record in completed:
        logical_id = record.get("original_logical_slot_id")
        raw_hash = record.get("raw_output_sha256")
        if (
            type(logical_id) is not str
            or logical_id in completed_logical_ids
            or logical_id == CANARY_LOGICAL_SLOT_ID
            or record.get("provider") != "anthropic"
            or record.get("model") != MODEL
            or record.get("model_profile_id") != MODEL_PROFILE_ID
            or record.get("thinking_mode") != THINKING_MODE.value
            or record.get("effort") != EFFORT.value
            or record.get("max_output_tokens") != MAX_OUTPUT_TOKENS
            or record.get("automatic_retry_count") != 0
            or record.get("response_status") not in {"STRUCTURED", "INCONCLUSIVE"}
            or record.get("score_status") not in {"SCORED", "INCONCLUSIVE"}
            or type(raw_hash) is not str
        ):
            _fail(RecoveryErrorCode.REUSABLE_RESULT_INVALID)
        completed_logical_ids.add(logical_id)
        raw_hashes.append(raw_hash)
        _validate_score_raw(
            root,
            record,
            raw_root_relative="artifacts/calibration/12.16-g2-r4-r3/raw",
        )
    raw_list_hash = _sha256(json.dumps(sorted(raw_hashes), separators=(",", ":")).encode("utf-8"))
    if len(completed) != 37 or raw_list_hash != R3_RAW_ORDERED_LIST_SHA256:
        _fail(RecoveryErrorCode.R3_EVIDENCE_MISMATCH)
    manifest_calls = r3_manifest.get("calls")
    if (
        r3_manifest.get("call_count") != 75
        or type(manifest_calls) is not list
        or any(type(item) is not dict for item in manifest_calls)
    ):
        _fail(RecoveryErrorCode.R3_EVIDENCE_MISMATCH)
    manifest_by_execution_id = {
        cast(str, item["execution_call_id"]): cast(dict[str, object], item)
        for item in cast(list[dict[str, object]], manifest_calls)
    }
    if len(manifest_by_execution_id) != 75:
        _fail(RecoveryErrorCode.R3_EVIDENCE_MISMATCH)
    for record in completed:
        execution_id = cast(str, record["execution_call_id"])
        item = manifest_by_execution_id.get(execution_id)
        if (
            item is None
            or item.get("logical_slot_id") != record["original_logical_slot_id"]
            or type(item.get("projection_sha256")) is not str
        ):
            _fail(RecoveryErrorCode.R3_EVIDENCE_MISMATCH)
    return {
        "r2": {"ledger": r2_ledger, "summary": r2_summary, "call": r2_call},
        "r3": {
            "ledger": r3_ledger,
            "summary": r3_summary,
            "manifest": r3_manifest,
            "manifest_by_execution_id": manifest_by_execution_id,
            "records": r3_records,
            "completed": completed,
            "failed": failed_record,
            "raw_ordered_list_sha256": raw_list_hash,
        },
    }


def _reusable_item(
    record: Mapping[str, object],
    *,
    proof_set: str,
    mapping_class: str,
    input_sha256: str,
) -> dict[str, object]:
    return {
        "proof_set": proof_set,
        "execution_call_id": record["execution_call_id"],
        "logical_slot_id": record["original_logical_slot_id"],
        "provider": record["provider"],
        "model": record["model"],
        "model_profile_id": record["model_profile_id"],
        "thinking_mode": record["thinking_mode"],
        "effort": record["effort"],
        "max_output_tokens": record["max_output_tokens"],
        "input_sha256": input_sha256,
        "schema_sha256": _provider_schema_sha256(),
        "output_sha256": record["raw_output_sha256"],
        "status": record["status"],
        "score_status": record["score_status"],
        "rational_score": record["rational_score"],
        "usage": {
            "input_tokens": record["input_tokens"],
            "cached_input_tokens": record["cached_input_tokens"],
            "output_tokens": record["output_tokens"],
            "thinking_tokens": record["thinking_tokens"],
            "total_tokens": record["total_tokens"],
        },
        "cost_usd": record["cost_usd"],
        "mapping_class": mapping_class,
    }


def build_reusable_manifest(root: Path = ROOT) -> dict[str, object]:
    evidence = audit_evidence(root)
    r2 = cast(dict[str, object], evidence["r2"])
    r3 = cast(dict[str, object], evidence["r3"])
    r2_summary = cast(dict[str, object], r2["summary"])
    r2_call = cast(dict[str, object], r2["call"])
    manifest_by_id = cast(dict[str, dict[str, object]], r3["manifest_by_execution_id"])
    items = [
        _reusable_item(
            r2_call,
            proof_set="R2_HOMOGENEOUS_CANARY",
            mapping_class="HOMOGENEOUS_POLICY_CANARY",
            input_sha256=cast(str, r2_summary["transfer_projection_sha256"]),
        )
    ]
    for record in cast(list[dict[str, object]], r3["completed"]):
        execution_id = cast(str, record["execution_call_id"])
        items.append(
            _reusable_item(
                record,
                proof_set="R3_COMPLETED_BEFORE_HTTP503",
                mapping_class="R3_REUSABLE_COMPLETED",
                input_sha256=cast(str, manifest_by_id[execution_id]["projection_sha256"]),
            )
        )
    logical_ids = [cast(str, item["logical_slot_id"]) for item in items]
    if (
        len(items) != 38
        or len(logical_ids) != len(set(logical_ids))
        or any(item["status"] != "COMPLETED" for item in items)
        or any(item["provider"] != "anthropic" for item in items)
        or any(item["model"] != MODEL for item in items)
        or any(item["thinking_mode"] != THINKING_MODE.value for item in items)
        or any(item["effort"] != EFFORT.value for item in items)
        or any(item["max_output_tokens"] != MAX_OUTPUT_TOKENS for item in items)
    ):
        _fail(RecoveryErrorCode.REUSABLE_RESULT_INVALID)
    return {
        "manifest_version": REUSABLE_MANIFEST_VERSION,
        "result_count": len(items),
        "raw_content_recorded": False,
        "diagnostic_only_results_included": False,
        "results": items,
    }


def reusable_manifest_sha256(root: Path = ROOT) -> str:
    return _canonical_sha256(build_reusable_manifest(root))


def _category(call: UniformScoringCallSpec) -> RecoveryCategory:
    if call.original_logical_slot_id.startswith("cal.score.output."):
        return RecoveryCategory.SELECTED_OUTPUT
    if call.repetition == 2:
        return RecoveryCategory.REPEATABILITY
    return RecoveryCategory.INITIAL_ANCHOR


def _new_execution_call_id(logical_slot_id: str) -> str:
    return f"continuation.r4-r4.{logical_slot_id}"


def build_recovery_matrix(root: Path = ROOT) -> tuple[RecoveryCallSpec, ...]:
    evidence = audit_evidence(root)
    reusable = build_reusable_manifest(root)
    reused_ids = {
        cast(str, item["logical_slot_id"])
        for item in cast(list[dict[str, object]], reusable["results"])
    }
    uniform = build_uniform_scoring_matrix()
    all_ids = {call.original_logical_slot_id for call in uniform}
    remaining_ids = all_ids - reused_ids
    if (
        len(all_ids) != 76
        or len(reused_ids) != 38
        or len(remaining_ids) != 38
        or all_ids != reused_ids | remaining_ids
        or reused_ids & remaining_ids
        or FAILED_LOGICAL_SLOT_ID not in remaining_ids
    ):
        _fail(RecoveryErrorCode.SLOT_SUBTRACTION_INVALID)
    r3 = cast(dict[str, object], evidence["r3"])
    records = cast(list[dict[str, object]], r3["records"])
    r3_by_logical_id = {cast(str, record["original_logical_slot_id"]): record for record in records}
    if set(r3_by_logical_id) != all_ids - {CANARY_LOGICAL_SLOT_ID}:
        _fail(RecoveryErrorCode.SLOT_SUBTRACTION_INVALID)
    remaining_uniform = [call for call in uniform if call.original_logical_slot_id in remaining_ids]
    failed_uniform = [
        call
        for call in remaining_uniform
        if call.original_logical_slot_id == FAILED_LOGICAL_SLOT_ID
    ]
    if len(failed_uniform) != 1:
        _fail(RecoveryErrorCode.RECOVERY_MATRIX_INVALID)
    ordered = failed_uniform + [
        call
        for call in remaining_uniform
        if call.original_logical_slot_id != FAILED_LOGICAL_SLOT_ID
    ]
    result: list[RecoveryCallSpec] = []
    for index, call in enumerate(ordered):
        source = r3_by_logical_id[call.original_logical_slot_id]
        is_canary = index == 0
        expected_status = "FAILED" if is_canary else "PENDING"
        if source.get("status") != expected_status:
            _fail(RecoveryErrorCode.RECOVERY_MATRIX_INVALID)
        result.append(
            RecoveryCallSpec(
                execution_call_id=(
                    REMEDIATION_EXECUTION_CALL_ID
                    if is_canary
                    else _new_execution_call_id(call.original_logical_slot_id)
                ),
                original_logical_slot_id=call.original_logical_slot_id,
                source_r3_call_id=cast(str, source["execution_call_id"]),
                remediation_source_failed_call_id=(FAILED_EXECUTION_CALL_ID if is_canary else None),
                mapping_class=(
                    "TRANSIENT_SERVER_ERROR_REMEDIATION" if is_canary else "R3_PENDING_CONTINUATION"
                ),
                category=_category(call),
                provider=call.provider.value,
                model=call.model,
                model_profile_id=call.model_profile_id,
                workload=call.workload.value,
                scenario_code=call.scenario_code,
                task_kind=call.task_kind,
                repetition=call.repetition,
                max_output_tokens=call.max_output_tokens,
                input_utf8_upper_bound_bytes=call.input_utf8_upper_bound_bytes,
                criterion_refs=call.criterion_refs,
                input_refs=call.input_refs,
                thinking_mode=call.thinking_mode.value,
                effort=call.effort.value,
                automatic_retry_count=0,
                automatic_rerun_count=0,
            )
        )
    split = Counter(item.category for item in result)
    old_execution_ids = {cast(str, record["execution_call_id"]) for record in records} | {
        cast(
            str,
            cast(dict[str, object], cast(dict[str, object], evidence["r2"])["call"])[
                "execution_call_id"
            ],
        )
    }
    if (
        len(result) != 38
        or split
        != {
            RecoveryCategory.INITIAL_ANCHOR: 10,
            RecoveryCategory.REPEATABILITY: 16,
            RecoveryCategory.SELECTED_OUTPUT: 12,
        }
        or len({item.execution_call_id for item in result}) != 38
        or len({item.original_logical_slot_id for item in result}) != 38
        or any(item.execution_call_id in old_execution_ids for item in result)
        or any(item.provider != "anthropic" for item in result)
        or any(item.model != MODEL for item in result)
        or any(item.model_profile_id != MODEL_PROFILE_ID for item in result)
        or any(item.thinking_mode != THINKING_MODE.value for item in result)
        or any(item.effort != EFFORT.value for item in result)
        or any(item.max_output_tokens != MAX_OUTPUT_TOKENS for item in result)
        or any(item.automatic_retry_count != 0 for item in result)
        or any(item.automatic_rerun_count != 0 for item in result)
    ):
        _fail(RecoveryErrorCode.RECOVERY_MATRIX_INVALID)
    return tuple(result)


def audit_selected_output_dependencies(root: Path = ROOT) -> dict[str, str]:
    selected = [
        call
        for call in build_recovery_matrix(root)
        if call.category is RecoveryCategory.SELECTED_OUTPUT
    ]
    source_ids = {call.input_refs[0].removeprefix("output:") for call in selected}
    ledger_path = _artifact_path(root, G2_LEDGER_RELATIVE_PATH)
    try:
        ledger = json.loads(ledger_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        _fail(RecoveryErrorCode.SELECTED_OUTPUT_DEPENDENCY_FAILED)
    if type(ledger) is not dict:
        _fail(RecoveryErrorCode.SELECTED_OUTPUT_DEPENDENCY_FAILED)
    records = _records(ledger, RecoveryErrorCode.SELECTED_OUTPUT_DEPENDENCY_FAILED)
    by_id = {record.get("call_id"): record for record in records}
    hashes: dict[str, str] = {}
    raw_root = _artifact_path(root, "artifacts/calibration/12.16-g2/raw")
    for source_id in source_ids:
        record = by_id.get(source_id)
        if (
            record is None
            or record.get("status") != "COMPLETED"
            or record.get("provider") != "openai"
        ):
            _fail(RecoveryErrorCode.SELECTED_OUTPUT_DEPENDENCY_FAILED)
        relative = record.get("raw_output_path")
        expected = record.get("raw_output_sha256")
        if type(relative) is not str or type(expected) is not str:
            _fail(RecoveryErrorCode.SELECTED_OUTPUT_DEPENDENCY_FAILED)
        path = _artifact_path(root, relative)
        if raw_root not in path.parents:
            _fail(RecoveryErrorCode.SELECTED_OUTPUT_DEPENDENCY_FAILED)
        try:
            raw = path.read_bytes()
            payload = json.loads(raw.decode("utf-8"))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError):
            _fail(RecoveryErrorCode.SELECTED_OUTPUT_DEPENDENCY_FAILED)
        if (
            _sha256(raw) != expected
            or type(payload) is not dict
            or payload.get("outcome") != "OUTPUT"
            or type(payload.get("sections")) is not list
            or not payload["sections"]
        ):
            _fail(RecoveryErrorCode.SELECTED_OUTPUT_DEPENDENCY_FAILED)
        for section in cast(list[object], payload["sections"]):
            if (
                type(section) is not dict
                or type(section.get("code")) is not str
                or type(section.get("text")) is not str
            ):
                _fail(RecoveryErrorCode.SELECTED_OUTPUT_DEPENDENCY_FAILED)
        hashes[source_id] = expected
    if len(selected) != 12 or len(source_ids) != 6 or len(hashes) != 6:
        _fail(RecoveryErrorCode.SELECTED_OUTPUT_DEPENDENCY_FAILED)
    return dict(sorted(hashes.items()))


def _call_payload(call: RecoveryCallSpec) -> dict[str, object]:
    payload = asdict(call)
    payload["category"] = call.category.value
    payload["criterion_refs"] = list(call.criterion_refs)
    payload["input_refs"] = list(call.input_refs)
    return payload


def estimate_recovery_cost(calls: Sequence[RecoveryCallSpec]) -> dict[str, object]:
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
    requested = _money(maximum * COST_MARGIN)
    if (
        len(per_call) != 38
        or any(value != Decimal("0.036480") for value in per_call)
        or maximum != EXPECTED_MAXIMUM_BEFORE_MARGIN_USD
        or requested != EXPECTED_REQUESTED_CEILING_USD
    ):
        _fail(RecoveryErrorCode.COST_INVALID)
    return {
        "call_count": len(calls),
        "input_max_per_call": INPUT_UTF8_UPPER_BOUND_BYTES,
        "output_max_per_call": MAX_OUTPUT_TOKENS,
        "per_call_maximum_usd": "0.036480",
        "maximum_before_margin_usd": str(maximum),
        "margin_multiplier": str(COST_MARGIN),
        "margin_amount_usd": str(_money(requested - maximum)),
        "requested_ceiling_usd": str(requested),
        "pricing": {
            "input_usd_per_mtok": str(INPUT_USD_PER_MTOK),
            "cache_hit_usd_per_mtok": str(CACHE_HIT_USD_PER_MTOK),
            "output_usd_per_mtok": str(OUTPUT_USD_PER_MTOK),
            "verified_on": "2026-08-30",
            "official_sources": list(OFFICIAL_SOURCES),
        },
    }


def recovery_matrix_payload(root: Path = ROOT) -> dict[str, object]:
    calls = build_recovery_matrix(root)
    return {
        "plan_version": RECOVERY_PLAN_VERSION,
        "calls": [_call_payload(call) for call in calls],
        "reusable_manifest_sha256": reusable_manifest_sha256(root),
        "prerequisite_proofs": {
            "r2_ledger_sha256": R2_LEDGER_SHA256,
            "r2_summary_sha256": R2_SUMMARY_SHA256,
            "r2_raw_sha256": R2_RAW_SHA256,
            "r3_ledger_sha256": R3_LEDGER_SHA256,
            "r3_summary_sha256": R3_SUMMARY_SHA256,
            "r3_transfer_manifest_sha256": R3_TRANSFER_MANIFEST_SHA256,
            "r3_raw_ordered_list_sha256": R3_RAW_ORDERED_LIST_SHA256,
        },
        "selected_output_dependencies": audit_selected_output_dependencies(root),
        "cost": estimate_recovery_cost(calls),
        "policy": {
            "provider": "anthropic",
            "model": MODEL,
            "thinking_mode": THINKING_MODE.value,
            "effort": EFFORT.value,
            "max_output_tokens": MAX_OUTPUT_TOKENS,
            "automatic_retry_count": 0,
            "automatic_rerun_count": 0,
            "canary_first": True,
            "stop_on_first_technical_failure": True,
        },
        "canary_semantics": {
            "call_number": 1,
            "execution_call_id": REMEDIATION_EXECUTION_CALL_ID,
            "logical_slot_id": FAILED_LOGICAL_SLOT_ID,
            "pass": "SCORED_OR_INCONCLUSIVE_STRUCTURED_POST_VALIDATED",
            "fail": "PAUSE_AND_BLOCK_CALLS_2_TO_38_BEFORE_PROVIDER",
        },
    }


def recovery_matrix_sha256(root: Path = ROOT) -> str:
    return _canonical_sha256(recovery_matrix_payload(root))


def financial_approval_text(matrix_sha256: str) -> str:
    return "\n".join(
        (
            "J'approuve exclusivement l'exécution conditionnelle de la matrice",
            f"{RECOVERY_PLAN_VERSION},",
            f"checksum {matrix_sha256},",
            (
                "38 appels maximum (38 Anthropic Scorer claude-sonnet-5, "
                "thinking adaptive, effort low, max_output_tokens 2048),"
            ),
            "plafond 1.732800 USD,",
            ("aucun retry, canary en premier et arrêt immédiat au premier échec technique."),
        )
    )


def transfer_approval_text(matrix_sha256: str) -> str:
    return "\n".join(
        (
            "J'autorise explicitement l'envoi à l'API Anthropic, exclusivement pour",
            f"la matrice conditionnelle {RECOVERY_PLAN_VERSION},",
            f"checksum {matrix_sha256},",
            (
                "des anchors synthétiques strictement nécessaires et des projections "
                "pédagogiques minimisées des six outputs historiques."
            ),
            ("Aucune base SQLite, aucun document source complet et aucun secret supplémentaire."),
        )
    )


def build_recovery_ledger(root: Path = ROOT) -> dict[str, object]:
    calls = build_recovery_matrix(root)
    matrix_hash = recovery_matrix_sha256(root)
    manifest_hash = reusable_manifest_sha256(root)
    return {
        "plan_version": RECOVERY_PLAN_VERSION,
        "matrix_sha256": matrix_hash,
        "approved_ceiling_usd": None,
        "requested_ceiling_usd": "1.732800",
        "financial_approval_required": True,
        "external_transfer_approval_required": True,
        "reusable_results_manifest": {
            "version": REUSABLE_MANIFEST_VERSION,
            "sha256": manifest_hash,
            "result_count": 38,
            "imported_as_provider_calls": False,
        },
        "provider_health_gate": {
            "required_before_credential_and_canary": True,
            "official_public_status_check_required": True,
            "model_api_pricing_revalidation_required": True,
            "active_api_incident_must_be_absent": True,
            "r1_check_performed": False,
        },
        "canary_gate": {
            "execution_call_id": REMEDIATION_EXECUTION_CALL_ID,
            "must_run_first": True,
            "on_technical_failure": "BLOCK_CALLS_2_TO_38_AND_STOP",
            "on_structured_terminal": "ALLOW_CALL_2",
        },
        "allowed_states": [status.value for status in RecoveryLedgerStatus],
        "provider_calls_attempted": 0,
        "automatic_retry_count": 0,
        "automatic_rerun_count": 0,
        "total_cost_usd": "0.000000",
        "run_status": "AWAITING_EXPLICIT_APPROVAL",
        "calls": [
            {
                **_call_payload(call),
                "status": RecoveryLedgerStatus.PENDING.value,
                "started_at": None,
                "completed_at": None,
                "closed_error_code": None,
                "cost_usd": "0.000000",
                "raw_output_path": None,
                "raw_output_sha256": None,
            }
            for call in calls
        ],
    }


def validate_recovery_ledger(
    ledger: Mapping[str, object],
    root: Path = ROOT,
) -> None:
    calls = build_recovery_matrix(root)
    if (
        ledger.get("plan_version") != RECOVERY_PLAN_VERSION
        or ledger.get("matrix_sha256") != recovery_matrix_sha256(root)
        or ledger.get("automatic_retry_count") != 0
        or ledger.get("automatic_rerun_count") != 0
        or ledger.get("allowed_states") != [status.value for status in RecoveryLedgerStatus]
    ):
        _fail(RecoveryErrorCode.LEDGER_INVALID)
    records = _records(ledger, RecoveryErrorCode.LEDGER_INVALID)
    if len(records) != len(calls):
        _fail(RecoveryErrorCode.LEDGER_INVALID)
    execution_ids: list[str] = []
    for record, call in zip(records, calls, strict=True):
        expected = _call_payload(call)
        if any(record.get(key) != value for key, value in expected.items()):
            _fail(RecoveryErrorCode.LEDGER_INVALID)
        status = record.get("status")
        execution_id = record.get("execution_call_id")
        if (
            status not in {item.value for item in RecoveryLedgerStatus}
            or type(execution_id) is not str
        ):
            _fail(RecoveryErrorCode.LEDGER_INVALID)
        execution_ids.append(execution_id)
    if len(execution_ids) != len(set(execution_ids)):
        _fail(RecoveryErrorCode.LEDGER_INVALID)


def next_executable_call_id(
    ledger: Mapping[str, object],
    root: Path = ROOT,
) -> str | None:
    validate_recovery_ledger(ledger, root)
    records = _records(ledger, RecoveryErrorCode.LEDGER_INVALID)
    if any(record.get("status") == RecoveryLedgerStatus.STARTED.value for record in records):
        _fail(RecoveryErrorCode.LEDGER_INVALID)
    if ledger.get("run_status") in {
        "PAUSED_CANARY_FAILURE",
        "PAUSED_SYSTEMIC_FAILURE",
    }:
        return None
    terminal = {
        RecoveryLedgerStatus.COMPLETED.value,
        RecoveryLedgerStatus.SKIPPED_DEPENDENCY_FAILED.value,
    }
    for index, record in enumerate(records):
        status = record.get("status")
        if status == RecoveryLedgerStatus.PENDING.value:
            if any(prior.get("status") not in terminal for prior in records[:index]):
                _fail(RecoveryErrorCode.LEDGER_INVALID)
            return cast(str, record["execution_call_id"])
        if status in {
            RecoveryLedgerStatus.FAILED.value,
            RecoveryLedgerStatus.BLOCKED_BY_CANARY.value,
        }:
            return None
    return None


def pause_after_technical_failure(
    ledger: Mapping[str, object],
    failed_execution_call_id: str,
    root: Path = ROOT,
) -> dict[str, object]:
    validate_recovery_ledger(ledger, root)
    updated = cast(dict[str, object], deepcopy(dict(ledger)))
    records = _records(updated, RecoveryErrorCode.LEDGER_INVALID)
    matches = [
        (index, record)
        for index, record in enumerate(records)
        if record.get("execution_call_id") == failed_execution_call_id
    ]
    if len(matches) != 1:
        _fail(RecoveryErrorCode.LEDGER_INVALID)
    index, failed = matches[0]
    if failed.get("status") != RecoveryLedgerStatus.STARTED.value:
        _fail(RecoveryErrorCode.LEDGER_INVALID)
    failed["status"] = RecoveryLedgerStatus.FAILED.value
    failed["closed_error_code"] = "TECHNICAL_FAILURE"
    if index == 0:
        for record in records[1:]:
            if record.get("status") == RecoveryLedgerStatus.PENDING.value:
                record["status"] = RecoveryLedgerStatus.BLOCKED_BY_CANARY.value
        updated["run_status"] = "PAUSED_CANARY_FAILURE"
    else:
        updated["run_status"] = "PAUSED_SYSTEMIC_FAILURE"
    validate_recovery_ledger(updated, root)
    return updated


def _validate_frozen_checksums(root: Path) -> None:
    if REUSABLE_MANIFEST_SHA256 and reusable_manifest_sha256(root) != REUSABLE_MANIFEST_SHA256:
        _fail(RecoveryErrorCode.REUSABLE_RESULT_INVALID)
    if RECOVERY_MATRIX_SHA256 and recovery_matrix_sha256(root) != RECOVERY_MATRIX_SHA256:
        _fail(RecoveryErrorCode.RECOVERY_MATRIX_INVALID)


def r1_payload(root: Path = ROOT) -> dict[str, object]:
    _validate_frozen_checksums(root)
    evidence = audit_evidence(root)
    calls = build_recovery_matrix(root)
    split = Counter(call.category.value for call in calls)
    transfer_counts = {
        "ANCHOR_SYNTHETIC": sum(
            call.category is not RecoveryCategory.SELECTED_OUTPUT for call in calls
        ),
        "AUTHORIZED_OUTPUT_PROJECTION": sum(
            call.category is RecoveryCategory.SELECTED_OUTPUT for call in calls
        ),
    }
    ledger = build_recovery_ledger(root)
    r3 = cast(dict[str, object], evidence["r3"])
    return {
        "phase": "12.16-G2-R3B-R4-R3-R1",
        "status": "PASS_CLOSED",
        "refs": {
            "branch": ENTRY_BRANCH,
            "entry_head": ENTRY_HEAD,
            "entry_upstream": ENTRY_HEAD,
            "entry_main": ENTRY_MAIN,
            "entry_origin_main": ENTRY_MAIN,
        },
        "proofs": {
            "r2_ledger_sha256": R2_LEDGER_SHA256,
            "r2_summary_sha256": R2_SUMMARY_SHA256,
            "r2_raw_sha256": R2_RAW_SHA256,
            "r3_ledger_sha256": R3_LEDGER_SHA256,
            "r3_summary_sha256": R3_SUMMARY_SHA256,
            "r3_transfer_manifest_sha256": R3_TRANSFER_MANIFEST_SHA256,
            "r3_raw_ordered_list_sha256": cast(str, r3["raw_ordered_list_sha256"]),
        },
        "http503_classification": {
            "classification": "HTTP_503_SERVER_ERROR",
            "failed_execution_call_id": FAILED_EXECUTION_CALL_ID,
            "failed_logical_slot_id": FAILED_LOGICAL_SLOT_ID,
            "historical_record_preserved": True,
            "historical_record_reset": False,
        },
        "reusable_results": {
            "count": 38,
            "r2_count": 1,
            "r3_count": 37,
            "manifest_version": REUSABLE_MANIFEST_VERSION,
            "manifest_sha256": reusable_manifest_sha256(root),
            "raw_content_recorded": False,
        },
        "slot_subtraction": {
            "original_count": 76,
            "reused_count": 38,
            "remaining_count": 38,
            "intersection_count": 0,
            "union_count": 76,
        },
        "continuation": {
            "plan_version": RECOVERY_PLAN_VERSION,
            "matrix_sha256": recovery_matrix_sha256(root),
            "call_count": len(calls),
            "canary_execution_call_id": REMEDIATION_EXECUTION_CALL_ID,
            "continuation_after_canary_count": 37,
            "split": dict(sorted(split.items())),
            "transfer_counts": transfer_counts,
            "selected_output_dependencies": audit_selected_output_dependencies(root),
            "calls": [_call_payload(call) for call in calls],
            "cost": estimate_recovery_cost(calls),
        },
        "ledger": {
            "relative_path": RECOVERY_LEDGER_RELATIVE_PATH,
            "sha256": _sha256(_pretty_json(ledger).encode("utf-8")),
            "states": [status.value for status in RecoveryLedgerStatus],
            "call_count": 38,
            "provider_calls_attempted": 0,
        },
        "provider_health_gate": ledger["provider_health_gate"],
        "approvals": {
            "financial": financial_approval_text(recovery_matrix_sha256(root)),
            "transfer": transfer_approval_text(recovery_matrix_sha256(root)),
            "recognized": False,
        },
        "offline_execution": {
            "openai_calls": 0,
            "anthropic_calls": 0,
            "provider_cost_usd": "0.000000",
            "credentials_resolved": False,
            "provider_transport_constructed": False,
            "prior_ledgers_mutated": False,
        },
        "adr": {"required": False, "applies": ["ADR-P12-063", "ADR-P12-064"]},
        "commit": {
            "message": "test: prepare Anthropic calibration continuation",
            "expected_parent": ENTRY_HEAD,
        },
    }


def render_baseline_markdown(root: Path = ROOT) -> str:
    payload = r1_payload(root)
    proofs = cast(dict[str, object], payload["proofs"])
    reusable = cast(dict[str, object], payload["reusable_results"])
    subtraction = cast(dict[str, object], payload["slot_subtraction"])
    continuation = cast(dict[str, object], payload["continuation"])
    cost = cast(dict[str, object], continuation["cost"])
    return "\n".join(
        (
            "# Phase 12.16-G2-R3B-R4-R3-R1 — Baseline de reprise HTTP 503",
            "",
            "## Résultat offline",
            "",
            "- Statut : `PASS_CLOSED`.",
            "- Classification : `HTTP_503_SERVER_ERROR`.",
            "- Appels provider R1 : `0` ; coût provider R1 : `0.000000 USD`.",
            "- Le record R3 échoué et tous les artefacts R2/R3 restent inchangés.",
            "",
            "## Preuves gelées",
            "",
            f"- R2 ledger : `{proofs['r2_ledger_sha256']}`.",
            f"- R2 summary : `{proofs['r2_summary_sha256']}`.",
            f"- R2 raw : `{proofs['r2_raw_sha256']}`.",
            f"- R3 ledger : `{proofs['r3_ledger_sha256']}`.",
            f"- R3 summary : `{proofs['r3_summary_sha256']}`.",
            f"- R3 transfer manifest : `{proofs['r3_transfer_manifest_sha256']}`.",
            f"- R3 raw ordered-list : `{proofs['r3_raw_ordered_list_sha256']}`.",
            "",
            "## Consolidation et soustraction",
            "",
            f"- Résultats homogènes réutilisables : `{reusable['count']}` (`1 R2 + 37 R3`).",
            f"- Manifest réutilisable : `{reusable['manifest_sha256']}`.",
            (
                f"- Slots : `{subtraction['original_count']} - {subtraction['reused_count']} "
                f"= {subtraction['remaining_count']}` ; union `{subtraction['union_count']}`."
            ),
            "- Split restant : `10 initial / 16 repeatability / 12 selected-output`.",
            "- Transfert futur : `26 ANCHOR_SYNTHETIC / 12 AUTHORIZED_OUTPUT_PROJECTION`.",
            "- Dépendances selected-output : `6/6` vérifiées par hash.",
            "",
            "## Plan rationalisé",
            "",
            f"- Version : `{continuation['plan_version']}`.",
            f"- Checksum : `{continuation['matrix_sha256']}`.",
            f"- Calls : `{continuation['call_count']}` ; canary puis `37` continuations.",
            f"- Canary : `{continuation['canary_execution_call_id']}`.",
            "- Policy : `claude-sonnet-5 / adaptive / low / 2048 / retry 0`.",
            "- Un échec technique du canary bloque les calls 2–38 avant provider.",
            "- Tout échec technique ultérieur suspend avant l'appel suivant.",
            f"- Maximum sans marge : `{cost['maximum_before_margin_usd']} USD`.",
            f"- Plafond demandé : `{cost['requested_ceiling_usd']} USD`.",
            "",
            "## Gouvernance",
            "",
            "- Le futur runner doit vérifier le statut public Anthropic avant credential/canary.",
            "- Les nouvelles autorisations liées au checksum sont obligatoires.",
            "- ADR supplémentaire : `NO`; ADR-P12-063 et ADR-P12-064 s'appliquent.",
            "- Revue humaine finale toujours requise.",
        )
    )


def render_plan_markdown(root: Path = ROOT) -> str:
    payload = r1_payload(root)
    continuation = cast(dict[str, object], payload["continuation"])
    ledger = cast(dict[str, object], payload["ledger"])
    approvals = cast(dict[str, object], payload["approvals"])
    cost = cast(dict[str, object], continuation["cost"])
    calls = cast(list[dict[str, object]], continuation["calls"])
    lines = [
        "# Phase 12.16-G2-R3B-R4-R3-R1 — Plan de continuation",
        "",
        "## Matrice gelée",
        "",
        f"- Version : `{continuation['plan_version']}`.",
        f"- Checksum : `{continuation['matrix_sha256']}`.",
        "- Cardinalité : `38` appels Anthropic, retry/rerun `0`.",
        "- Call 1 : canary de remédiation du HTTP 503 historique.",
        "- Calls 2–38 : anciens slots R3 `PENDING`, avec nouveaux execution IDs.",
        f"- Ledger : `{ledger['relative_path']}` ; hash initial `{ledger['sha256']}`.",
        "",
        "## Coût",
        "",
        f"- Maximum par call : `{cost['per_call_maximum_usd']} USD`.",
        f"- Maximum avant marge : `{cost['maximum_before_margin_usd']} USD`.",
        f"- Marge : `{cost['margin_amount_usd']} USD`.",
        f"- Plafond demandé : `{cost['requested_ceiling_usd']} USD`.",
        "",
        "## Calls",
        "",
    ]
    for index, call in enumerate(calls, start=1):
        lines.append(
            f"{index}. `{call['execution_call_id']}` → `{call['original_logical_slot_id']}` "
            f"(`{call['category']}`)."
        )
    lines.extend(
        (
            "",
            "## Approbation financière exacte requise",
            "",
            "```text",
            cast(str, approvals["financial"]),
            "```",
            "",
            "## Autorisation de transfert exacte requise",
            "",
            "```text",
            cast(str, approvals["transfer"]),
            "```",
            "",
            "Aucun de ces appels n'a été exécuté pendant R1.",
        )
    )
    return "\n".join(lines)


def render_plan_json(root: Path = ROOT) -> str:
    return _pretty_json(r1_payload(root))


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


def write_r1_outputs(root: Path = ROOT) -> None:
    _validate_frozen_checksums(root)
    outputs = {
        BASELINE_RELATIVE_PATH: render_baseline_markdown(root) + "\n",
        PLAN_MARKDOWN_RELATIVE_PATH: render_plan_markdown(root) + "\n",
        PLAN_JSON_RELATIVE_PATH: render_plan_json(root),
        REUSABLE_MANIFEST_RELATIVE_PATH: _pretty_json(build_reusable_manifest(root)),
    }
    recovery_path = root / RECOVERY_LEDGER_RELATIVE_PATH
    preserve_terminal_ledger = False
    if recovery_path.is_file():
        try:
            current = json.loads(recovery_path.read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError):
            current = None
        preserve_terminal_ledger = type(current) is dict and current.get("run_status") != (
            "AWAITING_EXPLICIT_APPROVAL"
        )
    if not preserve_terminal_ledger:
        outputs[RECOVERY_LEDGER_RELATIVE_PATH] = _pretty_json(build_recovery_ledger(root))
    for relative_path, content in outputs.items():
        _atomic_write(root / relative_path, content.encode("utf-8"))


def main() -> None:
    write_r1_outputs(ROOT)
    print(
        json.dumps(
            {
                "status": "PASS_CLOSED",
                "reusable_manifest_sha256": reusable_manifest_sha256(ROOT),
                "recovery_matrix_sha256": recovery_matrix_sha256(ROOT),
                "recovery_ledger_sha256": _sha256(
                    (ROOT / RECOVERY_LEDGER_RELATIVE_PATH).read_bytes()
                ),
                "live_provider_calls_r1": 0,
                "live_provider_cost_r1": "0.000000",
            },
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
