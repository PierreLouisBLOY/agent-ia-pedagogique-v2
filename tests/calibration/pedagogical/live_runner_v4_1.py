"""Offline-tested, resumable and owner-gated G2 V4 calibration runner."""

from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
import time
from collections import defaultdict
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import ROUND_CEILING, Decimal
from enum import StrEnum
from fractions import Fraction
from pathlib import Path
from typing import Protocol, cast

from backend.adapters.outbound.generation.openai import OpenAIGenerationAdapter
from backend.adapters.outbound.openai import (
    OpenAIReasoningEffort,
    OpenAIResponsesRequest,
    OpenAIResponsesResponse,
    OpenAIResponsesTransport,
    OpenAIResponsesTransportFactory,
    OpenAISDKResponsesTransportFactory,
    OpenAITransportError,
)
from backend.adapters.outbound.review.openai import OpenAIReviewAdapter
from backend.agent_runtime.agents.generation import (
    GenerationOperation,
    GenerationPortError,
    GenerationPortRequest,
    GenerationPortResultStatus,
)
from backend.agent_runtime.agents.review import (
    ReviewOperation,
    ReviewPortError,
    ReviewPortRequest,
    ReviewPortResultStatus,
)
from backend.agent_runtime.contracts import BudgetSpec, ReviewDimension
from backend.core_contracts.capability import CapabilityId
from backend.infrastructure.config.schemas.provider import (
    ModelCode,
    ModelContextLimits,
    ModelProfileConfig,
    ModelProfileId,
    ProviderCode,
    ProviderInvocationLimits,
    ProviderProfileConfig,
    ProviderProfileId,
    ProviderWorkloadKind,
)
from backend.infrastructure.config.secrets.provider import (
    EnvironmentProviderSecretResolver,
    ProviderCredentialRef,
)
from backend.shared_kernel.identifiers import TypedEntityId
from backend.shared_kernel.references import ObjectVersionRef, TypedEntityRef, VersionRef
from evaluation_harness import (
    EvaluationObservationFieldCode,
    EvaluationScorerRef,
    ObservationField,
    ObservationObject,
    ObservationScalar,
    ObservationScalarKind,
    ObservationSequence,
    ScoreStatus,
)
from tests.calibration.pedagogical.anchor_corpus_v4 import (
    V4_CRITERION_ORDERINGS,
    v4_calibration_corpus_sha256,
)
from tests.calibration.pedagogical.call_plan_v4_1 import (
    ANTHROPIC_CALL_COUNT,
    COST_SAFETY_MARGIN,
    OPENAI_CALL_COUNT,
    PEDAGOGICAL_CALIBRATION_CALL_MATRIX,
    PEDAGOGICAL_CALIBRATION_PLAN_VERSION,
    RAW_OUTPUT_DIRECTORY,
    V4_ANCHOR_BY_SCENARIO_TIER,
    V4_TIER_BY_ANCHOR_ID,
    CalibrationBudgetGuard,
    CalibrationCallSpec,
    CalibrationProvider,
    CalibrationRole,
    CalibrationWorkload,
    call_matrix_sha256,
    estimate_call_plan_cost,
    validate_call_matrix_contracts,
)
from tests.calibration.pedagogical.catalog import (
    AnchorTier,
    CalibrationScenario,
    anchor_by_id,
    scenario_by_code,
)
from tests.calibration.pedagogical.metrics import (
    CalibrationResponseStatus,
    InvocationObservation,
    PairwiseQualityObservation,
    QualityScoreObservation,
    RepeatScore,
    summarize_invocations,
    summarize_orderings,
    summarize_pairwise_quality,
    summarize_quality,
    summarize_repeatability,
)
from tests.calibration.pedagogical.pricing import (
    EXPECTED_PRICING_SNAPSHOT_SHA256,
    MODEL_PRICE_BY_NAME,
    PRICING_SNAPSHOT_ID,
    pricing_snapshot_payload,
    pricing_snapshot_sha256,
)
from tests.calibration.pedagogical.protocol import (
    CALIBRATION_CRITERION_ITEMS,
    MAX_CANDIDATE_PROJECTION_CHARACTERS,
    SCORER_OBSERVATION_FIELD_CODES,
    V4_CALIBRATION_CRITERION_ITEMS,
    build_blind_scorer_observation,
    build_v4_blind_scorer_observation,
)
from tests.calibration.pedagogical.v4_corrective_attestation_closure import (
    CORRECTED_FORM_SHA256,
    build_closure_payload,
)
from tests.providers.anthropic import (
    AnthropicEvaluationScorer,
    AnthropicProviderErrorType,
    AnthropicScorerError,
    AnthropicScoringRequest,
    AnthropicScoringResponse,
    AnthropicScoringTransport,
    AnthropicScoringTransportFactory,
    AnthropicSDKScoringTransportFactory,
    AnthropicStopReason,
    AnthropicTransportError,
)

ROOT = Path(__file__).resolve().parents[3]
EXPECTED_MATRIX_SHA256 = "94eb067ac7dd8498eeb2605ee506315fd0c831259f454555ecac88acbe94403a"
V4_CLOSURE_COMMIT = "a3de3a86f5ddd9afea10d71a277854458a7d4b5f"
EXPECTED_V4_CORPUS_SHA256 = (
    "9c8e262028f1d63fa50963f2f8bcb742e4c24d4e106a73244861416f826ca034"
)
PROPOSED_TECHNICAL_CEILING_USD = Decimal("4.984760")
OWNER_CONFIGURATION_APPROVAL = "APPROVED"
APPROVED_MATRIX_SHA256: str | None = EXPECTED_MATRIX_SHA256
APPROVED_PRICING_SHA256: str | None = EXPECTED_PRICING_SNAPSHOT_SHA256
APPROVED_MAX_CALL_COUNT: int | None = 102
APPROVED_HARD_CEILING_USD: Decimal | None = Decimal("4.984760")
OWNER_APPROVED_MANIFEST_SHA256 = (
    "79a2a967dca8fdc575e5efcc1138f44d7bfe00e5ac3e4ecf5bbc7478dba3a81d"
)
BASELINE_LIVE_AUTHORIZATION_DEFAULT = False
LIVE_PROVIDER_RECALIBRATION_AUTHORIZED = BASELINE_LIVE_AUTHORIZATION_DEFAULT
LEDGER_RELATIVE_PATH = "artifacts/calibration/12.16-g2-v4-1/ledger.json"
REPORT_JSON_RELATIVE_PATH = (
    "artifacts/calibration/12.16-g2-v4-1/safe_report.json"
)
REPORT_MARKDOWN_RELATIVE_PATH = (
    "artifacts/calibration/12.16-g2-v4-1/safe_report.md"
)
LIVE_FLAG = "RUN_PEDAGOGICAL_LIVE_CALIBRATION"
LIVE_OUTPUT_PATH_ENV = "PEDAGOGICAL_CALIBRATION_OUTPUT_PATH"
APPROVED_CEILING_ENV = "PEDAGOGICAL_CALIBRATION_APPROVED_CEILING_USD"

_CURRENT_PRICING_SNAPSHOT = pricing_snapshot_payload()
_G1_HISTORICAL_PRICING = {
    "snapshot_id": "official-2026-08-29",
    "terra_input_output_usd_per_mtok": "2.00/12.00",
    "sol_input_output_usd_per_mtok": "4.00/20.00",
    "sonnet_input_output_usd_per_mtok": "3.00/15.00",
    "estimated_base_cost_usd": "1.087576",
    "estimated_maximum_with_margin_usd": "4.096440",
}
_REPORT_FORBIDDEN_MARKERS = (
    "OPENAI_API_KEY=",
    "ANTHROPIC_API_KEY=",
    'api_key":"sk-',
    'authorization":"bearer ',
    "C:\\Users\\",
    "/Users/",
    "[context] La ressource porte",
    "[objective] Distinguer une finalite",
)


class LedgerCallStatus(StrEnum):
    PENDING = "PENDING"
    STARTED = "STARTED"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    SKIPPED_DEPENDENCY_FAILED = "SKIPPED_DEPENDENCY_FAILED"


class LiveCalibrationStopCode(StrEnum):
    V4_CLOSURE_BASELINE_MISMATCH = "V4_CLOSURE_BASELINE_MISMATCH"
    V4_CORRECTED_FORM_MISMATCH = "V4_CORRECTED_FORM_MISMATCH"
    V4_CORPUS_MISMATCH = "V4_CORPUS_MISMATCH"
    V4_HUMAN_PREVALIDATION_NOT_PASS = "V4_HUMAN_PREVALIDATION_NOT_PASS"
    V4_WORKTREE_DIRTY = "V4_WORKTREE_DIRTY"
    V4_BASELINE_COMMIT_NOT_ANCESTOR = "V4_BASELINE_COMMIT_NOT_ANCESTOR"
    MATRIX_MISMATCH = "MATRIX_MISMATCH"
    PRICING_SNAPSHOT_MISMATCH = "PRICING_SNAPSHOT_MISMATCH"
    OWNER_CONFIGURATION_MISMATCH = "OWNER_CONFIGURATION_MISMATCH"
    LIVE_OWNER_AUTHORIZATION_REQUIRED = "LIVE_OWNER_AUTHORIZATION_REQUIRED"
    LIVE_PROVIDER_CREDENTIAL_REQUIRED = "LIVE_PROVIDER_CREDENTIAL_REQUIRED"
    LIVE_ENVIRONMENT_GATE_CLOSED = "LIVE_ENVIRONMENT_GATE_CLOSED"
    RAW_OUTPUT_PATH_UNSAFE = "RAW_OUTPUT_PATH_UNSAFE"
    APPROVED_CEILING_INSUFFICIENT = "APPROVED_CEILING_INSUFFICIENT"
    LEDGER_INVALID = "LEDGER_INVALID"
    AMBIGUOUS_STARTED_CALL = "AMBIGUOUS_STARTED_CALL"
    CALL_ORDER_MISMATCH = "CALL_ORDER_MISMATCH"
    CALL_IDENTITY_MISMATCH = "CALL_IDENTITY_MISMATCH"
    ACTUAL_COST_UNAVAILABLE = "ACTUAL_COST_UNAVAILABLE"
    REPORT_REPRODUCIBILITY_FAILED = "REPORT_REPRODUCIBILITY_FAILED"
    CANARY_REQUIRED = "CANARY_REQUIRED"
    CANARY_BLOCKED = "CANARY_BLOCKED"
    CANARY_ALREADY_TERMINAL = "CANARY_ALREADY_TERMINAL"
    AUTHORIZATION_PROVENANCE_MISMATCH = "AUTHORIZATION_PROVENANCE_MISMATCH"


class LiveCalibrationStop(RuntimeError):
    code: LiveCalibrationStopCode

    def __init__(self, code: LiveCalibrationStopCode) -> None:
        self.code = code
        super().__init__(code.value)


class ProviderWorkloadFamily(StrEnum):
    OPENAI_GENERATION_CORRECTION = "OPENAI_GENERATION_CORRECTION"
    OPENAI_REVIEW = "OPENAI_REVIEW"
    ANTHROPIC_SCORER = "ANTHROPIC_SCORER"


class ProviderTransportCategory(StrEnum):
    INVALID_REQUEST = "INVALID_REQUEST"
    AUTHENTICATION = "AUTHENTICATION"
    PERMISSION = "PERMISSION"
    BILLING = "BILLING"
    RATE_LIMIT = "RATE_LIMIT"
    NOT_FOUND = "NOT_FOUND"
    TIMEOUT = "TIMEOUT"
    CONNECTION = "CONNECTION"
    SERVER = "SERVER"
    REFUSED = "REFUSED"
    UNAVAILABLE = "UNAVAILABLE"


class _CanaryState(StrEnum):
    PENDING = "PENDING"
    PASSED = "PASSED"
    BLOCKED = "BLOCKED"


class StructuredOutputValidationStatus(StrEnum):
    PASSED = "PASSED"
    FAILED = "FAILED"
    NOT_EVALUATED = "NOT_EVALUATED"


