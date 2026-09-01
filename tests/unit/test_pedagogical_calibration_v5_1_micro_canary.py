from __future__ import annotations

import json
from dataclasses import replace
from decimal import Decimal
from pathlib import Path

import pytest

from tests.calibration.pedagogical.scorer_contract_v5 import (
    V5_RUBRIC_BY_CRITERION,
    V5ScoreLevel,
    V5ScorerOutcome,
)
from tests.calibration.pedagogical.semantic_integration_v5 import (
    build_robust_pilot,
    estimate_pilot_budget,
    v5_logical_matrix_sha256,
)
from tests.calibration.pedagogical.semantic_micro_canary_v5_1 import (
    APPROVED_MICRO_CANARY_CEILING_USD,
    EXPECTED_MICRO_CANARY_CALL_SPEC_SHA256,
    EXPECTED_MICRO_CANARY_TRANSFER_PROJECTION_SHA256,
    LIVE_PROVIDER_RECALIBRATION_AUTHORIZED,
    MICRO_CANARY_CALL_ID,
    PROPOSED_MICRO_CANARY_CEILING_USD,
    V51MicroCanaryAuthorization,
    V51MicroCanaryGate,
    V51MicroCanaryGateError,
    V51MicroCanaryGateErrorCode,
    build_micro_canary_spec,
    estimate_micro_canary_budget,
    micro_canary_call_spec_sha256,
    micro_canary_source,
    process_micro_canary_response,
    validate_micro_canary_offline,
)
from tests.calibration.pedagogical.semantic_parser_adapter_v5_1 import (
    EXPECTED_V5_1_PARSER_CONTRACT_SHA256,
)
from tests.calibration.pedagogical.semantic_pilot_freeze_v5 import (
    EXPECTED_PEDAGOGICAL_TRANSFER_SCOPE_SHA256,
    pedagogical_transfer_scope_sha256,
)
from tests.providers.anthropic.contracts import (
    AnthropicScoringResponse,
    AnthropicStopReason,
)

ROOT = Path(__file__).resolve().parents[2]


def _authorization(
    *, live: bool = False, ceiling: Decimal | None = PROPOSED_MICRO_CANARY_CEILING_USD
) -> V51MicroCanaryAuthorization:
    identity = build_micro_canary_spec()
    return V51MicroCanaryAuthorization(
        baseline_commit_sha="a" * 40,
        parser_v5_1_sha256=identity.parser_v5_1_sha256,
        scorer_contract_sha256=identity.scorer_contract_sha256,
        matrix_sha256=identity.matrix_sha256,
        pricing_sha256=identity.pricing_sha256,
        transfer_scope_sha256=identity.transfer_scope_sha256,
        micro_canary_call_spec_sha256=identity.sha256(),
        micro_canary_transfer_projection_sha256=(identity.transfer_projection_sha256),
        approved_ceiling_usd=ceiling,
        provider="anthropic",
        live_provider_recalibration_authorized=live,
    )


def _valid_micro_canary_output() -> str:
    spec, _ = micro_canary_source()
    rubric = V5_RUBRIC_BY_CRITERION[spec.call.criterion_refs[0]]
    return json.dumps(
        {
            "status": "SCORED",
            "evidence": [
                {
                    "check_id": item.check_id,
                    "locator": "candidate",
                    "observation": "Contrôle pédagogique observé.",
                }
                for item in rubric.checks
            ],
            "defects": [],
            "score_level": 4,
            "confidence": "HIGH",
            "rationale": "Les quatre contrôles canoniques sont observés.",
        },
        ensure_ascii=False,
    )


def test_v5_1_micro_canary_selection_and_hashes_are_exact() -> None:
    spec, envelope = micro_canary_source()
    identity = build_micro_canary_spec()
    assert spec.call.call_id == envelope.call_id == MICRO_CANARY_CALL_ID
    assert spec is build_robust_pilot().calls[0]
    assert identity.provider == "anthropic"
    assert identity.model == "claude-sonnet-5"
    assert micro_canary_call_spec_sha256() == (EXPECTED_MICRO_CANARY_CALL_SPEC_SHA256)
    assert identity.transfer_projection_sha256 == (EXPECTED_MICRO_CANARY_TRANSFER_PROJECTION_SHA256)
    assert identity.parser_v5_1_sha256 == EXPECTED_V5_1_PARSER_CONTRACT_SHA256


def test_v5_1_micro_canary_budget_uses_exact_call_bounds() -> None:
    budget = estimate_micro_canary_budget()
    robust = estimate_pilot_budget(build_robust_pilot())
    assert budget.maximum_input_tokens == 8_000
    assert budget.maximum_output_tokens == 2_048
    assert budget.maximum_before_margin_usd == Decimal("0.036480")
    assert budget.safety_margin_multiplier == Decimal("1.25")
    assert budget.safety_margin_usd == Decimal("0.009120")
    assert budget.proposed_ceiling_usd == Decimal("0.045600")
    assert budget.proposed_ceiling_usd != robust.proposed_pilot_ceiling_usd / 21
    assert budget.approved_ceiling_usd is APPROVED_MICRO_CANARY_CEILING_USD is None


