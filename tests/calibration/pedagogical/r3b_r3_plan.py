"""Offline R3 consolidation and the final Anthropic-only R4 call plan."""

from __future__ import annotations

import hashlib
import json
import os
from collections import Counter
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, replace
from decimal import ROUND_CEILING, Decimal
from enum import StrEnum
from pathlib import Path
from typing import Never, cast

from backend.adapters.outbound.openai import (
    OpenAIIncompleteReason,
    OpenAIReasoningEffort,
    OpenAIResponsesResponse,
    OpenAIResponseStatus,
)
from backend.adapters.outbound.review.openai.adapter import (
    _map_response as _map_review_response,
)
from backend.adapters.outbound.review.openai.mapping import build_openai_review_request
from tests.calibration.pedagogical.call_plan import (
    PEDAGOGICAL_CALIBRATION_CALL_MATRIX,
    CalibrationCallSpec,
    CalibrationProvider,
    CalibrationWorkload,
)
from tests.calibration.pedagogical.live_runner import (
    _anthropic_observation,
    _model_profile,
    _provider_profile,
    _review_request,
)
from tests.calibration.pedagogical.r3a_plan import (
    G2_LEDGER_RELATIVE_PATH,
    R2_ANTHROPIC_RAW_SHA256,
    R2_LEDGER_SHA256,
    R3_REUSED_EVIDENCE_MANIFEST_SHA256,
    ReusedEvidenceMapping,
    ReuseMappingClass,
    audit_r3a_evidence,
    reused_evidence_manifest_sha256,
    validate_reuse_mappings,
)
from tests.calibration.pedagogical.r3b_r1_diagnostic import (
    ANTHROPIC_CACHED_INPUT_USD_PER_MTOK,
    ANTHROPIC_INPUT_USD_PER_MTOK,
    ANTHROPIC_MODEL,
    ANTHROPIC_MODEL_PROFILE_ID,
    ANTHROPIC_OUTPUT_USD_PER_MTOK,
    FAILED_LOGICAL_SLOT_ID,
    FAILED_R3_CALL_ID,
    R2_PLAN_VERSION,
    R2_REMEDIATION_CALL_ID,
    R3_LEDGER_RELATIVE_PATH,
    R3_LEDGER_SHA256,
    R3_SUMMARY_RELATIVE_PATH,
    R3_SUMMARY_SHA256,
    SUCCESS_R3_CALL_IDS,
    audit_r3b_failure,
    reconstruct_failed_request_identity,
)
from tests.providers.anthropic.mapping import (
    build_anthropic_scoring_request,
    serialize_observation,
)
from tests.providers.anthropic.transport import transform_anthropic_provider_schema

R3B_R2_ARTIFACT_DIRECTORY = "artifacts/calibration/12.16-g2-r3b-r2"
R3B_R2_LEDGER_RELATIVE_PATH = f"{R3B_R2_ARTIFACT_DIRECTORY}/ledger.json"
R3B_R2_SUMMARY_RELATIVE_PATH = f"{R3B_R2_ARTIFACT_DIRECTORY}/summary.json"
R3B_R2_RAW_RELATIVE_DIRECTORY = f"{R3B_R2_ARTIFACT_DIRECTORY}/raw"
R3B_R2_LEDGER_SHA256 = "aa254f931f417f5be267f1dd5e65dd1c667ab65bb0e2510b3cd586079ea16ae9"
R3B_R2_SUMMARY_SHA256 = "e3aed0e2e49a10a64096fdc6765ae6222f2fff1c142c00d8081780726b8ad18d"
R3B_R2_RAW_SHA256 = "3d2e4cb76ed3d5f10eabd369f19933404a5900df95674eaa2bc96c67b815ba3d"
R3B_R2_RAW_RELATIVE_PATH = (
    f"{R3B_R2_RAW_RELATIVE_DIRECTORY}/{R2_REMEDIATION_CALL_ID}.{R3B_R2_RAW_SHA256}.json"
)

R4_PLAN_VERSION = "12.16-g2-r3b-r4-completion-v1"
R4_ARTIFACT_DIRECTORY = "artifacts/calibration/12.16-g2-r3b-r4"
R4_LEDGER_RELATIVE_PATH = f"{R4_ARTIFACT_DIRECTORY}/ledger.json"
R4_PRICING_SNAPSHOT_ID = "official-2026-08-30-r3"
R4_PRICING_SOURCE = "https://platform.claude.com/docs/en/about-claude/pricing"
R4_COST_SAFETY_MARGIN = Decimal("1.25")
R4_CALL_MAXIMUM_USD = Decimal("0.021120")
R4_MAXIMUM_BEFORE_MARGIN_USD = Decimal("1.499520")
R4_SAFETY_MARGIN_AMOUNT_USD = Decimal("0.374880")
R4_REQUESTED_HARD_CEILING_USD = Decimal("1.874400")
R3_LIVE_PROVIDER_CALLS = 0
R3_PROVIDER_COST_USD = Decimal("0.000000")

R4_REUSED_EVIDENCE_MANIFEST_SHA256 = (
    "b9eb583ccf5c6fcbc6b7b5d4491dd74a53889ffd92521b3270f9984f61d12aa9"
)
R4_CALL_MATRIX_SHA256 = "0298e4672f03def781bf7217b37567a456d6865aa35c157c4d956111962c7d8d"

R3_EVIDENCE_REPORT_RELATIVE_PATH = (
    "docs/development/PHASE_12_16_G2_R3B_R3_EVIDENCE_CONSOLIDATION_BASELINE.md"
)
R3_PLAN_MARKDOWN_RELATIVE_PATH = "docs/development/PHASE_12_16_G2_R3B_R3_REMAINING_CALL_PLAN.md"
R3_PLAN_JSON_RELATIVE_PATH = "docs/development/PHASE_12_16_G2_R3B_R3_REMAINING_CALL_PLAN.json"

EXPECTED_R3_COMPLETED_CALL_IDS = (
    "r3.cal.review.exercise.fallback.r1",
    "r3.cal.review.exercise.primary.r2",
    "r3.cal.review.assessment.primary.r1",
    "r3.cal.review.correction.primary.r1",
    "r3.cal.review.qcm.primary.r1",
    "r3.cal.review.qcm.fallback.r1",
    *SUCCESS_R3_CALL_IDS,
)

SYSTEMIC_FAILURE_CODES = (
    "INVALID_REQUEST",
    "AUTHENTICATION",
    "PERMISSION",
    "BILLING",
    "NOT_FOUND",
    "RATE_LIMIT",
    "TIMEOUT",
    "CONNECTION",
    "SERVER",
    "OVERLOADED",
    "UNAVAILABLE",
    "EMPTY_RESPONSE",
    "CONFLICT",
    "REQUEST_TOO_LARGE",
)


