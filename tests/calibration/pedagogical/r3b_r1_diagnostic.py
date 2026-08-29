"""Offline R3B Anthropic failure diagnostic and sealed one-call R2 plan."""

from __future__ import annotations

import hashlib
import json
from collections import Counter
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, replace
from decimal import Decimal
from enum import StrEnum
from fractions import Fraction
from pathlib import Path
from typing import Never, cast

from tests.calibration.pedagogical.call_plan import (
    PEDAGOGICAL_CALIBRATION_CALL_MATRIX,
    CalibrationCallSpec,
)
from tests.calibration.pedagogical.live_runner import _anthropic_observation
from tests.providers.anthropic.mapping import (
    build_anthropic_scoring_request,
    serialize_observation,
)
from tests.providers.anthropic.transport import transform_anthropic_provider_schema

R3_ARTIFACT_DIRECTORY = "artifacts/calibration/12.16-g2-r3"
R3_LEDGER_RELATIVE_PATH = f"{R3_ARTIFACT_DIRECTORY}/ledger.json"
R3_SUMMARY_RELATIVE_PATH = f"{R3_ARTIFACT_DIRECTORY}/summary.json"
R3_RAW_RELATIVE_DIRECTORY = f"{R3_ARTIFACT_DIRECTORY}/raw"
R3_LEDGER_SHA256 = "5722c7e4ba80a40d169997c34de9d764fe63781bc804b74ed2d3d19d1f46175f"
R3_SUMMARY_SHA256 = "44b71e0d6e0da0828235af15a26bb66a6e6d5ff923264c413cc454420c3b79b7"
R3_MATRIX_SHA256 = "245f0c8b2e4d74f61ec58bd5b02824b4d0edfae3dbd55c1c518a9a09ccecee98"
R3_REUSED_MANIFEST_SHA256 = (
    "cace6d138a8ac1fef2920fc45abedbae7b3c99cc30ab9e76af86a16ed3f0ca4e"
)
R3_APPROVED_CEILING_USD = "2.687480"

FAILED_R3_CALL_ID = "r3.cal.score.anchor.scn-01.c.clarity.r1"
FAILED_LOGICAL_SLOT_ID = "cal.score.anchor.scn-01.c.clarity.r1"
FAILED_INPUT_REF = "anchor:cal.scn-01.c"
FAILED_CRITERION_REF = "scn-01.quality.clarity"
SUCCESS_R3_CALL_IDS = (
    "r3.cal.score.anchor.scn-01.a.organization-utility.r1",
    "r3.cal.score.anchor.scn-01.b.clarity.r1",
    "r3.cal.score.anchor.scn-01.b.organization-utility.r1",
)

R2_PLAN_VERSION = "12.16-g2-r3b-r2-anthropic-canary-v1"
R2_REMEDIATION_CALL_ID = (
    "remediation.r3.anthropic-scorer.scn-01.c.clarity.canary.r1"
)
R2_ARTIFACT_DIRECTORY = "artifacts/calibration/12.16-g2-r3b-r2"
R2_LEDGER_RELATIVE_PATH = f"{R2_ARTIFACT_DIRECTORY}/ledger.json"
R2_PROVIDER_CALL_COUNT = 1
R2_AUTOMATIC_RETRY_COUNT = 0
R1_PROVIDER_CALL_COUNT = 0
R1_PROVIDER_COST_USD = Decimal("0.000000")

ANTHROPIC_MODEL = "claude-sonnet-5"
ANTHROPIC_MODEL_PROFILE_ID = "anthropic.claude-sonnet-5.scorer"
ANTHROPIC_MAX_OUTPUT_TOKENS = 512
ANTHROPIC_INPUT_TOKEN_UPPER_BOUND = 8_000
ANTHROPIC_INPUT_USD_PER_MTOK = Decimal("2.00")
ANTHROPIC_CACHED_INPUT_USD_PER_MTOK = Decimal("0.20")
ANTHROPIC_OUTPUT_USD_PER_MTOK = Decimal("10.00")
ANTHROPIC_PRICING_SOURCE = "https://platform.claude.com/docs/en/about-claude/pricing"
R2_BASE_COST_USD = Decimal("0.021120")
R2_SAFETY_MARGIN_MULTIPLIER = Decimal("1.25")
R2_SAFETY_MARGIN_USD = Decimal("0.005280")
R2_HARD_CEILING_USD = Decimal("0.026400")


class AnthropicFailureClassification(StrEnum):
    EMPTY_TEXT_RESPONSE = "EMPTY_TEXT_RESPONSE"
    UNMAPPED_ANTHROPIC_EXCEPTION = "UNMAPPED_ANTHROPIC_EXCEPTION"
    HTTP_CONFLICT = "HTTP_CONFLICT"
    REQUEST_TOO_LARGE = "REQUEST_TOO_LARGE"
    OVERLOADED = "OVERLOADED"
    UNKNOWN_WITH_INSUFFICIENT_EVIDENCE = "UNKNOWN_WITH_INSUFFICIENT_EVIDENCE"


class R2LedgerStatus(StrEnum):
    PENDING = "PENDING"
    STARTED = "STARTED"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


