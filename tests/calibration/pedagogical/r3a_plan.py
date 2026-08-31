"""Offline-only R3A evidence consolidation and residual calibration plan."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, replace
from decimal import ROUND_CEILING, Decimal
from enum import StrEnum
from pathlib import Path
from typing import cast

from backend.adapters.outbound.generation.openai.adapter import (
    _map_response as _map_generation_response,
)
from backend.adapters.outbound.generation.openai.mapping import build_openai_request
from backend.adapters.outbound.openai import (
    OpenAIIncompleteReason,
    OpenAIReasoningEffort,
    OpenAIResponsesResponse,
    OpenAIResponseStatus,
)
from backend.adapters.outbound.review.openai.adapter import (
    _map_response as _map_review_response,
)
from backend.adapters.outbound.review.openai.mapping import (
    build_openai_review_request,
)
from tests.calibration.pedagogical.legacy_call_plan import (
    PEDAGOGICAL_CALIBRATION_CALL_MATRIX,
    PEDAGOGICAL_CALIBRATION_PLAN_VERSION,
    CalibrationCallSpec,
    CalibrationProvider,
    CalibrationWorkload,
)
from tests.calibration.pedagogical.live_runner import (
    _generation_request,
    _model_profile,
    _provider_profile,
    _review_request,
)
from tests.calibration.pedagogical.r2a_diagnostic import (
    audit_anthropic_canary_reuse,
)
from tests.calibration.pedagogical.remediation_plan import (
    R2_CANARY_MATRIX_SHA256,
    R2_CANARY_PLAN_VERSION,
    R2B_CANARY_CALL_MATRIX,
    R2B_CANARY_MATRIX_SHA256,
    R2B_CANARY_PLAN_VERSION,
)

G2_LEDGER_RELATIVE_PATH = "artifacts/calibration/12.16-g2/ledger.json"
R2_LEDGER_RELATIVE_PATH = "artifacts/calibration/12.16-g2-r2/ledger.json"
R2_SUMMARY_RELATIVE_PATH = "artifacts/calibration/12.16-g2-r2/summary.json"
R2B_LEDGER_RELATIVE_PATH = "artifacts/calibration/12.16-g2-r2b/ledger.json"
R2B_SUMMARY_RELATIVE_PATH = "artifacts/calibration/12.16-g2-r2b/summary.json"
R3_ARTIFACT_DIRECTORY = "artifacts/calibration/12.16-g2-r3"
R3_LEDGER_RELATIVE_PATH = f"{R3_ARTIFACT_DIRECTORY}/ledger.json"

G2_LEDGER_SHA256 = "909a973d6532570ce95a65018d6016ed8ecaeb6af45ff4216ec568a21fecf0d7"
R2_LEDGER_SHA256 = "45316f4e72f3d634cb31117e6f9cc690b68da43891b035558ed9a2aa46b33eb9"
R2_SUMMARY_SHA256 = "bf8aa0277c04dbceec63d2c8dff004bf9fb2849cfc069449b159d428025c67b7"
R2_ANTHROPIC_RAW_SHA256 = "be29addb485255f4ed3903747562fe27f9d26a5a2a90846aa31d2b34056fa70b"
R2B_LEDGER_SHA256 = "c37e2587e6d408233c716d7ce4c27c3364baec50e0c1ab180b9f344f23a509c8"
R2B_SUMMARY_SHA256 = "accab7309c4a3c5a25e8bbb40c8b494218da498c2808f26b4774eb3f7299ea2e"
R2B_RAW_SHA256 = "8430b6ae90a17451a94f69557de3aef1bca45e3e78ca6dff743ac161a4aac65b"

R3_PLAN_VERSION = "12.16-g2-r3-completion-v1"
R3_PRICING_SNAPSHOT_ID = "official-2026-08-29-r3a"
R3_APPROVAL_REQUIRED = True
R3_LIVE_PROVIDER_CALL_COUNT = 0
R3_PROVIDER_COST_USD = Decimal("0")
R3_COST_SAFETY_MARGIN = Decimal("1.25")
R3_PRODUCTION_REVIEW_LIMIT_ADOPTION = "DEFERRED_TO_12.16-H"
R3_CALL_MATRIX_SHA256 = "245f0c8b2e4d74f61ec58bd5b02824b4d0edfae3dbd55c1c518a9a09ccecee98"
R3_REUSED_EVIDENCE_MANIFEST_SHA256 = (
    "cace6d138a8ac1fef2920fc45abedbae7b3c99cc30ab9e76af86a16ed3f0ca4e"
)

EXPECTED_G2_ORIGINAL_REUSABLE_SLOT_IDS = (
    "cal.generation.course.primary.r1",
    "cal.generation.course.primary.r2",
    "cal.generation.course.fallback.r1",
    "cal.generation.exercise.primary.r1",
    "cal.generation.assessment.primary.r1",
    "cal.generation.assessment.fallback.r1",
    "cal.generation.qcm.primary.r1",
    "cal.generation.qcm.fallback.r1",
    "cal.transformation.resource.primary.r1",
    "cal.transformation.resource.primary.r2",
    "cal.correction.remediation.primary.r1",
    "cal.correction.remediation.primary.r2",
    "cal.correction.remediation.fallback.r1",
)
R2_ANTHROPIC_REUSED_LOGICAL_SLOT_ID = "cal.score.anchor.scn-01.a.clarity.r1"
R2B_REVIEW_REUSED_LOGICAL_SLOT_ID = "cal.review.exercise.primary.r1"
R2B_REMEDIATION_CALL_ID = "remediation.openai-review.scn-05.canary.r2b.r1"

EXPECTED_SELECTED_OUTPUT_SOURCE_SLOT_IDS = (
    "cal.generation.course.primary.r1",
    "cal.transformation.resource.primary.r1",
    "cal.generation.exercise.primary.r1",
    "cal.generation.assessment.primary.r1",
    "cal.correction.remediation.primary.r1",
    "cal.generation.qcm.primary.r1",
)


class ReuseMappingClass(StrEnum):
    EXACT_ORIGINAL_RESULT = "EXACT_ORIGINAL_RESULT"
    EXACT_REMEDIATION_EQUIVALENT = "EXACT_REMEDIATION_EQUIVALENT"
    AUTHORIZED_PARAMETER_REMEDIATION = "AUTHORIZED_PARAMETER_REMEDIATION"
    NOT_REUSABLE = "NOT_REUSABLE"


class R3ProviderFamily(StrEnum):
    OPENAI_REVIEW_SOL = "OPENAI_REVIEW_SOL"
    OPENAI_REVIEW_TERRA = "OPENAI_REVIEW_TERRA"
    ANTHROPIC_SCORER = "ANTHROPIC_SCORER"


class R3FamilyReadiness(StrEnum):
    PASSED = "PASSED"
    PENDING = "PENDING"
    BLOCKED = "BLOCKED"


class R3LedgerStatus(StrEnum):
    PENDING = "PENDING"
    STARTED = "STARTED"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    SKIPPED_DEPENDENCY_FAILED = "SKIPPED_DEPENDENCY_FAILED"
    BLOCKED_BY_CANARY = "BLOCKED_BY_CANARY"


class R3AErrorCode(StrEnum):
    REUSABLE_CALIBRATION_EVIDENCE_UNAVAILABLE = "REUSABLE_CALIBRATION_EVIDENCE_UNAVAILABLE"
    LOGICAL_SLOT_DUPLICATE = "LOGICAL_SLOT_DUPLICATE"
    REUSE_MAPPING_COLLISION = "REUSE_MAPPING_COLLISION"
    STARTED_CALL_AMBIGUOUS = "STARTED_CALL_AMBIGUOUS"
    LEDGER_INVALID = "LEDGER_INVALID"
    FAMILY_CANARY_REQUIRED = "FAMILY_CANARY_REQUIRED"
    FAMILY_BLOCKED = "FAMILY_BLOCKED"


class R3AError(RuntimeError):
    code: R3AErrorCode

    def __init__(self, code: R3AErrorCode) -> None:
        self.code = code
        super().__init__(code.value)


@dataclass(frozen=True, slots=True)
class ReusedEvidenceMapping:
    evidence_set: str
    provider: str
    model: str
    model_profile_id: str
    remediation_call_id: str | None
    original_logical_slot_id: str
    status: str
    input_sha256: str
    schema_sha256: str
    output_sha256: str
    input_tokens: int
    cached_input_tokens: int
    output_tokens: int
    reasoning_tokens: int | None
    total_tokens: int
    cost_usd: str
    mapping_class: ReuseMappingClass


@dataclass(frozen=True, slots=True)
class SelectedOutputDependency:
    logical_slot_id: str
    raw_output_sha256: str
    scoring_call_ids: tuple[str, str]


@dataclass(frozen=True, slots=True)
class R3AEvidenceAudit:
    proof_set_sha256: Mapping[str, str]
    reused_mappings: tuple[ReusedEvidenceMapping, ...]
    selected_output_dependencies: tuple[SelectedOutputDependency, ...]
    r2b_original_logical_input_sha256: str
    r2b_remediation_logical_input_sha256: str
    r2b_original_schema_sha256: str
    r2b_remediation_schema_sha256: str


@dataclass(frozen=True, slots=True)
class R3RemainingCallSpec:
    r3_call_id: str
    source_failed_call_id: str
    logical_slot_id: str
    provider: CalibrationProvider
    model: str
    model_profile_id: str
    role: str
    execution_role: str
    workload: CalibrationWorkload
    scenario_code: str
    task_kind: str
    repetition: int
    max_output_tokens: int
    input_utf8_upper_bound_bytes: int
    criterion_refs: tuple[str, ...]
    input_refs: tuple[str, ...]
    reasoning_effort: OpenAIReasoningEffort | None
    automatic_retry_count: int
    family: R3ProviderFamily
    family_canary: bool


@dataclass(frozen=True, slots=True)
class R3PriceQuote:
    provider: CalibrationProvider
    model: str
    input_usd_per_million_tokens: Decimal
    cached_input_usd_per_million_tokens: Decimal
    output_usd_per_million_tokens: Decimal
    source_url: str


@dataclass(frozen=True, slots=True)
class R3CostPlan:
    call_count: int
    estimated_reference_usd: Decimal
    maximum_before_margin_usd: Decimal
    safety_margin_multiplier: Decimal
    safety_margin_amount_usd: Decimal
    requested_hard_ceiling_usd: Decimal
    maximum_by_model_usd: Mapping[str, Decimal]
    maximum_by_workload_usd: Mapping[str, Decimal]


R3_PRICE_QUOTES = (
    R3PriceQuote(
        CalibrationProvider.OPENAI,
        "gpt-5.6-sol",
        Decimal("4.00"),
        Decimal("0.40"),
        Decimal("20.00"),
        "https://developers.openai.com/api/docs/models/gpt-5.6-sol",
    ),
    R3PriceQuote(
        CalibrationProvider.OPENAI,
        "gpt-5.6-terra",
        Decimal("2.00"),
        Decimal("0.20"),
        Decimal("12.00"),
        "https://developers.openai.com/api/docs/models/gpt-5.6-terra",
    ),
    R3PriceQuote(
        CalibrationProvider.ANTHROPIC,
        "claude-sonnet-5",
        Decimal("2.00"),
        Decimal("0.20"),
        Decimal("10.00"),
        "https://platform.claude.com/docs/en/about-claude/pricing",
    ),
)


def _sha256(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _canonical_sha256(payload: object) -> str:
    encoded = json.dumps(
        payload,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    return _sha256(encoded)


def _safe_json(root: Path, relative_path: str) -> tuple[dict[str, object], bytes]:
    path = (root / relative_path).resolve()
    artifact_root = (root / "artifacts").resolve()
    if artifact_root not in path.parents:
        _evidence_error()
    try:
        payload = path.read_bytes()
        value = json.loads(payload)
    except (OSError, UnicodeError, json.JSONDecodeError):
        _evidence_error()
    if type(value) is not dict:
        _evidence_error()
    return cast(dict[str, object], value), payload


def _safe_raw(root: Path, relative_path: object, expected_sha256: object) -> bytes:
    if type(relative_path) is not str or type(expected_sha256) is not str:
        _evidence_error()
    path = (root / relative_path).resolve()
    raw_root = (root / "artifacts/calibration").resolve()
    if raw_root not in path.parents:
        _evidence_error()
    try:
        payload = path.read_bytes()
    except OSError:
        _evidence_error()
    if _sha256(payload) != expected_sha256:
        _evidence_error()
    return payload


def _require_artifact_sha256(payload: bytes, expected: str) -> None:
    if _sha256(payload) != expected:
        _evidence_error()


def _mapping_payload(item: ReusedEvidenceMapping) -> dict[str, object]:
    return {
        "evidence_set": item.evidence_set,
        "provider": item.provider,
        "model": item.model,
        "model_profile_id": item.model_profile_id,
        "remediation_call_id": item.remediation_call_id,
        "original_logical_slot_id": item.original_logical_slot_id,
        "status": item.status,
        "input_sha256": item.input_sha256,
        "schema_sha256": item.schema_sha256,
        "output_sha256": item.output_sha256,
        "input_tokens": item.input_tokens,
        "cached_input_tokens": item.cached_input_tokens,
        "output_tokens": item.output_tokens,
        "reasoning_tokens": item.reasoning_tokens,
        "total_tokens": item.total_tokens,
        "cost_usd": item.cost_usd,
        "mapping_class": item.mapping_class.value,
    }


def _record_int(record: Mapping[str, object], field: str) -> int:
    value = record.get(field)
    if type(value) is not int:
        _evidence_error()
    return value


def _record_str(record: Mapping[str, object], field: str) -> str:
    value = record.get(field)
    if type(value) is not str:
        _evidence_error()
    return value


def _openai_request_hashes(call: CalibrationCallSpec) -> tuple[str, str]:
    if call.workload is CalibrationWorkload.REVIEW:
        provider_request = build_openai_review_request(
            request=_review_request(call),
            model_profile=_model_profile(call),
        )
    else:
        provider_request = build_openai_request(
            request=_generation_request(call),
            model_profile=_model_profile(call),
        )
    return (
        _sha256(provider_request.input_json.encode("utf-8")),
        _canonical_sha256(provider_request.output_schema),
    )


def _logical_review_hashes(call: CalibrationCallSpec) -> tuple[str, str]:
    provider_request = build_openai_review_request(
        request=_review_request(call),
        model_profile=_model_profile(call),
    )
    input_payload = json.loads(provider_request.input_json)
    if type(input_payload) is not dict:
        _evidence_error()
    input_payload.pop("source_step_id", None)
    return (
        _canonical_sha256(input_payload),
        _canonical_sha256(provider_request.output_schema),
    )


def _validate_original_openai_result(
    root: Path,
    call: CalibrationCallSpec,
    record: Mapping[str, object],
) -> ReusedEvidenceMapping:
    if (
        record.get("status") != R3LedgerStatus.COMPLETED.value
        or record.get("provider") != CalibrationProvider.OPENAI.value
        or record.get("model") != call.model
        or call.workload is CalibrationWorkload.REVIEW
    ):
        _evidence_error()
    raw = _safe_raw(
        root,
        record.get("raw_output_path"),
        record.get("raw_output_sha256"),
    )
    try:
        text = raw.decode("utf-8")
        json.loads(text)
        mapped = _map_generation_response(
            request=_generation_request(call),
            response=OpenAIResponsesResponse(
                status=OpenAIResponseStatus.COMPLETED,
                output_text=text,
            ),
            provider_profile=_provider_profile(call.provider),
            model_profile=_model_profile(call),
        )
    except (UnicodeError, json.JSONDecodeError, RuntimeError, TypeError, ValueError):
        _evidence_error()
    if mapped.status.value not in {"SUCCEEDED", "PARTIAL"}:
        _evidence_error()
    input_sha256, schema_sha256 = _openai_request_hashes(call)
    return ReusedEvidenceMapping(
        evidence_set="G2",
        provider=call.provider.value,
        model=call.model,
        model_profile_id=call.model_profile_id,
        remediation_call_id=None,
        original_logical_slot_id=call.call_id,
        status=R3LedgerStatus.COMPLETED.value,
        input_sha256=input_sha256,
        schema_sha256=schema_sha256,
        output_sha256=_record_str(record, "raw_output_sha256"),
        input_tokens=_record_int(record, "input_tokens"),
        cached_input_tokens=_record_int(record, "cached_input_tokens"),
        output_tokens=_record_int(record, "output_tokens"),
        reasoning_tokens=None,
        total_tokens=_record_int(record, "total_tokens"),
        cost_usd=_record_str(record, "cost_usd"),
        mapping_class=ReuseMappingClass.EXACT_ORIGINAL_RESULT,
    )


def _selected_output_dependencies(
    root: Path,
    mappings: Sequence[ReusedEvidenceMapping],
    records_by_id: Mapping[str, Mapping[str, object]],
) -> tuple[SelectedOutputDependency, ...]:
    mapped = {item.original_logical_slot_id: item for item in mappings}
    dependencies: list[SelectedOutputDependency] = []
    for source_id in EXPECTED_SELECTED_OUTPUT_SOURCE_SLOT_IDS:
        item = mapped.get(source_id)
        record = records_by_id.get(source_id)
        if item is None or record is None:
            _evidence_error()
        raw = _safe_raw(
            root,
            record.get("raw_output_path"),
            record.get("raw_output_sha256"),
        )
        try:
            payload = json.loads(raw)
        except (UnicodeError, json.JSONDecodeError):
            _evidence_error()
        if type(payload) is not dict or payload.get("outcome") != "OUTPUT":
            _evidence_error()
        sections = payload.get("sections")
        if type(sections) is not list or not sections:
            _evidence_error()
        if any(
            type(section) is not dict
            or type(section.get("code")) is not str
            or not section.get("code")
            or type(section.get("text")) is not str
            or not section.get("text")
            for section in sections
        ):
            _evidence_error()
        scoring_ids = tuple(
            call.call_id
            for call in PEDAGOGICAL_CALIBRATION_CALL_MATRIX
            if call.provider is CalibrationProvider.ANTHROPIC
            and call.input_refs == (f"output:{source_id}",)
        )
        if len(scoring_ids) != 2:
            _evidence_error()
        dependencies.append(
            SelectedOutputDependency(
                logical_slot_id=source_id,
                raw_output_sha256=item.output_sha256,
                scoring_call_ids=cast(tuple[str, str], scoring_ids),
            )
        )
    return tuple(dependencies)


def _audit_r2_anthropic(
    root: Path,
    ledger: Mapping[str, object],
) -> ReusedEvidenceMapping:
    records = ledger.get("calls")
    if type(records) is not list or len(records) != 2:
        _evidence_error()
    typed_records = [cast(dict[str, object], item) for item in records if type(item) is dict]
    if len(typed_records) != 2:
        _evidence_error()
    record = next(
        (
            item
            for item in typed_records
            if item.get("provider") == CalibrationProvider.ANTHROPIC.value
        ),
        None,
    )
    if record is None or record.get("status") != "PASSED":
        _evidence_error()
    raw = _safe_raw(root, record.get("raw_output_path"), record.get("raw_output_sha256"))
    if _sha256(raw) != R2_ANTHROPIC_RAW_SHA256:
        _evidence_error()
    try:
        score = json.loads(raw)
    except (UnicodeError, json.JSONDecodeError):
        _evidence_error()
    if (
        type(score) is not dict
        or score.get("status") != "SCORED"
        or type(score.get("score_numerator")) is not int
        or type(score.get("score_denominator")) is not int
    ):
        _evidence_error()
    equivalence = audit_anthropic_canary_reuse()
    comparisons = equivalence.get("comparisons")
    if (
        equivalence.get("anthropic_canary_reusable_as_g2_score") is not True
        or type(comparisons) is not dict
        or not all(comparisons.values())
    ):
        _evidence_error()
    return ReusedEvidenceMapping(
        evidence_set="R2",
        provider=CalibrationProvider.ANTHROPIC.value,
        model=_record_str(record, "model"),
        model_profile_id=cast(str, equivalence["model_profile_id"]),
        remediation_call_id=_record_str(record, "call_id"),
        original_logical_slot_id=R2_ANTHROPIC_REUSED_LOGICAL_SLOT_ID,
        status="PASSED",
        input_sha256=cast(str, equivalence["logical_observation_sha256"]),
        schema_sha256=cast(str, equivalence["schema_sha256"]),
        output_sha256=_record_str(record, "raw_output_sha256"),
        input_tokens=_record_int(record, "input_tokens"),
        cached_input_tokens=_record_int(record, "cached_input_tokens"),
        output_tokens=_record_int(record, "output_tokens"),
        reasoning_tokens=None,
        total_tokens=_record_int(record, "total_tokens"),
        cost_usd=_record_str(record, "cost_usd"),
        mapping_class=ReuseMappingClass.EXACT_REMEDIATION_EQUIVALENT,
    )


def _audit_r2b_review(
    root: Path,
    ledger: Mapping[str, object],
) -> tuple[ReusedEvidenceMapping, str, str, str, str]:
    records = ledger.get("calls")
    if type(records) is not list or len(records) != 1 or type(records[0]) is not dict:
        _evidence_error()
    record = cast(dict[str, object], records[0])
    if (
        record.get("call_id") != R2B_REMEDIATION_CALL_ID
        or record.get("status") != R3LedgerStatus.COMPLETED.value
        or record.get("provider_response_status") != OpenAIResponseStatus.COMPLETED.value
        or record.get("public_review_result_status") not in {"PARTIAL", "SUCCEEDED"}
        or record.get("incomplete_reason") != OpenAIIncompleteReason.NONE.value
        or record.get("private_diagnostic_code") is not None
        or record.get("public_error_code") is not None
        or record.get("output_present") is not True
    ):
        _evidence_error()
    raw = _safe_raw(root, record.get("raw_output_path"), record.get("raw_output_sha256"))
    if _sha256(raw) != R2B_RAW_SHA256:
        _evidence_error()
    spec = R2B_CANARY_CALL_MATRIX[0]
    original = next(
        call
        for call in PEDAGOGICAL_CALIBRATION_CALL_MATRIX
        if call.call_id == R2B_REVIEW_REUSED_LOGICAL_SLOT_ID
    )
    try:
        text = raw.decode("utf-8")
        json.loads(text)
        mapped = _map_review_response(
            request=_review_request(spec.call),
            response=OpenAIResponsesResponse(
                status=OpenAIResponseStatus.COMPLETED,
                output_text=text,
                incomplete_reason=OpenAIIncompleteReason.NONE,
            ),
            provider_profile=_provider_profile(spec.call.provider),
            model_profile=_model_profile(spec.call),
        )
    except (UnicodeError, json.JSONDecodeError, RuntimeError, TypeError, ValueError):
        _evidence_error()
    if mapped.status.value not in {"PARTIAL", "SUCCEEDED"}:
        _evidence_error()
    original_input, original_schema = _logical_review_hashes(original)
    remediation_input, remediation_schema = _logical_review_hashes(spec.call)
    if (
        original_input != remediation_input
        or original_schema != remediation_schema
        or original.scenario_code != spec.call.scenario_code
        or original.task_kind != spec.call.task_kind
        or original.model != spec.call.model
        or original.model_profile_id != spec.call.model_profile_id
        or original.max_output_tokens != 1_024
        or spec.call.max_output_tokens != 4_096
        or spec.reasoning_effort is not OpenAIReasoningEffort.LOW
        or spec.automatic_retry_count != 0
    ):
        _evidence_error()
    provider_request = build_openai_review_request(
        request=_review_request(spec.call),
        model_profile=_model_profile(spec.call),
        reasoning_effort=spec.reasoning_effort,
    )
    mapping = ReusedEvidenceMapping(
        evidence_set="R2B",
        provider=CalibrationProvider.OPENAI.value,
        model=spec.call.model,
        model_profile_id=spec.call.model_profile_id,
        remediation_call_id=R2B_REMEDIATION_CALL_ID,
        original_logical_slot_id=R2B_REVIEW_REUSED_LOGICAL_SLOT_ID,
        status=cast(str, record["public_review_result_status"]),
        input_sha256=_sha256(provider_request.input_json.encode("utf-8")),
        schema_sha256=_canonical_sha256(provider_request.output_schema),
        output_sha256=_record_str(record, "raw_output_sha256"),
        input_tokens=_record_int(record, "input_tokens"),
        cached_input_tokens=_record_int(record, "cached_input_tokens"),
        output_tokens=_record_int(record, "output_tokens"),
        reasoning_tokens=_record_int(record, "reasoning_tokens"),
        total_tokens=_record_int(record, "total_tokens"),
        cost_usd=_record_str(record, "cost_usd"),
        mapping_class=ReuseMappingClass.AUTHORIZED_PARAMETER_REMEDIATION,
    )
    return mapping, original_input, remediation_input, original_schema, remediation_schema


def validate_reuse_mappings(mappings: Sequence[ReusedEvidenceMapping]) -> None:
    logical_ids = [item.original_logical_slot_id for item in mappings]
    if len(logical_ids) != len(set(logical_ids)):
        raise R3AError(R3AErrorCode.LOGICAL_SLOT_DUPLICATE)
    remediation_ids = [
        item.remediation_call_id for item in mappings if item.remediation_call_id is not None
    ]
    if len(remediation_ids) != len(set(remediation_ids)):
        raise R3AError(R3AErrorCode.REUSE_MAPPING_COLLISION)
    known = {call.call_id for call in PEDAGOGICAL_CALIBRATION_CALL_MATRIX}
    if any(logical_id not in known for logical_id in logical_ids):
        raise R3AError(R3AErrorCode.REUSE_MAPPING_COLLISION)


def audit_r3a_evidence(root: Path) -> R3AEvidenceAudit:
    """Audit G2/R2/R2B without returning provider raw content."""

    g2, g2_bytes = _safe_json(root, G2_LEDGER_RELATIVE_PATH)
    r2, r2_bytes = _safe_json(root, R2_LEDGER_RELATIVE_PATH)
    r2_summary, r2_summary_bytes = _safe_json(root, R2_SUMMARY_RELATIVE_PATH)
    r2b, r2b_bytes = _safe_json(root, R2B_LEDGER_RELATIVE_PATH)
    r2b_summary, r2b_summary_bytes = _safe_json(root, R2B_SUMMARY_RELATIVE_PATH)
    for payload, expected in (
        (g2_bytes, G2_LEDGER_SHA256),
        (r2_bytes, R2_LEDGER_SHA256),
        (r2_summary_bytes, R2_SUMMARY_SHA256),
        (r2b_bytes, R2B_LEDGER_SHA256),
        (r2b_summary_bytes, R2B_SUMMARY_SHA256),
    ):
        _require_artifact_sha256(payload, expected)

    g2_records = g2.get("calls")
    if (
        g2.get("plan_version") != PEDAGOGICAL_CALIBRATION_PLAN_VERSION
        or type(g2_records) is not list
        or len(g2_records) != len(PEDAGOGICAL_CALIBRATION_CALL_MATRIX)
    ):
        _evidence_error()
    records = [cast(dict[str, object], item) for item in g2_records if type(item) is dict]
    if len(records) != 96:
        _evidence_error()
    status_counts = {
        status: sum(record.get("status") == status for record in records)
        for status in (R3LedgerStatus.COMPLETED.value, R3LedgerStatus.FAILED.value)
    }
    if status_counts != {R3LedgerStatus.COMPLETED.value: 13, R3LedgerStatus.FAILED.value: 83}:
        _evidence_error()
    records_by_id = {
        cast(str, record["call_id"]): record
        for record in records
        if type(record.get("call_id")) is str
    }
    if len(records_by_id) != 96:
        _evidence_error()
    planned = {call.call_id: call for call in PEDAGOGICAL_CALIBRATION_CALL_MATRIX}
    original_mappings = tuple(
        _validate_original_openai_result(root, planned[call_id], records_by_id[call_id])
        for call_id in EXPECTED_G2_ORIGINAL_REUSABLE_SLOT_IDS
    )
    if len(original_mappings) != 13:
        _evidence_error()
    selected = _selected_output_dependencies(root, original_mappings, records_by_id)

    if (
        r2.get("plan_version") != R2_CANARY_PLAN_VERSION
        or r2.get("matrix_sha256") != R2_CANARY_MATRIX_SHA256
        or r2_summary.get("ledger_sha256") != R2_LEDGER_SHA256
    ):
        _evidence_error()
    anthropic_mapping = _audit_r2_anthropic(root, r2)
    if (
        r2b.get("plan_version") != R2B_CANARY_PLAN_VERSION
        or r2b.get("matrix_sha256") != R2B_CANARY_MATRIX_SHA256
        or r2b_summary.get("ledger_sha256") != R2B_LEDGER_SHA256
    ):
        _evidence_error()
    (
        review_mapping,
        original_input,
        remediation_input,
        original_schema,
        remediation_schema,
    ) = _audit_r2b_review(root, r2b)
    mappings = (*original_mappings, anthropic_mapping, review_mapping)
    validate_reuse_mappings(mappings)
    if len(mappings) != 15:
        _evidence_error()
    return R3AEvidenceAudit(
        proof_set_sha256={
            G2_LEDGER_RELATIVE_PATH: G2_LEDGER_SHA256,
            R2_LEDGER_RELATIVE_PATH: R2_LEDGER_SHA256,
            R2_SUMMARY_RELATIVE_PATH: R2_SUMMARY_SHA256,
            R2B_LEDGER_RELATIVE_PATH: R2B_LEDGER_SHA256,
            R2B_SUMMARY_RELATIVE_PATH: R2B_SUMMARY_SHA256,
        },
        reused_mappings=tuple(mappings),
        selected_output_dependencies=selected,
        r2b_original_logical_input_sha256=original_input,
        r2b_remediation_logical_input_sha256=remediation_input,
        r2b_original_schema_sha256=original_schema,
        r2b_remediation_schema_sha256=remediation_schema,
    )


def reused_evidence_manifest_payload(audit: R3AEvidenceAudit) -> dict[str, object]:
    return {
        "proof_set_sha256": dict(sorted(audit.proof_set_sha256.items())),
        "mappings": [_mapping_payload(item) for item in audit.reused_mappings],
        "selected_output_dependencies": [
            {
                "logical_slot_id": item.logical_slot_id,
                "raw_output_sha256": item.raw_output_sha256,
                "scoring_call_ids": list(item.scoring_call_ids),
            }
            for item in audit.selected_output_dependencies
        ],
        "r2b_logical_equivalence": {
            "original_input_sha256": audit.r2b_original_logical_input_sha256,
            "remediation_input_sha256": audit.r2b_remediation_logical_input_sha256,
            "original_schema_sha256": audit.r2b_original_schema_sha256,
            "remediation_schema_sha256": audit.r2b_remediation_schema_sha256,
            "original_max_output_tokens": 1_024,
            "remediation_max_output_tokens": 4_096,
            "original_reasoning_effort": "implicit/default",
            "remediation_reasoning_effort": OpenAIReasoningEffort.LOW.value,
            "mapping_class": ReuseMappingClass.AUTHORIZED_PARAMETER_REMEDIATION.value,
        },
    }


def reused_evidence_manifest_sha256(audit: R3AEvidenceAudit) -> str:
    return _canonical_sha256(reused_evidence_manifest_payload(audit))


def _family(call: CalibrationCallSpec) -> R3ProviderFamily:
    if call.provider is CalibrationProvider.ANTHROPIC:
        return R3ProviderFamily.ANTHROPIC_SCORER
    if call.model == "gpt-5.6-terra":
        return R3ProviderFamily.OPENAI_REVIEW_TERRA
    return R3ProviderFamily.OPENAI_REVIEW_SOL


def _r3_call(call: CalibrationCallSpec, *, family_canary: bool) -> R3RemainingCallSpec:
    review = call.workload is CalibrationWorkload.REVIEW
    return R3RemainingCallSpec(
        r3_call_id=f"r3.{call.call_id}",
        source_failed_call_id=call.call_id,
        logical_slot_id=call.call_id,
        provider=call.provider,
        model=call.model,
        model_profile_id=call.model_profile_id,
        role=call.role.value,
        execution_role="FAMILY_CANARY" if family_canary else "MATRIX_MEMBER",
        workload=call.workload,
        scenario_code=call.scenario_code,
        task_kind=call.task_kind,
        repetition=call.repetition,
        max_output_tokens=4_096 if review else call.max_output_tokens,
        input_utf8_upper_bound_bytes=call.input_utf8_upper_bound_bytes,
        criterion_refs=call.criterion_refs,
        input_refs=call.input_refs,
        reasoning_effort=OpenAIReasoningEffort.LOW if review else None,
        automatic_retry_count=0,
        family=_family(call),
        family_canary=family_canary,
    )


def build_remaining_call_matrix() -> tuple[R3RemainingCallSpec, ...]:
    reusable = {
        *EXPECTED_G2_ORIGINAL_REUSABLE_SLOT_IDS,
        R2_ANTHROPIC_REUSED_LOGICAL_SLOT_ID,
        R2B_REVIEW_REUSED_LOGICAL_SLOT_ID,
    }
    remaining = [
        call for call in PEDAGOGICAL_CALIBRATION_CALL_MATRIX if call.call_id not in reusable
    ]
    terra_canary = next(
        call
        for call in remaining
        if call.workload is CalibrationWorkload.REVIEW and call.model == "gpt-5.6-terra"
    )
    ordered = [terra_canary, *(call for call in remaining if call != terra_canary)]
    return tuple(_r3_call(call, family_canary=index == 0) for index, call in enumerate(ordered))


R3_REMAINING_CALL_MATRIX = build_remaining_call_matrix()


def _call_payload(call: R3RemainingCallSpec) -> dict[str, object]:
    return {
        "r3_call_id": call.r3_call_id,
        "source_failed_call_id": call.source_failed_call_id,
        "logical_slot_id": call.logical_slot_id,
        "provider": call.provider.value,
        "model": call.model,
        "model_profile_id": call.model_profile_id,
        "original_role": call.role,
        "execution_role": call.execution_role,
        "workload": call.workload.value,
        "scenario_code": call.scenario_code,
        "task_kind": call.task_kind,
        "repetition": call.repetition,
        "max_output_tokens": call.max_output_tokens,
        "input_utf8_upper_bound_bytes": call.input_utf8_upper_bound_bytes,
        "criterion_refs": list(call.criterion_refs),
        "input_refs": list(call.input_refs),
        "reasoning_effort": (
            call.reasoning_effort.value if call.reasoning_effort is not None else None
        ),
        "automatic_retry_count": call.automatic_retry_count,
        "family": call.family.value,
        "family_canary": call.family_canary,
    }


def r3_call_matrix_sha256(
    calls: Sequence[R3RemainingCallSpec] = R3_REMAINING_CALL_MATRIX,
    *,
    manifest_sha256: str = R3_REUSED_EVIDENCE_MANIFEST_SHA256,
) -> str:
    cost = estimate_r3_cost(calls)
    payload = {
        "approval_required": R3_APPROVAL_REQUIRED,
        "plan_version": R3_PLAN_VERSION,
        "pricing_snapshot_id": R3_PRICING_SNAPSHOT_ID,
        "reused_evidence_manifest_sha256": manifest_sha256,
        "calls": [_call_payload(call) for call in calls],
        "cost": {
            "maximum_before_margin_usd": str(cost.maximum_before_margin_usd),
            "safety_margin_multiplier": str(cost.safety_margin_multiplier),
            "requested_hard_ceiling_usd": str(cost.requested_hard_ceiling_usd),
        },
    }
    return _canonical_sha256(payload)


def _money(value: Decimal) -> Decimal:
    return value.quantize(Decimal("0.000001"), rounding=ROUND_CEILING)


def _call_cost(
    call: R3RemainingCallSpec,
    quote: R3PriceQuote,
    *,
    maximum: bool,
) -> Decimal:
    if maximum:
        input_tokens = call.input_utf8_upper_bound_bytes
        output_tokens = call.max_output_tokens
    else:
        input_tokens = (call.input_utf8_upper_bound_bytes + 3) // 4
        output_tokens = (call.max_output_tokens + 1) // 2
    million = Decimal(1_000_000)
    return (
        Decimal(input_tokens) * quote.input_usd_per_million_tokens
        + Decimal(output_tokens) * quote.output_usd_per_million_tokens
    ) / million


def estimate_r3_cost(
    calls: Sequence[R3RemainingCallSpec] = R3_REMAINING_CALL_MATRIX,
) -> R3CostPlan:
    quotes = {item.model: item for item in R3_PRICE_QUOTES}
    reference = Decimal("0")
    maximum = Decimal("0")
    by_model: dict[str, Decimal] = {}
    by_workload: dict[str, Decimal] = {}
    for call in calls:
        quote = quotes[call.model]
        reference += _call_cost(call, quote, maximum=False)
        call_maximum = _call_cost(call, quote, maximum=True)
        maximum += call_maximum
        by_model[call.model] = by_model.get(call.model, Decimal("0")) + call_maximum
        by_workload[call.workload.value] = (
            by_workload.get(call.workload.value, Decimal("0")) + call_maximum
        )
    maximum_rounded = _money(maximum)
    ceiling = _money(maximum * R3_COST_SAFETY_MARGIN)
    return R3CostPlan(
        call_count=len(calls),
        estimated_reference_usd=_money(reference),
        maximum_before_margin_usd=maximum_rounded,
        safety_margin_multiplier=R3_COST_SAFETY_MARGIN,
        safety_margin_amount_usd=_money(ceiling - maximum_rounded),
        requested_hard_ceiling_usd=ceiling,
        maximum_by_model_usd={key: _money(value) for key, value in sorted(by_model.items())},
        maximum_by_workload_usd={key: _money(value) for key, value in sorted(by_workload.items())},
    )


def import_external_readiness(
    evidence_sha256: Mapping[str, str],
) -> dict[R3ProviderFamily, R3FamilyReadiness]:
    required = {
        "r2_ledger": R2_LEDGER_SHA256,
        "r2_anthropic_raw": R2_ANTHROPIC_RAW_SHA256,
        "r2b_ledger": R2B_LEDGER_SHA256,
        "r2b_openai_raw": R2B_RAW_SHA256,
    }
    if dict(evidence_sha256) != required:
        _evidence_error()
    return {
        R3ProviderFamily.OPENAI_REVIEW_SOL: R3FamilyReadiness.PASSED,
        R3ProviderFamily.OPENAI_REVIEW_TERRA: R3FamilyReadiness.PENDING,
        R3ProviderFamily.ANTHROPIC_SCORER: R3FamilyReadiness.PASSED,
    }


def default_external_evidence_sha256() -> dict[str, str]:
    return {
        "r2_ledger": R2_LEDGER_SHA256,
        "r2_anthropic_raw": R2_ANTHROPIC_RAW_SHA256,
        "r2b_ledger": R2B_LEDGER_SHA256,
        "r2b_openai_raw": R2B_RAW_SHA256,
    }


def build_r3_ledger_template(
    *,
    manifest_sha256: str = R3_REUSED_EVIDENCE_MANIFEST_SHA256,
) -> dict[str, object]:
    cost = estimate_r3_cost()
    readiness = import_external_readiness(default_external_evidence_sha256())
    return {
        "plan_version": R3_PLAN_VERSION,
        "matrix_sha256": R3_CALL_MATRIX_SHA256,
        "approved_ceiling_usd": None,
        "requested_hard_ceiling_usd": str(cost.requested_hard_ceiling_usd),
        "approval_required": True,
        "reused_evidence_manifest_sha256": manifest_sha256,
        "reused_slot_count": 15,
        "provider_calls_attempted": 0,
        "automatic_retry_count": 0,
        "automatic_rerun_count": 0,
        "total_cost_usd": "0.000000",
        "external_readiness": {
            family.value: readiness[family].value for family in R3ProviderFamily
        },
        "external_readiness_evidence_sha256": default_external_evidence_sha256(),
        "calls": [
            {
                **_call_payload(call),
                "status": R3LedgerStatus.PENDING.value,
                "started_at": None,
                "completed_at": None,
                "cost_usd": "0.000000",
                "closed_error_code": None,
                "raw_output_path": None,
                "raw_output_sha256": None,
            }
            for call in R3_REMAINING_CALL_MATRIX
        ],
    }


def next_executable_call_id(ledger: Mapping[str, object]) -> str | None:
    calls = ledger.get("calls")
    if type(calls) is not list:
        raise R3AError(R3AErrorCode.LEDGER_INVALID)
    records = [cast(dict[str, object], item) for item in calls if type(item) is dict]
    if len(records) != len(calls):
        raise R3AError(R3AErrorCode.LEDGER_INVALID)
    call_ids = [item.get("r3_call_id") for item in records]
    if any(type(call_id) is not str for call_id in call_ids) or len(call_ids) != len(set(call_ids)):
        raise R3AError(R3AErrorCode.LEDGER_INVALID)
    if any(item.get("status") == R3LedgerStatus.STARTED.value for item in records):
        raise R3AError(R3AErrorCode.STARTED_CALL_AMBIGUOUS)
    terra_canary = records[0] if records else None
    if (
        terra_canary is not None
        and terra_canary.get("family") == R3ProviderFamily.OPENAI_REVIEW_TERRA.value
        and terra_canary.get("family_canary") is True
        and terra_canary.get("status") == R3LedgerStatus.FAILED.value
    ):
        return None
    for item in records:
        if item.get("status") == R3LedgerStatus.PENDING.value:
            return cast(str, item["r3_call_id"])
        if item.get("status") not in {status.value for status in R3LedgerStatus}:
            raise R3AError(R3AErrorCode.LEDGER_INVALID)
    return None


def block_after_failed_terra_canary(
    ledger: Mapping[str, object],
) -> dict[str, object]:
    cloned = json.loads(json.dumps(ledger))
    if type(cloned) is not dict or type(cloned.get("calls")) is not list:
        raise R3AError(R3AErrorCode.LEDGER_INVALID)
    calls = cast(list[dict[str, object]], cloned["calls"])
    if (
        not calls
        or calls[0].get("family") != R3ProviderFamily.OPENAI_REVIEW_TERRA.value
        or calls[0].get("family_canary") is not True
        or calls[0].get("status") != R3LedgerStatus.FAILED.value
    ):
        raise R3AError(R3AErrorCode.FAMILY_CANARY_REQUIRED)
    for item in calls[1:]:
        if item.get("status") == R3LedgerStatus.PENDING.value:
            item["status"] = R3LedgerStatus.BLOCKED_BY_CANARY.value
            item["closed_error_code"] = "OPENAI_REVIEW_TERRA_CANARY_FAILED"
    return cast(dict[str, object], cloned)


def mutated_first_call_for_checksum_test() -> tuple[R3RemainingCallSpec, ...]:
    first, *rest = R3_REMAINING_CALL_MATRIX
    return (replace(first, max_output_tokens=first.max_output_tokens + 1), *rest)


def r3b_approval_text() -> str:
    cost = estimate_r3_cost()
    return "\n".join(
        (
            "J'approuve exclusivement l'exécution de la matrice",
            f"{R3_PLAN_VERSION},",
            f"checksum {R3_CALL_MATRIX_SHA256},",
            (
                "81 appels maximum (6 OpenAI Review : 4 gpt-5.6-sol et 2 "
                "gpt-5.6-terra, reasoning effort low, max_output_tokens 4096 ; "
                "75 Anthropic Scorer claude-sonnet-5, max_output_tokens 512),"
            ),
            f"plafond {cost.requested_hard_ceiling_usd} USD,",
            (
                "aucun retry, canary gpt-5.6-terra en premier et arrêt immédiat "
                "avant tout autre appel si ce canary échoue."
            ),
        )
    )


def r3_plan_payload(audit: R3AEvidenceAudit) -> dict[str, object]:
    cost = estimate_r3_cost()
    review_calls = [
        call for call in R3_REMAINING_CALL_MATRIX if call.workload is CalibrationWorkload.REVIEW
    ]
    scoring_calls = [
        call for call in R3_REMAINING_CALL_MATRIX if call.workload is CalibrationWorkload.SCORING
    ]
    return {
        "phase": "12.16-G2-R3A",
        "status": "PASS_CLOSED",
        "refs": {
            "branch": "phase12/12-16-provider-model-calibration",
            "entry_head": "fe6530528b00dfcb2b2d34797a97fe94ac349815",
            "entry_parent": "4d3b93be82bbda1e1600ba5a17c0c7906fcb4d50",
            "entry_main": "7ae02ee109bcc6399ec0f71616da6aef07abda81",
        },
        "proof_sets": dict(sorted(audit.proof_set_sha256.items())),
        "reused_evidence_manifest_sha256": reused_evidence_manifest_sha256(audit),
        "reused_evidence_manifest": reused_evidence_manifest_payload(audit),
        "slot_accounting": {
            "original_logical_slots": len(PEDAGOGICAL_CALIBRATION_CALL_MATRIX),
            "reused_logical_slots": len(audit.reused_mappings),
            "remaining_logical_slots": len(R3_REMAINING_CALL_MATRIX),
            "remaining_openai_review": len(review_calls),
            "remaining_anthropic_scoring": len(scoring_calls),
            "remaining_anthropic_breakdown": {
                "initial_anchor_scores": sum(
                    call.logical_slot_id.startswith("cal.score.anchor.") and call.repetition == 1
                    for call in scoring_calls
                ),
                "repeatability_scores": sum(
                    call.logical_slot_id.startswith("cal.score.anchor.") and call.repetition == 2
                    for call in scoring_calls
                ),
                "selected_output_scores": sum(
                    call.logical_slot_id.startswith("cal.score.output.") for call in scoring_calls
                ),
            },
        },
        "plan": {
            "version": R3_PLAN_VERSION,
            "matrix_sha256": R3_CALL_MATRIX_SHA256,
            "approval_required": R3_APPROVAL_REQUIRED,
            "production_review_limit_adoption": R3_PRODUCTION_REVIEW_LIMIT_ADOPTION,
            "calls": [_call_payload(call) for call in R3_REMAINING_CALL_MATRIX],
        },
        "family_readiness": {
            "OPENAI_REVIEW_SOL": {
                "status": "PASSED",
                "evidence_sha256": {
                    "ledger": R2B_LEDGER_SHA256,
                    "output": R2B_RAW_SHA256,
                },
            },
            "OPENAI_REVIEW_TERRA": {
                "status": "PENDING",
                "first_call_role": "FAMILY_CANARY",
                "first_call_id": R3_REMAINING_CALL_MATRIX[0].r3_call_id,
            },
            "ANTHROPIC_SCORER": {
                "status": "PASSED",
                "evidence_sha256": {
                    "ledger": R2_LEDGER_SHA256,
                    "output": R2_ANTHROPIC_RAW_SHA256,
                },
            },
        },
        "ledger": {
            "relative_path": R3_LEDGER_RELATIVE_PATH,
            "reused_evidence_import": "HASH_ONLY",
            "states": [status.value for status in R3LedgerStatus],
            "resume_policy": {
                "PENDING": "ONLY_EXECUTABLE_STATE",
                "STARTED": "STOP_AMBIGUOUS",
                "COMPLETED_OR_FAILED": "NEVER_RECALL",
                "retry": 0,
                "rerun": 0,
            },
        },
        "pricing": {
            "snapshot_id": R3_PRICING_SNAPSHOT_ID,
            "quotes": [
                {
                    "provider": quote.provider.value,
                    "model": quote.model,
                    "input_usd_per_million_tokens": str(quote.input_usd_per_million_tokens),
                    "cached_input_usd_per_million_tokens": str(
                        quote.cached_input_usd_per_million_tokens
                    ),
                    "output_usd_per_million_tokens": str(quote.output_usd_per_million_tokens),
                    "source_url": quote.source_url,
                }
                for quote in R3_PRICE_QUOTES
            ],
        },
        "cost": {
            "estimated_reference_usd": str(cost.estimated_reference_usd),
            "maximum_before_margin_usd": str(cost.maximum_before_margin_usd),
            "safety_margin_multiplier": str(cost.safety_margin_multiplier),
            "safety_margin_amount_usd": str(cost.safety_margin_amount_usd),
            "requested_hard_ceiling_usd": str(cost.requested_hard_ceiling_usd),
            "maximum_by_model_usd": {
                key: str(value) for key, value in cost.maximum_by_model_usd.items()
            },
            "maximum_by_workload_usd": {
                key: str(value) for key, value in cost.maximum_by_workload_usd.items()
            },
            "historical_measured_costs_usd": {
                "G2": "1.958050",
                "R2": "0.027598",
                "R2B": "0.034712",
            },
            "historical_reserves_are_actual_cost": False,
            "r3a_provider_cost_usd": "0",
            "future_r3_cost_consumed_usd": "0",
        },
        "approval_text": r3b_approval_text(),
        "execution": {
            "openai_calls": 0,
            "anthropic_calls": 0,
            "provider_cost_usd": "0",
            "r3_live_execution": "NOT_STARTED",
        },
        "adr_required": False,
    }


def render_evidence_baseline_markdown(audit: R3AEvidenceAudit) -> str:
    lines = [
        "# Phase 12.16-G2-R3A — Consolidation des preuves",
        "",
        "## Baseline et portée",
        "",
        "- Branche : `phase12/12-16-provider-model-calibration`",
        "- HEAD/upstream d'entrée : `fe6530528b00dfcb2b2d34797a97fe94ac349815`",
        "- Parent : `4d3b93be82bbda1e1600ba5a17c0c7906fcb4d50`",
        "- Main/origin-main : `7ae02ee109bcc6399ec0f71616da6aef07abda81`",
        "- Appels provider R3A : `0`",
        "- Coût provider R3A : `0 USD`",
        "- Exécution live R3 : `NOT_STARTED`",
        "",
        "## Proof sets hash-only",
        "",
        "| Chemin relatif | SHA-256 |",
        "|---|---|",
    ]
    lines.extend(
        f"| `{path}` | `{digest}` |" for path, digest in sorted(audit.proof_set_sha256.items())
    )
    lines.extend(
        [
            "",
            "## Manifeste des 15 réutilisations",
            "",
            f"SHA-256 canonique : `{reused_evidence_manifest_sha256(audit)}`",
            "",
            "| Slot logique original | Set | Classe | Modèle | Statut | Input SHA-256 | Schema SHA-256 | Output SHA-256 | Tokens in/out/total | Coût USD |",
            "|---|---|---|---|---|---|---|---|---|---|",
        ]
    )
    for item in audit.reused_mappings:
        lines.append(
            "| "
            f"`{item.original_logical_slot_id}` | `{item.evidence_set}` | "
            f"`{item.mapping_class.value}` | `{item.model}` | `{item.status}` | "
            f"`{item.input_sha256}` | `{item.schema_sha256}` | "
            f"`{item.output_sha256}` | "
            f"`{item.input_tokens}/{item.output_tokens}/{item.total_tokens}` | "
            f"`{item.cost_usd}` |"
        )
    lines.extend(
        [
            "",
            "## Selected-output dependencies",
            "",
            "| Source logique | Output SHA-256 | Appels scorer dépendants |",
            "|---|---|---|",
        ]
    )
    for item in audit.selected_output_dependencies:
        lines.append(
            f"| `{item.logical_slot_id}` | `{item.raw_output_sha256}` | "
            f"`{', '.join(item.scoring_call_ids)}` |"
        )
    lines.extend(
        [
            "",
            "Résultat : `SELECTED_OUTPUT_DEPENDENCIES = 6/6`, couvrant exactement 12 slots de scoring.",
            "",
            "## Équivalences de remédiation",
            "",
            "- Anthropic R2 mappe exactement vers `cal.score.anchor.scn-01.a.clarity.r1` avec la classe `EXACT_REMEDIATION_EQUIVALENT`.",
            "- OpenAI Review R2B mappe vers `cal.review.exercise.primary.r1` avec la classe `AUTHORIZED_PARAMETER_REMEDIATION`.",
            f"- Hash logique input original/remédiation : `{audit.r2b_original_logical_input_sha256}` / `{audit.r2b_remediation_logical_input_sha256}`.",
            f"- Hash schema original/remédiation : `{audit.r2b_original_schema_sha256}` / `{audit.r2b_remediation_schema_sha256}`.",
            "- Différences autorisées : `max_output_tokens 1024 -> 4096` et `reasoning effort implicit/default -> low`.",
            "- Le résultat R2B est `PARTIAL`, post-validé, sans incomplétude ni diagnostic privé.",
            "",
            "## Comptabilité et coûts historiques",
            "",
            "- Slots originaux : `96`",
            "- Résultats réutilisables : `15`",
            "- Slots restants : `81`",
            "- Coûts réels déjà mesurés : G2 `1.958050 USD`, R2 `0.027598 USD`, R2B `0.034712 USD`.",
            "- Les réserves historiques ne sont pas traitées comme des factures.",
            "- Aucun contenu brut n'est reproduit dans ce baseline.",
            "",
        ]
    )
    return "\n".join(lines)


def render_remaining_plan_markdown(audit: R3AEvidenceAudit) -> str:
    cost = estimate_r3_cost()
    reviews = [
        call for call in R3_REMAINING_CALL_MATRIX if call.workload is CalibrationWorkload.REVIEW
    ]
    lines = [
        "# Phase 12.16-G2-R3A — Matrice résiduelle",
        "",
        "## Gel canonique",
        "",
        f"- Plan : `{R3_PLAN_VERSION}`",
        f"- Matrice SHA-256 : `{R3_CALL_MATRIX_SHA256}`",
        f"- Manifeste réutilisé SHA-256 : `{reused_evidence_manifest_sha256(audit)}`",
        "- Approval required : `TRUE`",
        "- Retry/rerun : `0/0`",
        "- Appels live R3A : `0`",
        "- Coût live R3A : `0 USD`",
        "",
        "## Comptabilité résiduelle",
        "",
        "- `96 - 15 = 81` slots.",
        "- OpenAI Review : `6`.",
        "- Anthropic Scoring : `75` (`47` anchors initiaux, `16` répétabilités, `12` selected-output).",
        "",
        "## Reviews restantes et ordre",
        "",
        "| Ordre | Slot logique | Modèle | Profil | Effort | Max output | Rôle canary |",
        "|---:|---|---|---|---|---:|---|",
    ]
    for index, call in enumerate(reviews, start=1):
        lines.append(
            f"| {index} | `{call.logical_slot_id}` | `{call.model}` | "
            f"`{call.model_profile_id}` | `low` | 4096 | "
            f"`{'FAMILY_CANARY' if call.family_canary else 'NO'}` |"
        )
    lines.extend(
        [
            "",
            "La première Review Terra est le call 1 de toute la matrice. En cas d'échec, tous les autres appels deviennent `BLOCKED_BY_CANARY` avant tout fan-out.",
            "",
            "Les paramètres `low/4096` sont limités à la calibration remédiée. `PRODUCTION_REVIEW_LIMIT_ADOPTION = DEFERRED_TO_12.16-H`.",
            "",
            "## Readiness et ledger",
            "",
            "- `OPENAI_REVIEW_SOL = PASSED` via hashes R2B.",
            "- `ANTHROPIC_SCORER = PASSED` via hashes R2.",
            "- `OPENAI_REVIEW_TERRA = PENDING` jusqu'au canary R3.",
            f"- Ledger préparé : `{R3_LEDGER_RELATIVE_PATH}`.",
            "- États : `PENDING`, `STARTED`, `COMPLETED`, `FAILED`, `SKIPPED_DEPENDENCY_FAILED`, `BLOCKED_BY_CANARY`.",
            "- `PENDING` est le seul état exécutable ; `STARTED` est ambigu et arrête ; un terminal n'est jamais rappelé.",
            "- Le ledger importe uniquement le hash du manifeste, jamais les raws historiques.",
            "",
            "## Prix officiels revalidés",
            "",
            "| Modèle | Input / MTok | Cached input / MTok | Output / MTok | Source |",
            "|---|---:|---:|---:|---|",
        ]
    )
    for quote in R3_PRICE_QUOTES:
        lines.append(
            f"| `{quote.model}` | `{quote.input_usd_per_million_tokens}` | "
            f"`{quote.cached_input_usd_per_million_tokens}` | "
            f"`{quote.output_usd_per_million_tokens}` | {quote.source_url} |"
        )
    lines.extend(
        [
            "",
            "Terra supporte officiellement `low`, Responses et Structured Outputs ; le candidat `low/4096` est donc valide pour ses deux slots.",
            "",
            "## Coût R3 futur",
            "",
            f"- Estimation de référence : `{cost.estimated_reference_usd} USD`.",
            f"- Maximum conservateur avant marge : `{cost.maximum_before_margin_usd} USD`.",
            f"- Marge 25 % : `{cost.safety_margin_amount_usd} USD`.",
            f"- Hard ceiling demandé : `{cost.requested_hard_ceiling_usd} USD`.",
            f"- Par modèle : `{', '.join(f'{key}={value}' for key, value in cost.maximum_by_model_usd.items())}` USD.",
            "- Coût R3 déjà consommé : `0 USD`.",
            "",
            "## Approbation R3B requise",
            "",
            "```text",
            r3b_approval_text(),
            "```",
            "",
            "R3B n'est pas exécuté par R3A.",
            "",
        ]
    )
    return "\n".join(lines)


def _evidence_error() -> None:
    raise R3AError(R3AErrorCode.REUSABLE_CALIBRATION_EVIDENCE_UNAVAILABLE) from None