class ReviewOutputDiagnosticCategory(StrEnum):
    OUTPUT_TRUNCATED_CONFIRMED = "OUTPUT_TRUNCATED_CONFIRMED"
    OUTPUT_TRUNCATION_SUSPECTED = "OUTPUT_TRUNCATION_SUSPECTED"
    STRUCTURED_OUTPUT_INVALID_OTHER = "STRUCTURED_OUTPUT_INVALID_OTHER"


@dataclass(frozen=True, slots=True)
class RuntimeAuthorizationProvenance:
    effective: bool = False
    authorized_baseline_commit_sha: str | None = None
    authorized_matrix_sha256: str | None = None
    authorized_pricing_sha256: str | None = None
    authorized_max_call_count: int | None = None
    authorized_hard_ceiling_usd: Decimal | None = None
    attestation_source: str | None = None

    def as_ledger_payload(self) -> dict[str, object]:
        return {
            "baseline_live_authorization_default": (
                BASELINE_LIVE_AUTHORIZATION_DEFAULT
            ),
            "runtime_live_authorization_effective": self.effective,
            "authorized_baseline_commit_sha": self.authorized_baseline_commit_sha,
            "authorized_matrix_sha256": self.authorized_matrix_sha256,
            "authorized_pricing_sha256": self.authorized_pricing_sha256,
            "authorized_max_call_count": self.authorized_max_call_count,
            "authorized_hard_ceiling_usd": (
                str(self.authorized_hard_ceiling_usd)
                if self.authorized_hard_ceiling_usd is not None
                else None
            ),
            "attestation_source": self.attestation_source,
        }


CLOSED_RUNTIME_AUTHORIZATION = RuntimeAuthorizationProvenance()


class SystemicCanaryBreaker:
    """Require one successful, ledger-backed canary before family fan-out."""

    def __init__(
        self,
        *,
        states: Mapping[ProviderWorkloadFamily, _CanaryState] | None = None,
        failure_categories: Mapping[
            ProviderWorkloadFamily, ProviderTransportCategory
        ]
        | None = None,
    ) -> None:
        self._states = {
            family: (states or {}).get(family, _CanaryState.PENDING)
            for family in ProviderWorkloadFamily
        }
        self._failure_categories = dict(failure_categories or {})

    @classmethod
    def from_ledger(cls, ledger: Mapping[str, object]) -> SystemicCanaryBreaker:
        raw_canaries = cast(dict[str, dict[str, object]], ledger["canaries"])
        states = {
            family: _CanaryState(cast(str, raw_canaries[family.value]["state"]))
            for family in ProviderWorkloadFamily
        }
        failures = {
            family: ProviderTransportCategory(cast(str, raw["failure_category"]))
            for family in ProviderWorkloadFamily
            if (raw := raw_canaries[family.value]).get("failure_category")
            is not None
        }
        return cls(states=states, failure_categories=failures)

    def authorize(
        self,
        family: ProviderWorkloadFamily,
        *,
        is_canary: bool,
    ) -> None:
        state = self._states[family]
        if state is _CanaryState.BLOCKED:
            _stop(LiveCalibrationStopCode.CANARY_BLOCKED)
        if is_canary:
            if state is not _CanaryState.PENDING:
                _stop(LiveCalibrationStopCode.CANARY_ALREADY_TERMINAL)
            return
        if state is not _CanaryState.PASSED:
            _stop(LiveCalibrationStopCode.CANARY_REQUIRED)

    def record_canary(
        self,
        family: ProviderWorkloadFamily,
        *,
        succeeded: bool,
        failure_category: ProviderTransportCategory | None = None,
    ) -> None:
        if self._states[family] is not _CanaryState.PENDING:
            _stop(LiveCalibrationStopCode.CANARY_ALREADY_TERMINAL)
        if succeeded:
            if failure_category is not None:
                raise ValueError("a successful canary cannot have a failure category")
            self._states[family] = _CanaryState.PASSED
            return
        category = failure_category or ProviderTransportCategory.UNAVAILABLE
        self._states[family] = _CanaryState.BLOCKED
        self._failure_categories[family] = category

    def failure_category(
        self,
        family: ProviderWorkloadFamily,
    ) -> ProviderTransportCategory | None:
        return self._failure_categories.get(family)

    def state(self, family: ProviderWorkloadFamily) -> _CanaryState:
        return self._states[family]


def _workload_family(call: CalibrationCallSpec) -> ProviderWorkloadFamily:
    if call.provider is CalibrationProvider.ANTHROPIC:
        return ProviderWorkloadFamily.ANTHROPIC_SCORER
    if call.workload is CalibrationWorkload.REVIEW:
        return ProviderWorkloadFamily.OPENAI_REVIEW
    return ProviderWorkloadFamily.OPENAI_GENERATION_CORRECTION


CANARY_CALL_IDS = {
    family: next(
        call.call_id
        for call in PEDAGOGICAL_CALIBRATION_CALL_MATRIX
        if _workload_family(call) is family
    )
    for family in ProviderWorkloadFamily
}


@dataclass(frozen=True, slots=True)
class ProviderCallResult:
    response_status: CalibrationResponseStatus
    raw_output_text: str | None
    input_tokens: int | None
    cached_input_tokens: int | None
    output_tokens: int | None
    total_tokens: int | None
    latency_milliseconds: int
    closed_error_code: str | None = None
    provider_response_status: str | None = None
    incomplete_reason: str | None = None
    reasoning_tokens: int | None = None
    public_error_code: str | None = None
    private_diagnostic_code: str | None = None
    transport_http_status: int | None = None
    provider_error_type: AnthropicProviderErrorType | None = None
    response_received: bool = False
    stop_reason: AnthropicStopReason | None = None
    text_block_count: int | None = None
    thinking_block_count: int | None = None
    thinking_tokens: int | None = None
    finish_reason: str | None = None
    parse_error_category: ReviewOutputDiagnosticCategory | None = None
    structured_output_validation: StructuredOutputValidationStatus | None = None


def _review_output_diagnostic(
    *,
    response: OpenAIResponsesResponse | None,
    output_tokens: int | None,
    max_output_tokens: int,
    public_error_code: str | None,
    private_diagnostic_code: str | None,
) -> tuple[
    ReviewOutputDiagnosticCategory | None,
    StructuredOutputValidationStatus,
]:
    if public_error_code != "INVALID_RESPONSE":
        return None, StructuredOutputValidationStatus.NOT_EVALUATED
    explicit_truncation = (
        private_diagnostic_code == "OPENAI_REVIEW_INCOMPLETE_MAX_OUTPUT_TOKENS"
        or (
            response is not None
            and response.incomplete_reason.value == "max_output_tokens"
        )
    )
    if explicit_truncation:
        category = ReviewOutputDiagnosticCategory.OUTPUT_TRUNCATED_CONFIRMED
    elif output_tokens is not None and output_tokens >= max_output_tokens:
        category = ReviewOutputDiagnosticCategory.OUTPUT_TRUNCATION_SUSPECTED
    else:
        category = ReviewOutputDiagnosticCategory.STRUCTURED_OUTPUT_INVALID_OTHER
    return category, StructuredOutputValidationStatus.FAILED


def _systemic_failure_category(
    result: ProviderCallResult,
) -> ProviderTransportCategory | None:
    if result.response_status is not CalibrationResponseStatus.ERROR:
        return None
    markers = " ".join(
        value
        for value in (
            result.closed_error_code,
            result.public_error_code,
            result.private_diagnostic_code,
            result.provider_error_type.value
            if result.provider_error_type is not None
            else None,
        )
        if value is not None
    ).upper()
    if "REFUSAL" in markers or "INCONCLUSIVE" in markers:
        return None
    categories = (
        (("AUTH",), ProviderTransportCategory.AUTHENTICATION),
        (("PERMISSION", "FORBIDDEN"), ProviderTransportCategory.PERMISSION),
        (("BILLING", "CREDIT", "QUOTA"), ProviderTransportCategory.BILLING),
        (("RATE_LIMIT",), ProviderTransportCategory.RATE_LIMIT),
        (("NOT_FOUND", "MODEL"), ProviderTransportCategory.NOT_FOUND),
        (
            ("INVALID_REQUEST", "REQUEST_TOO_LARGE", "CONFIG"),
            ProviderTransportCategory.INVALID_REQUEST,
        ),
        (("TIMEOUT",), ProviderTransportCategory.TIMEOUT),
        (("CONNECTION",), ProviderTransportCategory.CONNECTION),
        (("SERVER",), ProviderTransportCategory.SERVER),
        (("UNAVAILABLE",), ProviderTransportCategory.UNAVAILABLE),
    )
    for needles, category in categories:
        if any(needle in markers for needle in needles):
            return category
    return ProviderTransportCategory.UNAVAILABLE


class CalibrationExecutor(Protocol):
    def execute(
        self,
        call: CalibrationCallSpec,
        *,
        dependency_candidate: str | None,
    ) -> ProviderCallResult: ...


class _AnchorProjection(Protocol):
    def candidate_projection(self) -> str: ...


def revalidated_theoretical_ceiling_usd() -> Decimal:
    maximum = sum(
        (_maximum_call_cost(call) for call in PEDAGOGICAL_CALIBRATION_CALL_MATRIX),
        start=Decimal("0"),
    )
    return _money(maximum * COST_SAFETY_MARGIN)


def _maximum_call_cost(call: CalibrationCallSpec) -> Decimal:
    quote = MODEL_PRICE_BY_NAME[call.model]
    return _money(
        (
            Decimal(call.input_utf8_upper_bound_bytes)
            * quote.input_usd_per_million_tokens
            + Decimal(call.max_output_tokens) * quote.output_usd_per_million_tokens
        )
        / Decimal(1_000_000)
    )


def _observed_call_cost(
    call: CalibrationCallSpec,
    result: ProviderCallResult,
) -> Decimal | None:
    if result.input_tokens is None or result.output_tokens is None:
        return None
    cached = result.cached_input_tokens or 0
    if cached > result.input_tokens:
        return None
    quote = MODEL_PRICE_BY_NAME[call.model]
    regular_input = result.input_tokens - cached
    cost = (
        Decimal(regular_input) * quote.input_usd_per_million_tokens
        + Decimal(cached) * quote.cached_input_usd_per_million_tokens
        + Decimal(result.output_tokens) * quote.output_usd_per_million_tokens
    ) / Decimal(1_000_000)
    return _money(cost)


def _money(value: Decimal) -> Decimal:
    return value.quantize(Decimal("0.000001"), rounding=ROUND_CEILING)


def _utc_now() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