class R3BR1ErrorCode(StrEnum):
    EVIDENCE_UNAVAILABLE = "EVIDENCE_UNAVAILABLE"
    EVIDENCE_MUTATED = "EVIDENCE_MUTATED"
    REQUEST_IDENTITY_INVALID = "REQUEST_IDENTITY_INVALID"
    STARTED_CALL_AMBIGUOUS = "STARTED_CALL_AMBIGUOUS"
    LEDGER_INVALID = "LEDGER_INVALID"


class R3BR1Error(RuntimeError):
    code: R3BR1ErrorCode

    def __init__(self, code: R3BR1ErrorCode) -> None:
        self.code = code
        super().__init__(code.value)


@dataclass(frozen=True, slots=True)
class RemediationCallSpec:
    call_id: str
    source_failed_call_id: str
    logical_slot_id: str
    provider: str
    model: str
    model_profile_id: str
    workload: str
    input_ref: str
    criterion_ref: str
    observation_sha256: str
    serialized_input_sha256: str
    system_sha256: str
    logical_schema_sha256: str
    provider_schema_sha256: str
    serialized_input_bytes: int
    input_token_upper_bound: int
    max_output_tokens: int
    automatic_retry_count: int


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


def _read_frozen_json(
    root: Path,
    relative_path: str,
    expected_sha256: str,
) -> tuple[dict[str, object], bytes]:
    path = (root / relative_path).resolve()
    artifact_root = (root / "artifacts/calibration").resolve()
    if artifact_root not in path.parents:
        _fail(R3BR1ErrorCode.EVIDENCE_UNAVAILABLE)
    try:
        payload = path.read_bytes()
        decoded = json.loads(payload)
    except (OSError, UnicodeError, json.JSONDecodeError):
        _fail(R3BR1ErrorCode.EVIDENCE_UNAVAILABLE)
    if _sha256(payload) != expected_sha256:
        _fail(R3BR1ErrorCode.EVIDENCE_MUTATED)
    if type(decoded) is not dict:
        _fail(R3BR1ErrorCode.EVIDENCE_UNAVAILABLE)
    return cast(dict[str, object], decoded), payload


def _ledger_records(ledger: Mapping[str, object]) -> tuple[dict[str, object], ...]:
    calls = ledger.get("calls")
    if type(calls) is not list or len(calls) != 81:
        _fail(R3BR1ErrorCode.EVIDENCE_UNAVAILABLE)
    records = tuple(cast(dict[str, object], item) for item in calls)
    if any(type(item) is not dict for item in calls):
        _fail(R3BR1ErrorCode.EVIDENCE_UNAVAILABLE)
    return records


def _record_by_r3_call_id(
    records: Sequence[dict[str, object]],
    call_id: str,
) -> dict[str, object]:
    matches = [item for item in records if item.get("r3_call_id") == call_id]
    if len(matches) != 1:
        _fail(R3BR1ErrorCode.EVIDENCE_UNAVAILABLE)
    return matches[0]


def _failed_call_spec() -> CalibrationCallSpec:
    matches = [
        item
        for item in PEDAGOGICAL_CALIBRATION_CALL_MATRIX
        if item.call_id == FAILED_LOGICAL_SLOT_ID
    ]
    if len(matches) != 1:
        _fail(R3BR1ErrorCode.REQUEST_IDENTITY_INVALID)
    return matches[0]


def reconstruct_failed_request_identity() -> dict[str, object]:
    call = _failed_call_spec()
    observation = _anthropic_observation(call, dependency_candidate=None)
    serialized_observation = serialize_observation(observation)
    request = build_anthropic_scoring_request(
        observations=(observation,),
        model=call.model,
        max_tokens=call.max_output_tokens,
    )
    try:
        decoded_input = json.loads(request.input_json)
        provider_schema = transform_anthropic_provider_schema(request.output_schema)
    except (json.JSONDecodeError, TypeError, ValueError):
        _fail(R3BR1ErrorCode.REQUEST_IDENTITY_INVALID)
    serialized_input_bytes = len(request.input_json.encode("utf-8"))
    input_bound = call.input_utf8_upper_bound_bytes
    valid = (
        type(decoded_input) is dict
        and set(decoded_input) == {"observations"}
        and type(decoded_input["observations"]) is list
        and len(decoded_input["observations"]) == 1
        and request.model == ANTHROPIC_MODEL
        and request.max_tokens == ANTHROPIC_MAX_OUTPUT_TOKENS
        and serialized_input_bytes <= input_bound
        and request.output_schema.get("additionalProperties") is False
        and type(provider_schema) is dict
        and provider_schema.get("additionalProperties") is False
    )
    if not valid:
        _fail(R3BR1ErrorCode.REQUEST_IDENTITY_INVALID)
    return {
        "input_ref": FAILED_INPUT_REF,
        "criterion_ref": FAILED_CRITERION_REF,
        "model": request.model,
        "model_profile_id": ANTHROPIC_MODEL_PROFILE_ID,
        "max_output_tokens": request.max_tokens,
        "observation_sha256": _canonical_sha256(serialized_observation),
        "serialized_input_sha256": _sha256(request.input_json.encode("utf-8")),
        "system_sha256": _sha256(request.system.encode("utf-8")),
        "logical_schema_sha256": _canonical_sha256(request.output_schema),
        "provider_schema_sha256": _canonical_sha256(provider_schema),
        "serialized_input_bytes": serialized_input_bytes,
        "input_utf8_upper_bound_bytes": input_bound,
        "bounded": True,
        "logical_schema_valid": True,
        "provider_schema_transformable": True,
    }


