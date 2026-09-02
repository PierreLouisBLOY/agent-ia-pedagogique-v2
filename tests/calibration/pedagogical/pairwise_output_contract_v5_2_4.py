"""Offline-only V5.2.4 comprehensive bounds contract for pairwise output.

The provider-neutral V5 scorer, semantic gate, call specifications, and transfer
projections remain unchanged.  This versioned parser widens both pairwise
locators after an observed 80-character locator exceeded the former 64-character
bound.  It also adds a fail-closed total UTF-8 response-size ceiling.  The module
contains no credential resolver or provider transport.
"""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Callable, Mapping
from copy import deepcopy
from dataclasses import asdict, dataclass
from decimal import ROUND_CEILING, Decimal
from enum import StrEnum
from typing import NoReturn, cast

from tests.calibration.pedagogical.pairwise_output_contract_v5_2_3 import (
    EXPECTED_V5_2_3_PAIRWISE_OUTPUT_CONTRACT_SHA256,
    v5_2_3_pairwise_output_contract_sha256,
)
from tests.calibration.pedagogical.pricing import MODEL_PRICE_BY_NAME
from tests.calibration.pedagogical.scorer_contract_v5 import (
    MAX_DIFFERENCES,
    MAX_LOCATOR_CHARACTERS,
    MAX_RATIONALE_CHARACTERS,
    V5Confidence,
    V5ContractError,
    V5ContractErrorCode,
    V5DifferenceSignificance,
    V5FavoredCandidate,
    V5PairwiseDecision,
)
from tests.calibration.pedagogical.semantic_integration_v5 import (
    V5CallContract,
    V5LogicalCallSpec,
)
from tests.providers.anthropic.contracts import (
    AnthropicScoringResponse,
    AnthropicStopReason,
)

V5_2_4_PAIRWISE_OUTPUT_CONTRACT_VERSION = (
    "12.16-g2-v5.2.4-comprehensive-pairwise-bounds-v1"
)
OLD_PAIRWISE_LOCATOR_CHARACTERS = MAX_LOCATOR_CHARACTERS
MAX_PAIRWISE_LOCATOR_CHARACTERS = 128
MAX_PAIRWISE_DIFFERENCE_OBSERVATION_CHARACTERS = 256
MAX_PAIRWISE_RATIONALE_CHARACTERS = MAX_RATIONALE_CHARACTERS
MAX_PAIRWISE_STRUCTURED_OUTPUT_BYTES = 8_192
EXPECTED_V5_2_4_PAIRWISE_OUTPUT_CONTRACT_SHA256 = (
    "8a40ce2abfbb8fce7b1dd22526d8a30322f6f13749817fe6443c414e4a89b444"
)
LIVE_PROVIDER_RECALIBRATION_AUTHORIZED = False

_SAFE_TOKEN = re.compile(r"^[A-Za-z0-9_. -]{1,64}$")
_SENSITIVE_TOKEN = re.compile(
    r"(?i)(?:secret|credential|password|api[_ -]?key|bearer|sk-ant-|sk-proj-)"
)
_MISSING = object()
_ALIASES = {"decision": {"A": "A_BETTER", "B": "B_BETTER", "EQUAL": "TIE"}}
_AMBIGUOUS_ALIASES = {"decision": {"BETTER": ("A_BETTER", "B_BETTER")}}


class V524PairwiseParserErrorCode(StrEnum):
    INVALID_JSON = "INVALID_JSON"
    MISSING_FIELD = "MISSING_FIELD"
    EXTRA_FIELD = "EXTRA_FIELD"
    INVALID_TYPE = "INVALID_TYPE"
    UNKNOWN_VALUE = "UNKNOWN_VALUE"
    AMBIGUOUS_ALIAS = "AMBIGUOUS_ALIAS"
    OUT_OF_BOUNDS = "OUT_OF_BOUNDS"
    STRUCTURED_OUTPUT_TOO_LARGE = "STRUCTURED_OUTPUT_TOO_LARGE"
    RESPONSE_TRUNCATED = "RESPONSE_TRUNCATED"
    CANONICAL_CONTRACT_REJECTED = "CANONICAL_CONTRACT_REJECTED"
    USAGE_UNAVAILABLE = "USAGE_UNAVAILABLE"


