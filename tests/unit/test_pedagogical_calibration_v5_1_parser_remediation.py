from __future__ import annotations

import json
from copy import deepcopy
from decimal import Decimal
from typing import cast

import pytest

from tests.calibration.pedagogical.offline_calibration_v5 import (
    V5SyntheticClass,
    build_v5_synthetic_pairwise_fixtures,
    build_v5_synthetic_score_fixtures,
    v5_contract_sha256,
)
from tests.calibration.pedagogical.pricing import pricing_snapshot_sha256
from tests.calibration.pedagogical.scorer_contract_v5 import (
    LIVE_PROVIDER_RECALIBRATION_AUTHORIZED as CONTRACT_LIVE_AUTHORIZED,
)
from tests.calibration.pedagogical.scorer_contract_v5 import (
    V5PairwiseDecision,
    V5PairwiseOutcome,
    V5ScorerOutcome,
)
from tests.calibration.pedagogical.semantic_integration_v5 import (
    LIVE_PROVIDER_RECALIBRATION_AUTHORIZED as INTEGRATION_LIVE_AUTHORIZED,
)
from tests.calibration.pedagogical.semantic_integration_v5 import (
    V5LogicalCallSpec,
    build_robust_pilot,
    estimate_pilot_budget,
    v5_logical_matrix_sha256,
)
from tests.calibration.pedagogical.semantic_parser_adapter_v5_1 import (
    EXPECTED_V5_1_PARSER_CONTRACT_SHA256,
    LIVE_PROVIDER_RECALIBRATION_AUTHORIZED,
    V51ParserError,
    V51ParserErrorCode,
    parse_v5_1_call_result,
    process_anthropic_v5_1_response,
    v5_1_parser_contract_sha256,
)
from tests.calibration.pedagogical.semantic_pilot_freeze_v5 import (
    EXPECTED_PEDAGOGICAL_TRANSFER_SCOPE_SHA256,
    pedagogical_transfer_scope_sha256,
)
from tests.calibration.pedagogical.semantic_pilot_freeze_v5 import (
    LIVE_PROVIDER_RECALIBRATION_AUTHORIZED as FREEZE_LIVE_AUTHORIZED,
)
from tests.providers.anthropic.contracts import (
    AnthropicScoringResponse,
    AnthropicStopReason,
)


def _score_fixture() -> tuple[V5LogicalCallSpec, dict[str, object], V5ScorerOutcome]:
    fixture = next(
        item
        for item in build_v5_synthetic_score_fixtures()
        if item.fixture_class is V5SyntheticClass.STRONG
    )
    outcome = fixture.outcome
    payload: dict[str, object] = {
        "status": outcome.status.value,
        "evidence": [
            {
                "check_id": item.check_id,
                "locator": item.locator,
                "observation": item.observation,
            }
            for item in outcome.evidence
        ],
        "defects": [
            {
                "check_id": item.check_id,
                "locator": item.locator,
                "observation": item.observation,
                "severity": item.severity.value,
            }
            for item in outcome.defects
        ],
        "score_level": int(outcome.score_level) if outcome.score_level is not None else None,
        "confidence": outcome.confidence.value,
        "rationale": outcome.rationale,
    }
    spec = next(
        item
        for item in build_robust_pilot().calls
        if item.call.criterion_refs == (fixture.criterion_ref,)
    )
    return spec, payload, outcome


def _pairwise_fixture() -> tuple[V5LogicalCallSpec, dict[str, object], V5PairwiseOutcome]:
    fixture = next(
        item
        for item in build_v5_synthetic_pairwise_fixtures()
        if item.outcome.decision is V5PairwiseDecision.A_BETTER
    )
    outcome = fixture.outcome
    payload: dict[str, object] = {
        "differences": [
            {
                "locator_a": item.locator_a,
                "locator_b": item.locator_b,
                "observation": item.observation,
                "significance": item.significance.value,
                "favored_candidate": item.favored_candidate.value,
            }
            for item in outcome.differences
        ],
        "decision": outcome.decision.value,
        "confidence": outcome.confidence.value,
        "rationale": outcome.rationale,
    }
    spec = build_robust_pilot().calls[3]
    return spec, payload, outcome