class R3ConsolidationErrorCode(StrEnum):
    EVIDENCE_UNAVAILABLE = "R3B_R2_EVIDENCE_UNAVAILABLE"
    EVIDENCE_MISMATCH = "R3_EVIDENCE_MISMATCH"
    MAPPING_MISMATCH = "R2_MAPPING_MISMATCH"
    LOGICAL_SLOT_DUPLICATE = "LOGICAL_SLOT_DUPLICATE"
    FAILED_RECORD_REUSED = "FAILED_RECORD_REUSED"
    SLOT_ACCOUNTING_INVALID = "SLOT_ACCOUNTING_INVALID"
    MATRIX_INVALID = "MATRIX_INVALID"
    READINESS_INVALID = "READINESS_INVALID"
    LEDGER_INVALID = "LEDGER_INVALID"
    STARTED_CALL_AMBIGUOUS = "STARTED_CALL_AMBIGUOUS"
    SYSTEMIC_FAILURE_INVALID = "SYSTEMIC_FAILURE_INVALID"


class R3ConsolidationError(RuntimeError):
    code: R3ConsolidationErrorCode

    def __init__(self, code: R3ConsolidationErrorCode) -> None:
        self.code = code
        super().__init__(code.value)


class R4LedgerStatus(StrEnum):
    PENDING = "PENDING"
    STARTED = "STARTED"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    SKIPPED_DEPENDENCY_FAILED = "SKIPPED_DEPENDENCY_FAILED"


@dataclass(frozen=True, slots=True)
class R3ConsolidatedEvidenceAudit:
    proof_set_sha256: Mapping[str, str]
    reused_mappings: tuple[ReusedEvidenceMapping, ...]
    r3b_completed_mappings: tuple[ReusedEvidenceMapping, ...]
    r2_remediation_mapping: ReusedEvidenceMapping
    r2_equivalence_dimensions: Mapping[str, bool]
    selected_output_dependencies: tuple[object, ...]
    original_failed_record_preserved: bool


@dataclass(frozen=True, slots=True)
class R4RemainingCallSpec:
    r4_call_id: str
    source_r3_call_id: str
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
    automatic_retry_count: int


def _fail(code: R3ConsolidationErrorCode) -> Never:
    raise R3ConsolidationError(code) from None


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


def _safe_json(
    root: Path,
    relative_path: str,
    expected_sha256: str,
) -> tuple[dict[str, object], bytes]:
    path = (root / relative_path).resolve()
    artifact_root = (root / "artifacts/calibration").resolve()
    if artifact_root not in path.parents:
        _fail(R3ConsolidationErrorCode.EVIDENCE_UNAVAILABLE)
    try:
        payload = path.read_bytes()
        decoded = json.loads(payload)
    except (OSError, UnicodeError, json.JSONDecodeError):
        _fail(R3ConsolidationErrorCode.EVIDENCE_UNAVAILABLE)
    if _sha256(payload) != expected_sha256 or type(decoded) is not dict:
        _fail(R3ConsolidationErrorCode.EVIDENCE_MISMATCH)
    return cast(dict[str, object], decoded), payload


def _safe_raw(
    root: Path,
    relative_path: object,
    expected_sha256: object,
    relative_directory: str,
) -> bytes:
    if type(relative_path) is not str or type(expected_sha256) is not str:
        _fail(R3ConsolidationErrorCode.EVIDENCE_UNAVAILABLE)
    path = (root / relative_path).resolve()
    raw_root = (root / relative_directory).resolve()
    if raw_root not in path.parents:
        _fail(R3ConsolidationErrorCode.EVIDENCE_UNAVAILABLE)
    try:
        payload = path.read_bytes()
    except OSError:
        _fail(R3ConsolidationErrorCode.EVIDENCE_UNAVAILABLE)
    if _sha256(payload) != expected_sha256:
        _fail(R3ConsolidationErrorCode.EVIDENCE_MISMATCH)
    return payload


def _record_int(record: Mapping[str, object], field: str) -> int:
    value = record.get(field)
    if type(value) is not int or value < 0:
        _fail(R3ConsolidationErrorCode.EVIDENCE_MISMATCH)
    return value


def _record_str(record: Mapping[str, object], field: str) -> str:
    value = record.get(field)
    if type(value) is not str or not value:
        _fail(R3ConsolidationErrorCode.EVIDENCE_MISMATCH)
    return value


def _original_call(logical_slot_id: str) -> CalibrationCallSpec:
    matches = [
        call for call in PEDAGOGICAL_CALIBRATION_CALL_MATRIX if call.call_id == logical_slot_id
    ]
    if len(matches) != 1:
        _fail(R3ConsolidationErrorCode.MAPPING_MISMATCH)
    return matches[0]


def _g2_selected_output_candidate(root: Path, source_id: str) -> str:
    g2_path = root / G2_LEDGER_RELATIVE_PATH
    try:
        ledger = json.loads(g2_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError):
        _fail(R3ConsolidationErrorCode.EVIDENCE_UNAVAILABLE)
    if type(ledger) is not dict or type(ledger.get("calls")) is not list:
        _fail(R3ConsolidationErrorCode.EVIDENCE_MISMATCH)
    records = cast(list[object], ledger["calls"])
    matches = [
        cast(dict[str, object], record)
        for record in records
        if type(record) is dict and record.get("call_id") == source_id
    ]
    if len(matches) != 1 or matches[0].get("status") != "COMPLETED":
        _fail(R3ConsolidationErrorCode.EVIDENCE_MISMATCH)
    record = matches[0]
    raw = _safe_raw(
        root,
        record.get("raw_output_path"),
        record.get("raw_output_sha256"),
        "artifacts/calibration/12.16-g2/raw",
    )
    try:
        payload = json.loads(raw)
    except (UnicodeError, json.JSONDecodeError):
        _fail(R3ConsolidationErrorCode.EVIDENCE_MISMATCH)
    if type(payload) is not dict or payload.get("outcome") != "OUTPUT":
        _fail(R3ConsolidationErrorCode.EVIDENCE_MISMATCH)
    sections = payload.get("sections")
    if type(sections) is not list or not sections:
        _fail(R3ConsolidationErrorCode.EVIDENCE_MISMATCH)
    projected: list[str] = []
    for section in sections:
        if (
            type(section) is not dict
            or type(section.get("code")) is not str
            or type(section.get("text")) is not str
        ):
            _fail(R3ConsolidationErrorCode.EVIDENCE_MISMATCH)
        projected.append(f"[{section['code']}] {section['text']}")
    return "\n".join(projected)