@dataclass(frozen=True, slots=True)
class V524PairwiseParserDiagnostic:
    error_code: V524PairwiseParserErrorCode
    field_path: str
    expected_type: str
    observed_type: str
    expected_constraint: str
    observed_value: str | int | None
    observed_value_sha256: str | None
    observed_length: int | None
    response_content_sha256: str
    stop_reason: str | None
    parser_schema_status: str = "FAIL"

    def safe_payload(self) -> dict[str, object]:
        payload = asdict(self)
        payload["error_code"] = self.error_code.value
        payload["raw_response_included"] = False
        return payload


class V524PairwiseParserError(ValueError):
    """Fail-closed parser error that never stores raw response content."""

    diagnostic: V524PairwiseParserDiagnostic

    def __init__(self, diagnostic: V524PairwiseParserDiagnostic) -> None:
        if type(diagnostic) is not V524PairwiseParserDiagnostic:
            raise TypeError("diagnostic must be V524PairwiseParserDiagnostic")
        self.diagnostic = diagnostic
        super().__init__(diagnostic.error_code.value)


@dataclass(frozen=True, slots=True)
class V524PairwiseDifference:
    locator_a: str
    locator_b: str
    observation: str
    significance: V5DifferenceSignificance
    favored_candidate: V5FavoredCandidate

    def __post_init__(self) -> None:
        _bounded_text_value(self.locator_a, MAX_PAIRWISE_LOCATOR_CHARACTERS)
        _bounded_text_value(self.locator_b, MAX_PAIRWISE_LOCATOR_CHARACTERS)
        _bounded_text_value(
            self.observation,
            MAX_PAIRWISE_DIFFERENCE_OBSERVATION_CHARACTERS,
        )
        if type(self.significance) is not V5DifferenceSignificance:
            raise TypeError("significance must be closed")
        if type(self.favored_candidate) is not V5FavoredCandidate:
            raise TypeError("favored_candidate must be closed")


@dataclass(frozen=True, slots=True)
class V524PairwiseOutcome:
    differences: tuple[V524PairwiseDifference, ...]
    decision: V5PairwiseDecision
    confidence: V5Confidence
    rationale: str

    def __post_init__(self) -> None:
        if not self.differences or len(self.differences) > MAX_DIFFERENCES:
            raise ValueError("pairwise differences must be non-empty and bounded")
        if any(type(item) is not V524PairwiseDifference for item in self.differences):
            raise TypeError("differences must contain V524PairwiseDifference")
        if type(self.decision) is not V5PairwiseDecision:
            raise TypeError("decision must be closed")
        if type(self.confidence) is not V5Confidence:
            raise TypeError("confidence must be closed")
        _bounded_text_value(self.rationale, MAX_PAIRWISE_RATIONALE_CHARACTERS)
        _validate_pairwise_decision(self.differences, self.decision)


def v5_2_4_pairwise_output_schema() -> dict[str, object]:
    """Return the isolated V5.2.4 pairwise acceptance schema."""

    difference = {
        "type": "object",
        "properties": {
            "locator_a": {
                "type": "string",
                "minLength": 1,
                "maxLength": MAX_PAIRWISE_LOCATOR_CHARACTERS,
            },
            "locator_b": {
                "type": "string",
                "minLength": 1,
                "maxLength": MAX_PAIRWISE_LOCATOR_CHARACTERS,
            },
            "observation": {
                "type": "string",
                "minLength": 1,
                "maxLength": MAX_PAIRWISE_DIFFERENCE_OBSERVATION_CHARACTERS,
            },
            "significance": {
                "type": "string",
                "enum": [item.value for item in V5DifferenceSignificance],
            },
            "favored_candidate": {
                "type": "string",
                "enum": [item.value for item in V5FavoredCandidate],
            },
        },
        "required": [
            "locator_a",
            "locator_b",
            "observation",
            "significance",
            "favored_candidate",
        ],
        "additionalProperties": False,
    }
    return {
        "type": "object",
        "properties": {
            "differences": {
                "type": "array",
                "items": difference,
                "minItems": 1,
                "maxItems": MAX_DIFFERENCES,
            },
            "decision": {
                "type": "string",
                "enum": [item.value for item in V5PairwiseDecision],
            },
            "confidence": {
                "type": "string",
                "enum": [item.value for item in V5Confidence],
            },
            "rationale": {
                "type": "string",
                "minLength": 1,
                "maxLength": MAX_PAIRWISE_RATIONALE_CHARACTERS,
            },
        },
        "required": ["differences", "decision", "confidence", "rationale"],
        "additionalProperties": False,
    }


