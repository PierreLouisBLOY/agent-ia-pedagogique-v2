"""Freeze and transfer-scope controls for the offline V5 semantic pilot.

The module inventories the exact pedagogical payloads of the approved robust
pilot.  It resolves neither credentials nor transports and keeps live execution
closed until a later, exact owner authorization is represented separately.
"""

from __future__ import annotations

import hashlib
import json
import re
from collections import defaultdict
from collections.abc import Mapping
from dataclasses import asdict, dataclass
from decimal import Decimal
from enum import StrEnum
from pathlib import Path
from typing import NoReturn, cast

from tests.calibration.pedagogical.offline_calibration_v5 import v5_contract_sha256
from tests.calibration.pedagogical.pricing import pricing_snapshot_sha256
from tests.calibration.pedagogical.scorer_contract_v5 import (
    V5PairwiseObservation,
    V5ScorerObservation,
    v5_pairwise_output_schema,
    v5_pairwise_system_instructions,
    v5_score_output_schema,
    v5_scorer_system_instructions,
)
from tests.calibration.pedagogical.semantic_integration_v5 import (
    EXPECTED_V5_MATRIX_SHA256,
    EXPECTED_V5_SCORER_CONTRACT_SHA256,
    V5CallContract,
    V5LogicalCallSpec,
    build_robust_pilot,
    build_v5_observation,
    estimate_pilot_budget,
    v5_logical_matrix_sha256,
)

ROOT = Path(__file__).resolve().parents[3]
OWNER_SEMANTIC_PILOT_APPROVAL = "APPROVED"
PILOT_MODE = "ROBUST"
PILOT_MAX_CALL_COUNT = 21
APPROVED_PILOT_CEILING_USD = Decimal("1.017600")
APPROVED_INTEGRATION_MANIFEST_PATH = Path(
    "docs/development/phase_12_16_g2_v5_semantic_validation_integration_offline/"
    "MANIFEST_SHA256.txt"
)
APPROVED_INTEGRATION_MANIFEST_SHA256 = (
    "6f7ef49bef952353787c6afa38fff38e5c36eb2b6f103bb32653707dbd56472f"
)
EXPECTED_ROBUST_PILOT_SELECTION_SHA256 = (
    "97c0a4a138f0539848f8ee644693fc9e130d9dcc6120da07d352deda6d96f2b2"
)
EXPECTED_PEDAGOGICAL_TRANSFER_SCOPE_SHA256 = (
    "c65e6460969d3eee4a5fb6a5d99e0a9bfbf3a253efc111ebb64e4af788df0e93"
)
V42_LEDGER_PATH = Path("artifacts/calibration/12.16-g2-v4-2/ledger.json")
V42_LEDGER_SHA256 = (
    "7d173accfc7591998d7cab1625a6ad562f1e530fc24027aea5f322a9c44bd10a"
)
V42_RAW_DIRECTORY = Path("artifacts/calibration/12.16-g2-v4-2/raw")
PEDAGOGICAL_TRANSFER_AUTHORIZED = False
LIVE_PROVIDER_RECALIBRATION_AUTHORIZED = False

_EMAIL = re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b")
_LOCAL_PATH = re.compile(r"(?:[A-Za-z]:[\\/]|file://|/(?:Users|home|var|tmp)/)")
_PHONE = re.compile(r"(?<!\d)(?:\+33|0)[1-9](?:[ .-]?\d{2}){4}(?!\d)")
_SENSITIVE = re.compile(
    r"(?i)(?:api[_ -]?key|password|passwd|bearer\s+[A-Za-z0-9._-]+|"
    r"credential|secret[_ -]?key|sqlite|raw_output_path)"
)


class TransferProjectionName(StrEnum):
    ABSOLUTE_ANCHOR = "V5_ABSOLUTE_ANCHOR_OBSERVATION"
    PAIRWISE_ANCHOR = "V5_PAIRWISE_ANCHOR_OBSERVATION"
    PAIRWISE_SELECTED_OUTPUT = "V5_PAIRWISE_SELECTED_OUTPUT_OBSERVATION"


