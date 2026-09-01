from __future__ import annotations

import json
from copy import deepcopy
from decimal import Decimal
from typing import cast

import pytest

from tests.calibration.pedagogical import semantic_gate_v5_2 as gate_v5_2
from tests.calibration.pedagogical.anchor_corpus_v4 import (
    v4_calibration_corpus_sha256,
)
from tests.calibration.pedagogical.offline_calibration_v5 import (
    v5_contract_sha256,
)
from tests.calibration.pedagogical.pairwise_output_contract_v5_2_3 import (
    EXPECTED_V5_2_3_PAIRWISE_OUTPUT_CONTRACT_SHA256,
    LIVE_PROVIDER_RECALIBRATION_AUTHORIZED,
    MAX_PAIRWISE_DIFFERENCE_OBSERVATION_CHARS,
    OLD_PAIRWISE_DIFFERENCE_OBSERVATION_CHARS,
    V523PairwiseParserError,
    V523PairwiseParserErrorCode,
    parse_v5_2_3_pairwise_call_result,
    process_anthropic_v5_2_3_pairwise_response,
    v5_2_3_pairwise_output_contract_sha256,
    v5_2_3_pairwise_output_schema,
)
from tests.calibration.pedagogical.pairwise_runner_v5_2_2 import (
    PROPOSED_V5_2_2_CEILING_USD,
    V5_2_2_NEW_CALL_IDS,
    PairwiseRunnerError,
    PairwiseRunnerErrorCode,
    extract_pairwise_projection_metadata,
)
from tests.calibration.pedagogical.pricing import (
    EXPECTED_PRICING_SNAPSHOT_SHA256,
    pricing_snapshot_sha256,
)
from tests.calibration.pedagogical.scorer_contract_v5 import (
    MAX_LOCATOR_CHARACTERS,
    MAX_RATIONALE_CHARACTERS,
)
from tests.calibration.pedagogical.semantic_gate_v5_2 import (
    EXPECTED_V5_2_CALL_SPEC_SHA256_BY_ID,
    EXPECTED_V5_2_GATE_CONTRACT_SHA256,
    EXPECTED_V5_2_TRANSFER_PROJECTION_SHA256_BY_ID,
    SCN_01_PAIRWISE_CALL_ID,
    SCN_06_PAIRWISE_CALL_ID,
    build_v5_2_call_specs,
    build_v5_2_new_calls,
    build_v5_2_transfer_envelopes,
    estimate_v5_2_budget,
    mixed_carry_forward_audit,
    strong_carry_forward_audit,
    v5_2_gate_contract_sha256,
)
from tests.calibration.pedagogical.semantic_integration_v5 import (
    EXPECTED_V5_MATRIX_SHA256,
    EXPECTED_V5_SCORER_CONTRACT_SHA256,
    V5LogicalCallSpec,
    v5_logical_matrix_sha256,
)
from tests.calibration.pedagogical.semantic_parser_adapter_v5_1 import (
    V51ParserError,
    V51ParserErrorCode,
    parse_v5_1_call_result,
)
from tests.calibration.pedagogical.semantic_pilot_freeze_v5 import (
    EXPECTED_PEDAGOGICAL_TRANSFER_SCOPE_SHA256,
    pedagogical_transfer_scope_sha256,
)
from tests.providers.anthropic.contracts import (
    AnthropicScoringResponse,
    AnthropicStopReason,
)


def _pairwise_spec() -> V5LogicalCallSpec:
    return next(
        item
        for item in build_v5_2_new_calls()
        if item.call.call_id == SCN_06_PAIRWISE_CALL_ID
    )


def _pairwise_payload(observation_length: int) -> dict[str, object]:
    differences: list[dict[str, object]] = []
    for index in range(4):
        differences.append(
            {
                "locator_a": f"A.section-{index + 1}",
                "locator_b": f"B.section-{index + 1}",
                "observation": (
                    "x" * observation_length
                    if index == 3
                    else f"Synthetic difference {index + 1}."
                ),
                "significance": "MATERIAL" if index == 0 else "NON_MATERIAL",
                "favored_candidate": "A" if index == 0 else "NEITHER",
            }
        )
    return {
        "differences": differences,
        "decision": "A_BETTER",
        "confidence": "HIGH",
        "rationale": "A has the only material difference on the criterion.",
    }


