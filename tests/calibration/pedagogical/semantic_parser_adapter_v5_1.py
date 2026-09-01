"""Offline V5.1 provider-response adaptation and safe parser telemetry.

This module has no credential resolver and no transport.  It normalizes only
explicit, unambiguous provider response variants before dispatching to the
unchanged canonical V5 parser.  Safe usage metadata is persisted before parsing.
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

from tests.calibration.pedagogical.pricing import MODEL_PRICE_BY_NAME
from tests.calibration.pedagogical.scorer_contract_v5 import (
    MAX_DEFECT_ITEMS,
    MAX_DIFFERENCES,
    MAX_EVIDENCE_ITEMS,
    MAX_LOCATOR_CHARACTERS,
    MAX_OBSERVATION_CHARACTERS,
    MAX_RATIONALE_CHARACTERS,
    V5_RUBRIC_BY_CRITERION,
    V5Confidence,
    V5ContractError,
    V5DefectSeverity,
    V5DifferenceSignificance,
    V5FavoredCandidate,
    V5PairwiseDecision,
    V5PairwiseOutcome,
    V5ScorerOutcome,
    V5ScoreStatus,
    parse_v5_pairwise_output,
    parse_v5_score_output,
)
from tests.calibration.pedagogical.semantic_integration_v5 import (
    V5CallContract,
    V5LogicalCallSpec,
)
from tests.providers.anthropic.contracts import (
    AnthropicScoringResponse,
    AnthropicStopReason,
)

V5_1_PARSER_ADAPTER_VERSION = "12.16-g2-v5.1-parser-adapter-v1"
EXPECTED_V5_1_PARSER_CONTRACT_SHA256 = (
    "2037ce91acdf3859408effbe6a5a70d4ac84e6cf58b812b8d3ac9772817f057b"
)
LIVE_PROVIDER_RECALIBRATION_AUTHORIZED = False

_SAFE_TOKEN = re.compile(r"^[A-Za-z0-9_. -]{1,64}$")
_SENSITIVE_TOKEN = re.compile(
    r"(?i)(?:secret|credential|password|api[_ -]?key|bearer|sk-ant-|sk-proj-)"
)
_MISSING = object()

_ALIASES: dict[str, dict[str, str]] = {
    "decision": {"A": "A_BETTER", "B": "B_BETTER", "EQUAL": "TIE"},
}
_AMBIGUOUS_ALIASES: dict[str, dict[str, tuple[str, ...]]] = {
    "decision": {"BETTER": ("A_BETTER", "B_BETTER")},
}


class V51ParserErrorCode(StrEnum):
    INVALID_JSON = "INVALID_JSON"
    MISSING_FIELD = "MISSING_FIELD"
    EXTRA_FIELD = "EXTRA_FIELD"
    INVALID_TYPE = "INVALID_TYPE"
    UNKNOWN_VALUE = "UNKNOWN_VALUE"
    AMBIGUOUS_ALIAS = "AMBIGUOUS_ALIAS"
    OUT_OF_BOUNDS = "OUT_OF_BOUNDS"
    RESPONSE_TRUNCATED = "RESPONSE_TRUNCATED"
    CANONICAL_CONTRACT_REJECTED = "CANONICAL_CONTRACT_REJECTED"
    USAGE_UNAVAILABLE = "USAGE_UNAVAILABLE"


@dataclass(frozen=True, slots=True)
class V51ParserDiagnostic:
    error_code: V51ParserErrorCode
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


class V51ParserError(ValueError):
    """Closed parse error that stores diagnostics but never raw response text."""

    diagnostic: V51ParserDiagnostic

    def __init__(self, diagnostic: V51ParserDiagnostic) -> None:
        if type(diagnostic) is not V51ParserDiagnostic:
            raise TypeError("diagnostic must be V51ParserDiagnostic")
        self.diagnostic = diagnostic
        super().__init__(diagnostic.error_code.value)

    def __repr__(self) -> str:
        return (
            "V51ParserError("
            f"error_code={self.diagnostic.error_code.value!r}, "
            f"field_path={self.diagnostic.field_path!r})"
        )


def v5_1_parser_contract_sha256() -> str:
    payload = {
        "version": V5_1_PARSER_ADAPTER_VERSION,
        "normalization": {
            "enum": "strip-uppercase-hyphen-and-whitespace-to-underscore",
            "bounded_text": "strip-outer-whitespace-only",
            "check_id": "casefold-only-when-exact-canonical-check-id",
            "unknown": "FAIL",
            "ambiguous": "FAIL",
            "invalid_type": "FAIL",
            "missing_or_extra": "FAIL",
        },
        "aliases": _ALIASES,
        "ambiguous_aliases": _AMBIGUOUS_ALIASES,
        "diagnostic_fields": tuple(V51ParserDiagnostic.__dataclass_fields__),
        "error_codes": [item.value for item in V51ParserErrorCode],
        "usage_before_parse": True,
        "raw_response_persistence": False,
    }
    digest = _sha256(_canonical_json(payload).encode("utf-8"))
    if (
        EXPECTED_V5_1_PARSER_CONTRACT_SHA256 != "TO_BE_COMPUTED"
        and digest != EXPECTED_V5_1_PARSER_CONTRACT_SHA256
    ):
        raise RuntimeError("V5_1_PARSER_CONTRACT_SHA256_MISMATCH")
    return digest


def parse_v5_1_call_result(
    spec: V5LogicalCallSpec,
    output_text: str,
    *,
    stop_reason: AnthropicStopReason | None,
) -> V5ScorerOutcome | V5PairwiseOutcome:
    response_hash = _response_hash(output_text)
    stop = stop_reason.value if stop_reason is not None else None
    if stop_reason is AnthropicStopReason.MAX_TOKENS:
        _fail(
            V51ParserErrorCode.RESPONSE_TRUNCATED,
            "$",
            "complete JSON object",
            "truncated_response",
            "stop_reason must not be max_tokens",
            stop,
            response_hash,
            stop,
        )
    payload = _json_object(output_text, response_hash, stop)
    if spec.contract is V5CallContract.V5_ABSOLUTE_SCORE:
        normalized = _adapt_score(payload, spec.call.criterion_refs[0], response_hash, stop)
        parser_kind = "ABSOLUTE"
    elif spec.contract is V5CallContract.V5_DIRECT_PAIRWISE:
        normalized = _adapt_pairwise(payload, response_hash, stop)
        parser_kind = "PAIRWISE"
    else:
        raise ValueError("unchanged calls do not use the V5.1 response adapter")
    try:
        normalized_json = _canonical_json(normalized)
        if parser_kind == "ABSOLUTE":
            return parse_v5_score_output(normalized_json, spec.call.criterion_refs[0])
        return parse_v5_pairwise_output(normalized_json)
    except V5ContractError as error:
        path, expected = _canonical_error_location(error.code.value)
        _fail(
            V51ParserErrorCode.CANONICAL_CONTRACT_REJECTED,
            path,
            "canonical V5 semantic invariant",
            "schema_valid_object",
            expected,
            error.code.value,
            response_hash,
            stop,
        )


def process_anthropic_v5_1_response(
    *,
    spec: V5LogicalCallSpec,
    response: AnthropicScoringResponse,
    persist_safe_record: Callable[[Mapping[str, object]], None],
) -> V5ScorerOutcome | V5PairwiseOutcome:
    """Persist usage and cost before parsing; never persist ``output_text``."""

    if not callable(persist_safe_record):
        raise TypeError("persist_safe_record must be callable")
    response_hash = _response_hash(response.output_text)
    usage_record = _usage_record(spec, response, response_hash)
    persist_safe_record(deepcopy(usage_record))
    try:
        outcome = parse_v5_1_call_result(
            spec,
            response.output_text,
            stop_reason=response.stop_reason,
        )
    except V51ParserError as error:
        failed = {
            **usage_record,
            "terminal_status": "FAILED",
            "parser_schema_status": "FAIL",
            "diagnostic": error.diagnostic.safe_payload(),
        }
        persist_safe_record(deepcopy(failed))
        raise
    completed = {
        **usage_record,
        "terminal_status": "COMPLETED",
        "parser_schema_status": "PASS",
        "diagnostic": None,
        "outcome_kind": ("ABSOLUTE" if type(outcome) is V5ScorerOutcome else "PAIRWISE"),
        "score_level": (
            int(outcome.score_level)
            if type(outcome) is V5ScorerOutcome and outcome.score_level is not None
            else None
        ),
        "pairwise_disposition": (
            outcome.decision.value if type(outcome) is V5PairwiseOutcome else None
        ),
    }
    persist_safe_record(deepcopy(completed))
    return outcome


def _usage_record(
    spec: V5LogicalCallSpec,
    response: AnthropicScoringResponse,
    response_hash: str,
) -> dict[str, object]:
    if response.input_tokens is None or response.output_tokens is None:
        _fail(
            V51ParserErrorCode.USAGE_UNAVAILABLE,
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
            V51ParserErrorCode.USAGE_UNAVAILABLE,
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


def _adapt_score(
    payload: dict[str, object],
    criterion_ref: str,
    response_hash: str,
    stop: str | None,
) -> dict[str, object]:
    expected = {"status", "evidence", "defects", "score_level", "confidence", "rationale"}
    _exact_fields(payload, expected, "$", response_hash, stop)
    status = _enum(payload["status"], V5ScoreStatus, "status", "$.status", response_hash, stop)
    confidence = _enum(
        payload["confidence"],
        V5Confidence,
        "confidence",
        "$.confidence",
        response_hash,
        stop,
    )
    rationale = _text(
        payload["rationale"],
        "$.rationale",
        MAX_RATIONALE_CHARACTERS,
        response_hash,
        stop,
    )
    evidence_raw = _list(
        payload["evidence"], "$.evidence", 0, MAX_EVIDENCE_ITEMS, response_hash, stop
    )
    defects_raw = _list(payload["defects"], "$.defects", 0, MAX_DEFECT_ITEMS, response_hash, stop)
    try:
        allowed_checks = {
            item.check_id: item.check_id for item in V5_RUBRIC_BY_CRITERION[criterion_ref].checks
        }
    except KeyError:
        raise ValueError("criterion_ref must be canonical") from None
    allowed_casefold = {key.casefold(): value for key, value in allowed_checks.items()}
    evidence = [
        _evidence_item(
            item,
            f"$.evidence[{index}]",
            allowed_casefold,
            response_hash,
            stop,
            defect=False,
        )
        for index, item in enumerate(evidence_raw)
    ]
    defects = [
        _evidence_item(
            item,
            f"$.defects[{index}]",
            allowed_casefold,
            response_hash,
            stop,
            defect=True,
        )
        for index, item in enumerate(defects_raw)
    ]
    level = payload["score_level"]
    if level is not None:
        if type(level) is not int:
            _fail(
                V51ParserErrorCode.INVALID_TYPE,
                "$.score_level",
                "integer or null",
                _type_name(level),
                "integer 0..4 or null",
                level,
                response_hash,
                stop,
            )
        if not 0 <= level <= 4:
            _fail(
                V51ParserErrorCode.OUT_OF_BOUNDS,
                "$.score_level",
                "integer",
                "integer",
                "0..4",
                level,
                response_hash,
                stop,
            )
    if status == V5ScoreStatus.INCONCLUSIVE.value and (
        level is not None or confidence != V5Confidence.LOW.value
    ):
        _fail(
            V51ParserErrorCode.UNKNOWN_VALUE,
            "$.score_level",
            "null with LOW confidence",
            _type_name(level),
            "INCONCLUSIVE requires score_level=null and confidence=LOW",
            level,
            response_hash,
            stop,
        )
    return {
        "status": status,
        "evidence": evidence,
        "defects": defects,
        "score_level": level,
        "confidence": confidence,
        "rationale": rationale,
    }


def _adapt_pairwise(
    payload: dict[str, object], response_hash: str, stop: str | None
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
    differences: list[dict[str, object]] = []
    item_fields = {
        "locator_a",
        "locator_b",
        "observation",
        "significance",
        "favored_candidate",
    }
    for index, raw in enumerate(raw_differences):
        path = f"$.differences[{index}]"
        item = _object(raw, path, response_hash, stop)
        _exact_fields(item, item_fields, path, response_hash, stop)
        differences.append(
            {
                "locator_a": _text(
                    item["locator_a"],
                    f"{path}.locator_a",
                    MAX_LOCATOR_CHARACTERS,
                    response_hash,
                    stop,
                ),
                "locator_b": _text(
                    item["locator_b"],
                    f"{path}.locator_b",
                    MAX_LOCATOR_CHARACTERS,
                    response_hash,
                    stop,
                ),
                "observation": _text(
                    item["observation"],
                    f"{path}.observation",
                    MAX_OBSERVATION_CHARACTERS,
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
            MAX_RATIONALE_CHARACTERS,
            response_hash,
            stop,
        ),
    }


def _evidence_item(
    raw: object,
    path: str,
    allowed_checks: dict[str, str],
    response_hash: str,
    stop: str | None,
    *,
    defect: bool,
) -> dict[str, object]:
    item = _object(raw, path, response_hash, stop)
    fields = {"check_id", "locator", "observation"} | ({"severity"} if defect else set())
    _exact_fields(item, fields, path, response_hash, stop)
    raw_check = item["check_id"]
    if type(raw_check) is not str:
        _fail(
            V51ParserErrorCode.INVALID_TYPE,
            f"{path}.check_id",
            "string",
            _type_name(raw_check),
            "one canonical rubric check id",
            raw_check,
            response_hash,
            stop,
        )
    token = raw_check.strip().casefold()
    if token not in allowed_checks:
        _fail(
            V51ParserErrorCode.UNKNOWN_VALUE,
            f"{path}.check_id",
            "string",
            "string",
            "one canonical rubric check id",
            raw_check,
            response_hash,
            stop,
        )
    result: dict[str, object] = {
        "check_id": allowed_checks[token],
        "locator": _text(
            item["locator"],
            f"{path}.locator",
            MAX_LOCATOR_CHARACTERS,
            response_hash,
            stop,
        ),
        "observation": _text(
            item["observation"],
            f"{path}.observation",
            MAX_OBSERVATION_CHARACTERS,
            response_hash,
            stop,
        ),
    }
    if defect:
        result["severity"] = _enum(
            item["severity"],
            V5DefectSeverity,
            "severity",
            f"{path}.severity",
            response_hash,
            stop,
        )
    return result


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
            V51ParserErrorCode.INVALID_TYPE,
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
            V51ParserErrorCode.AMBIGUOUS_ALIAS,
            path,
            "string",
            "string",
            f"ambiguous between {','.join(ambiguous)}",
            raw,
            response_hash,
            stop,
        )
    token = _ALIASES.get(alias_group, {}).get(token, token)
    allowed = {item.value for item in enum_type}
    if token not in allowed:
        _fail(
            V51ParserErrorCode.UNKNOWN_VALUE,
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
            V51ParserErrorCode.INVALID_TYPE,
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
            V51ParserErrorCode.OUT_OF_BOUNDS,
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
            V51ParserErrorCode.INVALID_TYPE,
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
            V51ParserErrorCode.OUT_OF_BOUNDS,
            path,
            "array",
            "array",
            f"items {minimum}..{maximum}",
            raw,
            response_hash,
            stop,
        )
    return cast(list[object], raw)


def _object(raw: object, path: str, response_hash: str, stop: str | None) -> dict[str, object]:
    if type(raw) is not dict:
        _fail(
            V51ParserErrorCode.INVALID_TYPE,
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
            V51ParserErrorCode.MISSING_FIELD,
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
            V51ParserErrorCode.EXTRA_FIELD,
            f"{path}.{field}" if path != "$" else f"$.{field}",
            "no additional property",
            _type_name(payload[field]),
            "additionalProperties=false",
            payload[field],
            response_hash,
            stop,
        )


def _json_object(output_text: str, response_hash: str, stop: str | None) -> dict[str, object]:
    if type(output_text) is not str:
        _fail(
            V51ParserErrorCode.INVALID_TYPE,
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
            V51ParserErrorCode.INVALID_JSON,
            "$",
            "JSON object",
            "invalid_json_string",
            "valid JSON object",
            output_text,
            response_hash,
            stop,
        )
    return _object(payload, "$", response_hash, stop)


def _canonical_error_location(code: str) -> tuple[str, str]:
    mapping = {
        "EVIDENCE_CHECK_UNKNOWN": (
            "$.evidence[*].check_id",
            "canonical rubric check id",
        ),
        "EVIDENCE_CHECK_DUPLICATE": (
            "$.evidence[*].check_id",
            "unique check ids",
        ),
        "DEFECT_COVERAGE_INVALID": (
            "$.defects",
            "exact coverage of unsatisfied checks",
        ),
        "SCORE_EVIDENCE_MISMATCH": (
            "$.score_level",
            "score equals satisfied-check count",
        ),
        "CONTRADICTION_SCORE_MISMATCH": (
            "$.score_level",
            "contradiction implies score 0",
        ),
        "PAIRWISE_TIE_MATERIAL_DIFFERENCE": (
            "$.decision",
            "TIE has no MATERIAL difference",
        ),
        "PAIRWISE_WINNER_UNSUPPORTED": (
            "$.decision",
            "winner supported by a MATERIAL difference",
        ),
        "PAIRWISE_MATERIAL_CONFLICT": (
            "$.differences",
            "no conflicting MATERIAL winners",
        ),
    }
    return mapping.get(code, ("$", code))


def _fail(
    code: V51ParserErrorCode,
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
    raise V51ParserError(
        V51ParserDiagnostic(
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
        ".status",
        ".confidence",
        ".score_level",
        ".severity",
        ".decision",
        ".significance",
        ".favored_candidate",
    )
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