class TransferScopeErrorCode(StrEnum):
    POST_APPROVAL_TECHNICAL_DRIFT = "POST_APPROVAL_TECHNICAL_DRIFT"
    SOURCE_LEDGER_INVALID = "SOURCE_LEDGER_INVALID"
    SOURCE_RAW_OUTPUT_INVALID = "SOURCE_RAW_OUTPUT_INVALID"
    TRANSFER_FIELD_FORBIDDEN = "TRANSFER_FIELD_FORBIDDEN"
    TRANSFER_CONTENT_FORBIDDEN = "TRANSFER_CONTENT_FORBIDDEN"
    TRANSFER_SCOPE_MISMATCH = "TRANSFER_SCOPE_MISMATCH"
    TRANSFER_SCOPE_AUTHORIZATION_REQUIRED = "TRANSFER_SCOPE_AUTHORIZATION_REQUIRED"
    LIVE_EXECUTION_FORBIDDEN = "LIVE_EXECUTION_FORBIDDEN"


class TransferScopeError(RuntimeError):
    code: TransferScopeErrorCode

    def __init__(self, code: TransferScopeErrorCode) -> None:
        self.code = code
        super().__init__(code.value)


@dataclass(frozen=True, slots=True)
class PedagogicalTransferEnvelope:
    call_id: str
    projection_name: TransferProjectionName
    model: str
    max_output_tokens: int
    system: str
    input_payload: dict[str, object]
    output_schema: dict[str, object]

    def transfer_payload(self) -> dict[str, object]:
        """Return only the logical request fields allowed to cross the boundary."""

        return {
            "model": self.model,
            "max_output_tokens": self.max_output_tokens,
            "system": self.system,
            "input": self.input_payload,
            "output_schema": self.output_schema,
        }

    def transfer_payload_sha256(self) -> str:
        return _canonical_sha256(self.transfer_payload())


@dataclass(frozen=True, slots=True)
class PedagogicalTransferInventoryItem:
    projection_name: TransferProjectionName
    source_local: str
    transformation: str
    fields_included: tuple[str, ...]
    fields_excluded: tuple[str, ...]
    provider: str
    purpose: str
    payload_instance_count: int
    pedagogical_projection_occurrence_count: int
    estimated_utf8_bytes: int
    personal_data_present: bool
    secrets_present: bool
    schema_or_payload_template_sha256: str


def robust_pilot_selection_sha256() -> str:
    call_ids = [item.call.call_id for item in build_robust_pilot().calls]
    return _canonical_sha256(call_ids)


def validate_post_approval_no_drift() -> None:
    manifest_path = ROOT / APPROVED_INTEGRATION_MANIFEST_PATH
    if _sha256(manifest_path.read_bytes()) != APPROVED_INTEGRATION_MANIFEST_SHA256:
        _error(TransferScopeErrorCode.POST_APPROVAL_TECHNICAL_DRIFT)
    plan = build_robust_pilot()
    budget = estimate_pilot_budget(plan)
    if (
        OWNER_SEMANTIC_PILOT_APPROVAL != "APPROVED"
        or PILOT_MODE != "ROBUST"
        or len(plan.calls) != PILOT_MAX_CALL_COUNT
        or budget.proposed_pilot_ceiling_usd != APPROVED_PILOT_CEILING_USD
        or v5_logical_matrix_sha256() != EXPECTED_V5_MATRIX_SHA256
        or v5_contract_sha256() != EXPECTED_V5_SCORER_CONTRACT_SHA256
        or pricing_snapshot_sha256()
        != "31f2a9287845da8986448f62abe312b2290af5e9578ff61643d1cb0045bfe1b8"
        or robust_pilot_selection_sha256()
        != EXPECTED_ROBUST_PILOT_SELECTION_SHA256
        or len(plan.canary_call_ids) != 4
        or len(plan.fanout_call_ids) != 17
    ):
        _error(TransferScopeErrorCode.POST_APPROVAL_TECHNICAL_DRIFT)