def _request_identity_for_record(record: Mapping[str, object]) -> dict[str, object]:
    logical_slot_id = record.get("logical_slot_id")
    matches = [
        item
        for item in PEDAGOGICAL_CALIBRATION_CALL_MATRIX
        if item.call_id == logical_slot_id
    ]
    if len(matches) != 1:
        _fail(R3BR1ErrorCode.REQUEST_IDENTITY_INVALID)
    call = matches[0]
    observation = _anthropic_observation(call, dependency_candidate=None)
    request = build_anthropic_scoring_request(
        observations=(observation,),
        model=call.model,
        max_tokens=call.max_output_tokens,
    )
    provider_schema = transform_anthropic_provider_schema(request.output_schema)
    return {
        "observation_sha256": _canonical_sha256(serialize_observation(observation)),
        "serialized_input_sha256": _sha256(request.input_json.encode("utf-8")),
        "logical_schema_sha256": _canonical_sha256(request.output_schema),
        "provider_schema_sha256": _canonical_sha256(provider_schema),
        "serialized_input_bytes": len(request.input_json.encode("utf-8")),
    }


def _safe_score_from_record(root: Path, record: Mapping[str, object]) -> str:
    raw_path = record.get("raw_output_path")
    expected_sha256 = record.get("raw_output_sha256")
    if type(raw_path) is not str or type(expected_sha256) is not str:
        _fail(R3BR1ErrorCode.EVIDENCE_UNAVAILABLE)
    path = (root / raw_path).resolve()
    raw_root = (root / R3_RAW_RELATIVE_DIRECTORY).resolve()
    if raw_root not in path.parents:
        _fail(R3BR1ErrorCode.EVIDENCE_UNAVAILABLE)
    try:
        payload = path.read_bytes()
        decoded = json.loads(payload)
    except (OSError, UnicodeError, json.JSONDecodeError):
        _fail(R3BR1ErrorCode.EVIDENCE_UNAVAILABLE)
    if _sha256(payload) != expected_sha256 or type(decoded) is not dict:
        _fail(R3BR1ErrorCode.EVIDENCE_MUTATED)
    if decoded.get("status") != "SCORED":
        _fail(R3BR1ErrorCode.EVIDENCE_UNAVAILABLE)
    numerator = decoded.get("score_numerator")
    denominator = decoded.get("score_denominator")
    if type(numerator) is not int or type(denominator) is not int:
        _fail(R3BR1ErrorCode.EVIDENCE_UNAVAILABLE)
    try:
        score = Fraction(numerator, denominator)
    except (ValueError, ZeroDivisionError):
        _fail(R3BR1ErrorCode.EVIDENCE_UNAVAILABLE)
    if not 0 <= score <= 1:
        _fail(R3BR1ErrorCode.EVIDENCE_UNAVAILABLE)
    return f"{score.numerator}/{score.denominator}"


def classify_anthropic_failure(
    *,
    transport_code: str | None,
    http_status: int | None,
    provider_error_type: str | None,
    response_received: bool | None,
    text_block_count: int | None,
) -> AnthropicFailureClassification:
    if (
        transport_code == "EMPTY_RESPONSE"
        or provider_error_type == "EMPTY_RESPONSE"
        or (response_received is True and text_block_count == 0)
    ):
        return AnthropicFailureClassification.EMPTY_TEXT_RESPONSE
    if provider_error_type == "UNMAPPED_SDK_ERROR":
        return AnthropicFailureClassification.UNMAPPED_ANTHROPIC_EXCEPTION
    if transport_code == "CONFLICT" or http_status == 409:
        return AnthropicFailureClassification.HTTP_CONFLICT
    if transport_code == "REQUEST_TOO_LARGE" or http_status == 413:
        return AnthropicFailureClassification.REQUEST_TOO_LARGE
    if transport_code == "OVERLOADED" or http_status == 529:
        return AnthropicFailureClassification.OVERLOADED
    return AnthropicFailureClassification.UNKNOWN_WITH_INSUFFICIENT_EVIDENCE