def _pairwise_json(observation_length: int) -> str:
    return json.dumps(
        _pairwise_payload(observation_length),
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    )


def test_exact_191_character_fixture_reproduces_v5_2_2_defect() -> None:
    payload = _pairwise_payload(191)
    differences = cast(list[dict[str, object]], payload["differences"])
    assert len(cast(str, differences[3]["observation"])) == 191
    with pytest.raises(V51ParserError) as captured:
        parse_v5_1_call_result(
            _pairwise_spec(),
            _pairwise_json(191),
            stop_reason=AnthropicStopReason.END_TURN,
        )
    diagnostic = captured.value.diagnostic
    assert diagnostic.error_code is V51ParserErrorCode.OUT_OF_BOUNDS
    assert diagnostic.field_path == "$.differences[3].observation"
    assert diagnostic.expected_constraint == "trimmed length 1..180"
    assert diagnostic.observed_length == 191
    assert diagnostic.observed_value is None


def test_v5_2_3_pairwise_observation_boundaries_pass_without_truncation() -> None:
    for length in (180, 181, 191, 255, 256):
        outcome = parse_v5_2_3_pairwise_call_result(
            _pairwise_spec(),
            _pairwise_json(length),
            stop_reason=AnthropicStopReason.END_TURN,
        )
        observed = outcome.differences[3].observation
        assert len(observed) == length
        assert observed == "x" * length


def test_v5_2_3_pairwise_max_plus_one_fails_closed() -> None:
    with pytest.raises(V523PairwiseParserError) as captured:
        parse_v5_2_3_pairwise_call_result(
            _pairwise_spec(),
            _pairwise_json(MAX_PAIRWISE_DIFFERENCE_OBSERVATION_CHARS + 1),
            stop_reason=AnthropicStopReason.END_TURN,
        )
    diagnostic = captured.value.diagnostic
    assert diagnostic.error_code is V523PairwiseParserErrorCode.OUT_OF_BOUNDS
    assert diagnostic.field_path == "$.differences[3].observation"
    assert diagnostic.expected_constraint == "trimmed length 1..256"
    assert diagnostic.observed_length == 257
    assert diagnostic.observed_value is None


def test_v5_2_3_output_schema_changes_only_pairwise_observation_bound() -> None:
    schema = v5_2_3_pairwise_output_schema()
    properties = cast(dict[str, object], schema["properties"])
    differences = cast(dict[str, object], properties["differences"])
    item = cast(dict[str, object], differences["items"])
    item_properties = cast(dict[str, object], item["properties"])
    observation = cast(dict[str, object], item_properties["observation"])
    rationale = cast(dict[str, object], properties["rationale"])
    locator_a = cast(dict[str, object], item_properties["locator_a"])
    locator_b = cast(dict[str, object], item_properties["locator_b"])
    assert OLD_PAIRWISE_DIFFERENCE_OBSERVATION_CHARS == 180
    assert observation["maxLength"] == MAX_PAIRWISE_DIFFERENCE_OBSERVATION_CHARS == 256
    assert rationale["maxLength"] == MAX_RATIONALE_CHARACTERS == 240
    assert locator_a["maxLength"] == locator_b["maxLength"] == MAX_LOCATOR_CHARACTERS == 64


def test_pairwise_semantic_ambiguity_still_fails_closed() -> None:
    payload = _pairwise_payload(191)
    payload["decision"] = "BETTER"
    with pytest.raises(V523PairwiseParserError) as captured:
        parse_v5_2_3_pairwise_call_result(
            _pairwise_spec(),
            json.dumps(payload),
            stop_reason=AnthropicStopReason.END_TURN,
        )
    assert (
        captured.value.diagnostic.error_code
        is V523PairwiseParserErrorCode.AMBIGUOUS_ALIAS
    )
    assert captured.value.diagnostic.field_path == "$.decision"