def build_pedagogical_transfer_envelopes() -> tuple[PedagogicalTransferEnvelope, ...]:
    output_projections = _selected_output_projections()
    envelopes: list[PedagogicalTransferEnvelope] = []
    for spec in build_robust_pilot().calls:
        observation = build_v5_observation(spec, output_projections)
        projection_name = _projection_name(spec)
        if type(observation) is V5ScorerObservation:
            system = v5_scorer_system_instructions()
            schema = v5_score_output_schema()
        elif type(observation) is V5PairwiseObservation:
            system = v5_pairwise_system_instructions()
            schema = v5_pairwise_output_schema()
        else:
            _error(TransferScopeErrorCode.TRANSFER_FIELD_FORBIDDEN)
        envelope = PedagogicalTransferEnvelope(
            call_id=spec.call.call_id,
            projection_name=projection_name,
            model=spec.call.model,
            max_output_tokens=spec.call.max_output_tokens,
            system=system,
            input_payload=cast(dict[str, object], observation.as_payload()),
            output_schema=schema,
        )
        validate_transfer_envelope(envelope)
        envelopes.append(envelope)
    if len(envelopes) != PILOT_MAX_CALL_COUNT:
        _error(TransferScopeErrorCode.TRANSFER_SCOPE_MISMATCH)
    return tuple(envelopes)


def build_pedagogical_transfer_inventory(
    envelopes: tuple[PedagogicalTransferEnvelope, ...] | None = None,
) -> tuple[PedagogicalTransferInventoryItem, ...]:
    items = envelopes or build_pedagogical_transfer_envelopes()
    grouped: defaultdict[
        TransferProjectionName, list[PedagogicalTransferEnvelope]
    ] = defaultdict(list)
    for item in items:
        validate_transfer_envelope(item)
        grouped[item.projection_name].append(item)
    definitions = {
        TransferProjectionName.ABSOLUTE_ANCHOR: (
            "tests/calibration/pedagogical/anchor_corpus_v4.py",
            "V4 anchor -> bounded V5 absolute observation; tier and expectation removed",
            15,
            "Score one anchor against one criterion on the evidence-first 0-4 scale",
        ),
        TransferProjectionName.PAIRWISE_ANCHOR: (
            "tests/calibration/pedagogical/anchor_corpus_v4.py",
            "two V4 anchors -> one blinded V5 direct-pairwise observation",
            10,
            "Compare two anchors directly on one criterion",
        ),
        TransferProjectionName.PAIRWISE_SELECTED_OUTPUT: (
            "artifacts/calibration/12.16-g2-v4-2/raw (local ignored source)",
            "verified raw JSON -> sections[code,text] only -> two bounded projections",
            2,
            "Test a direct tie decision on two minimized SCN-03 outputs",
        ),
    }
    result: list[PedagogicalTransferInventoryItem] = []
    for name in TransferProjectionName:
        category = grouped[name]
        if not category:
            _error(TransferScopeErrorCode.TRANSFER_SCOPE_MISMATCH)
        source, transformation, projection_count, purpose = definitions[name]
        result.append(
            PedagogicalTransferInventoryItem(
                projection_name=name,
                source_local=source,
                transformation=transformation,
                fields_included=(
                    "model",
                    "max_output_tokens",
                    "system",
                    "input.contract_version",
                    "input.opaque_observation_or_comparison_id",
                    "input.scenario",
                    "input.criterion",
                    "input.candidate_projection(s)",
                    "output_schema",
                ),
                fields_excluded=(
                    "tier",
                    "expected_score_or_decision",
                    "provider_or_producer_identity",
                    "local_path",
                    "raw_output_path",
                    "raw_file",
                    "warnings",
                    "uncertainties",
                    "credentials",
                    "secrets",
                    "personal_data",
                    "sqlite",
                    "source_document",
                    "out_of_scope_content",
                ),
                provider="anthropic",
                purpose=purpose,
                payload_instance_count=len(category),
                pedagogical_projection_occurrence_count=projection_count,
                estimated_utf8_bytes=sum(
                    len(_canonical_json(item.transfer_payload()).encode("utf-8"))
                    for item in category
                ),
                personal_data_present=False,
                secrets_present=False,
                schema_or_payload_template_sha256=_category_template_sha256(
                    category[0]
                ),
            )
        )
    return tuple(result)