def v5_2_4_pairwise_output_contract_sha256() -> str:
    """Hash every V5.2.4 parser rule independently of call input."""

    payload = {
        "version": V5_2_4_PAIRWISE_OUTPUT_CONTRACT_VERSION,
        "compatibility_scope": "PAIRWISE_OUTPUT_PARSER_ONLY",
        "base_contract_sha256": v5_2_3_pairwise_output_contract_sha256(),
        "bounds": {
            "structured_output_utf8_bytes": [1, MAX_PAIRWISE_STRUCTURED_OUTPUT_BYTES],
            "difference_count": [1, MAX_DIFFERENCES],
            "locator_a": [1, MAX_PAIRWISE_LOCATOR_CHARACTERS],
            "locator_b": [1, MAX_PAIRWISE_LOCATOR_CHARACTERS],
            "difference_observation": [
                1,
                MAX_PAIRWISE_DIFFERENCE_OBSERVATION_CHARACTERS,
            ],
            "rationale": [1, MAX_PAIRWISE_RATIONALE_CHARACTERS],
        },
        "normalization": {
            "bounded_text": "strip-outer-whitespace-only",
            "enum": "strip-uppercase-hyphen-and-whitespace-to-underscore",
            "unknown": "FAIL",
            "ambiguous": "FAIL",
            "over_bound": "FAIL",
            "truncation": "FORBIDDEN",
        },
        "semantic_invariants": (
            "PAIRWISE_TIE_MATERIAL_DIFFERENCE",
            "PAIRWISE_WINNER_UNSUPPORTED",
            "PAIRWISE_MATERIAL_CONFLICT",
        ),
        "schema": v5_2_4_pairwise_output_schema(),
        "usage_before_parse": True,
        "raw_response_persistence": False,
        "provider_transport_present": False,
        "live_authorized": False,
    }
    digest = _sha256(_canonical_json(payload).encode("utf-8"))
    if (
        EXPECTED_V5_2_4_PAIRWISE_OUTPUT_CONTRACT_SHA256 != "TO_BE_COMPUTED"
        and digest != EXPECTED_V5_2_4_PAIRWISE_OUTPUT_CONTRACT_SHA256
    ):
        raise RuntimeError("V5_2_4_PAIRWISE_OUTPUT_CONTRACT_SHA256_MISMATCH")
    return digest


def parse_v5_2_4_pairwise_call_result(
    spec: V5LogicalCallSpec,
    output_text: str,
    *,
    stop_reason: AnthropicStopReason | None,
) -> V524PairwiseOutcome:
    """Parse one pairwise response under the comprehensive V5.2.4 bounds."""

    if spec.contract is not V5CallContract.V5_DIRECT_PAIRWISE:
        raise ValueError("V5.2.4 output compatibility is pairwise-only")
    response_hash = _response_hash(output_text)
    stop = stop_reason.value if stop_reason is not None else None
    if stop_reason is AnthropicStopReason.MAX_TOKENS:
        _fail(
            V524PairwiseParserErrorCode.RESPONSE_TRUNCATED,
            "$",
            "complete JSON object",
            "truncated_response",
            "stop_reason must not be max_tokens",
            stop,
            response_hash,
            stop,
        )
    if type(output_text) is str:
        encoded_length = len(output_text.encode("utf-8"))
        if not 1 <= encoded_length <= MAX_PAIRWISE_STRUCTURED_OUTPUT_BYTES:
            _fail(
                V524PairwiseParserErrorCode.STRUCTURED_OUTPUT_TOO_LARGE,
                "$",
                "UTF-8 JSON object",
                "integer",
                f"UTF-8 bytes 1..{MAX_PAIRWISE_STRUCTURED_OUTPUT_BYTES}",
                encoded_length,
                response_hash,
                stop,
            )
    payload = _json_object(output_text, response_hash, stop)
    normalized = _adapt_pairwise(payload, response_hash, stop)
    try:
        raw_differences = cast(list[dict[str, object]], normalized["differences"])
        differences = tuple(
            V524PairwiseDifference(
                locator_a=cast(str, item["locator_a"]),
                locator_b=cast(str, item["locator_b"]),
                observation=cast(str, item["observation"]),
                significance=V5DifferenceSignificance(cast(str, item["significance"])),
                favored_candidate=V5FavoredCandidate(
                    cast(str, item["favored_candidate"])
                ),
            )
            for item in raw_differences
        )
        return V524PairwiseOutcome(
            differences=differences,
            decision=V5PairwiseDecision(cast(str, normalized["decision"])),
            confidence=V5Confidence(cast(str, normalized["confidence"])),
            rationale=cast(str, normalized["rationale"]),
        )
    except V5ContractError as error:
        path, expected = _canonical_error_location(error.code)
        _fail(
            V524PairwiseParserErrorCode.CANONICAL_CONTRACT_REJECTED,
            path,
            "canonical V5 pairwise semantic invariant",
            "schema_valid_object",
            expected,
            error.code.value,
            response_hash,
            stop,
        )
    except (TypeError, ValueError):
        _fail(
            V524PairwiseParserErrorCode.CANONICAL_CONTRACT_REJECTED,
            "$",
            "canonical V5.2.4 pairwise object",
            "schema_valid_object",
            "bounded and semantically coherent pairwise output",
            None,
            response_hash,
            stop,
        )


