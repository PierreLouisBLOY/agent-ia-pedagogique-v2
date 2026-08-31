"""Offline-only R2 evidence audit and R2A diagnostic projections."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from enum import StrEnum
from pathlib import Path
from typing import cast

from backend.adapters.outbound.openai import (
    OpenAIIncompleteReason,
    OpenAIResponsesResponse,
    OpenAIResponseStatus,
)
from backend.adapters.outbound.review.openai.adapter import _map_response
from backend.agent_runtime.agents.review import ReviewPortError
from tests.calibration.pedagogical.catalog import anchor_by_id
from tests.calibration.pedagogical.legacy_call_plan import (
    PEDAGOGICAL_CALIBRATION_CALL_MATRIX,
)
from tests.calibration.pedagogical.live_runner import (
    _anthropic_observation,
    _model_profile,
    _provider_profile,
    _review_request,
)
from tests.calibration.pedagogical.remediation_plan import (
    R2_CANARY_CALL_MATRIX,
    R2_CANARY_MATRIX_SHA256,
    R2_CANARY_PLAN_VERSION,
)
from tests.providers.anthropic.mapping import build_anthropic_scoring_request

R2_ARTIFACT_DIRECTORY = "artifacts/calibration/12.16-g2-r2"
R2_SUMMARY_RELATIVE_PATH = f"{R2_ARTIFACT_DIRECTORY}/summary.json"
R2_LEDGER_RELATIVE_PATH = f"{R2_ARTIFACT_DIRECTORY}/ledger.json"
R2_RAW_RELATIVE_DIRECTORY = f"{R2_ARTIFACT_DIRECTORY}/raw"
R2_APPROVED_CEILING_USD = "0.100200"
R2_EXPECTED_CALL_IDS = (
    "remediation.openai-review.scn-05.canary.r1",
    "remediation.anthropic-scorer.scn-01.clarity.canary.r1",
)


class R2EvidenceAuditError(RuntimeError):
    """Closed evidence failure with no raw artifact content."""

    def __init__(self) -> None:
        super().__init__("R2_LOCAL_EVIDENCE_UNAVAILABLE")


class OpenAIRawOutputClassification(StrEnum):
    NO_OUTPUT_TEXT = "NO_OUTPUT_TEXT"
    TRUNCATED_JSON = "TRUNCATED_JSON"
    PARSEABLE_CONTRACT_MISMATCH = "PARSEABLE_CONTRACT_MISMATCH"
    PARSEABLE_COMPLETE_BUT_INCOMPLETE_STATUS = (
        "PARSEABLE_COMPLETE_BUT_INCOMPLETE_STATUS"
    )
    OTHER_CLOSED_FAILURE = "OTHER_CLOSED_FAILURE"


def _sha256(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _read_json_object(path: Path) -> tuple[bytes, dict[str, object]]:
    try:
        payload = path.read_bytes()
        parsed = json.loads(payload)
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        raise R2EvidenceAuditError() from None
    if type(parsed) is not dict:
        raise R2EvidenceAuditError()
    return payload, cast(dict[str, object], parsed)


def _safe_artifact_path(root: Path, relative_path: str) -> Path:
    normalized = Path(relative_path)
    if normalized.is_absolute() or ".." in normalized.parts:
        raise R2EvidenceAuditError()
    resolved_root = root.resolve()
    resolved = (resolved_root / normalized).resolve()
    raw_directory = (resolved_root / R2_RAW_RELATIVE_DIRECTORY).resolve()
    if raw_directory not in resolved.parents:
        raise R2EvidenceAuditError()
    return resolved


def audit_r2_local_evidence(root: Path) -> dict[str, object]:
    """Validate and project R2 artifacts without returning raw provider text."""

    resolved_root = root.resolve()
    summary_bytes, summary = _read_json_object(
        resolved_root / R2_SUMMARY_RELATIVE_PATH
    )
    ledger_bytes, ledger = _read_json_object(resolved_root / R2_LEDGER_RELATIVE_PATH)
    calls = ledger.get("calls")
    if type(calls) is not list:
        raise R2EvidenceAuditError()
    call_records = cast(list[object], calls)
    if any(type(item) is not dict for item in call_records):
        raise R2EvidenceAuditError()
    records = cast(list[dict[str, object]], call_records)
    call_ids = tuple(record.get("call_id") for record in records)
    terminal = {"PASSED", "FAILED"}
    if (
        ledger.get("plan_version") != R2_CANARY_PLAN_VERSION
        or ledger.get("matrix_sha256") != R2_CANARY_MATRIX_SHA256
        or ledger.get("approved_ceiling_usd") != R2_APPROVED_CEILING_USD
        or call_ids != R2_EXPECTED_CALL_IDS
        or len(set(call_ids)) != len(call_ids)
        or any(record.get("status") not in terminal for record in records)
        or ledger.get("automatic_retry_count") != 0
        or ledger.get("automatic_rerun_count") != 0
        or ledger.get("provider_calls_attempted") != 2
        or summary.get("provider_calls_attempted") != 2
        or summary.get("automatic_retry_count") != 0
        or summary.get("automatic_rerun_count") != 0
        or summary.get("ledger_sha256") != _sha256(ledger_bytes)
        or summary.get("total_cost_usd") != ledger.get("total_cost_usd")
    ):
        raise R2EvidenceAuditError()

    referenced_raw_paths: set[str] = set()
    projected_calls: list[dict[str, object]] = []
    for record in records:
        raw_path = record.get("raw_output_path")
        raw_hash = record.get("raw_output_sha256")
        raw_size: int | None = None
        if raw_path is not None or raw_hash is not None:
            if type(raw_path) is not str or type(raw_hash) is not str:
                raise R2EvidenceAuditError()
            artifact_path = _safe_artifact_path(resolved_root, raw_path)
            try:
                raw_bytes = artifact_path.read_bytes()
            except OSError:
                raise R2EvidenceAuditError() from None
            if _sha256(raw_bytes) != raw_hash:
                raise R2EvidenceAuditError()
            referenced_raw_paths.add(raw_path)
            raw_size = len(raw_bytes)
        projected_calls.append(
            {
                "call_id": record.get("call_id"),
                "provider": record.get("provider"),
                "model": record.get("model"),
                "status": record.get("status"),
                "response_status": record.get("response_status"),
                "input_tokens": record.get("input_tokens"),
                "cached_input_tokens": record.get("cached_input_tokens"),
                "output_tokens": record.get("output_tokens"),
                "total_tokens": record.get("total_tokens"),
                "cost_usd": record.get("cost_usd"),
                "closed_error_code": record.get("closed_error_code"),
                "failure_category": record.get("failure_category"),
                "raw_output_path": raw_path,
                "raw_output_sha256": raw_hash,
                "raw_output_bytes": raw_size,
            }
        )

    raw_directory = resolved_root / R2_RAW_RELATIVE_DIRECTORY
    actual_raw_paths = (
        {
            path.relative_to(resolved_root).as_posix()
            for path in raw_directory.iterdir()
            if path.is_file()
        }
        if raw_directory.exists()
        else set()
    )
    if actual_raw_paths != referenced_raw_paths:
        raise R2EvidenceAuditError()

    return {
        "plan_version": ledger["plan_version"],
        "matrix_sha256": ledger["matrix_sha256"],
        "approved_ceiling_usd": ledger["approved_ceiling_usd"],
        "provider_calls_attempted": ledger["provider_calls_attempted"],
        "automatic_retry_count": ledger["automatic_retry_count"],
        "automatic_rerun_count": ledger["automatic_rerun_count"],
        "total_cost_usd": ledger["total_cost_usd"],
        "terminal_call_count": len(records),
        "pending_call_count": 0,
        "started_call_count": 0,
        "duplicate_call_count": 0,
        "summary": {
            "relative_path": R2_SUMMARY_RELATIVE_PATH,
            "bytes": len(summary_bytes),
            "sha256": _sha256(summary_bytes),
        },
        "ledger": {
            "relative_path": R2_LEDGER_RELATIVE_PATH,
            "bytes": len(ledger_bytes),
            "sha256": _sha256(ledger_bytes),
        },
        "calls": projected_calls,
    }


def _last_expected_json_syntax(error: json.JSONDecodeError) -> str | None:
    if error.msg.startswith("Unterminated string"):
        return "STRING_TERMINATOR"
    if error.msg in {"Expecting value", "Expecting ',' delimiter"}:
        return "VALUE_OR_CLOSING_TOKEN"
    if error.msg in {
        "Expecting property name enclosed in double quotes",
        "Expecting ':' delimiter",
    }:
        return "OBJECT_PROPERTY_OR_CLOSING_TOKEN"
    return None


def classify_openai_raw_output(
    root: Path,
    openai_record: Mapping[str, object],
) -> dict[str, object]:
    raw_path = openai_record.get("raw_output_path")
    raw_hash = openai_record.get("raw_output_sha256")
    if raw_path is None and raw_hash is None:
        return {
            "classification": OpenAIRawOutputClassification.NO_OUTPUT_TEXT.value,
            "utf8_bytes": 0,
            "sha256": None,
            "json_parse_status": "NOT_APPLICABLE",
            "post_validation_status": "NOT_APPLICABLE",
            "last_expected_syntax_type": None,
        }
    if type(raw_path) is not str or type(raw_hash) is not str:
        raise R2EvidenceAuditError()
    payload = _safe_artifact_path(root, raw_path).read_bytes()
    if _sha256(payload) != raw_hash:
        raise R2EvidenceAuditError()
    try:
        text = payload.decode("utf-8")
        json.loads(text)
    except UnicodeDecodeError:
        return {
            "classification": OpenAIRawOutputClassification.OTHER_CLOSED_FAILURE.value,
            "utf8_bytes": len(payload),
            "sha256": raw_hash,
            "json_parse_status": "INVALID_UTF8",
            "post_validation_status": "NOT_RUN",
            "last_expected_syntax_type": None,
        }
    except json.JSONDecodeError as error:
        syntax = _last_expected_json_syntax(error)
        classification = (
            OpenAIRawOutputClassification.TRUNCATED_JSON
            if syntax is not None and error.pos >= max(0, len(text) - 2)
            else OpenAIRawOutputClassification.OTHER_CLOSED_FAILURE
        )
        return {
            "classification": classification.value,
            "utf8_bytes": len(payload),
            "sha256": raw_hash,
            "json_parse_status": "FAILED",
            "post_validation_status": "NOT_RUN",
            "last_expected_syntax_type": syntax,
        }

    provider_status = OpenAIResponseStatus.COMPLETED
    status_value = openai_record.get("provider_response_status")
    if status_value == OpenAIResponseStatus.INCOMPLETE.value:
        provider_status = OpenAIResponseStatus.INCOMPLETE
    reason_value = openai_record.get("incomplete_reason")
    reason = next(
        (
            item
            for item in OpenAIIncompleteReason
            if item.value == reason_value
        ),
        OpenAIIncompleteReason.NONE,
    )
    call = R2_CANARY_CALL_MATRIX[0]
    try:
        _map_response(
            request=_review_request(call),
            response=OpenAIResponsesResponse(
                status=provider_status,
                output_text=text,
                incomplete_reason=reason,
            ),
            provider_profile=_provider_profile(call.provider),
            model_profile=_model_profile(call),
        )
    except ReviewPortError:
        classification = OpenAIRawOutputClassification.PARSEABLE_CONTRACT_MISMATCH
        post_validation = "FAILED"
    else:
        classification = (
            OpenAIRawOutputClassification.PARSEABLE_COMPLETE_BUT_INCOMPLETE_STATUS
            if provider_status is OpenAIResponseStatus.INCOMPLETE
            else OpenAIRawOutputClassification.OTHER_CLOSED_FAILURE
        )
        post_validation = "PASSED"
    return {
        "classification": classification.value,
        "utf8_bytes": len(payload),
        "sha256": raw_hash,
        "json_parse_status": "PASSED",
        "post_validation_status": post_validation,
        "last_expected_syntax_type": None,
    }


def audit_anthropic_canary_reuse() -> dict[str, object]:
    logical_call = next(
        call
        for call in PEDAGOGICAL_CALIBRATION_CALL_MATRIX
        if call.call_id == "cal.score.anchor.scn-01.a.clarity.r1"
    )
    canary_call = R2_CANARY_CALL_MATRIX[1]
    anchor = anchor_by_id("cal.scn-01.a")
    candidate = anchor.candidate_projection()
    logical_observation = _anthropic_observation(
        logical_call,
        dependency_candidate=None,
    )
    canary_observation = _anthropic_observation(
        canary_call,
        dependency_candidate=candidate,
    )
    logical_request = build_anthropic_scoring_request(
        observations=(logical_observation,),
        model=logical_call.model,
        max_tokens=logical_call.max_output_tokens,
    )
    canary_request = build_anthropic_scoring_request(
        observations=(canary_observation,),
        model=canary_call.model,
        max_tokens=canary_call.max_output_tokens,
    )
    anchor_bytes = candidate.encode("utf-8")
    logical_observation_bytes = logical_request.input_json.encode("utf-8")
    canary_observation_bytes = canary_request.input_json.encode("utf-8")
    logical_schema_bytes = json.dumps(
        logical_request.output_schema,
        separators=(",", ":"),
        sort_keys=True,
    ).encode()
    canary_schema_bytes = json.dumps(
        canary_request.output_schema,
        separators=(",", ":"),
        sort_keys=True,
    ).encode()
    comparisons = {
        "criterion": logical_call.criterion_refs == canary_call.criterion_refs,
        "scenario": logical_call.scenario_code == canary_call.scenario_code,
        "anchor": logical_call.input_refs == ("anchor:cal.scn-01.a",),
        "observation_serialization": (
            logical_observation_bytes == canary_observation_bytes
        ),
        "model_code": logical_call.model == canary_call.model,
        "model_profile": (
            logical_call.model_profile_id == canary_call.model_profile_id
        ),
        "schema_fingerprint": logical_schema_bytes == canary_schema_bytes,
        "max_output_tokens": (
            logical_call.max_output_tokens == canary_call.max_output_tokens
        ),
    }
    reusable = all(comparisons.values())
    return {
        "logical_g2_call_id": logical_call.call_id,
        "r2_canary_call_id": canary_call.call_id,
        "criterion_ref": logical_call.criterion_refs[0],
        "scenario_code": logical_call.scenario_code,
        "anchor_id": anchor.anchor_id,
        "anchor_bytes": len(anchor_bytes),
        "anchor_sha256": _sha256(anchor_bytes),
        "logical_observation_bytes": len(logical_observation_bytes),
        "logical_observation_sha256": _sha256(logical_observation_bytes),
        "canary_observation_bytes": len(canary_observation_bytes),
        "canary_observation_sha256": _sha256(canary_observation_bytes),
        "model_code": logical_call.model,
        "model_profile_id": logical_call.model_profile_id,
        "schema_sha256": _sha256(logical_schema_bytes),
        "max_output_tokens": logical_call.max_output_tokens,
        "comparisons": comparisons,
        "anthropic_canary_reusable_as_g2_score": reusable,
        "anthropic_family_readiness": "PASSED",
    }