def pedagogical_transfer_scope_payload() -> dict[str, object]:
    envelopes = build_pedagogical_transfer_envelopes()
    inventory = build_pedagogical_transfer_inventory(envelopes)
    return {
        "scope_version": "12.16-g2-v5-robust-pilot-transfer-scope-v1",
        "provider": "anthropic",
        "matrix_sha256": EXPECTED_V5_MATRIX_SHA256,
        "scorer_contract_sha256": EXPECTED_V5_SCORER_CONTRACT_SHA256,
        "pilot_mode": PILOT_MODE,
        "pilot_max_call_count": PILOT_MAX_CALL_COUNT,
        "inventory": [
            {
                **asdict(item),
                "projection_name": item.projection_name.value,
            }
            for item in inventory
        ],
        "records": [
            {
                "call_id": item.call_id,
                "projection_name": item.projection_name.value,
                "transfer_payload": item.transfer_payload(),
            }
            for item in envelopes
        ],
        "forbidden_categories": (
            "sqlite",
            "complete_files",
            "local_paths",
            "credentials",
            "secrets",
            "personal_data",
            "out_of_scope_content",
        ),
    }


def pedagogical_transfer_scope_sha256() -> str:
    digest = _canonical_sha256(pedagogical_transfer_scope_payload())
    if (
        EXPECTED_PEDAGOGICAL_TRANSFER_SCOPE_SHA256 != "TO_BE_COMPUTED"
        and digest != EXPECTED_PEDAGOGICAL_TRANSFER_SCOPE_SHA256
    ):
        _error(TransferScopeErrorCode.TRANSFER_SCOPE_MISMATCH)
    return digest


def validate_transfer_envelope(envelope: PedagogicalTransferEnvelope) -> None:
    payload = envelope.transfer_payload()
    if set(payload) != {
        "model",
        "max_output_tokens",
        "system",
        "input",
        "output_schema",
    }:
        _error(TransferScopeErrorCode.TRANSFER_FIELD_FORBIDDEN)
    if envelope.model != "claude-sonnet-5" or envelope.max_output_tokens != 2_048:
        _error(TransferScopeErrorCode.TRANSFER_FIELD_FORBIDDEN)
    _validate_input_shape(envelope.projection_name, envelope.input_payload)
    _validate_no_forbidden_content(payload)


class TransferScopeGuard:
    """Last pure-data gate before any future credential or transport boundary."""

    def authorize_before_transport(
        self,
        *,
        envelopes: tuple[PedagogicalTransferEnvelope, ...],
        authorized_transfer_scope_sha256: str | None,
    ) -> tuple[PedagogicalTransferEnvelope, ...]:
        validate_post_approval_no_drift()
        expected_call_ids = tuple(
            item.call.call_id for item in build_robust_pilot().calls
        )
        if tuple(item.call_id for item in envelopes) != expected_call_ids:
            _error(TransferScopeErrorCode.TRANSFER_SCOPE_MISMATCH)
        for envelope in envelopes:
            validate_transfer_envelope(envelope)
        actual = _scope_sha256_for_envelopes(envelopes)
        expected = pedagogical_transfer_scope_sha256()
        if actual != expected:
            _error(TransferScopeErrorCode.TRANSFER_SCOPE_MISMATCH)
        if authorized_transfer_scope_sha256 is None:
            _error(TransferScopeErrorCode.TRANSFER_SCOPE_AUTHORIZATION_REQUIRED)
        if authorized_transfer_scope_sha256 != expected:
            _error(TransferScopeErrorCode.TRANSFER_SCOPE_MISMATCH)
        if PEDAGOGICAL_TRANSFER_AUTHORIZED is not True:
            _error(TransferScopeErrorCode.TRANSFER_SCOPE_AUTHORIZATION_REQUIRED)
        if LIVE_PROVIDER_RECALIBRATION_AUTHORIZED is not True:
            _error(TransferScopeErrorCode.LIVE_EXECUTION_FORBIDDEN)
        return envelopes