def _parse_score(payload: dict[str, object]) -> V5ScorerOutcome:
    spec, _, _ = _score_fixture()
    result = parse_v5_1_call_result(
        spec,
        json.dumps(payload, ensure_ascii=False),
        stop_reason=AnthropicStopReason.END_TURN,
    )
    assert type(result) is V5ScorerOutcome
    return result


def _diagnostic(payload: dict[str, object] | str) -> V51ParserError:
    spec, _, _ = _score_fixture()
    output = payload if type(payload) is str else json.dumps(payload, ensure_ascii=False)
    with pytest.raises(V51ParserError) as error:
        parse_v5_1_call_result(
            spec,
            output,
            stop_reason=AnthropicStopReason.END_TURN,
        )
    return error.value


def test_v5_1_conforming_response_round_trips_unchanged_canonical_contract() -> None:
    _, payload, expected = _score_fixture()
    assert _parse_score(payload) == expected
    assert v5_contract_sha256() == (
        "a79928ba0aa402ffa012f353bd1a633b50c95e34eae368885c462690ec0b3344"
    )


def test_v5_1_normalizes_only_unambiguous_case_and_outer_spaces() -> None:
    _, payload, expected = _score_fixture()
    payload["status"] = "  scored  "
    payload["confidence"] = " high "
    payload["rationale"] = f"  {payload['rationale']}  "
    evidence = cast(list[dict[str, object]], payload["evidence"])
    for item in evidence:
        item["check_id"] = f" {cast(str, item['check_id']).upper()} "
        item["locator"] = f" {item['locator']} "
        item["observation"] = f" {item['observation']} "
    assert _parse_score(payload) == expected


def test_v5_1_accepts_only_explicit_pairwise_alias() -> None:
    spec, payload, expected = _pairwise_fixture()
    payload["decision"] = " a "
    result = parse_v5_1_call_result(
        spec,
        json.dumps(payload, ensure_ascii=False),
        stop_reason=AnthropicStopReason.END_TURN,
    )
    assert result == expected


def test_v5_1_rejects_unknown_and_ambiguous_enum_values() -> None:
    _, payload, _ = _score_fixture()
    payload["status"] = "MYSTERY"
    unknown = _diagnostic(payload).diagnostic
    assert unknown.error_code is V51ParserErrorCode.UNKNOWN_VALUE
    assert unknown.field_path == "$.status"
    assert unknown.observed_value == "MYSTERY"
    assert unknown.observed_value_sha256 is None

    spec, pairwise, _ = _pairwise_fixture()
    pairwise["decision"] = "BETTER"
    with pytest.raises(V51ParserError) as ambiguous:
        parse_v5_1_call_result(
            spec,
            json.dumps(pairwise),
            stop_reason=AnthropicStopReason.END_TURN,
        )
    assert ambiguous.value.diagnostic.error_code is V51ParserErrorCode.AMBIGUOUS_ALIAS


def test_v5_1_rejects_invalid_type_missing_extra_and_out_of_bounds() -> None:
    _, canonical, _ = _score_fixture()
    cases = []

    invalid_type = deepcopy(canonical)
    invalid_type["score_level"] = "4"
    cases.append((invalid_type, V51ParserErrorCode.INVALID_TYPE, "$.score_level"))

    missing = deepcopy(canonical)
    missing.pop("rationale")
    cases.append((missing, V51ParserErrorCode.MISSING_FIELD, "$.rationale"))

    extra = deepcopy(canonical)
    extra["unexpected"] = "value"
    cases.append((extra, V51ParserErrorCode.EXTRA_FIELD, "$.unexpected"))

    out_of_bounds = deepcopy(canonical)
    out_of_bounds["score_level"] = 5
    cases.append((out_of_bounds, V51ParserErrorCode.OUT_OF_BOUNDS, "$.score_level"))

    for payload, code, path in cases:
        diagnostic = _diagnostic(payload).diagnostic
        assert diagnostic.error_code is code
        assert diagnostic.field_path == path
        assert diagnostic.parser_schema_status == "FAIL"