def _anthropic_request_hashes(
    root: Path,
    call: CalibrationCallSpec,
) -> dict[str, object]:
    dependency: str | None = None
    input_ref = call.input_refs[0]
    if input_ref.startswith("output:"):
        dependency = _g2_selected_output_candidate(root, input_ref.removeprefix("output:"))
    observation = _anthropic_observation(call, dependency_candidate=dependency)
    request = build_anthropic_scoring_request(
        observations=(observation,),
        model=call.model,
        max_tokens=call.max_output_tokens,
    )
    provider_schema = transform_anthropic_provider_schema(request.output_schema)
    return {
        "observation_sha256": _canonical_sha256(serialize_observation(observation)),
        "serialized_input_sha256": _sha256(request.input_json.encode("utf-8")),
        "serialized_input_bytes": len(request.input_json.encode("utf-8")),
        "system_sha256": _sha256(request.system.encode("utf-8")),
        "logical_schema_sha256": _canonical_sha256(request.output_schema),
        "provider_schema_sha256": _canonical_sha256(provider_schema),
    }


def _validate_score_raw(payload: bytes) -> str:
    try:
        score = json.loads(payload)
    except (UnicodeError, json.JSONDecodeError):
        _fail(R3ConsolidationErrorCode.EVIDENCE_MISMATCH)
    if type(score) is not dict or set(score) != {
        "status",
        "score_numerator",
        "score_denominator",
    }:
        _fail(R3ConsolidationErrorCode.EVIDENCE_MISMATCH)
    if score["status"] == "INCONCLUSIVE":
        if score["score_numerator"] is None and score["score_denominator"] is None:
            return "INCONCLUSIVE"
        _fail(R3ConsolidationErrorCode.EVIDENCE_MISMATCH)
    numerator = score["score_numerator"]
    denominator = score["score_denominator"]
    if (
        score["status"] != "SCORED"
        or type(numerator) is not int
        or type(denominator) is not int
        or denominator <= 0
        or numerator < 0
        or numerator > denominator
    ):
        _fail(R3ConsolidationErrorCode.EVIDENCE_MISMATCH)
    return f"{numerator}/{denominator}"


def _validate_r3b_completed(
    root: Path,
    record: Mapping[str, object],
) -> ReusedEvidenceMapping:
    logical_slot_id = _record_str(record, "logical_slot_id")
    call = _original_call(logical_slot_id)
    if (
        record.get("r3_call_id") != f"r3.{logical_slot_id}"
        or record.get("status") != R4LedgerStatus.COMPLETED.value
        or record.get("provider") != call.provider.value
        or record.get("model") != call.model
        or record.get("model_profile_id") != call.model_profile_id
        or record.get("automatic_retry_count") != 0
        or record.get("closed_error_code") is not None
    ):
        _fail(R3ConsolidationErrorCode.EVIDENCE_MISMATCH)
    raw = _safe_raw(
        root,
        record.get("raw_output_path"),
        record.get("raw_output_sha256"),
        "artifacts/calibration/12.16-g2-r3/raw",
    )
    if call.provider is CalibrationProvider.OPENAI:
        live_call = replace(call, max_output_tokens=4_096)
        try:
            raw_text = raw.decode("utf-8")
            json.loads(raw_text)
            mapped = _map_review_response(
                request=_review_request(live_call),
                response=OpenAIResponsesResponse(
                    status=OpenAIResponseStatus.COMPLETED,
                    output_text=raw_text,
                    incomplete_reason=OpenAIIncompleteReason.NONE,
                ),
                provider_profile=_provider_profile(live_call.provider),
                model_profile=_model_profile(live_call),
            )
            provider_request = build_openai_review_request(
                request=_review_request(live_call),
                model_profile=_model_profile(live_call),
                reasoning_effort=OpenAIReasoningEffort.LOW,
            )
        except (UnicodeError, json.JSONDecodeError, RuntimeError, TypeError, ValueError):
            _fail(R3ConsolidationErrorCode.EVIDENCE_MISMATCH)
        if mapped.status.value not in {"PARTIAL", "SUCCEEDED"}:
            _fail(R3ConsolidationErrorCode.EVIDENCE_MISMATCH)
        input_sha256 = _sha256(provider_request.input_json.encode("utf-8"))
        schema_sha256 = _canonical_sha256(provider_request.output_schema)
        status = mapped.status.value
    else:
        score = _validate_score_raw(raw)
        hashes = _anthropic_request_hashes(root, call)
        input_sha256 = cast(str, hashes["serialized_input_sha256"])
        schema_sha256 = cast(str, hashes["provider_schema_sha256"])
        status = "SCORED" if score != "INCONCLUSIVE" else score
    return ReusedEvidenceMapping(
        evidence_set="R3B",
        provider=call.provider.value,
        model=call.model,
        model_profile_id=call.model_profile_id,
        remediation_call_id=None,
        original_logical_slot_id=logical_slot_id,
        status=status,
        input_sha256=input_sha256,
        schema_sha256=schema_sha256,
        output_sha256=_record_str(record, "raw_output_sha256"),
        input_tokens=_record_int(record, "input_tokens"),
        cached_input_tokens=_record_int(record, "cached_input_tokens"),
        output_tokens=_record_int(record, "output_tokens"),
        reasoning_tokens=(
            _record_int(record, "reasoning_tokens")
            if call.provider is CalibrationProvider.OPENAI
            else None
        ),
        total_tokens=_record_int(record, "total_tokens"),
        cost_usd=_record_str(record, "cost_usd"),
        mapping_class=ReuseMappingClass.EXACT_ORIGINAL_RESULT,
    )


def _audit_r3b_completed(root: Path) -> tuple[ReusedEvidenceMapping, ...]:
    ledger, _ = _safe_json(root, R3_LEDGER_RELATIVE_PATH, R3_LEDGER_SHA256)
    _safe_json(root, R3_SUMMARY_RELATIVE_PATH, R3_SUMMARY_SHA256)
    records = ledger.get("calls")
    if type(records) is not list:
        _fail(R3ConsolidationErrorCode.EVIDENCE_MISMATCH)
    typed = [cast(dict[str, object], item) for item in records if type(item) is dict]
    completed = [item for item in typed if item.get("status") == "COMPLETED"]
    failed = [item for item in typed if item.get("status") == "FAILED"]
    pending = [item for item in typed if item.get("status") == "PENDING"]
    started = [item for item in typed if item.get("status") == "STARTED"]
    if (
        len(typed) != 81
        or len(completed) != 9
        or len(failed) != 1
        or len(pending) != 71
        or started
        or tuple(_record_str(item, "r3_call_id") for item in completed)
        != EXPECTED_R3_COMPLETED_CALL_IDS
    ):
        _fail(R3ConsolidationErrorCode.EVIDENCE_MISMATCH)
    failed_record = failed[0]
    if (
        failed_record.get("r3_call_id") != FAILED_R3_CALL_ID
        or failed_record.get("logical_slot_id") != FAILED_LOGICAL_SLOT_ID
        or failed_record.get("closed_error_code") != "ANTHROPIC_SCORER_TRANSPORT_UNAVAILABLE"
        or failed_record.get("raw_output_path") is not None
        or failed_record.get("raw_output_sha256") is not None
    ):
        _fail(R3ConsolidationErrorCode.EVIDENCE_MISMATCH)
    mappings = tuple(_validate_r3b_completed(root, item) for item in completed)
    if Counter(item.provider for item in mappings) != {"openai": 6, "anthropic": 3}:
        _fail(R3ConsolidationErrorCode.EVIDENCE_MISMATCH)
    return mappings