def process_anthropic_v5_2_4_pairwise_response(
    *,
    spec: V5LogicalCallSpec,
    response: AnthropicScoringResponse,
    persist_safe_record: Callable[[Mapping[str, object]], None],
) -> V524PairwiseOutcome:
    """Persist safe usage/cost before parsing; never persist raw text."""

    if not callable(persist_safe_record):
        raise TypeError("persist_safe_record must be callable")
    response_hash = _response_hash(response.output_text)
    usage_record = _usage_record(spec, response, response_hash)
    persist_safe_record(deepcopy(usage_record))
    try:
        outcome = parse_v5_2_4_pairwise_call_result(
            spec,
            response.output_text,
            stop_reason=response.stop_reason,
        )
    except V524PairwiseParserError as error:
        persist_safe_record(
            deepcopy(
                {
                    **usage_record,
                    "terminal_status": "FAILED",
                    "parser_schema_status": "FAIL",
                    "diagnostic": error.diagnostic.safe_payload(),
                }
            )
        )
        raise
    persist_safe_record(
        deepcopy(
            {
                **usage_record,
                "terminal_status": "COMPLETED",
                "parser_schema_status": "PASS",
                "diagnostic": None,
                "outcome_kind": "PAIRWISE",
                "score_level": None,
                "pairwise_disposition": outcome.decision.value,
            }
        )
    )
    return outcome


def _adapt_pairwise(
    payload: dict[str, object],
    response_hash: str,
    stop: str | None,
) -> dict[str, object]:
    expected = {"differences", "decision", "confidence", "rationale"}
    _exact_fields(payload, expected, "$", response_hash, stop)
    raw_differences = _list(
        payload["differences"],
        "$.differences",
        1,
        MAX_DIFFERENCES,
        response_hash,
        stop,
    )
    item_fields = {
        "locator_a",
        "locator_b",
        "observation",
        "significance",
        "favored_candidate",
    }
    differences: list[dict[str, object]] = []
    for index, raw in enumerate(raw_differences):
        path = f"$.differences[{index}]"
        item = _object(raw, path, response_hash, stop)
        _exact_fields(item, item_fields, path, response_hash, stop)
        differences.append(
            {
                "locator_a": _text(
                    item["locator_a"],
                    f"{path}.locator_a",
                    MAX_PAIRWISE_LOCATOR_CHARACTERS,
                    response_hash,
                    stop,
                ),
                "locator_b": _text(
                    item["locator_b"],
                    f"{path}.locator_b",
                    MAX_PAIRWISE_LOCATOR_CHARACTERS,
                    response_hash,
                    stop,
                ),
                "observation": _text(
                    item["observation"],
                    f"{path}.observation",
                    MAX_PAIRWISE_DIFFERENCE_OBSERVATION_CHARACTERS,
                    response_hash,
                    stop,
                ),
                "significance": _enum(
                    item["significance"],
                    V5DifferenceSignificance,
                    "significance",
                    f"{path}.significance",
                    response_hash,
                    stop,
                ),
                "favored_candidate": _enum(
                    item["favored_candidate"],
                    V5FavoredCandidate,
                    "favored_candidate",
                    f"{path}.favored_candidate",
                    response_hash,
                    stop,
                ),
            }
        )
    return {
        "differences": differences,
        "decision": _enum(
            payload["decision"],
            V5PairwiseDecision,
            "decision",
            "$.decision",
            response_hash,
            stop,
        ),
        "confidence": _enum(
            payload["confidence"],
            V5Confidence,
            "confidence",
            "$.confidence",
            response_hash,
            stop,
        ),
        "rationale": _text(
            payload["rationale"],
            "$.rationale",
            MAX_PAIRWISE_RATIONALE_CHARACTERS,
            response_hash,
            stop,
        ),
    }