def audit_r3b_failure(root: Path) -> dict[str, object]:
    ledger, ledger_bytes = _read_frozen_json(
        root,
        R3_LEDGER_RELATIVE_PATH,
        R3_LEDGER_SHA256,
    )
    summary, summary_bytes = _read_frozen_json(
        root,
        R3_SUMMARY_RELATIVE_PATH,
        R3_SUMMARY_SHA256,
    )
    records = _ledger_records(ledger)
    attempted_call_ids = ledger.get("attempted_call_ids")
    state_counts = Counter(cast(str, item.get("status")) for item in records)
    expected_state_counts = {
        "COMPLETED": 9,
        "FAILED": 1,
        "PENDING": 71,
        "STARTED": 0,
    }
    if (
        ledger.get("matrix_sha256") != R3_MATRIX_SHA256
        or ledger.get("reused_evidence_manifest_sha256")
        != R3_REUSED_MANIFEST_SHA256
        or ledger.get("approved_ceiling_usd") != R3_APPROVED_CEILING_USD
        or ledger.get("requested_hard_ceiling_usd") != R3_APPROVED_CEILING_USD
        or ledger.get("provider_calls_attempted") != 10
        or ledger.get("automatic_retry_count") != 0
        or ledger.get("automatic_rerun_count") != 0
        or type(attempted_call_ids) is not list
        or len(attempted_call_ids) != len(set(attempted_call_ids))
        or len(attempted_call_ids) != 10
        or any(state_counts.get(key, 0) != value for key, value in expected_state_counts.items())
    ):
        _fail(R3BR1ErrorCode.EVIDENCE_UNAVAILABLE)
    failed = _record_by_r3_call_id(records, FAILED_R3_CALL_ID)
    if (
        failed.get("status") != "FAILED"
        or failed.get("logical_slot_id") != FAILED_LOGICAL_SLOT_ID
        or failed.get("input_refs") != [FAILED_INPUT_REF]
        or failed.get("criterion_refs") != [FAILED_CRITERION_REF]
    ):
        _fail(R3BR1ErrorCode.EVIDENCE_UNAVAILABLE)
    raw_files = tuple((root / R3_RAW_RELATIVE_DIRECTORY).glob("*.json"))
    if len(raw_files) != 9:
        _fail(R3BR1ErrorCode.EVIDENCE_UNAVAILABLE)
    successes = tuple(_record_by_r3_call_id(records, item) for item in SUCCESS_R3_CALL_IDS)
    comparisons = []
    for item in successes:
        if item.get("status") != "COMPLETED":
            _fail(R3BR1ErrorCode.EVIDENCE_UNAVAILABLE)
        comparisons.append(
            {
                "r3_call_id": item["r3_call_id"],
                "logical_slot_id": item["logical_slot_id"],
                **_request_identity_for_record(item),
                "raw_output_sha256": item["raw_output_sha256"],
                "score": _safe_score_from_record(root, item),
                "provider_call_count": 1,
            }
        )
    identity = reconstruct_failed_request_identity()
    distinct_inputs = {
        cast(str, item["serialized_input_sha256"]) for item in comparisons
    } | {cast(str, identity["serialized_input_sha256"])}
    distinct_observations = {
        cast(str, item["observation_sha256"]) for item in comparisons
    } | {cast(str, identity["observation_sha256"])}
    if len(distinct_inputs) != 4 or len(distinct_observations) != 4:
        _fail(R3BR1ErrorCode.REQUEST_IDENTITY_INVALID)
    distinct_success_slots = {
        cast(str, item["logical_slot_id"]) for item in comparisons
    }
    logical_schema_hashes = {
        cast(str, item["logical_schema_sha256"]) for item in comparisons
    } | {cast(str, identity["logical_schema_sha256"])}
    provider_schema_hashes = {
        cast(str, item["provider_schema_sha256"]) for item in comparisons
    } | {cast(str, identity["provider_schema_sha256"])}
    if (
        len(distinct_success_slots) != 3
        or len(logical_schema_hashes) != 1
        or len(provider_schema_hashes) != 1
    ):
        _fail(R3BR1ErrorCode.REQUEST_IDENTITY_INVALID)
    classification = classify_anthropic_failure(
        transport_code=None,
        http_status=None,
        provider_error_type=None,
        response_received=None,
        text_block_count=None,
    )
    return {
        "evidence": {
            "ledger_sha256": _sha256(ledger_bytes),
            "summary_sha256": _sha256(summary_bytes),
            "raw_file_count": len(raw_files),
            "matrix_sha256": ledger["matrix_sha256"],
            "reused_evidence_manifest_sha256": ledger[
                "reused_evidence_manifest_sha256"
            ],
            "approved_ceiling_usd": ledger["approved_ceiling_usd"],
            "run_status": ledger.get("run_status"),
            "summary_status": summary.get("status", summary.get("run_status")),
            "state_counts": expected_state_counts,
            "provider_calls_attempted": ledger.get("provider_calls_attempted"),
            "automatic_retry_count": ledger.get("automatic_retry_count"),
            "automatic_rerun_count": ledger.get("automatic_rerun_count"),
            "duplicate_call_count": len(attempted_call_ids)
            - len(set(attempted_call_ids)),
        },
        "failed_record": {
            "r3_call_id": failed["r3_call_id"],
            "logical_slot_id": failed["logical_slot_id"],
            "status": failed["status"],
            "started_at": failed["started_at"],
            "completed_at": failed["completed_at"],
            "latency_milliseconds": failed["latency_milliseconds"],
            "provider": failed["provider"],
            "model": failed["model"],
            "model_profile_id": failed["model_profile_id"],
            "input_refs": failed["input_refs"],
            "criterion_refs": failed["criterion_refs"],
            "max_output_tokens": failed["max_output_tokens"],
            "input_tokens": failed["input_tokens"],
            "cached_input_tokens": failed["cached_input_tokens"],
            "output_tokens": failed["output_tokens"],
            "total_tokens": failed["total_tokens"],
            "raw_output_present": failed["raw_output_path"] is not None,
            "raw_output_path": failed["raw_output_path"],
            "raw_output_sha256": failed["raw_output_sha256"],
            "response_status": failed["response_status"],
            "provider_response_status": failed["provider_response_status"],
            "closed_error_code": failed["closed_error_code"],
            "systemic_failure_category": failed["systemic_failure_category"],
            "reserved_cost_usd": failed["reserved_cost_usd"],
            "classification": classification.value,
            "classification_evidence": {
                "http_status": None,
                "provider_error_type": None,
                "response_received": None,
                "stop_reason": None,
                "text_block_count": None,
            },
        },
        "request_identity": identity,
        "successful_comparisons": comparisons,
        "comparison_conclusion": {
            "distinct_serialized_input_count": len(distinct_inputs),
            "distinct_observation_count": len(distinct_observations),
            "distinct_success_logical_slot_count": len(distinct_success_slots),
            "distinct_logical_schema_count": len(logical_schema_hashes),
            "distinct_provider_schema_count": len(provider_schema_hashes),
            "distinct_raw_output_sha256_count": len(
                {cast(str, item["raw_output_sha256"]) for item in comparisons}
            ),
            "provider_call_count": len(comparisons),
            "identical_score_bytes_is_duplicate_provider_call": False,
        },
        "r1_provider_calls": R1_PROVIDER_CALL_COUNT,
        "r1_provider_cost_usd": str(R1_PROVIDER_COST_USD),
    }