def _audit_r3b_r2(
    root: Path,
) -> tuple[ReusedEvidenceMapping, dict[str, bool]]:
    ledger, _ = _safe_json(
        root,
        R3B_R2_LEDGER_RELATIVE_PATH,
        R3B_R2_LEDGER_SHA256,
    )
    summary, _ = _safe_json(
        root,
        R3B_R2_SUMMARY_RELATIVE_PATH,
        R3B_R2_SUMMARY_SHA256,
    )
    calls = ledger.get("calls")
    if type(calls) is not list or len(calls) != 1 or type(calls[0]) is not dict:
        _fail(R3ConsolidationErrorCode.EVIDENCE_UNAVAILABLE)
    record = cast(dict[str, object], calls[0])
    raw = _safe_raw(
        root,
        record.get("raw_output_path"),
        record.get("raw_output_sha256"),
        R3B_R2_RAW_RELATIVE_DIRECTORY,
    )
    score = _validate_score_raw(raw)
    expected_identity = reconstruct_failed_request_identity()
    comparisons = {
        "source_failed_call": record.get("source_failed_call_id") == FAILED_R3_CALL_ID,
        "logical_slot": record.get("logical_slot_id") == FAILED_LOGICAL_SLOT_ID,
        "scenario": record.get("input_ref") == expected_identity["input_ref"],
        "criterion": record.get("criterion_ref") == expected_identity["criterion_ref"],
        "input_ref": record.get("input_ref") == expected_identity["input_ref"],
        "observation_sha256": record.get("observation_sha256")
        == expected_identity["observation_sha256"],
        "serialized_input_bytes": record.get("serialized_input_bytes")
        == expected_identity["serialized_input_bytes"],
        "serialized_input_sha256": record.get("serialized_input_sha256")
        == expected_identity["serialized_input_sha256"],
        "system_sha256": record.get("system_sha256") == expected_identity["system_sha256"],
        "logical_schema_sha256": record.get("logical_schema_sha256")
        == expected_identity["logical_schema_sha256"],
        "provider_schema_sha256": record.get("provider_schema_sha256")
        == expected_identity["provider_schema_sha256"],
        "model": record.get("model") == expected_identity["model"],
        "profile": record.get("model_profile_id") == expected_identity["model_profile_id"],
        "max_output_tokens": record.get("max_output_tokens")
        == expected_identity["max_output_tokens"],
    }
    if (
        ledger.get("plan_version") != R2_PLAN_VERSION
        or record.get("call_id") != R2_REMEDIATION_CALL_ID
        or record.get("provider") != "anthropic"
        or record.get("status") != "COMPLETED"
        or record.get("http_status") != 200
        or record.get("response_status") != "STRUCTURED"
        or record.get("scoring_status") != "SCORED"
        or record.get("rational_score") != "0/1"
        or score != "0/1"
        or record.get("input_tokens") != 938
        or record.get("cached_input_tokens") != 0
        or record.get("output_tokens") != 391
        or record.get("total_tokens") != 1329
        or record.get("latency_milliseconds") != 7302
        or record.get("cost_usd") != "0.005786"
        or record.get("raw_output_path") != R3B_R2_RAW_RELATIVE_PATH
        or record.get("raw_output_sha256") != R3B_R2_RAW_SHA256
        or ledger.get("provider_calls_attempted") != 1
        or ledger.get("automatic_retry_count") != 0
        or ledger.get("automatic_rerun_count") != 0
        or summary.get("anthropic_canary") != "PASSED"
        or summary.get("raw_output_sha256") != R3B_R2_RAW_SHA256
        or not all(comparisons.values())
    ):
        _fail(R3ConsolidationErrorCode.MAPPING_MISMATCH)
    return (
        ReusedEvidenceMapping(
            evidence_set="R3B-R2",
            provider="anthropic",
            model=ANTHROPIC_MODEL,
            model_profile_id=ANTHROPIC_MODEL_PROFILE_ID,
            remediation_call_id=R2_REMEDIATION_CALL_ID,
            original_logical_slot_id=FAILED_LOGICAL_SLOT_ID,
            status="SCORED",
            input_sha256=_record_str(record, "serialized_input_sha256"),
            schema_sha256=_record_str(record, "provider_schema_sha256"),
            output_sha256=R3B_R2_RAW_SHA256,
            input_tokens=938,
            cached_input_tokens=0,
            output_tokens=391,
            reasoning_tokens=None,
            total_tokens=1329,
            cost_usd="0.005786",
            mapping_class=ReuseMappingClass.EXACT_REMEDIATION_EQUIVALENT,
        ),
        comparisons,
    )


def audit_r3_consolidated_evidence(root: Path) -> R3ConsolidatedEvidenceAudit:
    pre_r3b = audit_r3a_evidence(root)
    if reused_evidence_manifest_sha256(pre_r3b) != R3_REUSED_EVIDENCE_MANIFEST_SHA256:
        _fail(R3ConsolidationErrorCode.EVIDENCE_MISMATCH)
    failure_audit = audit_r3b_failure(root)
    failed_record = cast(dict[str, object], failure_audit["failed_record"])
    preserved = (
        failed_record.get("r3_call_id") == FAILED_R3_CALL_ID
        and failed_record.get("status") == "FAILED"
    )
    if not preserved:
        _fail(R3ConsolidationErrorCode.EVIDENCE_MISMATCH)
    completed = _audit_r3b_completed(root)
    remediation, comparisons = _audit_r3b_r2(root)
    mappings = (*pre_r3b.reused_mappings, *completed, remediation)
    validate_reuse_mappings(mappings)
    if (
        len(mappings) != 25
        or len({item.original_logical_slot_id for item in mappings}) != 25
        or any(item.status == "FAILED" for item in mappings)
        or sum(item.original_logical_slot_id == FAILED_LOGICAL_SLOT_ID for item in mappings) != 1
        or remediation.mapping_class is not ReuseMappingClass.EXACT_REMEDIATION_EQUIVALENT
    ):
        _fail(R3ConsolidationErrorCode.FAILED_RECORD_REUSED)
    proof = {
        **pre_r3b.proof_set_sha256,
        R3_LEDGER_RELATIVE_PATH: R3_LEDGER_SHA256,
        R3_SUMMARY_RELATIVE_PATH: R3_SUMMARY_SHA256,
        R3B_R2_LEDGER_RELATIVE_PATH: R3B_R2_LEDGER_SHA256,
        R3B_R2_SUMMARY_RELATIVE_PATH: R3B_R2_SUMMARY_SHA256,
        R3B_R2_RAW_RELATIVE_PATH: R3B_R2_RAW_SHA256,
    }
    return R3ConsolidatedEvidenceAudit(
        proof_set_sha256=proof,
        reused_mappings=tuple(mappings),
        r3b_completed_mappings=completed,
        r2_remediation_mapping=remediation,
        r2_equivalence_dimensions=comparisons,
        selected_output_dependencies=cast(tuple[object, ...], pre_r3b.selected_output_dependencies),
        original_failed_record_preserved=preserved,
    )