def _validate_pairwise_decision(
    differences: tuple[V524PairwiseDifference, ...],
    decision: V5PairwiseDecision,
) -> None:
    material = tuple(
        item
        for item in differences
        if item.significance is V5DifferenceSignificance.MATERIAL
    )
    favored = {
        item.favored_candidate
        for item in material
        if item.favored_candidate in {V5FavoredCandidate.A, V5FavoredCandidate.B}
    }
    if favored == {V5FavoredCandidate.A, V5FavoredCandidate.B}:
        raise V5ContractError(V5ContractErrorCode.PAIRWISE_MATERIAL_CONFLICT)
    if decision is V5PairwiseDecision.TIE and material:
        raise V5ContractError(V5ContractErrorCode.PAIRWISE_TIE_MATERIAL_DIFFERENCE)
    if decision is V5PairwiseDecision.A_BETTER and V5FavoredCandidate.A not in favored:
        raise V5ContractError(V5ContractErrorCode.PAIRWISE_WINNER_UNSUPPORTED)
    if decision is V5PairwiseDecision.B_BETTER and V5FavoredCandidate.B not in favored:
        raise V5ContractError(V5ContractErrorCode.PAIRWISE_WINNER_UNSUPPORTED)


def _bounded_text_value(value: str, maximum: int) -> None:
    if type(value) is not str or not value or value != value.strip() or len(value) > maximum:
        raise ValueError("text is empty, untrimmed, or exceeds its bound")


def _usage_record(
    spec: V5LogicalCallSpec,
    response: AnthropicScoringResponse,
    response_hash: str,
) -> dict[str, object]:
    if response.input_tokens is None or response.output_tokens is None:
        _fail(
            V524PairwiseParserErrorCode.USAGE_UNAVAILABLE,
            "$.usage",
            "non-negative integer input_tokens and output_tokens",
            "missing_usage",
            "exact usage required before parsing",
            None,
            response_hash,
            response.stop_reason.value if response.stop_reason else None,
        )
    cached = response.cached_input_tokens or 0
    if cached > response.input_tokens:
        _fail(
            V524PairwiseParserErrorCode.USAGE_UNAVAILABLE,
            "$.usage.cached_input_tokens",
            "integer <= input_tokens",
            "integer",
            f"0..{response.input_tokens}",
            cached,
            response_hash,
            response.stop_reason.value if response.stop_reason else None,
        )
    quote = MODEL_PRICE_BY_NAME[spec.call.model]
    regular = response.input_tokens - cached
    exact_cost = _money(
        (
            Decimal(regular) * quote.input_usd_per_million_tokens
            + Decimal(cached) * quote.cached_input_usd_per_million_tokens
            + Decimal(response.output_tokens) * quote.output_usd_per_million_tokens
        )
        / Decimal(1_000_000)
    )
    return {
        "call_id": spec.call.call_id,
        "provider": "anthropic",
        "model": spec.call.model,
        "usage": {
            "input_tokens": response.input_tokens,
            "cached_input_tokens": cached,
            "output_tokens": response.output_tokens,
            "total_tokens": response.total_tokens,
            "thinking_tokens": response.thinking_tokens,
        },
        "measured_cost_usd": format(exact_cost, "f"),
        "stop_reason": response.stop_reason.value if response.stop_reason else None,
        "response_content_sha256": response_hash,
        "response_length": len(response.output_text),
        "parser_schema_status": "PENDING",
        "terminal_status": "RESPONSE_RECEIVED",
        "raw_response_persisted": False,
    }