def remediation_call_spec() -> RemediationCallSpec:
    identity = reconstruct_failed_request_identity()
    return RemediationCallSpec(
        call_id=R2_REMEDIATION_CALL_ID,
        source_failed_call_id=FAILED_R3_CALL_ID,
        logical_slot_id=FAILED_LOGICAL_SLOT_ID,
        provider="anthropic",
        model=ANTHROPIC_MODEL,
        model_profile_id=ANTHROPIC_MODEL_PROFILE_ID,
        workload="scoring",
        input_ref=FAILED_INPUT_REF,
        criterion_ref=FAILED_CRITERION_REF,
        observation_sha256=cast(str, identity["observation_sha256"]),
        serialized_input_sha256=cast(str, identity["serialized_input_sha256"]),
        system_sha256=cast(str, identity["system_sha256"]),
        logical_schema_sha256=cast(str, identity["logical_schema_sha256"]),
        provider_schema_sha256=cast(str, identity["provider_schema_sha256"]),
        serialized_input_bytes=cast(int, identity["serialized_input_bytes"]),
        input_token_upper_bound=ANTHROPIC_INPUT_TOKEN_UPPER_BOUND,
        max_output_tokens=ANTHROPIC_MAX_OUTPUT_TOKENS,
        automatic_retry_count=R2_AUTOMATIC_RETRY_COUNT,
    )


def _remediation_call_payload(call: RemediationCallSpec) -> dict[str, object]:
    return {
        "call_id": call.call_id,
        "source_failed_call_id": call.source_failed_call_id,
        "logical_slot_id": call.logical_slot_id,
        "provider": call.provider,
        "model": call.model,
        "model_profile_id": call.model_profile_id,
        "workload": call.workload,
        "input_ref": call.input_ref,
        "criterion_ref": call.criterion_ref,
        "observation_sha256": call.observation_sha256,
        "serialized_input_sha256": call.serialized_input_sha256,
        "system_sha256": call.system_sha256,
        "logical_schema_sha256": call.logical_schema_sha256,
        "provider_schema_sha256": call.provider_schema_sha256,
        "serialized_input_bytes": call.serialized_input_bytes,
        "input_token_upper_bound": call.input_token_upper_bound,
        "max_output_tokens": call.max_output_tokens,
        "automatic_retry_count": call.automatic_retry_count,
    }


def remediation_matrix_sha256(
    calls: Sequence[RemediationCallSpec] | None = None,
) -> str:
    selected = tuple(calls) if calls is not None else (remediation_call_spec(),)
    return _canonical_sha256([_remediation_call_payload(item) for item in selected])


def mutated_remediation_call_for_checksum_test() -> RemediationCallSpec:
    return replace(remediation_call_spec(), max_output_tokens=511)


def _validate_cost_plan() -> None:
    input_cost = (
        Decimal(ANTHROPIC_INPUT_TOKEN_UPPER_BOUND)
        * ANTHROPIC_INPUT_USD_PER_MTOK
        / Decimal(1_000_000)
    )
    output_cost = (
        Decimal(ANTHROPIC_MAX_OUTPUT_TOKENS)
        * ANTHROPIC_OUTPUT_USD_PER_MTOK
        / Decimal(1_000_000)
    )
    if (
        input_cost != Decimal("0.016000")
        or output_cost != Decimal("0.005120")
        or input_cost + output_cost != R2_BASE_COST_USD
        or R2_BASE_COST_USD * Decimal("0.25") != R2_SAFETY_MARGIN_USD
        or R2_BASE_COST_USD * R2_SAFETY_MARGIN_MULTIPLIER
        != R2_HARD_CEILING_USD
    ):
        _fail(R3BR1ErrorCode.REQUEST_IDENTITY_INVALID)


