from __future__ import annotations

import json
from typing import Final, cast

from calibration_tooling.contracts.errors import CalibrationErrorCode, fail_contract
from calibration_tooling.contracts.models import (
    MAX_PROVIDER_OUTPUT_BYTES,
    AbsoluteObservationResult,
    AbsoluteObservationSpec,
    AbsoluteScoreStatus,
    CalibrationObservationResult,
    CalibrationObservationSpec,
    ObservationKind,
    PairwiseDecision,
    PairwiseObservationResult,
    PairwiseObservationSpec,
    RawProviderResponse,
)

ACTIVE_PARSER_TARGET: Final = "calibration_tooling.contracts.parser.v1"
ACTIVE_OUTPUT_SCHEMA_VERSION: Final = "calibration-output.v1"
_ABSOLUTE_FIELDS: Final = frozenset(
    {"schema_version", "call_ref", "kind", "status", "score_level"}
)
_PAIRWISE_FIELDS: Final = frozenset(
    {"schema_version", "call_ref", "kind", "decision"}
)


def active_output_schema(kind: ObservationKind) -> dict[str, object]:
    """Return the sole machine-readable schema definition consumed by adapters."""

    if kind is ObservationKind.ABSOLUTE:
        return {
            "type": "object",
            "properties": {
                "schema_version": {
                    "type": "string",
                    "const": ACTIVE_OUTPUT_SCHEMA_VERSION,
                },
                "call_ref": {"type": "string", "minLength": 1, "maxLength": 128},
                "kind": {"type": "string", "const": ObservationKind.ABSOLUTE.value},
                "status": {
                    "type": "string",
                    "enum": [item.value for item in AbsoluteScoreStatus],
                },
                "score_level": {"type": ["integer", "null"], "minimum": 0, "maximum": 4},
            },
            "required": sorted(_ABSOLUTE_FIELDS),
            "additionalProperties": False,
        }
    if kind is ObservationKind.PAIRWISE:
        return {
            "type": "object",
            "properties": {
                "schema_version": {
                    "type": "string",
                    "const": ACTIVE_OUTPUT_SCHEMA_VERSION,
                },
                "call_ref": {"type": "string", "minLength": 1, "maxLength": 128},
                "kind": {"type": "string", "const": ObservationKind.PAIRWISE.value},
                "decision": {
                    "type": "string",
                    "enum": [item.value for item in PairwiseDecision],
                },
            },
            "required": sorted(_PAIRWISE_FIELDS),
            "additionalProperties": False,
        }
    raise TypeError("kind must be an ObservationKind")


class CanonicalCalibrationOutputParser:
    """Strict active parser: exact fields, bounded bytes and no normalization."""

    def parse(
        self,
        spec: CalibrationObservationSpec,
        response: RawProviderResponse,
    ) -> CalibrationObservationResult:
        if response.call_ref != spec.call_ref:
            fail_contract(CalibrationErrorCode.IDENTITY_MISMATCH)
        if not response.complete:
            fail_contract(CalibrationErrorCode.RESPONSE_TRUNCATED)
        size = len(response.output_text.encode("utf-8"))
        if not 1 <= size <= MAX_PROVIDER_OUTPUT_BYTES:
            fail_contract(CalibrationErrorCode.RESPONSE_TOO_LARGE)
        payload = _json_object(response.output_text)
        if type(spec) is AbsoluteObservationSpec:
            return _parse_absolute(spec, payload)
        if type(spec) is PairwiseObservationSpec:
            return _parse_pairwise(spec, payload)
        fail_contract(CalibrationErrorCode.INVALID_CONTRACT)


def _parse_absolute(
    spec: AbsoluteObservationSpec,
    payload: dict[str, object],
) -> AbsoluteObservationResult:
    _require_exact_fields(payload, _ABSOLUTE_FIELDS)
    _require_identity(payload, spec.call_ref.value, "ABSOLUTE")
    status_raw = payload["status"]
    if type(status_raw) is not str:
        fail_contract(CalibrationErrorCode.INVALID_PAYLOAD)
    try:
        status = AbsoluteScoreStatus(status_raw)
    except ValueError:
        fail_contract(CalibrationErrorCode.INVALID_PAYLOAD)
    score_level = payload["score_level"]
    if status is AbsoluteScoreStatus.SCORED:
        if type(score_level) is not int or not 0 <= score_level <= 4:
            fail_contract(CalibrationErrorCode.INVALID_PAYLOAD)
        return AbsoluteObservationResult(spec.call_ref, status, score_level)
    if score_level is not None:
        fail_contract(CalibrationErrorCode.INVALID_PAYLOAD)
    return AbsoluteObservationResult(spec.call_ref, status, None)


def _parse_pairwise(
    spec: PairwiseObservationSpec,
    payload: dict[str, object],
) -> PairwiseObservationResult:
    _require_exact_fields(payload, _PAIRWISE_FIELDS)
    _require_identity(payload, spec.call_ref.value, "PAIRWISE")
    decision_raw = payload["decision"]
    if type(decision_raw) is not str:
        fail_contract(CalibrationErrorCode.INVALID_PAYLOAD)
    try:
        decision = PairwiseDecision(decision_raw)
    except ValueError:
        fail_contract(CalibrationErrorCode.INVALID_PAYLOAD)
    return PairwiseObservationResult(spec.call_ref, decision)


def _require_identity(
    payload: dict[str, object],
    expected_call_ref: str,
    expected_kind: str,
) -> None:
    if payload["schema_version"] != ACTIVE_OUTPUT_SCHEMA_VERSION:
        fail_contract(CalibrationErrorCode.INVALID_CONTRACT)
    if payload["call_ref"] != expected_call_ref:
        fail_contract(CalibrationErrorCode.IDENTITY_MISMATCH)
    if payload["kind"] != expected_kind:
        fail_contract(CalibrationErrorCode.RESULT_MISMATCH)


def _require_exact_fields(
    payload: dict[str, object],
    expected: frozenset[str],
) -> None:
    if set(payload) != expected:
        fail_contract(CalibrationErrorCode.INVALID_PAYLOAD)


def _json_object(output_text: str) -> dict[str, object]:
    try:
        decoded = cast(object, json.loads(output_text))
    except (json.JSONDecodeError, UnicodeDecodeError):
        fail_contract(CalibrationErrorCode.INVALID_PAYLOAD)
    if type(decoded) is not dict:
        fail_contract(CalibrationErrorCode.INVALID_PAYLOAD)
    payload = cast(dict[object, object], decoded)
    if any(type(key) is not str for key in payload):
        fail_contract(CalibrationErrorCode.INVALID_PAYLOAD)
    return cast(dict[str, object], payload)