def _enum(
    raw: object,
    enum_type: type[StrEnum],
    alias_group: str,
    path: str,
    response_hash: str,
    stop: str | None,
) -> str:
    if type(raw) is not str:
        _fail(
            V524PairwiseParserErrorCode.INVALID_TYPE,
            path,
            "string",
            _type_name(raw),
            _enum_constraint(enum_type),
            raw,
            response_hash,
            stop,
        )
    token = re.sub(r"[_\s-]+", "_", raw.strip().upper())
    ambiguous = _AMBIGUOUS_ALIASES.get(alias_group, {}).get(token)
    if ambiguous is not None:
        _fail(
            V524PairwiseParserErrorCode.AMBIGUOUS_ALIAS,
            path,
            "string",
            "string",
            f"ambiguous between {','.join(ambiguous)}",
            raw,
            response_hash,
            stop,
        )
    token = _ALIASES.get(alias_group, {}).get(token, token)
    if token not in {item.value for item in enum_type}:
        _fail(
            V524PairwiseParserErrorCode.UNKNOWN_VALUE,
            path,
            "string",
            "string",
            _enum_constraint(enum_type),
            raw,
            response_hash,
            stop,
        )
    return token


def _text(
    raw: object,
    path: str,
    maximum: int,
    response_hash: str,
    stop: str | None,
) -> str:
    if type(raw) is not str:
        _fail(
            V524PairwiseParserErrorCode.INVALID_TYPE,
            path,
            "string",
            _type_name(raw),
            f"trimmed length 1..{maximum}",
            raw,
            response_hash,
            stop,
        )
    normalized = raw.strip()
    if not 1 <= len(normalized) <= maximum:
        _fail(
            V524PairwiseParserErrorCode.OUT_OF_BOUNDS,
            path,
            "string",
            "string",
            f"trimmed length 1..{maximum}",
            raw,
            response_hash,
            stop,
        )
    return normalized


def _list(
    raw: object,
    path: str,
    minimum: int,
    maximum: int,
    response_hash: str,
    stop: str | None,
) -> list[object]:
    if type(raw) is not list:
        _fail(
            V524PairwiseParserErrorCode.INVALID_TYPE,
            path,
            "array",
            _type_name(raw),
            f"items {minimum}..{maximum}",
            raw,
            response_hash,
            stop,
        )
    if not minimum <= len(raw) <= maximum:
        _fail(
            V524PairwiseParserErrorCode.OUT_OF_BOUNDS,
            path,
            "array",
            "array",
            f"items {minimum}..{maximum}",
            raw,
            response_hash,
            stop,
        )
    return cast(list[object], raw)


def _object(
    raw: object,
    path: str,
    response_hash: str,
    stop: str | None,
) -> dict[str, object]:
    if type(raw) is not dict:
        _fail(
            V524PairwiseParserErrorCode.INVALID_TYPE,
            path,
            "object",
            _type_name(raw),
            "JSON object",
            raw,
            response_hash,
            stop,
        )
    return cast(dict[str, object], raw)


def _exact_fields(
    payload: dict[str, object],
    expected: set[str],
    path: str,
    response_hash: str,
    stop: str | None,
) -> None:
    missing = sorted(expected.difference(payload))
    if missing:
        field = missing[0]
        _fail(
            V524PairwiseParserErrorCode.MISSING_FIELD,
            f"{path}.{field}" if path != "$" else f"$.{field}",
            "required field",
            "missing",
            "field must be present",
            _MISSING,
            response_hash,
            stop,
        )
    extra = sorted(set(payload).difference(expected))
    if extra:
        field = extra[0]
        _fail(
            V524PairwiseParserErrorCode.EXTRA_FIELD,
            f"{path}.{field}" if path != "$" else f"$.{field}",
            "no additional property",
            _type_name(payload[field]),
            "additionalProperties=false",
            payload[field],
            response_hash,
            stop,
        )