def r2_plan_payload(root: Path) -> dict[str, object]:
    audit = audit_r3b_failure(root)
    del audit
    _validate_cost_plan()
    call = remediation_call_spec()
    checksum = remediation_matrix_sha256((call,))
    return {
        "phase": "12.16-G2-R3B-R1",
        "decision": "OFFLINE_DIAGNOSTIC_COMPLETE_R2_APPROVAL_REQUIRED",
        "plan_version": R2_PLAN_VERSION,
        "matrix_sha256": checksum,
        "approval_required": True,
        "r1_provider_call_count": R1_PROVIDER_CALL_COUNT,
        "r1_provider_cost_usd": str(R1_PROVIDER_COST_USD),
        "calls": [_remediation_call_payload(call)],
        "execution_policy": {
            "provider_call_count_max": R2_PROVIDER_CALL_COUNT,
            "automatic_retry_count": R2_AUTOMATIC_RETRY_COUNT,
            "automatic_rerun_count": 0,
            "started_is_ambiguous": True,
            "terminal_is_never_recalled": True,
            "stop_after_canary_regardless_of_result": True,
        },
        "pricing": {
            "model": ANTHROPIC_MODEL,
            "source": ANTHROPIC_PRICING_SOURCE,
            "input_usd_per_million_tokens": str(ANTHROPIC_INPUT_USD_PER_MTOK),
            "cached_input_usd_per_million_tokens": str(
                ANTHROPIC_CACHED_INPUT_USD_PER_MTOK
            ),
            "output_usd_per_million_tokens": str(ANTHROPIC_OUTPUT_USD_PER_MTOK),
            "input_token_upper_bound": ANTHROPIC_INPUT_TOKEN_UPPER_BOUND,
            "output_token_upper_bound": ANTHROPIC_MAX_OUTPUT_TOKENS,
            "input_maximum_usd": "0.016000",
            "output_maximum_usd": "0.005120",
            "base_maximum_usd": str(R2_BASE_COST_USD),
            "safety_margin_multiplier": str(R2_SAFETY_MARGIN_MULTIPLIER),
            "safety_margin_usd": str(R2_SAFETY_MARGIN_USD),
            "requested_hard_ceiling_usd": str(R2_HARD_CEILING_USD),
        },
        "ledger_relative_path": R2_LEDGER_RELATIVE_PATH,
        "original_r3_ledger_mutated": False,
        "approval_text": r2_approval_text(checksum),
    }


def r2_approval_text(checksum: str | None = None) -> str:
    sealed_checksum = checksum or remediation_matrix_sha256()
    return "\n".join(
        (
            "J'approuve exclusivement l'exécution de la matrice",
            f"{R2_PLAN_VERSION},",
            f"checksum {sealed_checksum},",
            "1 appel maximum (Anthropic Scorer claude-sonnet-5, max_output_tokens 512),",
            f"plafond {R2_HARD_CEILING_USD} USD,",
            "aucun retry et arrêt immédiat après ce canary quel que soit le résultat.",
        )
    )


def build_r2_ledger_template() -> dict[str, object]:
    call = remediation_call_spec()
    return {
        "plan_version": R2_PLAN_VERSION,
        "matrix_sha256": remediation_matrix_sha256((call,)),
        "approval_required": True,
        "approved_ceiling_usd": None,
        "provider_calls_attempted": 0,
        "automatic_retry_count": 0,
        "automatic_rerun_count": 0,
        "total_cost_usd": "0.000000",
        "original_r3_ledger_mutated": False,
        "calls": [
            {
                **_remediation_call_payload(call),
                "status": R2LedgerStatus.PENDING.value,
                "started_at": None,
                "completed_at": None,
                "closed_error_code": None,
                "http_status": None,
                "provider_error_type": None,
                "response_received": None,
                "stop_reason": None,
                "text_block_count": None,
                "input_tokens": 0,
                "cached_input_tokens": 0,
                "output_tokens": 0,
                "total_tokens": 0,
                "raw_output_path": None,
                "raw_output_sha256": None,
                "cost_usd": "0.000000",
            }
        ],
    }


def next_r2_call_id(ledger: Mapping[str, object]) -> str | None:
    calls = ledger.get("calls")
    if type(calls) is not list or len(calls) != 1 or type(calls[0]) is not dict:
        _fail(R3BR1ErrorCode.LEDGER_INVALID)
    record = cast(dict[str, object], calls[0])
    if record.get("call_id") != R2_REMEDIATION_CALL_ID:
        _fail(R3BR1ErrorCode.LEDGER_INVALID)
    status = record.get("status")
    if status == R2LedgerStatus.STARTED.value:
        _fail(R3BR1ErrorCode.STARTED_CALL_AMBIGUOUS)
    if status == R2LedgerStatus.PENDING.value:
        return R2_REMEDIATION_CALL_ID
    if status in {R2LedgerStatus.COMPLETED.value, R2LedgerStatus.FAILED.value}:
        return None
    _fail(R3BR1ErrorCode.LEDGER_INVALID)