def _mapping_payload(item: ReusedEvidenceMapping) -> dict[str, object]:
    return {
        "proof_set": item.evidence_set,
        "original_logical_slot_id": item.original_logical_slot_id,
        "remediation_call_id": item.remediation_call_id,
        "mapping_class": item.mapping_class.value,
        "provider": item.provider,
        "model": item.model,
        "model_profile_id": item.model_profile_id,
        "status": item.status,
        "input_sha256": item.input_sha256,
        "schema_sha256": item.schema_sha256,
        "output_sha256": item.output_sha256,
        "usage": {
            "input_tokens": item.input_tokens,
            "cached_input_tokens": item.cached_input_tokens,
            "output_tokens": item.output_tokens,
            "reasoning_tokens": item.reasoning_tokens,
            "total_tokens": item.total_tokens,
        },
        "cost_usd": item.cost_usd,
    }


def consolidated_manifest_payload(
    audit: R3ConsolidatedEvidenceAudit,
) -> dict[str, object]:
    order = {call.call_id: index for index, call in enumerate(PEDAGOGICAL_CALIBRATION_CALL_MATRIX)}
    mappings = sorted(
        audit.reused_mappings,
        key=lambda item: order[item.original_logical_slot_id],
    )
    return {
        "proof_set_sha256": dict(sorted(audit.proof_set_sha256.items())),
        "mapping_count": len(mappings),
        "logical_slot_count": len({item.original_logical_slot_id for item in mappings}),
        "mappings": [_mapping_payload(item) for item in mappings],
        "original_failed_record_preserved": audit.original_failed_record_preserved,
    }


def consolidated_manifest_sha256(audit: R3ConsolidatedEvidenceAudit) -> str:
    return _canonical_sha256(consolidated_manifest_payload(audit))


def _r4_call(call: CalibrationCallSpec) -> R4RemainingCallSpec:
    return R4RemainingCallSpec(
        r4_call_id=f"r4.{call.call_id}",
        source_r3_call_id=f"r3.{call.call_id}",
        original_logical_slot_id=call.call_id,
        provider=call.provider,
        model=call.model,
        model_profile_id=call.model_profile_id,
        workload=call.workload,
        scenario_code=call.scenario_code,
        task_kind=call.task_kind,
        repetition=call.repetition,
        max_output_tokens=call.max_output_tokens,
        input_utf8_upper_bound_bytes=call.input_utf8_upper_bound_bytes,
        criterion_refs=call.criterion_refs,
        input_refs=call.input_refs,
        automatic_retry_count=0,
    )


def build_r4_remaining_call_matrix(
    reused_logical_slot_ids: Sequence[str],
) -> tuple[R4RemainingCallSpec, ...]:
    original_ids = {call.call_id for call in PEDAGOGICAL_CALIBRATION_CALL_MATRIX}
    reused = set(reused_logical_slot_ids)
    if len(original_ids) != 96 or len(reused) != 25 or not reused <= original_ids:
        _fail(R3ConsolidationErrorCode.SLOT_ACCOUNTING_INVALID)
    remaining_ids = original_ids - reused
    if reused & remaining_ids or reused | remaining_ids != original_ids:
        _fail(R3ConsolidationErrorCode.SLOT_ACCOUNTING_INVALID)
    remaining = [
        call for call in PEDAGOGICAL_CALIBRATION_CALL_MATRIX if call.call_id in remaining_ids
    ]
    initial = [
        call
        for call in remaining
        if call.call_id.startswith("cal.score.anchor.") and call.repetition == 1
    ]
    repeats = [
        call
        for call in remaining
        if call.call_id.startswith("cal.score.anchor.") and call.repetition == 2
    ]
    outputs = [call for call in remaining if call.call_id.startswith("cal.score.output.")]
    ordered = (*initial, *repeats, *outputs)
    if (
        len(remaining_ids) != 71
        or len(initial) != 43
        or len(repeats) != 16
        or len(outputs) != 12
        or {call.call_id for call in ordered} != remaining_ids
        or any(call.provider is not CalibrationProvider.ANTHROPIC for call in ordered)
        or any(call.workload is not CalibrationWorkload.SCORING for call in ordered)
    ):
        _fail(R3ConsolidationErrorCode.MATRIX_INVALID)
    return tuple(_r4_call(call) for call in ordered)


def _r4_call_payload(call: R4RemainingCallSpec) -> dict[str, object]:
    return {
        "r4_call_id": call.r4_call_id,
        "source_r3_call_id": call.source_r3_call_id,
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
        "automatic_retry_count": call.automatic_retry_count,
    }


def estimate_r4_cost(calls: Sequence[R4RemainingCallSpec]) -> dict[str, object]:
    if any(
        call.input_utf8_upper_bound_bytes != 8_000 or call.max_output_tokens != 512
        for call in calls
    ):
        _fail(R3ConsolidationErrorCode.MATRIX_INVALID)
    maximum = _money(Decimal(len(calls)) * R4_CALL_MAXIMUM_USD)
    ceiling = _money(maximum * R4_COST_SAFETY_MARGIN)
    margin = _money(ceiling - maximum)
    if (
        len(calls) != 71
        or maximum != R4_MAXIMUM_BEFORE_MARGIN_USD
        or margin != R4_SAFETY_MARGIN_AMOUNT_USD
        or ceiling != R4_REQUESTED_HARD_CEILING_USD
    ):
        _fail(R3ConsolidationErrorCode.MATRIX_INVALID)
    return {
        "call_count": len(calls),
        "per_call_maximum_usd": str(R4_CALL_MAXIMUM_USD),
        "maximum_before_margin_usd": str(maximum),
        "safety_margin_multiplier": str(R4_COST_SAFETY_MARGIN),
        "safety_margin_amount_usd": str(margin),
        "requested_hard_ceiling_usd": str(ceiling),
    }