def test_v5_1_rejects_invalid_json_and_truncated_response_without_raw_text() -> None:
    invalid = _diagnostic('{"status":').diagnostic
    assert invalid.error_code is V51ParserErrorCode.INVALID_JSON
    assert invalid.observed_value is None
    assert invalid.observed_value_sha256 is not None

    spec, payload, _ = _score_fixture()
    with pytest.raises(V51ParserError) as truncated:
        parse_v5_1_call_result(
            spec,
            json.dumps(payload),
            stop_reason=AnthropicStopReason.MAX_TOKENS,
        )
    assert truncated.value.diagnostic.error_code is V51ParserErrorCode.RESPONSE_TRUNCATED
    safe = json.dumps(truncated.value.diagnostic.safe_payload(), sort_keys=True)
    assert cast(str, payload["rationale"]) not in safe


def test_v5_1_usage_and_exact_cost_are_persisted_before_parse_failure() -> None:
    spec, payload, _ = _score_fixture()
    payload["status"] = "UNKNOWN_STATUS"
    raw = json.dumps(payload, ensure_ascii=False)
    snapshots: list[dict[str, object]] = []
    response = AnthropicScoringResponse(
        output_text=raw,
        input_tokens=1_000,
        cached_input_tokens=100,
        output_tokens=500,
        total_tokens=1_500,
        stop_reason=AnthropicStopReason.END_TURN,
    )
    with pytest.raises(V51ParserError):
        process_anthropic_v5_1_response(
            spec=spec,
            response=response,
            persist_safe_record=lambda item: snapshots.append(dict(item)),
        )
    assert len(snapshots) == 2
    assert snapshots[0]["terminal_status"] == "RESPONSE_RECEIVED"
    assert snapshots[0]["parser_schema_status"] == "PENDING"
    assert snapshots[0]["measured_cost_usd"] == "0.006820"
    assert snapshots[1]["terminal_status"] == "FAILED"
    assert snapshots[1]["parser_schema_status"] == "FAIL"
    serialized = json.dumps(snapshots, ensure_ascii=False, sort_keys=True)
    assert raw not in serialized
    assert cast(str, payload["rationale"]) not in serialized
    assert '"raw_response_persisted": false' in serialized


def test_v5_1_truncation_still_persists_usage_before_parser_diagnostic() -> None:
    spec, payload, _ = _score_fixture()
    snapshots: list[dict[str, object]] = []
    response = AnthropicScoringResponse(
        output_text=json.dumps(payload),
        input_tokens=250,
        cached_input_tokens=0,
        output_tokens=100,
        total_tokens=350,
        stop_reason=AnthropicStopReason.MAX_TOKENS,
    )
    with pytest.raises(V51ParserError) as error:
        process_anthropic_v5_1_response(
            spec=spec,
            response=response,
            persist_safe_record=lambda item: snapshots.append(dict(item)),
        )
    assert snapshots[0]["measured_cost_usd"] == "0.001500"
    assert error.value.diagnostic.error_code is V51ParserErrorCode.RESPONSE_TRUNCATED
    assert snapshots[1]["diagnostic"]["error_code"] == "RESPONSE_TRUNCATED"  # type: ignore[index]


def test_v5_1_matrix_budget_transfer_scope_and_live_gates_remain_closed() -> None:
    assert v5_logical_matrix_sha256() == (
        "3c3a9eb418cb21ac44b657a49f0a3932443a5ea5c427bf32e359d680e2bc2d7c"
    )
    assert pricing_snapshot_sha256() == (
        "31f2a9287845da8986448f62abe312b2290af5e9578ff61643d1cb0045bfe1b8"
    )
    assert pedagogical_transfer_scope_sha256() == (EXPECTED_PEDAGOGICAL_TRANSFER_SCOPE_SHA256)
    budget = estimate_pilot_budget(build_robust_pilot())
    assert len(build_robust_pilot().calls) == 21
    assert budget.proposed_pilot_ceiling_usd == Decimal("1.017600")
    assert budget.approved_pilot_ceiling_usd is None
    assert EXPECTED_V5_1_PARSER_CONTRACT_SHA256 != "TO_BE_COMPUTED"
    assert v5_1_parser_contract_sha256() == EXPECTED_V5_1_PARSER_CONTRACT_SHA256
    assert all(
        value is False
        for value in (
            LIVE_PROVIDER_RECALIBRATION_AUTHORIZED,
            CONTRACT_LIVE_AUTHORIZED,
            INTEGRATION_LIVE_AUTHORIZED,
            FREEZE_LIVE_AUTHORIZED,
        )
    )