def test_v5_1_micro_canary_wires_adapter_parser_and_usage_before_parse() -> None:
    snapshots: list[dict[str, object]] = []
    outcome = process_micro_canary_response(
        response=AnthropicScoringResponse(
            output_text=_valid_micro_canary_output(),
            input_tokens=200,
            cached_input_tokens=0,
            output_tokens=100,
            total_tokens=300,
            stop_reason=AnthropicStopReason.END_TURN,
        ),
        persist_safe_record=lambda item: snapshots.append(dict(item)),
    )
    assert type(outcome) is V5ScorerOutcome
    assert outcome.score_level is V5ScoreLevel.VERY_SATISFACTORY
    assert snapshots[0]["terminal_status"] == "RESPONSE_RECEIVED"
    assert snapshots[0]["parser_schema_status"] == "PENDING"
    assert snapshots[0]["measured_cost_usd"] == "0.001400"
    assert snapshots[1]["terminal_status"] == "COMPLETED"
    assert snapshots[1]["parser_schema_status"] == "PASS"
    assert all("output_text" not in item for item in snapshots)


def test_v5_1_micro_canary_gate_is_closed_without_approval_and_live() -> None:
    gate = V51MicroCanaryGate()
    with pytest.raises(V51MicroCanaryGateError) as ceiling:
        gate.authorize_before_credentials(
            observed_baseline_commit_sha="a" * 40,
            authorization=_authorization(ceiling=None),
        )
    assert ceiling.value.code is V51MicroCanaryGateErrorCode.APPROVED_CEILING_MISSING

    with pytest.raises(V51MicroCanaryGateError) as live:
        gate.authorize_before_credentials(
            observed_baseline_commit_sha="a" * 40,
            authorization=_authorization(),
        )
    assert live.value.code is V51MicroCanaryGateErrorCode.LIVE_EXECUTION_FORBIDDEN


def test_v5_1_micro_canary_gate_rejects_every_frozen_identity() -> None:
    gate = V51MicroCanaryGate()
    base = _authorization(live=True)
    cases = (
        (
            replace(base, parser_v5_1_sha256="0" * 64),
            V51MicroCanaryGateErrorCode.PARSER_MISMATCH,
        ),
        (
            replace(base, scorer_contract_sha256="0" * 64),
            V51MicroCanaryGateErrorCode.SCORER_MISMATCH,
        ),
        (
            replace(base, matrix_sha256="0" * 64),
            V51MicroCanaryGateErrorCode.MATRIX_MISMATCH,
        ),
        (
            replace(base, pricing_sha256="0" * 64),
            V51MicroCanaryGateErrorCode.PRICING_MISMATCH,
        ),
        (
            replace(base, transfer_scope_sha256="0" * 64),
            V51MicroCanaryGateErrorCode.TRANSFER_SCOPE_MISMATCH,
        ),
        (
            replace(base, micro_canary_call_spec_sha256="0" * 64),
            V51MicroCanaryGateErrorCode.CALL_SPEC_MISMATCH,
        ),
        (
            replace(base, micro_canary_transfer_projection_sha256="0" * 64),
            V51MicroCanaryGateErrorCode.PROJECTION_MISMATCH,
        ),
        (
            replace(base, approved_ceiling_usd=Decimal("0.045601")),
            V51MicroCanaryGateErrorCode.CEILING_MISMATCH,
        ),
        (
            replace(base, provider="openai"),
            V51MicroCanaryGateErrorCode.PROVIDER_NOT_ALLOWED,
        ),
    )
    for authorization, expected in cases:
        with pytest.raises(V51MicroCanaryGateError) as error:
            gate.authorize_before_credentials(
                observed_baseline_commit_sha="a" * 40,
                authorization=authorization,
            )
        assert error.value.code is expected

    with pytest.raises(V51MicroCanaryGateError) as baseline:
        gate.authorize_before_credentials(
            observed_baseline_commit_sha="b" * 40,
            authorization=base,
        )
    assert baseline.value.code is V51MicroCanaryGateErrorCode.BASELINE_MISMATCH


def test_v5_1_micro_canary_offline_identity_does_not_change_matrix_or_scope() -> None:
    validate_micro_canary_offline()
    assert v5_logical_matrix_sha256() == (
        "3c3a9eb418cb21ac44b657a49f0a3932443a5ea5c427bf32e359d680e2bc2d7c"
    )
    assert pedagogical_transfer_scope_sha256() == (EXPECTED_PEDAGOGICAL_TRANSFER_SCOPE_SHA256)
    assert PROPOSED_MICRO_CANARY_CEILING_USD == Decimal("0.045600")
    assert LIVE_PROVIDER_RECALIBRATION_AUTHORIZED is False


def test_v5_1_micro_canary_module_has_no_secret_resolver_or_transport() -> None:
    source = (ROOT / "tests/calibration/pedagogical/semantic_micro_canary_v5_1.py").read_text(
        encoding="utf-8"
    )
    assert all(
        marker not in source
        for marker in (
            "EnvironmentProviderSecretResolver",
            "ProviderCredentialRef",
            "AnthropicSDKScoringTransport",
            "OpenAI",
        )
    )