def validate_freeze_readiness() -> None:
    validate_post_approval_no_drift()
    envelopes = build_pedagogical_transfer_envelopes()
    inventory = build_pedagogical_transfer_inventory(envelopes)
    if (
        len(envelopes) != 21
        or tuple(item.payload_instance_count for item in inventory) != (15, 5, 1)
        or tuple(
            item.pedagogical_projection_occurrence_count for item in inventory
        )
        != (15, 10, 2)
        or any(item.personal_data_present or item.secrets_present for item in inventory)
    ):
        _error(TransferScopeErrorCode.TRANSFER_SCOPE_MISMATCH)
    pedagogical_transfer_scope_sha256()


def _scope_sha256_for_envelopes(
    envelopes: tuple[PedagogicalTransferEnvelope, ...],
) -> str:
    canonical = pedagogical_transfer_scope_payload()
    canonical["records"] = [
        {
            "call_id": item.call_id,
            "projection_name": item.projection_name.value,
            "transfer_payload": item.transfer_payload(),
        }
        for item in envelopes
    ]
    return _canonical_sha256(canonical)


def _projection_name(spec: V5LogicalCallSpec) -> TransferProjectionName:
    if spec.contract is V5CallContract.V5_ABSOLUTE_SCORE:
        return TransferProjectionName.ABSOLUTE_ANCHOR
    if all(ref.startswith("anchor:") for ref in spec.call.input_refs):
        return TransferProjectionName.PAIRWISE_ANCHOR
    if all(ref.startswith("output:") for ref in spec.call.input_refs):
        return TransferProjectionName.PAIRWISE_SELECTED_OUTPUT
    _error(TransferScopeErrorCode.TRANSFER_FIELD_FORBIDDEN)


def _selected_output_projections() -> dict[str, str]:
    ledger_path = ROOT / V42_LEDGER_PATH
    if _sha256(ledger_path.read_bytes()) != V42_LEDGER_SHA256:
        _error(TransferScopeErrorCode.SOURCE_LEDGER_INVALID)
    try:
        ledger = json.loads(ledger_path.read_text(encoding="utf-8"))
        calls = ledger["calls"]
    except (OSError, json.JSONDecodeError, KeyError, TypeError):
        _error(TransferScopeErrorCode.SOURCE_LEDGER_INVALID)
    if type(calls) is not list:
        _error(TransferScopeErrorCode.SOURCE_LEDGER_INVALID)
    required = (
        "cal.generation.course.primary.r1",
        "cal.generation.course.fallback.r1",
    )
    records = {
        raw.get("call_id"): raw
        for raw in calls
        if type(raw) is dict and raw.get("call_id") in required
    }
    if set(records) != set(required):
        _error(TransferScopeErrorCode.SOURCE_LEDGER_INVALID)
    return {call_id: _minimized_output_projection(records[call_id]) for call_id in required}


def _minimized_output_projection(record: Mapping[str, object]) -> str:
    relative = record.get("raw_output_path")
    expected = record.get("raw_output_sha256")
    status = record.get("status")
    if (
        type(relative) is not str
        or type(expected) is not str
        or status != "COMPLETED"
    ):
        _error(TransferScopeErrorCode.SOURCE_RAW_OUTPUT_INVALID)
    allowed_root = (ROOT / V42_RAW_DIRECTORY).resolve()
    path = (ROOT / relative).resolve()
    if not path.is_relative_to(allowed_root) or path.suffix != ".json":
        _error(TransferScopeErrorCode.SOURCE_RAW_OUTPUT_INVALID)
    raw_bytes = path.read_bytes()
    if _sha256(raw_bytes) != expected:
        _error(TransferScopeErrorCode.SOURCE_RAW_OUTPUT_INVALID)
    try:
        payload = json.loads(raw_bytes)
    except json.JSONDecodeError:
        _error(TransferScopeErrorCode.SOURCE_RAW_OUTPUT_INVALID)
    if type(payload) is not dict or set(payload) != {
        "outcome",
        "sections",
        "warnings",
        "uncertainties",
    }:
        _error(TransferScopeErrorCode.SOURCE_RAW_OUTPUT_INVALID)
    if payload["warnings"] != [] or payload["uncertainties"] != []:
        _error(TransferScopeErrorCode.SOURCE_RAW_OUTPUT_INVALID)
    sections = payload["sections"]
    if type(sections) is not list or not sections:
        _error(TransferScopeErrorCode.SOURCE_RAW_OUTPUT_INVALID)
    projected: list[str] = []
    for section in sections:
        if type(section) is not dict or set(section) != {"code", "text"}:
            _error(TransferScopeErrorCode.SOURCE_RAW_OUTPUT_INVALID)
        code = section["code"]
        text = section["text"]
        if type(code) is not str or type(text) is not str or not code or not text:
            _error(TransferScopeErrorCode.SOURCE_RAW_OUTPUT_INVALID)
        projected.append(f"[{code}] {text}")
    projection = "\n".join(projected)
    if len(projection) > 2_500:
        _error(TransferScopeErrorCode.SOURCE_RAW_OUTPUT_INVALID)
    return projection