def _atomic_write_bytes(path: Path, payload: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    try:
        with temporary.open("wb") as stream:
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
        try:
            os.chmod(temporary, 0o600)
        except OSError:
            pass
        os.replace(temporary, path)
    finally:
        if temporary.exists():
            temporary.unlink()


def _initial_ledger(
    approved_ceiling_usd: Decimal | None,
    runtime_authorization: RuntimeAuthorizationProvenance,
) -> dict[str, object]:
    return {
        "plan_version": PEDAGOGICAL_CALIBRATION_PLAN_VERSION,
        "matrix_sha256": EXPECTED_MATRIX_SHA256,
        "proposed_technical_ceiling_usd": str(PROPOSED_TECHNICAL_CEILING_USD),
        "approved_ceiling_usd": (
            str(approved_ceiling_usd) if approved_ceiling_usd is not None else None
        ),
        "pricing_snapshot_id": PRICING_SNAPSHOT_ID,
        "pricing_snapshot_sha256": pricing_snapshot_sha256(),
        "pricing_snapshot": _CURRENT_PRICING_SNAPSHOT,
        "authorization_provenance": runtime_authorization.as_ledger_payload(),
        "canaries": {
            family.value: {
                "call_id": CANARY_CALL_IDS[family],
                "state": _CanaryState.PENDING.value,
                "failure_category": None,
            }
            for family in ProviderWorkloadFamily
        },
        "calls": [
            {
                "call_id": call.call_id,
                "provider": call.provider.value,
                "model": call.model,
                "status": LedgerCallStatus.PENDING.value,
                "started_at": None,
                "completed_at": None,
                "input_tokens": 0,
                "cached_input_tokens": 0,
                "output_tokens": 0,
                "total_tokens": 0,
                "latency_milliseconds": 0,
                "closed_error_code": None,
                "provider_response_status": None,
                "incomplete_reason": None,
                "finish_reason": None,
                "parse_error_category": None,
                "structured_output_validation": None,
                "private_diagnostic_code": None,
                "raw_output_sha256": None,
                "raw_output_path": None,
                "cost_usd": "0.000000",
            }
            for call in PEDAGOGICAL_CALIBRATION_CALL_MATRIX
        ],
        "total_cost_usd": "0.000000",
    }


class AtomicCalibrationLedger:
    def __init__(
        self,
        path: Path,
        *,
        approved_ceiling_usd: Decimal | None = APPROVED_HARD_CEILING_USD,
        runtime_authorization: RuntimeAuthorizationProvenance = (
            CLOSED_RUNTIME_AUTHORIZATION
        ),
    ) -> None:
        self.path = path
        self.approved_ceiling_usd = approved_ceiling_usd
        self.runtime_authorization = runtime_authorization

    def initialize(self) -> dict[str, object]:
        if not self.path.exists():
            self.write(
                _initial_ledger(
                    self.approved_ceiling_usd,
                    self.runtime_authorization,
                )
            )
        return self.read()

    def read(self) -> dict[str, object]:
        try:
            ledger = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            _stop(LiveCalibrationStopCode.LEDGER_INVALID)
        if type(ledger) is not dict:
            _stop(LiveCalibrationStopCode.LEDGER_INVALID)
        normalized = cast(dict[str, object], ledger)
        _validate_ledger(
            normalized,
            self.approved_ceiling_usd,
            self.runtime_authorization,
        )
        return normalized

    def write(self, ledger: Mapping[str, object]) -> None:
        _validate_ledger(
            dict(ledger),
            self.approved_ceiling_usd,
            self.runtime_authorization,
        )
        payload = (
            json.dumps(
                ledger,
                ensure_ascii=False,
                indent=2,
                sort_keys=True,
            )
            + "\n"
        ).encode("utf-8")
        _atomic_write_bytes(self.path, payload)

    def mark_started(self, call_id: str) -> dict[str, object]:
        ledger = self.read()
        record = _ledger_record(ledger, call_id)
        if record["status"] != LedgerCallStatus.PENDING.value:
            _stop(LiveCalibrationStopCode.CALL_ORDER_MISMATCH)
        record["status"] = LedgerCallStatus.STARTED.value
        record["started_at"] = _utc_now()
        self.write(ledger)
        return ledger

    def mark_terminal(
        self,
        call_id: str,
        *,
        status: LedgerCallStatus,
        result: ProviderCallResult | None,
        raw_output_sha256: str | None,
        raw_output_path: str | None,
        cost_usd: Decimal,
        closed_error_code: str | None = None,
        canary_family: ProviderWorkloadFamily | None = None,
        canary_succeeded: bool | None = None,
        canary_failure_category: ProviderTransportCategory | None = None,
    ) -> dict[str, object]:
        ledger = self.read()
        record = _ledger_record(ledger, call_id)
        expected = (
            LedgerCallStatus.PENDING.value
            if status is LedgerCallStatus.SKIPPED_DEPENDENCY_FAILED
            else LedgerCallStatus.STARTED.value
        )
        if record["status"] != expected:
            _stop(LiveCalibrationStopCode.CALL_ORDER_MISMATCH)
        record["status"] = status.value
        record["completed_at"] = _utc_now()
        record["closed_error_code"] = (
            closed_error_code
            if closed_error_code is not None
            else (result.closed_error_code if result is not None else None)
        )
        record["provider_response_status"] = (
            result.provider_response_status if result is not None else None
        )
        record["incomplete_reason"] = (
            result.incomplete_reason if result is not None else None
        )
        record["finish_reason"] = (
            result.finish_reason if result is not None else None
        )
        record["parse_error_category"] = (
            result.parse_error_category.value
            if result is not None and result.parse_error_category is not None
            else None
        )
        record["structured_output_validation"] = (
            result.structured_output_validation.value
            if result is not None
            and result.structured_output_validation is not None
            else None
        )
        record["private_diagnostic_code"] = (
            result.private_diagnostic_code if result is not None else None
        )
        record["raw_output_sha256"] = raw_output_sha256
        record["raw_output_path"] = raw_output_path
        record["cost_usd"] = str(_money(cost_usd))
        if result is not None:
            record["input_tokens"] = result.input_tokens or 0
            record["cached_input_tokens"] = result.cached_input_tokens or 0
            record["output_tokens"] = result.output_tokens or 0
            record["total_tokens"] = result.total_tokens or (
                (result.input_tokens or 0) + (result.output_tokens or 0)
            )
            record["latency_milliseconds"] = result.latency_milliseconds
        if canary_family is not None:
            if canary_succeeded is None:
                _stop(LiveCalibrationStopCode.LEDGER_INVALID)
            raw_canaries = cast(dict[str, dict[str, object]], ledger["canaries"])
            canary = raw_canaries[canary_family.value]
            if (
                canary["call_id"] != call_id
                or canary["state"] != _CanaryState.PENDING.value
            ):
                _stop(LiveCalibrationStopCode.CANARY_ALREADY_TERMINAL)
            canary["state"] = (
                _CanaryState.PASSED.value
                if canary_succeeded
                else _CanaryState.BLOCKED.value
            )
            canary["failure_category"] = (
                None
                if canary_succeeded
                else (canary_failure_category or ProviderTransportCategory.UNAVAILABLE).value
            )
        ledger["total_cost_usd"] = str(
            _money(
                sum(
                    (
                        Decimal(cast(dict[str, object], item)["cost_usd"])
                        for item in cast(list[object], ledger["calls"])
                    ),
                    start=Decimal("0"),
                )
            )
        )
        self.write(ledger)
        return ledger


def _validate_ledger(
    ledger: dict[str, object],
    approved_ceiling_usd: Decimal | None,
    runtime_authorization: RuntimeAuthorizationProvenance,
) -> None:
    expected_approved = (
        str(approved_ceiling_usd) if approved_ceiling_usd is not None else None
    )
    if (
        ledger.get("plan_version") != PEDAGOGICAL_CALIBRATION_PLAN_VERSION
        or ledger.get("matrix_sha256") != EXPECTED_MATRIX_SHA256
        or ledger.get("proposed_technical_ceiling_usd")
        != str(PROPOSED_TECHNICAL_CEILING_USD)
        or ledger.get("approved_ceiling_usd") != expected_approved
        or ledger.get("pricing_snapshot_id") != PRICING_SNAPSHOT_ID
        or ledger.get("pricing_snapshot_sha256") != pricing_snapshot_sha256()
        or ledger.get("pricing_snapshot") != _CURRENT_PRICING_SNAPSHOT
        or ledger.get("authorization_provenance")
        != runtime_authorization.as_ledger_payload()
    ):
        _stop(LiveCalibrationStopCode.LEDGER_INVALID)
    _validate_runtime_authorization_shape(runtime_authorization)
    canaries = ledger.get("canaries")
    if type(canaries) is not dict or set(canaries) != {
        family.value for family in ProviderWorkloadFamily
    }:
        _stop(LiveCalibrationStopCode.LEDGER_INVALID)
    for family in ProviderWorkloadFamily:
        raw = cast(dict[str, object], canaries.get(family.value))
        if type(raw) is not dict:
            _stop(LiveCalibrationStopCode.LEDGER_INVALID)
        try:
            state = _CanaryState(cast(str, raw.get("state")))
        except ValueError:
            _stop(LiveCalibrationStopCode.LEDGER_INVALID)
        failure = raw.get("failure_category")
        if raw.get("call_id") != CANARY_CALL_IDS[family]:
            _stop(LiveCalibrationStopCode.LEDGER_INVALID)
        if state is _CanaryState.BLOCKED:
            try:
                ProviderTransportCategory(cast(str, failure))
            except ValueError:
                _stop(LiveCalibrationStopCode.LEDGER_INVALID)
        elif failure is not None:
            _stop(LiveCalibrationStopCode.LEDGER_INVALID)
    calls = ledger.get("calls")
    if type(calls) is not list or len(calls) != len(PEDAGOGICAL_CALIBRATION_CALL_MATRIX):
        _stop(LiveCalibrationStopCode.LEDGER_INVALID)
    expected = tuple(call.call_id for call in PEDAGOGICAL_CALIBRATION_CALL_MATRIX)
    actual: list[str] = []
    cost = Decimal("0")
    allowed_statuses = {item.value for item in LedgerCallStatus}
    for raw in calls:
        if type(raw) is not dict:
            _stop(LiveCalibrationStopCode.LEDGER_INVALID)
        record = cast(dict[str, object], raw)
        call_id = record.get("call_id")
        if type(call_id) is not str or record.get("status") not in allowed_statuses:
            _stop(LiveCalibrationStopCode.LEDGER_INVALID)
        parse_error = record.get("parse_error_category")
        validation = record.get("structured_output_validation")
        if parse_error is not None:
            try:
                ReviewOutputDiagnosticCategory(cast(str, parse_error))
            except ValueError:
                _stop(LiveCalibrationStopCode.LEDGER_INVALID)
        if validation is not None:
            try:
                StructuredOutputValidationStatus(cast(str, validation))
            except ValueError:
                _stop(LiveCalibrationStopCode.LEDGER_INVALID)
        actual.append(call_id)
        try:
            item_cost = Decimal(cast(str, record["cost_usd"]))
        except (KeyError, ArithmeticError):
            _stop(LiveCalibrationStopCode.LEDGER_INVALID)
        if item_cost < 0:
            _stop(LiveCalibrationStopCode.LEDGER_INVALID)
        cost += item_cost
    if tuple(actual) != expected or len(actual) != len(set(actual)):
        _stop(LiveCalibrationStopCode.LEDGER_INVALID)
    try:
        total = Decimal(cast(str, ledger["total_cost_usd"]))
    except (KeyError, ArithmeticError):
        _stop(LiveCalibrationStopCode.LEDGER_INVALID)
    ceiling = approved_ceiling_usd or Decimal("0")
    if _money(cost) != total or total > ceiling:
        _stop(LiveCalibrationStopCode.LEDGER_INVALID)


def _validate_runtime_authorization_shape(
    authorization: RuntimeAuthorizationProvenance,
) -> None:
    values = (
        authorization.authorized_baseline_commit_sha,
        authorization.authorized_matrix_sha256,
        authorization.authorized_pricing_sha256,
        authorization.authorized_max_call_count,
        authorization.authorized_hard_ceiling_usd,
        authorization.attestation_source,
    )
    if not authorization.effective:
        if any(value is not None for value in values):
            _stop(LiveCalibrationStopCode.AUTHORIZATION_PROVENANCE_MISMATCH)
        return
    if (
        not authorization.authorized_baseline_commit_sha
        or not authorization.authorized_matrix_sha256
        or not authorization.authorized_pricing_sha256
        or type(authorization.authorized_max_call_count) is not int
        or authorization.authorized_hard_ceiling_usd is None
        or authorization.authorized_hard_ceiling_usd <= 0
    ):
        _stop(LiveCalibrationStopCode.AUTHORIZATION_PROVENANCE_MISMATCH)


def _ledger_record(ledger: Mapping[str, object], call_id: str) -> dict[str, object]:
    for raw in cast(list[object], ledger["calls"]):
        record = cast(dict[str, object], raw)
        if record["call_id"] == call_id:
            return record
    _stop(LiveCalibrationStopCode.LEDGER_INVALID)


class RawOutputStore:
    def __init__(self, root: Path, relative_directory: str = RAW_OUTPUT_DIRECTORY) -> None:
        self.root = root.resolve()
        self.relative_directory = relative_directory
        self.directory = (root / relative_directory).resolve()
        if self.root not in self.directory.parents:
            _stop(LiveCalibrationStopCode.RAW_OUTPUT_PATH_UNSAFE)

    def write(self, call_id: str, output_text: str) -> tuple[str, str]:
        payload = output_text.encode("utf-8")
        digest = hashlib.sha256(payload).hexdigest()
        safe_call_id = re.sub(r"[^a-z0-9._-]", "-", call_id.casefold())
        path = self.directory / f"{safe_call_id}.{digest}.json"
        _atomic_write_bytes(path, payload)
        return digest, path.relative_to(self.root).as_posix()

    def read(self, relative_path: str, expected_sha256: str) -> str:
        path = (self.root / relative_path).resolve()
        if self.directory not in path.parents:
            _stop(LiveCalibrationStopCode.RAW_OUTPUT_PATH_UNSAFE)
        try:
            payload = path.read_bytes()
        except OSError:
            _stop(LiveCalibrationStopCode.LEDGER_INVALID)
        if hashlib.sha256(payload).hexdigest() != expected_sha256:
            _stop(LiveCalibrationStopCode.LEDGER_INVALID)
        return payload.decode("utf-8")


class _RecordingOpenAITransport:
    def __init__(self, inner: OpenAIResponsesTransport) -> None:
        self._inner = inner
        self.response: OpenAIResponsesResponse | None = None
        self.error_code: str | None = None

    def create(self, *, request: OpenAIResponsesRequest) -> OpenAIResponsesResponse:
        try:
            self.response = self._inner.create(request=request)
            return self.response
        except OpenAITransportError as error:
            self.error_code = error.code.value
            raise


class _RecordingOpenAIFactory:
    def __init__(self) -> None:
        self._inner: OpenAIResponsesTransportFactory = OpenAISDKResponsesTransportFactory()
        self.transport: _RecordingOpenAITransport | None = None

    def build(self, *, secret: object, timeout_seconds: float) -> OpenAIResponsesTransport:
        inner = self._inner.build(secret=secret, timeout_seconds=timeout_seconds)  # type: ignore[arg-type]
        self.transport = _RecordingOpenAITransport(inner)
        return self.transport

    @property
    def response(self) -> OpenAIResponsesResponse | None:
        return self.transport.response if self.transport is not None else None

    @property
    def error_code(self) -> str | None:
        return self.transport.error_code if self.transport is not None else None


class _RecordingAnthropicTransport:
    def __init__(self, inner: AnthropicScoringTransport) -> None:
        self._inner = inner
        self.response: AnthropicScoringResponse | None = None
        self.error_code: str | None = None
        self.error: AnthropicTransportError | None = None

    def create(self, *, request: AnthropicScoringRequest) -> AnthropicScoringResponse:
        try:
            self.response = self._inner.create(request=request)
            return self.response
        except AnthropicTransportError as error:
            self.error = error
            self.error_code = error.code.value
            raise


class _RecordingAnthropicFactory:
    def __init__(self) -> None:
        self._inner: AnthropicScoringTransportFactory = AnthropicSDKScoringTransportFactory()
        self.transport: _RecordingAnthropicTransport | None = None

    def build(self, *, secret: object, timeout_seconds: float) -> AnthropicScoringTransport:
        inner = self._inner.build(secret=secret, timeout_seconds=timeout_seconds)  # type: ignore[arg-type]
        self.transport = _RecordingAnthropicTransport(inner)
        return self.transport

    @property
    def response(self) -> AnthropicScoringResponse | None:
        return self.transport.response if self.transport is not None else None

    @property
    def error_code(self) -> str | None:
        return self.transport.error_code if self.transport is not None else None

    @property
    def error(self) -> AnthropicTransportError | None:
        return self.transport.error if self.transport is not None else None


class RealCalibrationExecutor:
    """One-shot provider executor using only the existing V2 adapter boundaries."""

    def __init__(
        self,
        environment: Mapping[str, str],
        *,
        review_reasoning_effort: OpenAIReasoningEffort | None = None,
    ) -> None:
        self._environment = dict(environment)
        self._resolver = EnvironmentProviderSecretResolver(self._environment)
        self._review_reasoning_effort = review_reasoning_effort

    def execute(
        self,
        call: CalibrationCallSpec,
        *,
        dependency_candidate: str | None,
    ) -> ProviderCallResult:
        if call.provider is CalibrationProvider.OPENAI:
            return self._execute_openai(call)
        return self._execute_anthropic(
            call,
            dependency_candidate=dependency_candidate,
        )

    def _execute_openai(self, call: CalibrationCallSpec) -> ProviderCallResult:
        factory = _RecordingOpenAIFactory()
        provider = _provider_profile(CalibrationProvider.OPENAI)
        model = _model_profile(call)
        started = time.perf_counter_ns()
        error_code: str | None = None
        public_error_code: str | None = None
        private_diagnostic_code: str | None = None
        status = CalibrationResponseStatus.ERROR
        try:
            if call.workload is CalibrationWorkload.REVIEW:
                result = OpenAIReviewAdapter(
                    provider_profile=provider,
                    model_profile=model,
                    secret_resolver=self._resolver,
                    transport_factory=factory,
                    reasoning_effort=self._review_reasoning_effort,
                ).review(request=_review_request(call))
                if result.status is ReviewPortResultStatus.REFUSED:
                    status = CalibrationResponseStatus.REFUSAL
                    error_code = "OPENAI_PROVIDER_REFUSAL"
                else:
                    status = CalibrationResponseStatus.STRUCTURED
            else:
                generation = OpenAIGenerationAdapter(
                    provider_profile=provider,
                    model_profile=model,
                    secret_resolver=self._resolver,
                    transport_factory=factory,
                ).generate(request=_generation_request(call))
                if generation.status is GenerationPortResultStatus.REFUSED:
                    status = CalibrationResponseStatus.REFUSAL
                    error_code = "OPENAI_PROVIDER_REFUSAL"
                elif generation.status is GenerationPortResultStatus.INSUFFICIENT_EVIDENCE:
                    status = CalibrationResponseStatus.INCONCLUSIVE
                    error_code = "OPENAI_INSUFFICIENT_EVIDENCE"
                else:
                    status = CalibrationResponseStatus.STRUCTURED
        except GenerationPortError as error:
            public_error_code = error.code.value
            error_code = (
                f"OPENAI_GENERATION_TRANSPORT_{factory.error_code}"
                if factory.error_code is not None
                else f"OPENAI_GENERATION_{error.code.value}"
            )
            private_diagnostic_code = error_code
        except ReviewPortError as error:
            public_error_code = error.code.value
            error_code = (
                f"OPENAI_REVIEW_TRANSPORT_{factory.error_code}"
                if factory.error_code is not None
                else f"OPENAI_REVIEW_{error.code.value}"
            )
            diagnostic = getattr(error, "diagnostic_code", None)
            private_diagnostic_code = getattr(diagnostic, "value", error_code)
        except Exception:
            error_code = "OPENAI_CLOSED_UNEXPECTED_ERROR"
            private_diagnostic_code = error_code
        latency = max(0, (time.perf_counter_ns() - started) // 1_000_000)
        return _openai_result(
            factory.response,
            status,
            latency,
            error_code,
            public_error_code,
            private_diagnostic_code,
            is_review=call.workload is CalibrationWorkload.REVIEW,
            max_output_tokens=call.max_output_tokens,
        )

    def _execute_anthropic(
        self,
        call: CalibrationCallSpec,
        *,
        dependency_candidate: str | None,
    ) -> ProviderCallResult:
        factory = _RecordingAnthropicFactory()
        scorer = AnthropicEvaluationScorer(
            provider_profile=_provider_profile(CalibrationProvider.ANTHROPIC),
            model_profile=_model_profile(call),
            secret_resolver=self._resolver,
            transport_factory=factory,
        )
        observation = _anthropic_observation(
            call,
            dependency_candidate=dependency_candidate,
        )
        started = time.perf_counter_ns()
        status = CalibrationResponseStatus.ERROR
        error_code: str | None = None
        scorer_error: AnthropicScorerError | None = None
        try:
            outcome = scorer.score(
                EvaluationScorerRef("pedagogical-quality-fixture-scorer"),
                (observation,),
            )
            status = (
                CalibrationResponseStatus.STRUCTURED
                if outcome.status is ScoreStatus.SCORED
                else CalibrationResponseStatus.INCONCLUSIVE
            )
            if status is CalibrationResponseStatus.INCONCLUSIVE:
                error_code = "ANTHROPIC_SCORER_INCONCLUSIVE"
        except AnthropicScorerError as error:
            scorer_error = error
            error_code = (
                f"ANTHROPIC_SCORER_TRANSPORT_{factory.error_code}"
                if factory.error_code is not None
                else f"ANTHROPIC_SCORER_{error.code.value}"
            )
        except Exception:
            error_code = "ANTHROPIC_CLOSED_UNEXPECTED_ERROR"
        latency = max(0, (time.perf_counter_ns() - started) // 1_000_000)
        return _anthropic_result(
            factory.response,
            status,
            latency,
            error_code,
            scorer_error=scorer_error,
        )


def _openai_result(
    response: OpenAIResponsesResponse | None,
    status: CalibrationResponseStatus,
    latency: int,
    error_code: str | None,
    public_error_code: str | None,
    private_diagnostic_code: str | None,
    *,
    is_review: bool = False,
    max_output_tokens: int | None = None,
) -> ProviderCallResult:
    usage = response.usage if response is not None else None
    output_tokens = usage.output_tokens if usage is not None else None
    parse_error_category = None
    structured_output_validation = None
    if is_review:
        if status is CalibrationResponseStatus.STRUCTURED:
            structured_output_validation = StructuredOutputValidationStatus.PASSED
        elif max_output_tokens is None:
            structured_output_validation = (
                StructuredOutputValidationStatus.NOT_EVALUATED
            )
        else:
            (
                parse_error_category,
                structured_output_validation,
            ) = _review_output_diagnostic(
                response=response,
                output_tokens=output_tokens,
                max_output_tokens=max_output_tokens,
                public_error_code=public_error_code,
                private_diagnostic_code=private_diagnostic_code,
            )
    return ProviderCallResult(
        response_status=status,
        raw_output_text=response.output_text if response is not None else None,
        input_tokens=usage.input_tokens if usage is not None else None,
        cached_input_tokens=usage.cached_input_tokens if usage is not None else None,
        output_tokens=output_tokens,
        total_tokens=usage.total_tokens if usage is not None else None,
        latency_milliseconds=latency,
        closed_error_code=error_code,
        provider_response_status=(response.status.value if response is not None else None),
        incomplete_reason=(response.incomplete_reason.value if response is not None else None),
        reasoning_tokens=(usage.reasoning_tokens if usage is not None else None),
        public_error_code=public_error_code,
        private_diagnostic_code=private_diagnostic_code,
        finish_reason=None,
        parse_error_category=parse_error_category,
        structured_output_validation=structured_output_validation,
    )


def _anthropic_result(
    response: AnthropicScoringResponse | None,
    status: CalibrationResponseStatus,
    latency: int,
    error_code: str | None,
    *,
    scorer_error: AnthropicScorerError | None = None,
) -> ProviderCallResult:
    input_tokens = (
        response.input_tokens
        if response is not None
        else (scorer_error.input_tokens if scorer_error is not None else None)
    )
    cached_input_tokens = (
        response.cached_input_tokens
        if response is not None
        else (scorer_error.cached_input_tokens if scorer_error is not None else None)
    )
    output_tokens = (
        response.output_tokens
        if response is not None
        else (scorer_error.output_tokens if scorer_error is not None else None)
    )
    total_tokens = (
        response.total_tokens
        if response is not None
        else (scorer_error.total_tokens if scorer_error is not None else None)
    )
    return ProviderCallResult(
        response_status=status,
        raw_output_text=response.output_text if response is not None else None,
        input_tokens=input_tokens,
        cached_input_tokens=cached_input_tokens,
        output_tokens=output_tokens,
        total_tokens=total_tokens,
        latency_milliseconds=latency,
        closed_error_code=error_code,
        transport_http_status=(scorer_error.http_status if scorer_error is not None else None),
        provider_error_type=(
            scorer_error.provider_error_type if scorer_error is not None else None
        ),
        response_received=(
            scorer_error.response_received if scorer_error is not None else response is not None
        ),
        stop_reason=(
            response.stop_reason
            if response is not None
            else (scorer_error.stop_reason if scorer_error is not None else None)
        ),
        text_block_count=(
            response.text_block_count
            if response is not None
            else (scorer_error.text_block_count if scorer_error is not None else None)
        ),
        thinking_block_count=(
            response.thinking_block_count
            if response is not None
            else (scorer_error.thinking_block_count if scorer_error is not None else None)
        ),
        thinking_tokens=(
            response.thinking_tokens
            if response is not None
            else (scorer_error.thinking_tokens if scorer_error is not None else None)
        ),
    )


def _provider_profile(provider: CalibrationProvider) -> ProviderProfileConfig:
    if provider is CalibrationProvider.OPENAI:
        return ProviderProfileConfig(
            ProviderProfileId("openai-live-calibration-provider"),
            ProviderCode("openai"),
            ProviderCredentialRef("OPENAI_API_KEY"),
        )
    return ProviderProfileConfig(
        ProviderProfileId("anthropic-live-calibration-provider"),
        ProviderCode("anthropic"),
        ProviderCredentialRef("ANTHROPIC_API_KEY"),
    )


def _model_profile(call: CalibrationCallSpec) -> ModelProfileConfig:
    provider_id = (
        "openai-live-calibration-provider"
        if call.provider is CalibrationProvider.OPENAI
        else "anthropic-live-calibration-provider"
    )
    workload = {
        CalibrationWorkload.GENERATION: ProviderWorkloadKind.GENERATION,
        CalibrationWorkload.TRANSFORMATION: ProviderWorkloadKind.GENERATION,
        CalibrationWorkload.CORRECTION: ProviderWorkloadKind.CORRECTION,
        CalibrationWorkload.REVIEW: ProviderWorkloadKind.REVIEW,
        CalibrationWorkload.SCORING: ProviderWorkloadKind.EVALUATION_SCORING,
    }[call.workload]
    return ModelProfileConfig(
        ModelProfileId(call.model_profile_id),
        ProviderProfileId(provider_id),
        ModelCode(call.model),
        ModelContextLimits(1_050_000, 900_000, 128_000),
        ProviderInvocationLimits(
            1,
            120_000,
            max_output_tokens=call.max_output_tokens,
        ),
        (workload,),
        structured_output_required=True,
    )


def _generation_request(call: CalibrationCallSpec) -> GenerationPortRequest:
    scenario = scenario_by_code(call.scenario_code)
    operation = {
        CalibrationWorkload.GENERATION: GenerationOperation.GENERATE,
        CalibrationWorkload.TRANSFORMATION: GenerationOperation.TRANSFORM,
        CalibrationWorkload.CORRECTION: GenerationOperation.CORRECT,
    }[call.workload]
    strong = _strong_anchor_projection(call)
    target_ref = None
    target_version_ref = None
    if operation is GenerationOperation.TRANSFORM:
        target_ref = f"calibration-production:{call.scenario_code.lower()}"
    elif operation is GenerationOperation.CORRECT:
        target_version_ref = ObjectVersionRef(
            TypedEntityRef(TypedEntityId("calibration-production", call.scenario_code.lower())),
            VersionRef("v1"),
        )
    return GenerationPortRequest(
        operation=operation,
        source_step_id=call.call_id,
        production_kind=call.task_kind,
        objective=(
            f"Produire un contenu pedagogique synthetique pour {scenario.level_code} "
            f"et le scenario {scenario.scenario_code}."
        ),
        output_format="structured-sections",
        pedagogical_context={
            "level": scenario.level_code,
            "task_kind": scenario.task_kind,
        },
        resolved_inputs={"synthetic_reference": strong.candidate_projection()},
        constraints={
            "reference_constraints": scenario.reference_constraints,
            "brevity": "Deux phrases courtes maximum par section.",
            "external_sources": "forbidden",
        },
        target_ref=target_ref,
        target_version_ref=target_version_ref,
        expected_sections=scenario.required_sections,
        output_contract={"required_sections": scenario.required_sections},
    )


def _review_request(call: CalibrationCallSpec) -> ReviewPortRequest:
    scenario = scenario_by_code(call.scenario_code)
    strong = _strong_anchor_projection(call)
    return ReviewPortRequest(
        source_step_id=call.call_id,
        operation=ReviewOperation.SEMANTIC_REVIEW,
        capability_id=CapabilityId("CAP-V01"),
        target_production_ref=ObjectVersionRef(
            TypedEntityRef(TypedEntityId("calibration-production", call.scenario_code.lower())),
            VersionRef("v1"),
        ),
        review_dimensions=(ReviewDimension.ACCURACY, ReviewDimension.PEDAGOGY),
        target_content=strong.candidate_projection(),
        target_payload={"required_sections": scenario.required_sections},
        criteria={
            "criterion_refs": scenario.criterion_refs,
            "reference_constraints": scenario.reference_constraints,
        },
        output_contract={"type": "technical_review"},
        review_budget=BudgetSpec(max_tokens=call.max_output_tokens),
    )


def _anthropic_observation(
    call: CalibrationCallSpec,
    *,
    dependency_candidate: str | None,
) -> ObservationObject:
    criterion_ref = call.criterion_refs[0]
    input_ref = call.input_refs[0]
    if input_ref.startswith("anchor:"):
        anchor_id = input_ref.removeprefix("anchor:")
        if anchor_id not in V4_TIER_BY_ANCHOR_ID:
            item = next(
                criterion
                for criterion in CALIBRATION_CRITERION_ITEMS
                if criterion.anchor_id == anchor_id
                and criterion.criterion_ref == criterion_ref
            )
            return build_blind_scorer_observation(item)
        item = next(
            criterion
            for criterion in V4_CALIBRATION_CRITERION_ITEMS
            if criterion.anchor_id == anchor_id and criterion.criterion_ref == criterion_ref
        )
        return build_v4_blind_scorer_observation(item)
    if dependency_candidate is None:
        raise ValueError("selected output dependency is unavailable")
    return _blind_output_observation(
        scenario_by_code(call.scenario_code),
        criterion_ref,
        dependency_candidate,
    )


def _strong_anchor_projection(call: CalibrationCallSpec) -> _AnchorProjection:
    input_ref = call.input_refs[0]
    if input_ref.startswith("corpus:12.16-g2-v4-plan-v1:"):
        return V4_ANCHOR_BY_SCENARIO_TIER[
            (call.scenario_code, AnchorTier.STRONG)
        ]
    return anchor_by_id(f"cal.{call.scenario_code.lower()}.a")


def _blind_output_observation(
    scenario: CalibrationScenario,
    criterion_ref: str,
    candidate: str,
) -> ObservationObject:
    bounded = candidate[:MAX_CANDIDATE_PROJECTION_CHARACTERS]

    def scalar(value: str) -> ObservationScalar:
        return ObservationScalar(ObservationScalarKind.STRING, value)

    def sequence(values: tuple[str, ...]) -> ObservationSequence:
        return ObservationSequence(tuple(scalar(value) for value in values))

    values = (
        scalar(criterion_ref),
        scalar(scenario.scenario_code),
        scalar(scenario.level_code),
        scalar(scenario.task_kind),
        scalar(bounded),
        sequence(scenario.reference_constraints),
        sequence(scenario.required_sections),
    )
    return ObservationObject(
        tuple(
            ObservationField(EvaluationObservationFieldCode(code), value)
            for code, value in zip(
                SCORER_OBSERVATION_FIELD_CODES,
                values,
                strict=True,
            )
        )
    )


def _git_baseline_state(root: Path) -> tuple[bool, bool]:
    try:
        ancestor = subprocess.run(
            (
                "git",
                "-C",
                str(root),
                "merge-base",
                "--is-ancestor",
                V4_CLOSURE_COMMIT,
                "HEAD",
            ),
            capture_output=True,
            check=False,
            text=True,
        )
        status = subprocess.run(
            (
                "git",
                "-C",
                str(root),
                "status",
                "--porcelain",
                "--untracked-files=all",
            ),
            capture_output=True,
            check=False,
            text=True,
        )
    except OSError:
        return False, False
    return ancestor.returncode == 0, status.returncode == 0 and not status.stdout.strip()


def validate_v4_baseline(
    root: Path,
    *,
    closure_builder: Callable[[Path], dict[str, object]] = build_closure_payload,
    corpus_hash_builder: Callable[[], str] = v4_calibration_corpus_sha256,
    git_probe: Callable[[Path], tuple[bool, bool]] = _git_baseline_state,
) -> None:
    ancestor, worktree_clean = git_probe(root)
    if not ancestor:
        _stop(LiveCalibrationStopCode.V4_BASELINE_COMMIT_NOT_ANCESTOR)
    if not worktree_clean:
        _stop(LiveCalibrationStopCode.V4_WORKTREE_DIRTY)
    try:
        closure = closure_builder(root)
    except Exception:
        _stop(LiveCalibrationStopCode.V4_CLOSURE_BASELINE_MISMATCH)
    if closure.get("corrected_form_sha256") != CORRECTED_FORM_SHA256:
        _stop(LiveCalibrationStopCode.V4_CORRECTED_FORM_MISMATCH)
    try:
        corpus_sha256 = corpus_hash_builder()
    except Exception:
        _stop(LiveCalibrationStopCode.V4_CORPUS_MISMATCH)
    if corpus_sha256 != EXPECTED_V4_CORPUS_SHA256:
        _stop(LiveCalibrationStopCode.V4_CORPUS_MISMATCH)
    gate_a = cast(dict[str, object], closure.get("gate_a"))
    gate_b = cast(dict[str, object], closure.get("gate_b"))
    closure_pass = (
        closure.get("trace_correction_check") == "PASS"
        and type(gate_a) is dict
        and gate_a.get("status") == "PASS"
        and type(gate_b) is dict
        and gate_b.get("status") == "PASS"
        and closure.get("human_v4_prevalidation")
        == "PASS_WITH_CORRECTIVE_ATTESTATION"
        and closure.get("methodological_status") == "PASS"
    )
    if not closure_pass:
        _stop(LiveCalibrationStopCode.V4_HUMAN_PREVALIDATION_NOT_PASS)


class LiveCalibrationRunner:
    def __init__(
        self,
        *,
        root: Path,
        environment: Mapping[str, str],
        executor: CalibrationExecutor,
        progress: Callable[[str], None] | None = None,
        baseline_validator: Callable[[Path], None] = validate_v4_baseline,
        approved_ceiling_usd: Decimal | None = APPROVED_HARD_CEILING_USD,
        runtime_authorization: RuntimeAuthorizationProvenance = (
            CLOSED_RUNTIME_AUTHORIZATION
        ),
        gates_prevalidated: bool = False,
    ) -> None:
        self.root = root
        self.environment = dict(environment)
        self.executor = executor
        self.progress = progress or (lambda _: None)
        self.baseline_validator = baseline_validator
        self.approved_ceiling_usd = approved_ceiling_usd
        self.runtime_authorization = runtime_authorization
        self.gates_prevalidated = gates_prevalidated
        self.ledger = AtomicCalibrationLedger(
            root / LEDGER_RELATIVE_PATH,
            approved_ceiling_usd=approved_ceiling_usd,
            runtime_authorization=runtime_authorization,
        )
        self.raw_store = RawOutputStore(root)

    def run(self) -> dict[str, object]:
        if not self.gates_prevalidated:
            _validate_live_gates(
                self.root,
                self.environment,
                approved_ceiling_usd=self.approved_ceiling_usd,
                runtime_authorization=self.runtime_authorization,
                baseline_validator=self.baseline_validator,
            )
        ledger = self.ledger.initialize()
        total_calls = len(PEDAGOGICAL_CALIBRATION_CALL_MATRIX)
        for index, call in enumerate(PEDAGOGICAL_CALIBRATION_CALL_MATRIX, start=1):
            ledger = self.ledger.read()
            breaker = SystemicCanaryBreaker.from_ledger(ledger)
            family = _workload_family(call)
            is_canary = CANARY_CALL_IDS[family] == call.call_id
            record = _ledger_record(ledger, call.call_id)
            status = LedgerCallStatus(cast(str, record["status"]))
            if status is LedgerCallStatus.STARTED:
                _stop(LiveCalibrationStopCode.AMBIGUOUS_STARTED_CALL)
            if status in {
                LedgerCallStatus.COMPLETED,
                LedgerCallStatus.FAILED,
                LedgerCallStatus.SKIPPED_DEPENDENCY_FAILED,
            }:
                continue
            _require_prior_calls_terminal(ledger, index - 1)
            if breaker.state(family) is _CanaryState.BLOCKED and not is_canary:
                self.ledger.mark_terminal(
                    call.call_id,
                    status=LedgerCallStatus.SKIPPED_DEPENDENCY_FAILED,
                    result=None,
                    raw_output_sha256=None,
                    raw_output_path=None,
                    cost_usd=Decimal("0"),
                    closed_error_code=f"CANARY_BLOCKED_{family.value}",
                )
                self.progress(
                    f"{index:03d}/{total_calls} SKIPPED {call.call_id} canary-blocked"
                )
                continue
            breaker.authorize(family, is_canary=is_canary)
            dependency_candidate = _selected_output_dependency(
                call,
                ledger,
                self.raw_store,
            )
            if _is_selected_output_score(call) and dependency_candidate is None:
                self.ledger.mark_terminal(
                    call.call_id,
                    status=LedgerCallStatus.SKIPPED_DEPENDENCY_FAILED,
                    result=None,
                    raw_output_sha256=None,
                    raw_output_path=None,
                    cost_usd=Decimal("0"),
                    closed_error_code="SELECTED_OUTPUT_DEPENDENCY_FAILED",
                )
                self.progress(f"{index:03d}/{total_calls} SKIPPED {call.call_id}")
                continue
            self._authorize(call, ledger)
            self.ledger.mark_started(call.call_id)
            try:
                result = self.executor.execute(
                    call,
                    dependency_candidate=dependency_candidate,
                )
            except Exception:
                result = ProviderCallResult(
                    CalibrationResponseStatus.ERROR,
                    None,
                    None,
                    None,
                    None,
                    None,
                    0,
                    "CLOSED_EXECUTOR_ERROR",
                )
            raw_sha = None
            raw_path = None
            if result.raw_output_text is not None:
                raw_sha, raw_path = self.raw_store.write(
                    call.call_id,
                    result.raw_output_text,
                )
            cost = _observed_call_cost(call, result)
            if cost is None:
                cost = _maximum_call_cost(call)
            terminal = (
                LedgerCallStatus.FAILED
                if result.response_status is CalibrationResponseStatus.ERROR
                else LedgerCallStatus.COMPLETED
            )
            failure_category = (
                _systemic_failure_category(result) if is_canary else None
            )
            if is_canary:
                breaker.record_canary(
                    family,
                    succeeded=failure_category is None,
                    failure_category=failure_category,
                )
            self.ledger.mark_terminal(
                call.call_id,
                status=terminal,
                result=result,
                raw_output_sha256=raw_sha,
                raw_output_path=raw_path,
                cost_usd=cost,
                canary_family=family if is_canary else None,
                canary_succeeded=(failure_category is None) if is_canary else None,
                canary_failure_category=failure_category,
            )
            self.progress(
                f"{index:03d}/{total_calls} {terminal.value} {call.call_id} cost={cost}"
            )
        final_ledger = self.ledger.read()
        first = build_safe_aggregate(final_ledger, self.raw_store)
        second = build_safe_aggregate(final_ledger, self.raw_store)
        json_a, markdown_a = render_safe_reports(first)
        json_b, markdown_b = render_safe_reports(second)
        if json_a != json_b or markdown_a != markdown_b:
            _stop(LiveCalibrationStopCode.REPORT_REPRODUCIBILITY_FAILED)
        _assert_safe_report(json_a)
        _assert_safe_report(markdown_a)
        _atomic_write_bytes(self.root / REPORT_JSON_RELATIVE_PATH, json_a)
        _atomic_write_bytes(self.root / REPORT_MARKDOWN_RELATIVE_PATH, markdown_a)
        return first

    def _authorize(
        self,
        call: CalibrationCallSpec,
        ledger: Mapping[str, object],
    ) -> None:
        validate_call_identity(call)
        if self.approved_ceiling_usd is None:
            _stop(LiveCalibrationStopCode.LIVE_OWNER_AUTHORIZATION_REQUIRED)
        actual = Decimal(cast(str, ledger["total_cost_usd"]))
        if actual + _maximum_call_cost(call) > self.approved_ceiling_usd:
            _stop(LiveCalibrationStopCode.APPROVED_CEILING_INSUFFICIENT)
        completed = tuple(
            cast(str, record["call_id"])
            for record in cast(list[dict[str, object]], ledger["calls"])
            if record["status"]
            in {
                LedgerCallStatus.COMPLETED.value,
                LedgerCallStatus.FAILED.value,
                LedgerCallStatus.SKIPPED_DEPENDENCY_FAILED.value,
            }
        )
        CalibrationBudgetGuard().authorize_next(
            call_id=call.call_id,
            provider=call.provider,
            model=call.model,
            model_profile_id=call.model_profile_id,
            matrix_checksum=call_matrix_sha256(),
            approved_ceiling_usd=self.approved_ceiling_usd,
            credential_available=True,
            completed_call_ids=completed,
            actual_cost_usd=actual,
        )


def validate_call_identity(call: CalibrationCallSpec) -> None:
    planned = next(
        (item for item in PEDAGOGICAL_CALIBRATION_CALL_MATRIX if item.call_id == call.call_id),
        None,
    )
    if planned is None or planned != call:
        _stop(LiveCalibrationStopCode.CALL_IDENTITY_MISMATCH)


def _validate_live_gates(
    root: Path,
    environment: Mapping[str, str],
    *,
    approved_ceiling_usd: Decimal | None,
    runtime_authorization: RuntimeAuthorizationProvenance = (
        CLOSED_RUNTIME_AUTHORIZATION
    ),
    baseline_validator: Callable[[Path], None] = validate_v4_baseline,
) -> None:
    baseline_validator(root)
    try:
        validate_call_matrix_contracts()
    except RuntimeError:
        _stop(LiveCalibrationStopCode.MATRIX_MISMATCH)
    try:
        current_pricing_sha256 = pricing_snapshot_sha256()
    except RuntimeError:
        _stop(LiveCalibrationStopCode.PRICING_SNAPSHOT_MISMATCH)
    try:
        current_matrix_sha256 = call_matrix_sha256()
    except RuntimeError:
        _stop(LiveCalibrationStopCode.MATRIX_MISMATCH)
    if current_matrix_sha256 != EXPECTED_MATRIX_SHA256:
        _stop(LiveCalibrationStopCode.MATRIX_MISMATCH)
    if (
        current_pricing_sha256 != EXPECTED_PRICING_SNAPSHOT_SHA256
        or revalidated_theoretical_ceiling_usd()
        != PROPOSED_TECHNICAL_CEILING_USD
        or estimate_call_plan_cost().estimated_maximum_with_margin_usd
        != PROPOSED_TECHNICAL_CEILING_USD
    ):
        _stop(LiveCalibrationStopCode.PRICING_SNAPSHOT_MISMATCH)
    if (
        OWNER_CONFIGURATION_APPROVAL != "APPROVED"
        or APPROVED_MATRIX_SHA256 != current_matrix_sha256
        or APPROVED_PRICING_SHA256 != current_pricing_sha256
        or APPROVED_MAX_CALL_COUNT != len(PEDAGOGICAL_CALIBRATION_CALL_MATRIX)
        or approved_ceiling_usd != APPROVED_HARD_CEILING_USD
    ):
        _stop(LiveCalibrationStopCode.OWNER_CONFIGURATION_MISMATCH)
    if approved_ceiling_usd is None:
        _stop(LiveCalibrationStopCode.LIVE_OWNER_AUTHORIZATION_REQUIRED)
    if revalidated_theoretical_ceiling_usd() > approved_ceiling_usd:
        _stop(LiveCalibrationStopCode.APPROVED_CEILING_INSUFFICIENT)
    _validate_runtime_authorization_shape(runtime_authorization)
    if not runtime_authorization.effective:
        _stop(LiveCalibrationStopCode.LIVE_OWNER_AUTHORIZATION_REQUIRED)
    if (
        runtime_authorization.authorized_matrix_sha256
        != current_matrix_sha256
        or runtime_authorization.authorized_pricing_sha256
        != current_pricing_sha256
        or runtime_authorization.authorized_max_call_count
        != len(PEDAGOGICAL_CALIBRATION_CALL_MATRIX)
        or runtime_authorization.authorized_hard_ceiling_usd
        != approved_ceiling_usd
        or runtime_authorization.authorized_baseline_commit_sha
        != _current_head_sha(root)
    ):
        _stop(LiveCalibrationStopCode.AUTHORIZATION_PROVENANCE_MISMATCH)
    if (
        not environment.get("OPENAI_API_KEY", "").strip()
        or not environment.get("ANTHROPIC_API_KEY", "").strip()
    ):
        _stop(LiveCalibrationStopCode.LIVE_PROVIDER_CREDENTIAL_REQUIRED)
    if environment.get(LIVE_FLAG) != "1":
        _stop(LiveCalibrationStopCode.LIVE_ENVIRONMENT_GATE_CLOSED)
    if environment.get(LIVE_OUTPUT_PATH_ENV) != RAW_OUTPUT_DIRECTORY:
        _stop(LiveCalibrationStopCode.RAW_OUTPUT_PATH_UNSAFE)
    try:
        ceiling = Decimal(environment.get(APPROVED_CEILING_ENV, ""))
    except ArithmeticError:
        _stop(LiveCalibrationStopCode.LIVE_ENVIRONMENT_GATE_CLOSED)
    if ceiling != approved_ceiling_usd:
        _stop(LiveCalibrationStopCode.LIVE_ENVIRONMENT_GATE_CLOSED)
    gitignore = root / ".gitignore"
    if (
        not gitignore.exists()
        or "/artifacts/" not in gitignore.read_text(encoding="utf-8").splitlines()
    ):
        _stop(LiveCalibrationStopCode.RAW_OUTPUT_PATH_UNSAFE)


def _current_head_sha(root: Path) -> str:
    try:
        completed = subprocess.run(
            ("git", "rev-parse", "HEAD"),
            cwd=root,
            check=True,
            capture_output=True,
            text=True,
        )
    except (OSError, subprocess.CalledProcessError):
        _stop(LiveCalibrationStopCode.AUTHORIZATION_PROVENANCE_MISMATCH)
    return completed.stdout.strip()


def _require_prior_calls_terminal(ledger: Mapping[str, object], count: int) -> None:
    terminal = {
        LedgerCallStatus.COMPLETED.value,
        LedgerCallStatus.FAILED.value,
        LedgerCallStatus.SKIPPED_DEPENDENCY_FAILED.value,
    }
    records = cast(list[dict[str, object]], ledger["calls"])
    if any(record["status"] not in terminal for record in records[:count]):
        _stop(LiveCalibrationStopCode.CALL_ORDER_MISMATCH)


def _is_selected_output_score(call: CalibrationCallSpec) -> bool:
    return call.provider is CalibrationProvider.ANTHROPIC and call.input_refs[0].startswith(
        "output:"
    )


def _selected_output_dependency(
    call: CalibrationCallSpec,
    ledger: Mapping[str, object],
    raw_store: RawOutputStore,
) -> str | None:
    if not _is_selected_output_score(call):
        return None
    source_call_id = call.input_refs[0].removeprefix("output:")
    record = _ledger_record(ledger, source_call_id)
    if record["status"] != LedgerCallStatus.COMPLETED.value:
        return None
    path = record.get("raw_output_path")
    digest = record.get("raw_output_sha256")
    if type(path) is not str or type(digest) is not str:
        return None
    try:
        payload = json.loads(raw_store.read(path, digest))
    except (json.JSONDecodeError, UnicodeDecodeError, LiveCalibrationStop):
        return None
    if type(payload) is not dict or payload.get("outcome") != "OUTPUT":
        return None
    sections = payload.get("sections")
    if type(sections) is not list or not sections:
        return None
    projected: list[str] = []
    for item in sections:
        if (
            type(item) is not dict
            or type(item.get("code")) is not str
            or type(item.get("text")) is not str
        ):
            return None
        projected.append(f"[{item['code']}] {item['text']}")
    return "\n".join(projected)


def _score_from_record(
    record: Mapping[str, object],
    raw_store: RawOutputStore,
) -> Fraction | None:
    if record.get("status") != LedgerCallStatus.COMPLETED.value:
        return None
    path = record.get("raw_output_path")
    digest = record.get("raw_output_sha256")
    if type(path) is not str or type(digest) is not str:
        return None
    try:
        payload = json.loads(raw_store.read(path, digest))
    except (json.JSONDecodeError, LiveCalibrationStop):
        return None
    if type(payload) is not dict or payload.get("status") != "SCORED":
        return None
    numerator = payload.get("score_numerator")
    denominator = payload.get("score_denominator")
    if type(numerator) is not int or type(denominator) is not int:
        return None
    try:
        score = Fraction(numerator, denominator)
    except (ZeroDivisionError, TypeError):
        return None
    return score if 0 <= score <= 1 else None


def _fraction(value: Fraction | None) -> str | None:
    return f"{value.numerator}/{value.denominator}" if value is not None else None


def build_safe_aggregate(
    ledger: Mapping[str, object],
    raw_store: RawOutputStore,
) -> dict[str, object]:
    records = {
        cast(str, item["call_id"]): item for item in cast(list[dict[str, object]], ledger["calls"])
    }
    matrix_by_id = {
        call.call_id: call for call in PEDAGOGICAL_CALIBRATION_CALL_MATRIX
    }
    call_results: list[dict[str, object]] = []
    invocation_observations: list[InvocationObservation] = []
    scores_by_key: dict[tuple[str, str], Fraction | None] = {}
    repeat_observations: list[RepeatScore] = []
    quality_observations: list[QualityScoreObservation] = []
    selected_scores: list[dict[str, object]] = []
    costs_by_provider: defaultdict[str, Decimal] = defaultdict(Decimal)
    costs_by_model: defaultdict[str, Decimal] = defaultdict(Decimal)
    costs_by_workload: defaultdict[str, Decimal] = defaultdict(Decimal)
    measured_costs_by_provider: defaultdict[str, Decimal] = defaultdict(Decimal)
    measured_total = Decimal("0")
    for call in PEDAGOGICAL_CALIBRATION_CALL_MATRIX:
        record = records[call.call_id]
        terminal = cast(str, record["status"])
        response_status = _aggregate_response_status(call, record, raw_store)
        cost = Decimal(cast(str, record["cost_usd"]))
        has_measured_usage = bool(record["input_tokens"] or record["output_tokens"])
        measured_cost = cost if has_measured_usage else Decimal("0")
        if terminal != LedgerCallStatus.SKIPPED_DEPENDENCY_FAILED.value:
            costs_by_provider[call.provider.value] += cost
            costs_by_model[call.model] += cost
            costs_by_workload[call.workload.value] += cost
            measured_costs_by_provider[call.provider.value] += measured_cost
            measured_total += measured_cost
        call_results.append(
            {
                "call_id": call.call_id,
                "provider": call.provider.value,
                "model": call.model,
                "workload": call.workload.value,
                "terminal_status": terminal,
                "response_status": response_status.value,
                "input_tokens": record["input_tokens"],
                "cached_input_tokens": record["cached_input_tokens"],
                "output_tokens": record["output_tokens"],
                "total_tokens": record["total_tokens"],
                "latency_milliseconds": record["latency_milliseconds"],
                "cost_usd": record["cost_usd"],
                "closed_error_code": record["closed_error_code"],
                "provider_response_status": record["provider_response_status"],
                "incomplete_reason": record["incomplete_reason"],
                "finish_reason": record["finish_reason"],
                "parse_error_category": record["parse_error_category"],
                "structured_output_validation": record[
                    "structured_output_validation"
                ],
                "private_diagnostic_code": record["private_diagnostic_code"],
                "raw_output_sha256": record["raw_output_sha256"],
            }
        )
        if terminal != LedgerCallStatus.SKIPPED_DEPENDENCY_FAILED.value:
            invocation_observations.append(
                InvocationObservation(
                    call.call_id,
                    call.provider.value,
                    call.model,
                    call.workload.value,
                    response_status,
                    cast(int, record["input_tokens"]),
                    cast(int, record["cached_input_tokens"]),
                    cast(int, record["output_tokens"]),
                    cast(int, record["latency_milliseconds"]),
                    measured_cost,
                )
            )
        if call.provider is CalibrationProvider.ANTHROPIC:
            score = _score_from_record(record, raw_store)
            criterion = call.criterion_refs[0]
            subject = call.input_refs[0].split(":", 1)[1]
            if subject in V4_TIER_BY_ANCHOR_ID:
                if call.repetition == 1:
                    scores_by_key[(criterion, subject)] = score
                if V4_TIER_BY_ANCHOR_ID[subject] is AnchorTier.STRONG:
                    repeat_observations.append(
                        RepeatScore(subject, criterion, call.repetition, score)
                    )
            else:
                source_call = matrix_by_id[subject]
                quality_observations.append(
                    QualityScoreObservation(
                        call.scenario_code,
                        criterion,
                        source_call.model,
                        score,
                    )
                )
                selected_scores.append(
                    {
                        "call_id": call.call_id,
                        "scenario_code": call.scenario_code,
                        "criterion_ref": criterion,
                        "source_call_id": subject,
                        "producer_model": source_call.model,
                        "producer_role": source_call.role.value,
                        "status": response_status.value,
                        "score": _fraction(score),
                    }
                )
    orderings = summarize_orderings(V4_CRITERION_ORDERINGS, scores_by_key)
    ordering_details = []
    for ordering in V4_CRITERION_ORDERINGS:
        metric = summarize_orderings((ordering,), scores_by_key)
        ordering_details.append(
            {
                "scenario_code": ordering.criterion_ref.split(".", 1)[0].upper(),
                "criterion_ref": ordering.criterion_ref,
                "scores": [
                    _fraction(scores_by_key.get((ordering.criterion_ref, anchor_id)))
                    for anchor_id in ordering.ordered_anchor_ids
                ],
                "strict_monotonicity": metric.strict_ordering_count == 1,
                "weak_monotonicity": metric.weak_ordering_count == 1,
                "tied_pairs": metric.tied_pair_count,
                "inverted_pairs": metric.inverted_pair_count,
                "inconclusive": metric.inconclusive_count == 1,
            }
        )
    repeatability = summarize_repeatability(tuple(repeat_observations))
    invocation_metrics = summarize_invocations(tuple(invocation_observations))
    quality_metrics = summarize_quality(tuple(quality_observations))
    pairwise = summarize_pairwise_quality(tuple(_pairwise_quality(selected_scores)))
    status_counts = {
        provider.value: {
            status.value: sum(
                record["status"] == status.value
                for call_id, record in records.items()
                if next(
                    call.provider
                    for call in PEDAGOGICAL_CALIBRATION_CALL_MATRIX
                    if call.call_id == call_id
                )
                is provider
            )
            for status in LedgerCallStatus
        }
        for provider in CalibrationProvider
    }
    approved_ceiling_raw = ledger.get("approved_ceiling_usd")
    approved_ceiling = (
        Decimal(cast(str, approved_ceiling_raw))
        if approved_ceiling_raw is not None
        else None
    )
    authorization_provenance = cast(
        dict[str, object],
        ledger["authorization_provenance"],
    )
    runtime_authorized = cast(
        bool,
        authorization_provenance["runtime_live_authorization_effective"],
    )
    aggregate: dict[str, object] = {
        "phase": "12.16-G2-V4.1",
        "decision": "CALIBRATION_INCONCLUSIVE",
        "confidence": (
            "PROVISIONAL_PROVIDER_EXECUTION_RECORDED"
            if runtime_authorized
            else "CONFIGURATION_APPROVED_LIVE_AUTHORIZATION_ABSENT"
        ),
        "refs": {
            "branch": "phase12/12-16-provider-model-calibration",
            "closure_commit": V4_CLOSURE_COMMIT,
            "entry_main": "7ae02ee109bcc6399ec0f71616da6aef07abda81",
            "corrected_form_sha256": CORRECTED_FORM_SHA256,
            "v4_corpus_sha256": EXPECTED_V4_CORPUS_SHA256,
        },
        "authorization": {
            "plan_version": PEDAGOGICAL_CALIBRATION_PLAN_VERSION,
            "call_matrix_sha256": EXPECTED_MATRIX_SHA256,
            "openai_call_count": OPENAI_CALL_COUNT,
            "anthropic_call_count": ANTHROPIC_CALL_COUNT,
            "total_matrix_call_count": len(PEDAGOGICAL_CALIBRATION_CALL_MATRIX),
            "proposed_technical_ceiling_usd": str(
                PROPOSED_TECHNICAL_CEILING_USD
            ),
            "approved_hard_ceiling_usd": approved_ceiling_raw,
            "owner_configuration_approval": OWNER_CONFIGURATION_APPROVAL,
            "owner_approved_manifest_sha256": OWNER_APPROVED_MANIFEST_SHA256,
            **authorization_provenance,
        },
        "pricing": {
            "historical_g1": _G1_HISTORICAL_PRICING,
            "snapshot_id": PRICING_SNAPSHOT_ID,
            "snapshot_sha256": pricing_snapshot_sha256(),
            "current_v4": _CURRENT_PRICING_SNAPSHOT,
            "revalidated_theoretical_ceiling_usd": str(revalidated_theoretical_ceiling_usd()),
        },
        "credential_readiness": {
            "openai": (
                "PRESENT_AT_EXECUTION"
                if runtime_authorized
                else "NOT_RESOLVED_OFFLINE"
            ),
            "anthropic": (
                "PRESENT_AT_EXECUTION"
                if runtime_authorized
                else "NOT_RESOLVED_OFFLINE"
            ),
            "values_recorded": False,
        },
        "storage": {
            "raw_output_directory": RAW_OUTPUT_DIRECTORY,
            "ledger_path": LEDGER_RELATIVE_PATH,
            "git_ignored": True,
            "raw_retention_max_days": 7,
            "raw_cleanup_status": "RETAINED_LOCAL_PENDING_VERIFIED_CLEANUP",
        },
        "execution": {
            "status_counts": status_counts,
            "provider_calls_attempted": sum(
                result["terminal_status"] != LedgerCallStatus.SKIPPED_DEPENDENCY_FAILED.value
                and result["terminal_status"] != LedgerCallStatus.PENDING.value
                for result in call_results
            ),
            "dependency_skipped_calls": sum(
                result["terminal_status"] == LedgerCallStatus.SKIPPED_DEPENDENCY_FAILED.value
                for result in call_results
            ),
            "automatic_retries": 0,
            "automatic_reruns": 0,
            "duplicate_call_ids": [],
            "sequential_execution": True,
            "canaries": ledger["canaries"],
            "call_results": call_results,
        },
        "invocation_metrics": [
            {
                "provider": item.provider,
                "workload": item.workload,
                "call_count": item.call_count,
                "structured_count": item.structured_count,
                "refusal_count": item.refusal_count,
                "error_count": item.error_count,
                "inconclusive_count": item.inconclusive_count,
                "valid_structured_response_rate": _fraction(item.valid_structured_response_rate),
                "refusal_rate": _fraction(item.refusal_rate),
                "error_rate": _fraction(item.error_rate),
                "input_tokens": item.input_tokens,
                "cached_input_tokens": item.cached_input_tokens,
                "output_tokens": item.output_tokens,
                "latency_milliseconds": item.latency_milliseconds,
                "observed_cost_usd": str(_money(item.observed_cost_usd)),
            }
            for item in invocation_metrics
        ],
        "anchor_metrics": {
            "criterion_count": orderings.criterion_count,
            "strict_monotonicity_count": orderings.strict_ordering_count,
            "weak_monotonicity_count": orderings.weak_ordering_count,
            "tied_pair_count": orderings.tied_pair_count,
            "inverted_pair_count": orderings.inverted_pair_count,
            "inconclusive_count": orderings.inconclusive_count,
            "by_criterion": ordering_details,
        },
        "repeatability": {
            "scope": "STRONG_ANCHOR_ONLY",
            "group_count": repeatability.group_count,
            "exact_agreement_count": repeatability.exact_agreement_count,
            "inconclusive_count": repeatability.inconclusive_count,
            "exact_agreement_rate": _fraction(repeatability.exact_agreement_rate),
            "inconclusive_rate": _fraction(repeatability.inconclusive_rate),
            "maximum_spread": _fraction(repeatability.maximum_spread),
            "mean_absolute_rational_delta": _fraction(repeatability.mean_absolute_rational_delta),
        },
        "selected_output_metrics": {
            "scores": selected_scores,
            "quality_aggregates": [
                {
                    "scenario_code": item.scenario_code,
                    "criterion_ref": item.criterion_ref,
                    "model": item.model,
                    "observation_count": item.observation_count,
                    "inconclusive_count": item.inconclusive_count,
                    "mean_score": _fraction(item.mean_score),
                }
                for item in quality_metrics
            ],
            "pairwise_comparison_count": pairwise.comparison_count,
            "pairwise_primary_win_count": pairwise.primary_win_count,
            "pairwise_fallback_win_count": pairwise.fallback_win_count,
            "pairwise_tie_count": pairwise.tie_count,
            "pairwise_inconclusive_count": pairwise.inconclusive_count,
            "fallback_soft_quality_comparison": "ESTABLISHED_FOR_EXPLICIT_PAIRS",
        },
        "cost": {
            "estimated_v4_base_usd": str(
                estimate_call_plan_cost().estimated_base_usd
            ),
            "proposed_technical_ceiling_usd": str(
                PROPOSED_TECHNICAL_CEILING_USD
            ),
            "approved_hard_ceiling_usd": approved_ceiling_raw,
            "revalidated_theoretical_ceiling_usd": str(revalidated_theoretical_ceiling_usd()),
            "actual_measured_total_usd": str(_money(measured_total)),
            "prudent_unknown_usage_reserve_usd": str(
                _money(Decimal(cast(str, ledger["total_cost_usd"])) - measured_total)
            ),
            "budget_accounted_total_usd": ledger["total_cost_usd"],
            "actual_measured_by_provider_usd": {
                key: str(_money(value)) for key, value in sorted(measured_costs_by_provider.items())
            },
            "budget_accounted_by_provider_usd": {
                key: str(_money(value)) for key, value in sorted(costs_by_provider.items())
            },
            "budget_accounted_by_model_usd": {
                key: str(_money(value)) for key, value in sorted(costs_by_model.items())
            },
            "budget_accounted_by_workload_usd": {
                key: str(_money(value)) for key, value in sorted(costs_by_workload.items())
            },
            "ceiling_preserved": (
                approved_ceiling is not None
                and Decimal(cast(str, ledger["total_cost_usd"])) <= approved_ceiling
            ),
        },
        "human_anchor_review": "PASS_WITH_CORRECTIVE_ATTESTATION",
        "release_threshold_adoption": "NOT_ALLOWED",
        "adr_required": False,
        "limitations": [
            "No definitive release threshold is adopted.",
            "Repeatability covers strong anchors only.",
            "Pairwise model comparison is limited to explicit producer pairs.",
            *(
                []
                if runtime_authorized
                else [
                    "Live provider execution still requires separate runtime authorization."
                ]
            ),
        ],
        "reproducibility": {
            "aggregate_json_double_build_equal": True,
            "aggregate_markdown_double_build_equal": True,
            "timestamps_excluded_from_canonical_projection": True,
        },
    }
    canonical = json.dumps(
        aggregate,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    aggregate["canonical_projection_sha256"] = hashlib.sha256(canonical).hexdigest()
    return aggregate


def _aggregate_response_status(
    call: CalibrationCallSpec,
    record: Mapping[str, object],
    raw_store: RawOutputStore,
) -> CalibrationResponseStatus:
    terminal = record["status"]
    if terminal == LedgerCallStatus.FAILED.value:
        return CalibrationResponseStatus.ERROR
    if terminal == LedgerCallStatus.SKIPPED_DEPENDENCY_FAILED.value:
        return CalibrationResponseStatus.INCONCLUSIVE
    closed = record.get("closed_error_code")
    if closed and "REFUSAL" in cast(str, closed):
        return CalibrationResponseStatus.REFUSAL
    if closed and "INCONCLUSIVE" in cast(str, closed):
        return CalibrationResponseStatus.INCONCLUSIVE
    if call.provider is CalibrationProvider.ANTHROPIC:
        return (
            CalibrationResponseStatus.STRUCTURED
            if _score_from_record(record, raw_store) is not None
            else CalibrationResponseStatus.INCONCLUSIVE
        )
    return CalibrationResponseStatus.STRUCTURED


def _pairwise_quality(
    selected_scores: list[dict[str, object]],
) -> tuple[PairwiseQualityObservation, ...]:
    grouped: dict[
        tuple[str, str],
        dict[str, tuple[str, Fraction | None]],
    ] = defaultdict(dict)
    for item in selected_scores:
        role = cast(str, item["producer_role"])
        if role not in {CalibrationRole.PRIMARY.value, CalibrationRole.FALLBACK.value}:
            continue
        grouped[
            (cast(str, item["scenario_code"]), cast(str, item["criterion_ref"]))
        ][role] = (
            cast(str, item["producer_model"]),
            _parse_fraction(cast(str | None, item["score"])),
        )
    observations: list[PairwiseQualityObservation] = []
    for (scenario_code, criterion_ref), values in sorted(grouped.items()):
        if not {
            CalibrationRole.PRIMARY.value,
            CalibrationRole.FALLBACK.value,
        }.issubset(values):
            continue
        primary_model, primary_score = values[CalibrationRole.PRIMARY.value]
        fallback_model, fallback_score = values[CalibrationRole.FALLBACK.value]
        observations.append(
            PairwiseQualityObservation(
                scenario_code,
                criterion_ref,
                primary_model,
                fallback_model,
                primary_score,
                fallback_score,
            )
        )
    return tuple(observations)


def _parse_fraction(value: str | None) -> Fraction | None:
    if value is None:
        return None
    try:
        numerator, denominator = value.split("/", 1)
        return Fraction(int(numerator), int(denominator))
    except (ValueError, ZeroDivisionError):
        return None


def render_safe_reports(aggregate: Mapping[str, object]) -> tuple[bytes, bytes]:
    json_bytes = (
        json.dumps(aggregate, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    ).encode("utf-8")
    authorization = cast(dict[str, object], aggregate["authorization"])
    execution = cast(dict[str, object], aggregate["execution"])
    anchor = cast(dict[str, object], aggregate["anchor_metrics"])
    repeatability = cast(dict[str, object], aggregate["repeatability"])
    cost = cast(dict[str, object], aggregate["cost"])
    runtime_authorized = cast(
        bool,
        authorization["runtime_live_authorization_effective"],
    )
    provenance_lines = [
        "- Approbation propriétaire de configuration : "
        f"`{authorization['owner_configuration_approval']}`",
        "- Manifest approuvé : "
        f"`{authorization['owner_approved_manifest_sha256']}`",
        "- Autorisation live par défaut de la baseline : "
        f"`{authorization['baseline_live_authorization_default']}`",
        "- Autorisation live runtime effective : "
        f"`{runtime_authorized}`",
    ]
    if runtime_authorized:
        provenance_lines.extend(
            (
                "- Commit autorisé : "
                f"`{authorization['authorized_baseline_commit_sha']}`",
                "- Matrice autorisée : "
                f"`{authorization['authorized_matrix_sha256']}`",
                "- Pricing autorisé : "
                f"`{authorization['authorized_pricing_sha256']}`",
                "- Nombre maximal autorisé : "
                f"`{authorization['authorized_max_call_count']}`",
                "- Plafond autorisé : "
                f"`{authorization['authorized_hard_ceiling_usd']} USD`",
                "- Source d'attestation : "
                f"`{authorization['attestation_source']}`",
            )
        )
    else:
        provenance_lines.append("- Autorisation d'exécution live : `ABSENT`")
    lines = [
        "# Phase 12.16-G2-V4.1 — Calibration pédagogique fournisseur",
        "",
        "## Résultat descriptif",
        "",
        f"- Décision : `{aggregate['decision']}`",
        f"- Confiance : `{aggregate['confidence']}`",
        "- Revue humaine des anchors : `PASS_WITH_CORRECTIVE_ATTESTATION`",
        "- Adoption d'un seuil de release : `NOT_ALLOWED`",
        "",
        "## Autorisation et exécution",
        "",
        f"- Plan : `{authorization['plan_version']}`",
        f"- Matrice : `{authorization['call_matrix_sha256']}`",
        f"- Appels matriciels : `{authorization['total_matrix_call_count']}`",
        f"- Appels provider tentés : `{execution['provider_calls_attempted']}`",
        f"- Dépendances ignorées : `{execution['dependency_skipped_calls']}`",
        *provenance_lines,
        "- Retry automatique : `0`",
        "- Rerun automatique : `0`",
        "",
        "## Métriques anchors",
        "",
        f"- Critères : `{anchor['criterion_count']}`",
        f"- Monotonicité stricte : `{anchor['strict_monotonicity_count']}`",
        f"- Monotonicité faible : `{anchor['weak_monotonicity_count']}`",
        f"- Paires à égalité : `{anchor['tied_pair_count']}`",
        f"- Paires inversées : `{anchor['inverted_pair_count']}`",
        f"- Critères inconclusifs : `{anchor['inconclusive_count']}`",
        "",
        "## Répétabilité",
        "",
        f"- Portée : `{repeatability['scope']}`",
        f"- Accord exact : `{repeatability['exact_agreement_rate']}`",
        f"- Delta rationnel moyen : `{repeatability['mean_absolute_rational_delta']}`",
        f"- Écart maximal : `{repeatability['maximum_spread']}`",
        "",
        "## Coûts",
        "",
        f"- Base estimée V4 : `{cost['estimated_v4_base_usd']} USD`",
        f"- Plafond théorique G2 revalidé : `{cost['revalidated_theoretical_ceiling_usd']} USD`",
        f"- Coût réel mesuré : `{cost['actual_measured_total_usd']} USD`",
        f"- Réserve prudente pour usage inconnu : `{cost['prudent_unknown_usage_reserve_usd']} USD`",
        f"- Total comptabilisé pour le budget : `{cost['budget_accounted_total_usd']} USD`",
        f"- Plafond technique proposé : `{cost['proposed_technical_ceiling_usd']} USD`",
        f"- Plafond propriétaire approuvé : `{cost['approved_hard_ceiling_usd']}`",
        f"- Plafond préservé : `{cost['ceiling_preserved']}`",
        "",
        "## Limites",
        "",
        "- La comparaison pairwise couvre uniquement les paires de producteurs explicites.",
        "- La répétabilité porte uniquement sur les anchors forts.",
        "- Aucun score n'est une autorité ni un seuil de release.",
        "- Les sorties brutes restent locales et Git-ignorées, avec rétention maximale de 7 jours.",
        "",
        "Le JSON compagnon contient les métriques par appel, scénario et critère, sans prompt ni sortie brute.",
        "",
        f"Projection canonique SHA-256 : `{aggregate['canonical_projection_sha256']}`",
        "",
    ]
    return json_bytes, "\n".join(lines).encode("utf-8")


def _assert_safe_report(payload: bytes) -> None:
    rendered = payload.decode("utf-8")
    if any(marker.casefold() in rendered.casefold() for marker in _REPORT_FORBIDDEN_MARKERS):
        _stop(LiveCalibrationStopCode.REPORT_REPRODUCIBILITY_FAILED)


def run_live_calibration(
    *,
    root: Path = ROOT,
    environment: Mapping[str, str] | None = None,
    progress: Callable[[str], None] | None = None,
    baseline_validator: Callable[[Path], None] = validate_v4_baseline,
    runtime_authorization: RuntimeAuthorizationProvenance = (
        CLOSED_RUNTIME_AUTHORIZATION
    ),
) -> dict[str, object]:
    effective_environment = dict(os.environ if environment is None else environment)
    _validate_live_gates(
        root,
        effective_environment,
        approved_ceiling_usd=APPROVED_HARD_CEILING_USD,
        runtime_authorization=runtime_authorization,
        baseline_validator=baseline_validator,
    )
    return LiveCalibrationRunner(
        root=root,
        environment=effective_environment,
        executor=RealCalibrationExecutor(effective_environment),
        progress=progress,
        approved_ceiling_usd=APPROVED_HARD_CEILING_USD,
        runtime_authorization=runtime_authorization,
        gates_prevalidated=True,
    ).run()


def _stop(code: LiveCalibrationStopCode) -> None:
    raise LiveCalibrationStop(code) from None