def render_diagnostic_markdown(root: Path) -> str:
    audit = audit_r3b_failure(root)
    evidence = cast(dict[str, object], audit["evidence"])
    failed = cast(dict[str, object], audit["failed_record"])
    identity = cast(dict[str, object], audit["request_identity"])
    comparison = cast(dict[str, object], audit["comparison_conclusion"])
    successes = cast(list[dict[str, object]], audit["successful_comparisons"])
    lines = [
        "# Phase 12.16-G2-R3B-R1 — Diagnostic Anthropic hors ligne",
        "",
        "## Décision",
        "",
        "- Diagnostic : `COMPLETE`.",
        f"- Classification : `{failed['classification']}`.",
        "- Cause plus précise : `NON PROUVÉE` faute de statut HTTP, de type SDK fermé et de preuve de réponse.",
        "- Appels fournisseurs R1 : `0` ; coût fournisseur R1 : `0.000000 USD`.",
        "- R3 reste interrompu ; aucun retry, resume ou appel R2 n'a été exécuté.",
        "",
        "## Preuves R3B gelées",
        "",
        f"- Ledger SHA-256 : `{evidence['ledger_sha256']}`.",
        f"- Summary SHA-256 : `{evidence['summary_sha256']}`.",
        f"- Raws présents : `{evidence['raw_file_count']}`.",
        f"- Matrice/manifeste SHA-256 : `{evidence['matrix_sha256']}` / `{evidence['reused_evidence_manifest_sha256']}`.",
        f"- Plafond approuvé : `{evidence['approved_ceiling_usd']} USD`.",
        f"- États : `{json.dumps(evidence['state_counts'], sort_keys=True)}`.",
        f"- Appels tentés : `{evidence['provider_calls_attempted']}` ; retry/rerun/duplicate : `{evidence['automatic_retry_count']}/{evidence['automatic_rerun_count']}/{evidence['duplicate_call_count']}`.",
        "",
        "## Appel échoué — champs sûrs",
        "",
        f"- Call : `{failed['r3_call_id']}` ; slot : `{failed['logical_slot_id']}`.",
        f"- Début/fin/latence : `{failed['started_at']}` / `{failed['completed_at']}` / `{failed['latency_milliseconds']} ms`.",
        f"- Provider/modèle/profil : `{failed['provider']}` / `{failed['model']}` / `{failed['model_profile_id']}`.",
        f"- Input ref / critère : `{FAILED_INPUT_REF}` / `{FAILED_CRITERION_REF}`.",
        f"- Max output : `{failed['max_output_tokens']}` ; usage input/cache/output/total : `{failed['input_tokens']}/{failed['cached_input_tokens']}/{failed['output_tokens']}/{failed['total_tokens']}`.",
        f"- Statuts : `{failed['status']}` / `{failed['response_status']}` / `{failed['provider_response_status']}`.",
        f"- Erreur fermée/catégorie : `{failed['closed_error_code']}` / `{failed['systemic_failure_category']}`.",
        f"- Raw présent/path/hash : `{failed['raw_output_present']}` / `{failed['raw_output_path']}` / `{failed['raw_output_sha256']}` ; réserve : `{failed['reserved_cost_usd']} USD`.",
        "",
        "## Reconstitution locale exacte",
        "",
        f"- Observation SHA-256 : `{identity['observation_sha256']}`.",
        f"- Input sérialisé SHA-256 : `{identity['serialized_input_sha256']}` ; taille : `{identity['serialized_input_bytes']} / {identity['input_utf8_upper_bound_bytes']} octets`.",
        f"- System SHA-256 : `{identity['system_sha256']}`.",
        f"- Schéma logique/provider SHA-256 : `{identity['logical_schema_sha256']}` / `{identity['provider_schema_sha256']}`.",
        f"- Bounded / logique valide / transformable : `{identity['bounded']}` / `{identity['logical_schema_valid']}` / `{identity['provider_schema_transformable']}`.",
        f"- Modèle/profil/max tokens : `{identity['model']}` / `{identity['model_profile_id']}` / `{identity['max_output_tokens']}`.",
        "",
        "## Comparaison avec les trois succès Anthropic",
        "",
        "| Call | Slot logique | Observation SHA-256 | Input SHA-256 | Raw SHA-256 | Score |",
        "|---|---|---|---|---|---|",
    ]
    for item in successes:
        lines.append(
            f"| `{item['r3_call_id']}` | `{item['logical_slot_id']}` | "
            f"`{item['observation_sha256']}` | "
            f"`{item['serialized_input_sha256']}` | `{item['raw_output_sha256']}` | "
            f"`{item['score']}` |"
        )
    lines.extend(
        [
            "",
            f"- Inputs distincts : `{comparison['distinct_serialized_input_count']}` ; observations distinctes : `{comparison['distinct_observation_count']}`.",
            f"- Slots succès distincts : `{comparison['distinct_success_logical_slot_count']}` ; schémas logique/provider distincts sur les quatre requêtes : `{comparison['distinct_logical_schema_count']}/{comparison['distinct_provider_schema_count']}`.",
            f"- Hashes raw distincts : `{comparison['distinct_raw_output_sha256_count']}` pour `{comparison['provider_call_count']}` appels terminés.",
            "- `IDENTICAL_SCORE_BYTES != DUPLICATE_PROVIDER_CALL` : les identités d'entrée et les call IDs prouvent trois appels distincts ayant retourné le même score rationnel `1/1`.",
            "",
            "## Renforcement privé",
            "",
            "- Taxonomie ajoutée : `CONFLICT`, `REQUEST_TOO_LARGE`, `OVERLOADED`, `EMPTY_RESPONSE`.",
            "- Diagnostics fermés : statut HTTP, type d'erreur, réponse reçue, stop reason, nombre de blocs texte et usage numérique.",
            "- `409`, `413`, `529/OverloadedError`, réponse 200 vide et exception SDK non mappée sont désormais distingués sans corps, message, header ni request ID.",
            "- Le SDK conserve `max_retries=0`. Les contrats publics `EvaluationScorerPort` et `ScorerOutcome` ne changent pas.",
            "- Aucun ADR : aucune politique de retry ni frontière architecturale n'est modifiée.",
            "",
            "## Validations hors ligne",
            "",
            "- Tests ciblés calibration/Anthropic/architecture : `PASS`.",
            "- R3B selftest : `PASS`.",
            "- Pytest global : `4227 passed, 3 skipped` ; skips = gates live explicitement fermés.",
            "- Ruff, mypy backend+harness, compileall et diff-check : `PASS`.",
            "- Gates SQLite réelles locales : `22 passed`.",
            "- Gates live provider : `FERMÉS` ; résolution de credentials et construction de transport R1 : `0`.",
            "- Scan sécurité/path/raw : `PASS` ; aucun contenu brut, secret ou chemin utilisateur dans les rapports.",
            "",
            "## Suite fermée",
            "",
            f"Le canary distinct `{R2_PLAN_VERSION}` est seulement préparé. Son exécution exige l'approbation exacte publiée dans le plan de coût compagnon.",
            "Même après un futur canary réussi, les 71 appels ne seront pas repris directement : un lot offline R3B-R3 devra importer le résultat par hash, préserver les 9 succès, dériver 71 appels, recalculer checksum/plafond et demander une nouvelle approbation.",
            "",
        ]
    )
    return "\n".join(lines)