def _json_object(
    output_text: str,
    response_hash: str,
    stop: str | None,
) -> dict[str, object]:
    if type(output_text) is not str:
        _fail(
            V524PairwiseParserErrorCode.INVALID_TYPE,
            "$",
            "string containing one JSON object",
            _type_name(output_text),
            "valid JSON",
            output_text,
            response_hash,
            stop,
        )
    try:
        payload = json.loads(output_text)
    except json.JSONDecodeError:
        _fail(
            V524PairwiseParserErrorCode.INVALID_JSON,
            "$",
            "JSON object",
            "invalid_json_string",
            "valid JSON object",
            output_text,
            response_hash,
            stop,
        )
    return _object(payload, "$", response_hash, stop)


def _canonical_error_location(code: V5ContractErrorCode) -> tuple[str, str]:
    mapping = {
        V5ContractErrorCode.PAIRWISE_TIE_MATERIAL_DIFFERENCE: (
            "$.decision",
            "TIE has no MATERIAL difference",
        ),
        V5ContractErrorCode.PAIRWISE_WINNER_UNSUPPORTED: (
            "$.decision",
            "winner supported by a MATERIAL difference",
        ),
        V5ContractErrorCode.PAIRWISE_MATERIAL_CONFLICT: (
            "$.differences",
            "no conflicting MATERIAL winners",
        ),
    }
    return mapping.get(code, ("$", code.value))


def _fail(
    code: V524PairwiseParserErrorCode,
    path: str,
    expected_type: str,
    observed_type: str,
    expected_constraint: str,
    observed: object,
    response_hash: str,
    stop: str | None,
) -> NoReturn:
    observed_value, observed_hash = _safe_observed(path, observed)
    length = len(observed) if isinstance(observed, (str, list, tuple, dict)) else None
    raise V524PairwiseParserError(
        V524PairwiseParserDiagnostic(
            error_code=code,
            field_path=path,
            expected_type=expected_type,
            observed_type=observed_type,
            expected_constraint=expected_constraint,
            observed_value=observed_value,
            observed_value_sha256=observed_hash,
            observed_length=length,
            response_content_sha256=response_hash,
            stop_reason=stop,
        )
    ) from None


def _safe_observed(path: str, observed: object) -> tuple[str | int | None, str | None]:
    if observed is _MISSING:
        return None, None
    allowlisted_suffixes = (
        ".confidence",
        ".decision",
        ".significance",
        ".favored_candidate",
    )
    if path == "$" and type(observed) is int:
        return observed, None
    if path.endswith(allowlisted_suffixes):
        if type(observed) is int:
            return observed, None
        if (
            type(observed) is str
            and _SAFE_TOKEN.fullmatch(observed) is not None
            and _SENSITIVE_TOKEN.search(observed) is None
        ):
            return observed, None
    return None, _sha256(_canonical_observed(observed))


def _canonical_observed(value: object) -> bytes:
    try:
        return _canonical_json(value).encode("utf-8")
    except TypeError:
        return f"<{_type_name(value)}>".encode("ascii")


def _response_hash(output_text: object) -> str:
    if type(output_text) is str:
        return _sha256(output_text.encode("utf-8"))
    return _sha256(f"<{_type_name(output_text)}>".encode("ascii"))


def _enum_constraint(enum_type: type[StrEnum]) -> str:
    return "enum{" + ",".join(item.value for item in enum_type) + "}"


def _type_name(value: object) -> str:
    if value is None:
        return "null"
    if type(value) is bool:
        return "boolean"
    if type(value) is int:
        return "integer"
    if type(value) is str:
        return "string"
    if type(value) is list:
        return "array"
    if type(value) is dict:
        return "object"
    return type(value).__name__


def _canonical_json(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"), sort_keys=True)


def _sha256(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _money(value: Decimal) -> Decimal:
    return value.quantize(Decimal("0.000001"), rounding=ROUND_CEILING)


if OLD_PAIRWISE_LOCATOR_CHARACTERS != 64:
    raise RuntimeError("V5_2_4_OLD_LOCATOR_BOUND_DRIFT")
if (
    v5_2_3_pairwise_output_contract_sha256()
    != EXPECTED_V5_2_3_PAIRWISE_OUTPUT_CONTRACT_SHA256
):
    raise RuntimeError("V5_2_4_BASE_CONTRACT_IDENTITY_MISMATCH")