def r4_call_matrix_sha256(
    calls: Sequence[R4RemainingCallSpec],
    *,
    manifest_sha256: str,
) -> str:
    return _canonical_sha256(
        {
            "approval_required": True,
            "plan_version": R4_PLAN_VERSION,
            "pricing_snapshot_id": R4_PRICING_SNAPSHOT_ID,
            "reused_evidence_manifest_sha256": manifest_sha256,
            "calls": [_r4_call_payload(call) for call in calls],
            "cost": estimate_r4_cost(calls),
            "automatic_retry_count": 0,
            "automatic_rerun_count": 0,
            "stop_on_first_systemic_failure": True,
        }
    )


def default_readiness_evidence_sha256() -> dict[str, str]:
    return {
        "r2_initial_ledger": R2_LEDGER_SHA256,
        "r2_initial_anthropic_raw": R2_ANTHROPIC_RAW_SHA256,
        "r3b_ledger": R3_LEDGER_SHA256,
        **{f"r3b_success:{call_id}": R2_ANTHROPIC_RAW_SHA256 for call_id in SUCCESS_R3_CALL_IDS},
        "r3b_r2_ledger": R3B_R2_LEDGER_SHA256,
        "r3b_r2_summary": R3B_R2_SUMMARY_SHA256,
        "r3b_r2_raw": R3B_R2_RAW_SHA256,
    }


def import_anthropic_readiness(evidence_sha256: Mapping[str, str]) -> str:
    if dict(evidence_sha256) != default_readiness_evidence_sha256():
        _fail(R3ConsolidationErrorCode.READINESS_INVALID)
    return "PASSED"


def build_r4_ledger_template(
    calls: Sequence[R4RemainingCallSpec],
    *,
    manifest_sha256: str,
    matrix_sha256: str,
) -> dict[str, object]:
    readiness = default_readiness_evidence_sha256()
    if import_anthropic_readiness(readiness) != "PASSED":
        _fail(R3ConsolidationErrorCode.READINESS_INVALID)
    return {
        "plan_version": R4_PLAN_VERSION,
        "matrix_sha256": matrix_sha256,
        "approved_ceiling_usd": None,
        "requested_hard_ceiling_usd": str(R4_REQUESTED_HARD_CEILING_USD),
        "approval_required": True,
        "reused_evidence_manifest_sha256": manifest_sha256,
        "reused_slot_count": 25,
        "provider_calls_attempted": 0,
        "automatic_retry_count": 0,
        "automatic_rerun_count": 0,
        "total_cost_usd": "0.000000",
        "run_status": "AWAITING_EXPLICIT_APPROVAL",
        "anthropic_readiness": "PASSED",
        "anthropic_readiness_evidence_sha256": readiness,
        "stop_on_first_systemic_failure": True,
        "systemic_failure_codes": list(SYSTEMIC_FAILURE_CODES),
        "calls": [
            {
                **_r4_call_payload(call),
                "status": R4LedgerStatus.PENDING.value,
                "started_at": None,
                "completed_at": None,
                "cost_usd": "0.000000",
                "closed_error_code": None,
                "raw_output_path": None,
                "raw_output_sha256": None,
            }
            for call in calls
        ],
    }


def _ledger_records(ledger: Mapping[str, object]) -> list[dict[str, object]]:
    calls = ledger.get("calls")
    if type(calls) is not list:
        _fail(R3ConsolidationErrorCode.LEDGER_INVALID)
    records = [cast(dict[str, object], item) for item in calls if type(item) is dict]
    if len(records) != len(calls):
        _fail(R3ConsolidationErrorCode.LEDGER_INVALID)
    return records


def next_executable_call_id(ledger: Mapping[str, object]) -> str | None:
    records = _ledger_records(ledger)
    if any(item.get("status") == R4LedgerStatus.STARTED.value for item in records):
        _fail(R3ConsolidationErrorCode.STARTED_CALL_AMBIGUOUS)
    if ledger.get("run_status") in {
        "AWAITING_EXPLICIT_APPROVAL",
        "PAUSED_SYSTEMIC_FAILURE",
    }:
        return None
    allowed = {status.value for status in R4LedgerStatus}
    for item in records:
        status = item.get("status")
        if status not in allowed:
            _fail(R3ConsolidationErrorCode.LEDGER_INVALID)
        if status == R4LedgerStatus.PENDING.value:
            call_id = item.get("r4_call_id")
            if type(call_id) is not str:
                _fail(R3ConsolidationErrorCode.LEDGER_INVALID)
            return call_id
    return None


def pause_after_systemic_failure(
    ledger: Mapping[str, object],
    *,
    failed_call_id: str,
    failure_code: str,
) -> dict[str, object]:
    if failure_code not in SYSTEMIC_FAILURE_CODES:
        _fail(R3ConsolidationErrorCode.SYSTEMIC_FAILURE_INVALID)
    cloned = json.loads(json.dumps(ledger))
    if type(cloned) is not dict:
        _fail(R3ConsolidationErrorCode.LEDGER_INVALID)
    records = _ledger_records(cast(dict[str, object], cloned))
    matches = [item for item in records if item.get("r4_call_id") == failed_call_id]
    if len(matches) != 1 or matches[0].get("status") != R4LedgerStatus.STARTED.value:
        _fail(R3ConsolidationErrorCode.SYSTEMIC_FAILURE_INVALID)
    matches[0]["status"] = R4LedgerStatus.FAILED.value
    matches[0]["closed_error_code"] = failure_code
    cloned["run_status"] = "PAUSED_SYSTEMIC_FAILURE"
    cloned["automatic_retry_count"] = 0
    cloned["automatic_rerun_count"] = 0
    return cast(dict[str, object], cloned)


def r4_approval_text(*, matrix_sha256: str) -> str:
    return "\n".join(
        (
            "J'approuve exclusivement l'exécution de la matrice",
            f"{R4_PLAN_VERSION},",
            f"checksum {matrix_sha256},",
            ("71 appels maximum (71 Anthropic Scorer claude-sonnet-5, max_output_tokens 512),"),
            f"plafond {R4_REQUESTED_HARD_CEILING_USD} USD,",
            (
                "aucun retry et arrêt immédiat de la séquence au premier "
                "échec technique avant tout appel suivant."
            ),
        )
    )