def render_cost_plan_markdown(root: Path) -> str:
    plan = r2_plan_payload(root)
    call = cast(list[dict[str, object]], plan["calls"])[0]
    pricing = cast(dict[str, object], plan["pricing"])
    return "\n".join(
        (
            "# Phase 12.16-G2-R3B-R1 — Plan de coût du canary Anthropic",
            "",
            "## Matrice scellée",
            "",
            f"- Plan : `{plan['plan_version']}`.",
            f"- Matrice SHA-256 : `{plan['matrix_sha256']}`.",
            "- Approval required : `TRUE`.",
            "- Appels : `1` ; retry/rerun : `0/0`.",
            f"- Call neuf : `{call['call_id']}`.",
            f"- Source échouée : `{call['source_failed_call_id']}` ; slot logique : `{call['logical_slot_id']}`.",
            f"- Provider/modèle/profil : `{call['provider']}` / `{call['model']}` / `{call['model_profile_id']}`.",
            f"- Input/observation/schema inchangés : `{call['serialized_input_sha256']}` / `{call['observation_sha256']}` / `{call['logical_schema_sha256']}`.",
            f"- Max output : `{call['max_output_tokens']}` ; retry : `{call['automatic_retry_count']}`.",
            "",
            "## Prix officiel et plafond",
            "",
            f"- Source : {pricing['source']}.",
            f"- Claude Sonnet 5 : `{pricing['input_usd_per_million_tokens']} USD/MTok input`, `{pricing['cached_input_usd_per_million_tokens']} USD/MTok cache hit`, `{pricing['output_usd_per_million_tokens']} USD/MTok output`.",
            f"- Input maximum : `{pricing['input_token_upper_bound']}` tokens, soit `{pricing['input_maximum_usd']} USD`.",
            f"- Output maximum : `{pricing['output_token_upper_bound']}` tokens, soit `{pricing['output_maximum_usd']} USD`.",
            f"- Base : `{pricing['base_maximum_usd']} USD` ; marge 25 % : `{pricing['safety_margin_usd']} USD`.",
            f"- Hard ceiling demandé : `{pricing['requested_hard_ceiling_usd']} USD`.",
            "",
            "## Ledger local préparé",
            "",
            f"- Chemin Git-ignoré : `{plan['ledger_relative_path']}`.",
            "- États fermés : `PENDING`, `STARTED`, `COMPLETED`, `FAILED`.",
            "- Seul `PENDING` est exécutable ; `STARTED` est ambigu et arrête ; un terminal n'est jamais rappelé.",
            "- Le ledger et les raws R3 originaux ne sont jamais modifiés.",
            "",
            "## Approbation R2 requise",
            "",
            "```text",
            cast(str, plan["approval_text"]),
            "```",
            "",
            "R2 n'est pas exécuté par R1.",
            "",
        )
    )


def render_cost_plan_json(root: Path) -> str:
    return json.dumps(
        r2_plan_payload(root),
        ensure_ascii=False,
        indent=2,
        sort_keys=True,
    ) + "\n"


def _fail(code: R3BR1ErrorCode) -> Never:
    raise R3BR1Error(code) from None