def test_nested_candidate_a_b_pass_and_mixed_representation_fails_closed() -> None:
    envelope = next(
        item
        for item in build_v5_2_transfer_envelopes()
        if item.call_id == SCN_06_PAIRWISE_CALL_ID
    )
    metadata = extract_pairwise_projection_metadata(envelope.input_payload)
    assert len(metadata.source_projection_ids) == 2
    ambiguous = deepcopy(envelope.input_payload)
    ambiguous["candidate_a_id"] = "legacy-a"
    with pytest.raises(PairwiseRunnerError) as captured:
        extract_pairwise_projection_metadata(ambiguous)
    assert captured.value.code is PairwiseRunnerErrorCode.AMBIGUOUS_NESTED_AND_FLAT


def test_safe_usage_is_persisted_before_v5_2_3_parse() -> None:
    records: list[dict[str, object]] = []
    outcome = process_anthropic_v5_2_3_pairwise_response(
        spec=_pairwise_spec(),
        response=AnthropicScoringResponse(
            output_text=_pairwise_json(191),
            input_tokens=100,
            cached_input_tokens=0,
            output_tokens=50,
            total_tokens=150,
            stop_reason=AnthropicStopReason.END_TURN,
            text_block_count=1,
            thinking_block_count=0,
            thinking_tokens=0,
        ),
        persist_safe_record=lambda record: records.append(dict(record)),
    )
    assert outcome.decision.value == "A_BETTER"
    assert [record["terminal_status"] for record in records] == [
        "RESPONSE_RECEIVED",
        "COMPLETED",
    ]
    assert records[0]["parser_schema_status"] == "PENDING"
    assert records[1]["parser_schema_status"] == "PASS"
    assert all(record["raw_response_persisted"] is False for record in records)
    assert all("output_text" not in record for record in records)


def test_authorization_identities_anchor_and_budget_remain_unchanged() -> None:
    call_specs = {
        item.call_id: item
        for item in build_v5_2_call_specs()
        if item.call_id in V5_2_2_NEW_CALL_IDS
    }
    for call_id in (SCN_06_PAIRWISE_CALL_ID, SCN_01_PAIRWISE_CALL_ID):
        assert call_specs[call_id].sha256() == EXPECTED_V5_2_CALL_SPEC_SHA256_BY_ID[call_id]
        assert call_specs[call_id].transfer_projection_sha256 == (
            EXPECTED_V5_2_TRANSFER_PROJECTION_SHA256_BY_ID[call_id]
        )
    assert v5_logical_matrix_sha256() == EXPECTED_V5_MATRIX_SHA256
    assert v5_contract_sha256() == EXPECTED_V5_SCORER_CONTRACT_SHA256
    assert pricing_snapshot_sha256() == EXPECTED_PRICING_SNAPSHOT_SHA256
    assert v5_2_gate_contract_sha256() == EXPECTED_V5_2_GATE_CONTRACT_SHA256
    assert (
        pedagogical_transfer_scope_sha256()
        == EXPECTED_PEDAGOGICAL_TRANSFER_SCOPE_SHA256
    )
    assert v4_calibration_corpus_sha256() == (
        "9c8e262028f1d63fa50963f2f8bcb742e4c24d4e106a73244861416f826ca034"
    )
    pairwise_budget = tuple(
        item
        for item in estimate_v5_2_budget().items
        if item.call_id in V5_2_2_NEW_CALL_IDS
    )
    assert sum(
        (item.proposed_ceiling_usd for item in pairwise_budget),
        Decimal("0"),
    ) == PROPOSED_V5_2_2_CEILING_USD == Decimal("0.111200")


def test_existing_absolute_carry_forward_and_live_state_are_unchanged() -> None:
    assert strong_carry_forward_audit().eligible is True
    assert mixed_carry_forward_audit().eligible is True
    assert LIVE_PROVIDER_RECALIBRATION_AUTHORIZED is False
    assert gate_v5_2.LIVE_PROVIDER_RECALIBRATION_AUTHORIZED is False


def test_v5_2_3_output_contract_hash_is_frozen() -> None:
    assert EXPECTED_V5_2_3_PAIRWISE_OUTPUT_CONTRACT_SHA256 != "TO_BE_COMPUTED"
    assert (
        v5_2_3_pairwise_output_contract_sha256()
        == EXPECTED_V5_2_3_PAIRWISE_OUTPUT_CONTRACT_SHA256
    )