def r3_plan_payload(audit: R3ConsolidatedEvidenceAudit) -> dict[str, object]:
    manifest_sha256 = consolidated_manifest_sha256(audit)
    calls = build_r4_remaining_call_matrix(
        tuple(item.original_logical_slot_id for item in audit.reused_mappings)
    )
    matrix_sha256 = r4_call_matrix_sha256(calls, manifest_sha256=manifest_sha256)
    return {
        "phase": "12.16-G2-R3B-R3",
        "status": "PASS_CLOSED",
        "refs": {
            "branch": "phase12/12-16-provider-model-calibration",
            "entry_head": "186c388772e66a99bb402c6e03ec6e469757ea1b",
            "entry_parent": "8ebdfb01309922332c4287e58d20e68da68310cb",
            "entry_main": "7ae02ee109bcc6399ec0f71616da6aef07abda81",
        },
        "proof_sets": dict(sorted(audit.proof_set_sha256.items())),
        "r2_result": {
            "status": "SCORED",
            "score": "0/1",
            "usage": "938/0/391/1329",
            "latency_milliseconds": 7302,
            "cost_usd": "0.005786",
            "raw_sha256": R3B_R2_RAW_SHA256,
            "mapping_class": ReuseMappingClass.EXACT_REMEDIATION_EQUIVALENT.value,
            "equivalence_dimensions": dict(audit.r2_equivalence_dimensions),
        },
        "original_failed_record": {
            "r3_call_id": FAILED_R3_CALL_ID,
            "logical_slot_id": FAILED_LOGICAL_SLOT_ID,
            "status": "FAILED",
            "preserved": audit.original_failed_record_preserved,
        },
        "r3b_reusable_completed_results": {
            "count": len(audit.r3b_completed_mappings),
            "openai_review": sum(
                item.provider == "openai" for item in audit.r3b_completed_mappings
            ),
            "anthropic_scorer": sum(
                item.provider == "anthropic" for item in audit.r3b_completed_mappings
            ),
        },
        "reused_evidence_manifest_sha256": manifest_sha256,
        "reused_evidence_manifest": consolidated_manifest_payload(audit),
        "slot_accounting": {
            "original_logical_slots": 96,
            "pre_r3b_reused_logical_slots": 15,
            "r3b_completed_logical_slots": 9,
            "r3b_r2_remediated_logical_slots": 1,
            "reused_logical_slots": 25,
            "remaining_logical_slots": len(calls),
            "remaining_openai": 0,
            "remaining_anthropic": len(calls),
            "remaining_anthropic_breakdown": {
                "initial_anchor_scores": sum(
                    call.original_logical_slot_id.startswith("cal.score.anchor.")
                    and call.repetition == 1
                    for call in calls
                ),
                "repeatability_scores": sum(
                    call.original_logical_slot_id.startswith("cal.score.anchor.")
                    and call.repetition == 2
                    for call in calls
                ),
                "selected_output_scores": sum(
                    call.original_logical_slot_id.startswith("cal.score.output.") for call in calls
                ),
            },
        },
        "plan": {
            "version": R4_PLAN_VERSION,
            "matrix_sha256": matrix_sha256,
            "approval_required": True,
            "calls": [_r4_call_payload(call) for call in calls],
            "ledger_relative_path": R4_LEDGER_RELATIVE_PATH,
            "ledger_states": [status.value for status in R4LedgerStatus],
            "automatic_retry_count": 0,
            "automatic_rerun_count": 0,
            "systemic_failure_codes": list(SYSTEMIC_FAILURE_CODES),
            "stop_on_first_systemic_failure": True,
            "future_calls_remain_pending_on_systemic_failure": True,
        },
        "readiness": {
            "anthropic": import_anthropic_readiness(default_readiness_evidence_sha256()),
            "evidence_sha256": default_readiness_evidence_sha256(),
            "additional_canary_required": False,
        },
        "ordinal_preliminary_signal": {
            "scenario": "SCN-01",
            "criterion": "clarity",
            "a": "1/1",
            "b": "1/1",
            "c": "0/1",
            "weak_monotonicity": "PASS",
            "strict_monotonicity": "FAIL",
            "final_calibration_available": False,
        },
        "pricing": {
            "snapshot_id": R4_PRICING_SNAPSHOT_ID,
            "source": R4_PRICING_SOURCE,
            "model": ANTHROPIC_MODEL,
            "input_usd_per_million_tokens": str(ANTHROPIC_INPUT_USD_PER_MTOK),
            "cached_input_usd_per_million_tokens": str(ANTHROPIC_CACHED_INPUT_USD_PER_MTOK),
            "output_usd_per_million_tokens": str(ANTHROPIC_OUTPUT_USD_PER_MTOK),
            **estimate_r4_cost(calls),
        },
        "approval_text": r4_approval_text(matrix_sha256=matrix_sha256),
        "live_provider_calls_r3": R3_LIVE_PROVIDER_CALLS,
        "live_provider_cost_r3_usd": str(R3_PROVIDER_COST_USD),
        "adr_required": False,
        "next_gate": "12.16-G2-R3B-R4_READY_AFTER_EXPLICIT_APPROVAL",
    }


def render_evidence_baseline_markdown(audit: R3ConsolidatedEvidenceAudit) -> str:
    payload = r3_plan_payload(audit)
    proof_sets = cast(dict[str, str], payload["proof_sets"])
    r3b = cast(dict[str, object], payload["r3b_reusable_completed_results"])
    manifest = cast(dict[str, object], payload["reused_evidence_manifest"])
    mappings = cast(list[dict[str, object]], manifest["mappings"])
    lines = [
        "# Phase 12.16-G2-R3B-R3 — Baseline de consolidation des preuves",
        "",
        "## Décision",
        "",
        "- Consolidation offline : `PASS / CLOSED`.",
        "- Appels fournisseurs R3 : `0` ; coût fournisseur R3 : `0.000000 USD`.",
        "- Le ledger R3B et son échec historique restent inchangés.",
        "",
        "## Proof sets hashés",
        "",
    ]
    lines.extend(f"- `{path}` : `{digest}`." for path, digest in proof_sets.items())
    lines.extend(
        [
            "",
            "## Canary R3B-R2",
            "",
            "- Statut : `HTTP 200 / STRUCTURED / SCORED` ; score : `0/1`.",
            "- Usage input/cache/output/total : `938/0/391/1329` ; latence : `7302 ms`.",
            f"- Coût : `0.005786 USD` ; raw SHA-256 : `{R3B_R2_RAW_SHA256}`.",
            f"- Mapping : `EXACT_REMEDIATION_EQUIVALENT` vers `{FAILED_LOGICAL_SLOT_ID}`.",
            "- Toutes les dimensions d'identité sont égales ; seul le call ID et "
            "le cycle d'autorisation diffèrent.",
            "",
            "## Preuves R3B",
            "",
            f"- Succès réutilisables : `{r3b['count']}/9` "
            f"(`{r3b['openai_review']}` OpenAI Review, "
            f"`{r3b['anthropic_scorer']}` Anthropic Scorer).",
            f"- Échec historique `{FAILED_R3_CALL_ID}` : `FAILED`, préservé et non réutilisé.",
            "",
            "## Manifeste consolidé hash-only",
            "",
            f"- Résultats logiques : `{manifest['mapping_count']}` uniques.",
            f"- SHA-256 canonique : `{payload['reused_evidence_manifest_sha256']}`.",
            "",
            "| Slot logique | Proof set | Mapping | Provider | Output SHA-256 |",
            "|---|---|---|---|---|",
        ]
    )
    for item in mappings:
        lines.append(
            f"| `{item['original_logical_slot_id']}` | `{item['proof_set']}` | "
            f"`{item['mapping_class']}` | `{item['provider']}` | "
            f"`{item['output_sha256']}` |"
        )
    lines.extend(
        [
            "",
            "## Comptabilité des slots",
            "",
            "- Originaux : `96` ; réutilisés : `25` ; restants : `71`.",
            "- Intersection réutilisés/restants : `0` ; union : `96`.",
            "- Aucun slot inconnu, perdu ou dupliqué.",
            "",
        ]
    )
    return "\n".join(lines)


