"""Approved, resumable and budget-bounded G2 live calibration runner."""

from __future__ import annotations

import hashlib
import json
import os
import re
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
from tests.calibration.pedagogical.call_plan import (
    COST_SAFETY_MARGIN,
    PEDAGOGICAL_CALIBRATION_CALL_MATRIX,
    PEDAGOGICAL_CALIBRATION_PLAN_VERSION,
    RAW_OUTPUT_DIRECTORY,
    CalibrationBudgetGuard,
    CalibrationCallSpec,
    CalibrationProvider,
    CalibrationWorkload,
    call_matrix_sha256,
)
from tests.calibration.pedagogical.catalog import (
    CRITERION_ORDERINGS,
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
from tests.calibration.pedagogical.protocol import (
    CALIBRATION_CRITERION_ITEMS,
    MAX_CANDIDATE_PROJECTION_CHARACTERS,
    SCORER_OBSERVATION_FIELD_CODES,
    build_blind_scorer_observation,
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
EXPECTED_MATRIX_SHA256 = "997e814f65ac7c5fc25da990cf286800fa6ca4edd761d821a6f6f59f5e2550ed"
APPROVED_HARD_CEILING_USD = Decimal("4.096440")
LEDGER_RELATIVE_PATH = "artifacts/calibration/12.16-g2/ledger.json"
REPORT_JSON_RELATIVE_PATH = "docs/development/PHASE_12_16_G2_PEDAGOGICAL_CALIBRATION_REPORT.json"
REPORT_MARKDOWN_RELATIVE_PATH = "docs/development/PHASE_12_16_G2_PEDAGOGICAL_CALIBRATION_REPORT.md"
LIVE_FLAG = "RUN_PEDAGOGICAL_LIVE_CALIBRATION"
LIVE_OUTPUT_PATH_ENV = "PEDAGOGICAL_CALIBRATION_OUTPUT_PATH"
APPROVED_CEILING_ENV = "PEDAGOGICAL_CALIBRATION_APPROVED_CEILING_USD"

_G2_PRICING = {
    "gpt-5.6-terra": {
        "provider": "openai",
        "input_usd_per_million_tokens": "2.00",
        "cached_input_usd_per_million_tokens": "0.20",
        "output_usd_per_million_tokens": "12.00",
        "source_url": "https://developers.openai.com/api/docs/models/gpt-5.6-terra",
        "verified_on": "2026-08-29",
    },
    "gpt-5.6-sol": {
        "provider": "openai",
        "input_usd_per_million_tokens": "4.00",
        "cached_input_usd_per_million_tokens": "0.40",
        "output_usd_per_million_tokens": "20.00",
        "source_url": "https://developers.openai.com/api/docs/models/compare",
        "verified_on": "2026-08-29",
    },
    "claude-sonnet-5": {
        "provider": "anthropic",
        "input_usd_per_million_tokens": "2.00",
        "cached_input_usd_per_million_tokens": "0.20",
        "output_usd_per_million_tokens": "10.00",
        "source_url": "https://platform.claude.com/docs/en/about-claude/pricing",
        "verified_on": "2026-08-29",
    },
}
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
    ENTRY_BASELINE_MISMATCH = "ENTRY_BASELINE_MISMATCH"
    MATRIX_MISMATCH = "MATRIX_MISMATCH"
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


class LiveCalibrationStop(RuntimeError):
    code: LiveCalibrationStopCode

    def __init__(self, code: LiveCalibrationStopCode) -> None:
        self.code = code
        super().__init__(code.value)


class ProviderWorkloadFamily(StrEnum):
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


class SystemicCanaryBreaker:
    """Test-only owner that requires one successful canary before family fan-out."""

    def __init__(self) -> None:
        self._states = {family: _CanaryState.PENDING for family in ProviderWorkloadFamily}
        self._failure_categories: dict[ProviderWorkloadFamily, ProviderTransportCategory] = {}

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


class CalibrationExecutor(Protocol):
    def execute(
        self,
        call: CalibrationCallSpec,
        *,
        dependency_candidate: str | None,
    ) -> ProviderCallResult: ...


def revalidated_theoretical_ceiling_usd() -> Decimal:
    maximum = sum(
        (_maximum_call_cost(call) for call in PEDAGOGICAL_CALIBRATION_CALL_MATRIX),
        start=Decimal("0"),
    )
    return _money(maximum * COST_SAFETY_MARGIN)


def _maximum_call_cost(call: CalibrationCallSpec) -> Decimal:
    quote = _G2_PRICING[call.model]
    return _money(
        (
            Decimal(call.input_utf8_upper_bound_bytes)
            * Decimal(quote["input_usd_per_million_tokens"])
            + Decimal(call.max_output_tokens) * Decimal(quote["output_usd_per_million_tokens"])
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
    quote = _G2_PRICING[call.model]
    regular_input = result.input_tokens - cached
    cost = (
        Decimal(regular_input) * Decimal(quote["input_usd_per_million_tokens"])
        + Decimal(cached) * Decimal(quote["cached_input_usd_per_million_tokens"])
        + Decimal(result.output_tokens) * Decimal(quote["output_usd_per_million_tokens"])
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


def _initial_ledger() -> dict[str, object]:
    return {
        "plan_version": PEDAGOGICAL_CALIBRATION_PLAN_VERSION,
        "matrix_sha256": EXPECTED_MATRIX_SHA256,
        "approved_ceiling_usd": str(APPROVED_HARD_CEILING_USD),
        "pricing_snapshot": _G2_PRICING,
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
                "raw_output_sha256": None,
                "raw_output_path": None,
                "cost_usd": "0.000000",
            }
            for call in PEDAGOGICAL_CALIBRATION_CALL_MATRIX
        ],
        "total_cost_usd": "0.000000",
    }


class AtomicCalibrationLedger:
    def __init__(self, path: Path) -> None:
        self.path = path

    def initialize(self) -> dict[str, object]:
        if not self.path.exists():
            self.write(_initial_ledger())
        return self.read()

    def read(self) -> dict[str, object]:
        try:
            ledger = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            _stop(LiveCalibrationStopCode.LEDGER_INVALID)
        if type(ledger) is not dict:
            _stop(LiveCalibrationStopCode.LEDGER_INVALID)
        normalized = cast(dict[str, object], ledger)
        _validate_ledger(normalized)
        return normalized

    def write(self, ledger: Mapping[str, object]) -> None:
        _validate_ledger(dict(ledger))
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


def _validate_ledger(ledger: dict[str, object]) -> None:
    if (
        ledger.get("plan_version") != PEDAGOGICAL_CALIBRATION_PLAN_VERSION
        or ledger.get("matrix_sha256") != EXPECTED_MATRIX_SHA256
        or ledger.get("approved_ceiling_usd") != str(APPROVED_HARD_CEILING_USD)
        or ledger.get("pricing_snapshot") != _G2_PRICING
    ):
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
    if _money(cost) != total or total > APPROVED_HARD_CEILING_USD:
        _stop(LiveCalibrationStopCode.LEDGER_INVALID)


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
) -> ProviderCallResult:
    usage = response.usage if response is not None else None
    return ProviderCallResult(
        response_status=status,
        raw_output_text=response.output_text if response is not None else None,
        input_tokens=usage.input_tokens if usage is not None else None,
        cached_input_tokens=usage.cached_input_tokens if usage is not None else None,
        output_tokens=usage.output_tokens if usage is not None else None,
        total_tokens=usage.total_tokens if usage is not None else None,
        latency_milliseconds=latency,
        closed_error_code=error_code,
        provider_response_status=(response.status.value if response is not None else None),
        incomplete_reason=(response.incomplete_reason.value if response is not None else None),
        reasoning_tokens=(usage.reasoning_tokens if usage is not None else None),
        public_error_code=public_error_code,
        private_diagnostic_code=private_diagnostic_code,
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
    strong = anchor_by_id(f"cal.{call.scenario_code.lower()}.a")
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
    strong = anchor_by_id(f"cal.{call.scenario_code.lower()}.a")
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
        item = next(
            criterion
            for criterion in CALIBRATION_CRITERION_ITEMS
            if criterion.anchor_id == anchor_id and criterion.criterion_ref == criterion_ref
        )
        return build_blind_scorer_observation(item)
    if dependency_candidate is None:
        raise ValueError("selected output dependency is unavailable")
    return _blind_output_observation(
        scenario_by_code(call.scenario_code),
        criterion_ref,
        dependency_candidate,
    )


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


class LiveCalibrationRunner:
    def __init__(
        self,
        *,
        root: Path,
        environment: Mapping[str, str],
        executor: CalibrationExecutor,
        progress: Callable[[str], None] | None = None,
    ) -> None:
        self.root = root
        self.environment = dict(environment)
        self.executor = executor
        self.progress = progress or (lambda _: None)
        self.ledger = AtomicCalibrationLedger(root / LEDGER_RELATIVE_PATH)
        self.raw_store = RawOutputStore(root)

    def run(self) -> dict[str, object]:
        _validate_live_gates(self.root, self.environment)
        ledger = self.ledger.initialize()
        for index, call in enumerate(PEDAGOGICAL_CALIBRATION_CALL_MATRIX, start=1):
            ledger = self.ledger.read()
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
                self.progress(f"{index:02d}/96 SKIPPED {call.call_id}")
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
            self.ledger.mark_terminal(
                call.call_id,
                status=terminal,
                result=result,
                raw_output_sha256=raw_sha,
                raw_output_path=raw_path,
                cost_usd=cost,
            )
            self.progress(f"{index:02d}/96 {terminal.value} {call.call_id} cost={cost}")
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
        actual = Decimal(cast(str, ledger["total_cost_usd"]))
        if actual + _maximum_call_cost(call) > APPROVED_HARD_CEILING_USD:
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
            approved_ceiling_usd=APPROVED_HARD_CEILING_USD,
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


def _validate_live_gates(root: Path, environment: Mapping[str, str]) -> None:
    if call_matrix_sha256() != EXPECTED_MATRIX_SHA256:
        _stop(LiveCalibrationStopCode.MATRIX_MISMATCH)
    if revalidated_theoretical_ceiling_usd() > APPROVED_HARD_CEILING_USD:
        _stop(LiveCalibrationStopCode.APPROVED_CEILING_INSUFFICIENT)
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
    if ceiling != APPROVED_HARD_CEILING_USD:
        _stop(LiveCalibrationStopCode.LIVE_ENVIRONMENT_GATE_CLOSED)
    gitignore = root / ".gitignore"
    if (
        not gitignore.exists()
        or "/artifacts/" not in gitignore.read_text(encoding="utf-8").splitlines()
    ):
        _stop(LiveCalibrationStopCode.RAW_OUTPUT_PATH_UNSAFE)


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
            if subject.startswith("cal.scn-"):
                if call.repetition == 1:
                    scores_by_key[(criterion, subject)] = score
                if subject.endswith(".a"):
                    repeat_observations.append(
                        RepeatScore(subject, criterion, call.repetition, score)
                    )
            else:
                quality_observations.append(
                    QualityScoreObservation(
                        call.scenario_code,
                        criterion,
                        call.model,
                        score,
                    )
                )
                selected_scores.append(
                    {
                        "call_id": call.call_id,
                        "scenario_code": call.scenario_code,
                        "criterion_ref": criterion,
                        "source_call_id": subject,
                        "status": response_status.value,
                        "score": _fraction(score),
                    }
                )
    orderings = summarize_orderings(CRITERION_ORDERINGS, scores_by_key)
    ordering_details = []
    for ordering in CRITERION_ORDERINGS:
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
    aggregate: dict[str, object] = {
        "phase": "12.16-G2",
        "decision": "CALIBRATION_INCONCLUSIVE",
        "confidence": "PROVISIONAL_PENDING_HUMAN_REVIEW",
        "refs": {
            "branch": "phase12/12-16-provider-model-calibration",
            "entry_head": "413a61ad2f50f6c061891a44d8c0987374722f81",
            "entry_parent": "619c5a5d11e2091c5a311bc913c4b6684358ff6d",
            "entry_main": "7ae02ee109bcc6399ec0f71616da6aef07abda81",
        },
        "authorization": {
            "plan_version": PEDAGOGICAL_CALIBRATION_PLAN_VERSION,
            "call_matrix_sha256": EXPECTED_MATRIX_SHA256,
            "openai_call_count": 20,
            "anthropic_call_count": 76,
            "total_matrix_call_count": 96,
            "approved_hard_ceiling_usd": str(APPROVED_HARD_CEILING_USD),
        },
        "pricing": {
            "historical_g1": _G1_HISTORICAL_PRICING,
            "revalidated_g2": _G2_PRICING,
            "revalidated_theoretical_ceiling_usd": str(revalidated_theoretical_ceiling_usd()),
        },
        "credential_readiness": {
            "openai": "PRESENT_AT_EXECUTION",
            "anthropic": "PRESENT_AT_EXECUTION",
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
            "fallback_soft_quality_comparison": ("NOT_FULLY_ESTABLISHED_BY_G2_MATRIX"),
        },
        "cost": {
            "estimated_g1_base_usd": "1.087576",
            "approved_hard_ceiling_usd": str(APPROVED_HARD_CEILING_USD),
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
                Decimal(cast(str, ledger["total_cost_usd"])) <= APPROVED_HARD_CEILING_USD
            ),
        },
        "human_anchor_review": "NOT_COMPLETED",
        "release_threshold_adoption": "NOT_ALLOWED",
        "adr_required": False,
        "limitations": [
            "No definitive release threshold is adopted.",
            "Human review of the 24 anchors is not completed.",
            "Repeatability covers strong anchors only.",
            "Fallback soft-quality comparison is not established by this matrix.",
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
    del selected_scores
    return ()


def render_safe_reports(aggregate: Mapping[str, object]) -> tuple[bytes, bytes]:
    json_bytes = (
        json.dumps(aggregate, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    ).encode("utf-8")
    authorization = cast(dict[str, object], aggregate["authorization"])
    execution = cast(dict[str, object], aggregate["execution"])
    anchor = cast(dict[str, object], aggregate["anchor_metrics"])
    repeatability = cast(dict[str, object], aggregate["repeatability"])
    cost = cast(dict[str, object], aggregate["cost"])
    lines = [
        "# Phase 12.16-G2 — Calibration pédagogique live",
        "",
        "## Résultat descriptif",
        "",
        f"- Décision : `{aggregate['decision']}`",
        f"- Confiance : `{aggregate['confidence']}`",
        "- Revue humaine des anchors : `NOT_COMPLETED`",
        "- Adoption d'un seuil de release : `NOT_ALLOWED`",
        "",
        "## Autorisation et exécution",
        "",
        f"- Plan : `{authorization['plan_version']}`",
        f"- Matrice : `{authorization['call_matrix_sha256']}`",
        f"- Appels matriciels : `{authorization['total_matrix_call_count']}`",
        f"- Appels provider tentés : `{execution['provider_calls_attempted']}`",
        f"- Dépendances ignorées : `{execution['dependency_skipped_calls']}`",
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
        f"- Base estimée G1 : `{cost['estimated_g1_base_usd']} USD`",
        f"- Plafond théorique G2 revalidé : `{cost['revalidated_theoretical_ceiling_usd']} USD`",
        f"- Coût réel mesuré : `{cost['actual_measured_total_usd']} USD`",
        f"- Réserve prudente pour usage inconnu : `{cost['prudent_unknown_usage_reserve_usd']} USD`",
        f"- Total comptabilisé pour le budget : `{cost['budget_accounted_total_usd']} USD`",
        f"- Plafond absolu : `{cost['approved_hard_ceiling_usd']} USD`",
        f"- Plafond préservé : `{cost['ceiling_preserved']}`",
        "",
        "## Limites",
        "",
        "- La comparaison pédagogique soft des fallbacks n'est pas établie par cette matrice.",
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
) -> dict[str, object]:
    effective_environment = dict(os.environ if environment is None else environment)
    return LiveCalibrationRunner(
        root=root,
        environment=effective_environment,
        executor=RealCalibrationExecutor(effective_environment),
        progress=progress,
    ).run()


def _stop(code: LiveCalibrationStopCode) -> None:
    raise LiveCalibrationStop(code) from None
