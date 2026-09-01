"""Offline V5.1 micro-canary selection, identity, budget, and closed gate."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Callable, Mapping
from dataclasses import asdict, dataclass
from decimal import ROUND_CEILING, Decimal
from enum import StrEnum
from typing import NoReturn

from tests.calibration.pedagogical.offline_calibration_v5 import v5_contract_sha256
from tests.calibration.pedagogical.pricing import (
    MODEL_PRICE_BY_NAME,
    pricing_snapshot_sha256,
)
from tests.calibration.pedagogical.scorer_contract_v5 import (
    V5PairwiseOutcome,
    V5ScorerOutcome,
)
from tests.calibration.pedagogical.semantic_integration_v5 import (
    COST_SAFETY_MARGIN,
    EXPECTED_V5_MATRIX_SHA256,
    EXPECTED_V5_SCORER_CONTRACT_SHA256,
    V5LogicalCallSpec,
    build_robust_pilot,
    v5_call_spec_sha256,
    v5_logical_matrix_sha256,
)
from tests.calibration.pedagogical.semantic_parser_adapter_v5_1 import (
    EXPECTED_V5_1_PARSER_CONTRACT_SHA256,
    process_anthropic_v5_1_response,
    v5_1_parser_contract_sha256,
)
from tests.calibration.pedagogical.semantic_pilot_freeze_v5 import (
    EXPECTED_PEDAGOGICAL_TRANSFER_SCOPE_SHA256,
    PedagogicalTransferEnvelope,
    build_pedagogical_transfer_envelopes,
    pedagogical_transfer_scope_sha256,
)
from tests.providers.anthropic.contracts import AnthropicScoringResponse

V5_1_MICRO_CANARY_VERSION = "12.16-g2-v5.1-micro-canary-v1"
MICRO_CANARY_CALL_ID = "cal.score.anchor.scn-06.strong.marking-scheme-coherence.r1"
EXPECTED_SOURCE_CALL_SPEC_SHA256 = (
    "f897bee689581b1ed126b90dc17b6ff0f5912137d3baffe6980469accc76806e"
)
EXPECTED_MICRO_CANARY_TRANSFER_PROJECTION_SHA256 = (
    "e44c8d0ce1a7ed044dc383157d859a16abb8897af7aed43f2bc6c2d71b124eb4"
)
EXPECTED_MICRO_CANARY_CALL_SPEC_SHA256 = (
    "282b1e562aa24ace1072e0d9612e045c76950d83727a01ca1e840e091608a44e"
)
PROPOSED_MICRO_CANARY_CEILING_USD = Decimal("0.045600")
APPROVED_MICRO_CANARY_CEILING_USD: Decimal | None = None
LIVE_PROVIDER_RECALIBRATION_AUTHORIZED = False


@dataclass(frozen=True, slots=True)
class V51MicroCanarySpec:
    version: str
    call_id: str
    provider: str
    model: str
    source_call_spec_sha256: str
    parser_v5_1_sha256: str
    scorer_contract_sha256: str
    matrix_sha256: str
    pricing_sha256: str
    transfer_scope_sha256: str
    transfer_projection_sha256: str
    max_input_tokens: int
    max_output_tokens: int

    def sha256(self) -> str:
        return _canonical_sha256(asdict(self))


@dataclass(frozen=True, slots=True)
class V51MicroCanaryBudget:
    maximum_input_tokens: int
    maximum_output_tokens: int
    maximum_before_margin_usd: Decimal
    safety_margin_multiplier: Decimal
    safety_margin_usd: Decimal
    proposed_ceiling_usd: Decimal
    approved_ceiling_usd: Decimal | None


@dataclass(frozen=True, slots=True)
class V51MicroCanaryAuthorization:
    baseline_commit_sha: str
    parser_v5_1_sha256: str
    scorer_contract_sha256: str
    matrix_sha256: str
    pricing_sha256: str
    transfer_scope_sha256: str
    micro_canary_call_spec_sha256: str
    micro_canary_transfer_projection_sha256: str
    approved_ceiling_usd: Decimal | None
    provider: str
    live_provider_recalibration_authorized: bool


class V51MicroCanaryGateErrorCode(StrEnum):
    BASELINE_MISMATCH = "BASELINE_MISMATCH"
    PARSER_MISMATCH = "PARSER_MISMATCH"
    SCORER_MISMATCH = "SCORER_MISMATCH"
    MATRIX_MISMATCH = "MATRIX_MISMATCH"
    PRICING_MISMATCH = "PRICING_MISMATCH"
    TRANSFER_SCOPE_MISMATCH = "TRANSFER_SCOPE_MISMATCH"
    CALL_SPEC_MISMATCH = "CALL_SPEC_MISMATCH"
    PROJECTION_MISMATCH = "PROJECTION_MISMATCH"
    APPROVED_CEILING_MISSING = "APPROVED_CEILING_MISSING"
    CEILING_MISMATCH = "CEILING_MISMATCH"
    PROVIDER_NOT_ALLOWED = "PROVIDER_NOT_ALLOWED"
    LIVE_EXECUTION_FORBIDDEN = "LIVE_EXECUTION_FORBIDDEN"


class V51MicroCanaryGateError(RuntimeError):
    code: V51MicroCanaryGateErrorCode

    def __init__(self, code: V51MicroCanaryGateErrorCode) -> None:
        if type(code) is not V51MicroCanaryGateErrorCode:
            raise TypeError("code must be V51MicroCanaryGateErrorCode")
        self.code = code
        super().__init__(code.value)


def micro_canary_source() -> tuple[V5LogicalCallSpec, PedagogicalTransferEnvelope]:
    plan = build_robust_pilot()
    envelopes = build_pedagogical_transfer_envelopes()
    spec = plan.calls[0]
    envelope = envelopes[0]
    if (
        spec.call.call_id != MICRO_CANARY_CALL_ID
        or envelope.call_id != MICRO_CANARY_CALL_ID
        or spec.call.provider.value != "anthropic"
        or envelope.model != "claude-sonnet-5"
        or v5_call_spec_sha256(spec) != EXPECTED_SOURCE_CALL_SPEC_SHA256
        or envelope.transfer_payload_sha256() != EXPECTED_MICRO_CANARY_TRANSFER_PROJECTION_SHA256
    ):
        raise RuntimeError("V5_1_MICRO_CANARY_SELECTION_DRIFT")
    return spec, envelope


def build_micro_canary_spec() -> V51MicroCanarySpec:
    spec, envelope = micro_canary_source()
    identity = V51MicroCanarySpec(
        version=V5_1_MICRO_CANARY_VERSION,
        call_id=spec.call.call_id,
        provider=spec.call.provider.value,
        model=spec.call.model,
        source_call_spec_sha256=v5_call_spec_sha256(spec),
        parser_v5_1_sha256=v5_1_parser_contract_sha256(),
        scorer_contract_sha256=v5_contract_sha256(),
        matrix_sha256=v5_logical_matrix_sha256(),
        pricing_sha256=pricing_snapshot_sha256(),
        transfer_scope_sha256=pedagogical_transfer_scope_sha256(),
        transfer_projection_sha256=envelope.transfer_payload_sha256(),
        max_input_tokens=spec.call.input_utf8_upper_bound_bytes,
        max_output_tokens=spec.call.max_output_tokens,
    )
    digest = identity.sha256()
    if (
        EXPECTED_MICRO_CANARY_CALL_SPEC_SHA256 != "TO_BE_COMPUTED"
        and digest != EXPECTED_MICRO_CANARY_CALL_SPEC_SHA256
    ):
        raise RuntimeError("V5_1_MICRO_CANARY_CALL_SPEC_SHA256_MISMATCH")
    return identity


def micro_canary_call_spec_sha256() -> str:
    return build_micro_canary_spec().sha256()


def estimate_micro_canary_budget() -> V51MicroCanaryBudget:
    spec, _ = micro_canary_source()
    quote = MODEL_PRICE_BY_NAME[spec.call.model]
    maximum = _money(
        (
            Decimal(spec.call.input_utf8_upper_bound_bytes) * quote.input_usd_per_million_tokens
            + Decimal(spec.call.max_output_tokens) * quote.output_usd_per_million_tokens
        )
        / Decimal(1_000_000)
    )
    proposed = _money(maximum * COST_SAFETY_MARGIN)
    budget = V51MicroCanaryBudget(
        maximum_input_tokens=spec.call.input_utf8_upper_bound_bytes,
        maximum_output_tokens=spec.call.max_output_tokens,
        maximum_before_margin_usd=maximum,
        safety_margin_multiplier=COST_SAFETY_MARGIN,
        safety_margin_usd=_money(proposed - maximum),
        proposed_ceiling_usd=proposed,
        approved_ceiling_usd=APPROVED_MICRO_CANARY_CEILING_USD,
    )
    if proposed != PROPOSED_MICRO_CANARY_CEILING_USD:
        raise RuntimeError("V5_1_MICRO_CANARY_BUDGET_DRIFT")
    return budget


class V51MicroCanaryGate:
    """Pure-data gate that must pass before any future credential resolution."""

    def authorize_before_credentials(
        self,
        *,
        observed_baseline_commit_sha: str,
        authorization: V51MicroCanaryAuthorization,
    ) -> V51MicroCanarySpec:
        identity = build_micro_canary_spec()
        budget = estimate_micro_canary_budget()
        checks = (
            (
                observed_baseline_commit_sha == authorization.baseline_commit_sha,
                V51MicroCanaryGateErrorCode.BASELINE_MISMATCH,
            ),
            (
                authorization.parser_v5_1_sha256 == EXPECTED_V5_1_PARSER_CONTRACT_SHA256,
                V51MicroCanaryGateErrorCode.PARSER_MISMATCH,
            ),
            (
                authorization.scorer_contract_sha256 == EXPECTED_V5_SCORER_CONTRACT_SHA256,
                V51MicroCanaryGateErrorCode.SCORER_MISMATCH,
            ),
            (
                authorization.matrix_sha256 == EXPECTED_V5_MATRIX_SHA256,
                V51MicroCanaryGateErrorCode.MATRIX_MISMATCH,
            ),
            (
                authorization.pricing_sha256 == pricing_snapshot_sha256(),
                V51MicroCanaryGateErrorCode.PRICING_MISMATCH,
            ),
            (
                authorization.transfer_scope_sha256 == EXPECTED_PEDAGOGICAL_TRANSFER_SCOPE_SHA256,
                V51MicroCanaryGateErrorCode.TRANSFER_SCOPE_MISMATCH,
            ),
            (
                authorization.micro_canary_call_spec_sha256 == identity.sha256(),
                V51MicroCanaryGateErrorCode.CALL_SPEC_MISMATCH,
            ),
            (
                authorization.micro_canary_transfer_projection_sha256
                == identity.transfer_projection_sha256,
                V51MicroCanaryGateErrorCode.PROJECTION_MISMATCH,
            ),
        )
        for valid, error_code in checks:
            if not valid:
                _error(error_code)
        if authorization.approved_ceiling_usd is None:
            _error(V51MicroCanaryGateErrorCode.APPROVED_CEILING_MISSING)
        if authorization.approved_ceiling_usd != budget.proposed_ceiling_usd:
            _error(V51MicroCanaryGateErrorCode.CEILING_MISMATCH)
        if authorization.provider != "anthropic":
            _error(V51MicroCanaryGateErrorCode.PROVIDER_NOT_ALLOWED)
        if authorization.live_provider_recalibration_authorized is not True:
            _error(V51MicroCanaryGateErrorCode.LIVE_EXECUTION_FORBIDDEN)
        return identity


def process_micro_canary_response(
    *,
    response: AnthropicScoringResponse,
    persist_safe_record: Callable[[Mapping[str, object]], None],
) -> V5ScorerOutcome | V5PairwiseOutcome:
    spec, _ = micro_canary_source()
    return process_anthropic_v5_1_response(
        spec=spec,
        response=response,
        persist_safe_record=persist_safe_record,
    )


def validate_micro_canary_offline() -> None:
    identity = build_micro_canary_spec()
    budget = estimate_micro_canary_budget()
    if (
        identity.call_id != MICRO_CANARY_CALL_ID
        or identity.provider != "anthropic"
        or identity.model != "claude-sonnet-5"
        or identity.parser_v5_1_sha256 != EXPECTED_V5_1_PARSER_CONTRACT_SHA256
        or identity.scorer_contract_sha256 != EXPECTED_V5_SCORER_CONTRACT_SHA256
        or identity.matrix_sha256 != EXPECTED_V5_MATRIX_SHA256
        or identity.transfer_scope_sha256 != EXPECTED_PEDAGOGICAL_TRANSFER_SCOPE_SHA256
        or budget.proposed_ceiling_usd != PROPOSED_MICRO_CANARY_CEILING_USD
        or budget.approved_ceiling_usd is not None
        or LIVE_PROVIDER_RECALIBRATION_AUTHORIZED is not False
    ):
        raise RuntimeError("V5_1_MICRO_CANARY_OFFLINE_VALIDATION_FAILED")


def _canonical_sha256(value: object) -> str:
    return hashlib.sha256(
        json.dumps(
            value,
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        ).encode("utf-8")
    ).hexdigest()


def _money(value: Decimal) -> Decimal:
    return value.quantize(Decimal("0.000001"), rounding=ROUND_CEILING)


def _error(code: V51MicroCanaryGateErrorCode) -> NoReturn:
    raise V51MicroCanaryGateError(code) from None