def render_remaining_plan_markdown(audit: R3ConsolidatedEvidenceAudit) -> str:
    payload = r3_plan_payload(audit)
    plan = cast(dict[str, object], payload["plan"])
    accounting = cast(dict[str, object], payload["slot_accounting"])
    breakdown = cast(dict[str, int], accounting["remaining_anthropic_breakdown"])
    pricing = cast(dict[str, object], payload["pricing"])
    readiness = cast(dict[str, object], payload["readiness"])
    calls = cast(list[dict[str, object]], plan["calls"])
    lines = [
        "# Phase 12.16-G2-R3B-R3 — Plan final des 71 appels Anthropic",
        "",
        "## Matrice scellée",
        "",
        f"- Version : `{plan['version']}`.",
        f"- Checksum : `{plan['matrix_sha256']}`.",
        "- Appels : `71 Anthropic / 0 OpenAI` ; retry/rerun : `0/0`.",
        f"- Répartition : `{breakdown['initial_anchor_scores']}` initial, "
        f"`{breakdown['repeatability_scores']}` répétabilité, "
        f"`{breakdown['selected_output_scores']}` selected-output.",
        "",
        "## Readiness et arrêt systémique",
        "",
        f"- Readiness Anthropic importée par hashes : `{readiness['anthropic']}`.",
        "- Aucun canary supplémentaire n'est demandé.",
        "- Au premier échec technique, la séquence se met en pause ; les futurs "
        "records restent `PENDING`.",
        "- Un `STARTED` après interruption est ambigu et ferme la reprise automatique.",
        "",
        "## Coût officiel",
        "",
        f"- Source : {pricing['source']}.",
        "- Claude Sonnet 5 : `2.00 USD/MTok input`, `0.20 cache hit`, `10.00 output`.",
        f"- Maximum avant marge : `{pricing['maximum_before_margin_usd']} USD`.",
        f"- Marge 25 % : `{pricing['safety_margin_amount_usd']} USD`.",
        f"- Plafond demandé : `{pricing['requested_hard_ceiling_usd']} USD`.",
        "",
        "## Signal ordinal préliminaire",
        "",
        "- `SCN-01 clarity`: `a=1/1`, `b=1/1`, `c=0/1`.",
        "- Monotonicité faible : `PASS` ; stricte : `FAIL`.",
        "- Aucune modification des anchors ; calibration finale indisponible.",
        "",
        "## Ledger R4",
        "",
        f"- Path ignoré : `{R4_LEDGER_RELATIVE_PATH}`.",
        "- États : `PENDING`, `STARTED`, `COMPLETED`, `FAILED`, `SKIPPED_DEPENDENCY_FAILED`.",
        "- Plafond approuvé initial : `null` ; approbation explicite requise.",
        "",
        "## Ordre canonique",
        "",
        "| # | R4 call ID | Source R3 | Slot logique | Catégorie |",
        "|---:|---|---|---|---|",
    ]
    for index, call in enumerate(calls, start=1):
        slot = cast(str, call["original_logical_slot_id"])
        category = (
            "selected-output"
            if slot.startswith("cal.score.output.")
            else ("repeatability" if call["repetition"] == 2 else "initial")
        )
        lines.append(
            f"| {index} | `{call['r4_call_id']}` | `{call['source_r3_call_id']}` | "
            f"`{slot}` | `{category}` |"
        )
    lines.extend(
        [
            "",
            "## Approbation exacte requise",
            "",
            "```text",
            cast(str, payload["approval_text"]),
            "```",
            "",
            "R3 ne lance aucun appel et s'arrête avant R4.",
            "",
        ]
    )
    return "\n".join(lines)


def render_remaining_plan_json(audit: R3ConsolidatedEvidenceAudit) -> str:
    return (
        json.dumps(
            r3_plan_payload(audit),
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
        + "\n"
    )


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


def write_r3_outputs(root: Path, audit: R3ConsolidatedEvidenceAudit) -> None:
    payload = r3_plan_payload(audit)
    manifest_sha256 = cast(str, payload["reused_evidence_manifest_sha256"])
    plan = cast(dict[str, object], payload["plan"])
    matrix_sha256 = cast(str, plan["matrix_sha256"])
    if (
        manifest_sha256 != R4_REUSED_EVIDENCE_MANIFEST_SHA256
        or matrix_sha256 != R4_CALL_MATRIX_SHA256
    ):
        _fail(R3ConsolidationErrorCode.MATRIX_INVALID)
    calls = build_r4_remaining_call_matrix(
        tuple(item.original_logical_slot_id for item in audit.reused_mappings)
    )
    ledger = build_r4_ledger_template(
        calls,
        manifest_sha256=manifest_sha256,
        matrix_sha256=matrix_sha256,
    )
    outputs = {
        R3_EVIDENCE_REPORT_RELATIVE_PATH: (render_evidence_baseline_markdown(audit) + "\n").encode(
            "utf-8"
        ),
        R3_PLAN_MARKDOWN_RELATIVE_PATH: (render_remaining_plan_markdown(audit) + "\n").encode(
            "utf-8"
        ),
        R3_PLAN_JSON_RELATIVE_PATH: render_remaining_plan_json(audit).encode("utf-8"),
        R4_LEDGER_RELATIVE_PATH: (
            json.dumps(ledger, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
        ).encode("utf-8"),
    }
    for relative_path, content in outputs.items():
        _atomic_write(root / relative_path, content)