def _validate_input_shape(
    projection_name: TransferProjectionName,
    payload: dict[str, object],
) -> None:
    common = {"contract_version", "scenario", "criterion"}
    if projection_name is TransferProjectionName.ABSOLUTE_ANCHOR:
        expected = common | {"observation_id", "candidate_projection"}
    else:
        expected = common | {"comparison_id", "candidate_a", "candidate_b"}
    if set(payload) != expected:
        _error(TransferScopeErrorCode.TRANSFER_FIELD_FORBIDDEN)
    scenario = payload.get("scenario")
    criterion = payload.get("criterion")
    if type(scenario) is not dict or set(scenario) != {
        "scenario_code",
        "pedagogical_level",
        "task_kind",
        "reference_constraints",
        "required_sections",
    }:
        _error(TransferScopeErrorCode.TRANSFER_FIELD_FORBIDDEN)
    if type(criterion) is not dict or set(criterion) != {
        "criterion_ref",
        "measured_dimension",
        "not_measured",
        "observable_checks",
        "scale_version",
        "level_descriptors",
    }:
        _error(TransferScopeErrorCode.TRANSFER_FIELD_FORBIDDEN)
    if projection_name is not TransferProjectionName.ABSOLUTE_ANCHOR:
        for key in ("candidate_a", "candidate_b"):
            candidate = payload.get(key)
            if type(candidate) is not dict or set(candidate) != {
                "candidate_id",
                "projection",
            }:
                _error(TransferScopeErrorCode.TRANSFER_FIELD_FORBIDDEN)


def _validate_no_forbidden_content(value: object) -> None:
    if type(value) is dict:
        for key, item in value.items():
            if key in {
                "tier",
                "expected_score",
                "expected_decision",
                "raw_output_path",
                "credential",
                "secret",
                "local_path",
            }:
                _error(TransferScopeErrorCode.TRANSFER_FIELD_FORBIDDEN)
            _validate_no_forbidden_content(item)
        return
    if type(value) is list or type(value) is tuple:
        for item in value:
            _validate_no_forbidden_content(item)
        return
    if type(value) is str and (
        _EMAIL.search(value)
        or _LOCAL_PATH.search(value)
        or _PHONE.search(value)
        or _SENSITIVE.search(value)
    ):
        _error(TransferScopeErrorCode.TRANSFER_CONTENT_FORBIDDEN)


def _category_template_sha256(envelope: PedagogicalTransferEnvelope) -> str:
    template = {
        "projection_name": envelope.projection_name.value,
        "system": envelope.system,
        "input_shape": _shape(envelope.input_payload),
        "output_schema": envelope.output_schema,
        "model": envelope.model,
        "max_output_tokens": envelope.max_output_tokens,
    }
    return _canonical_sha256(template)


def _shape(value: object) -> object:
    if type(value) is dict:
        return {key: _shape(item) for key, item in sorted(value.items())}
    if type(value) is list:
        return [_shape(value[0])] if value else []
    return type(value).__name__


def _canonical_json(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"), sort_keys=True)


def _canonical_sha256(value: object) -> str:
    return _sha256(_canonical_json(value).encode("utf-8"))


def _sha256(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _error(code: TransferScopeErrorCode) -> NoReturn:
    raise TransferScopeError(code) from None
