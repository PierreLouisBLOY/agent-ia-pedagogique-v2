from __future__ import annotations

import hashlib
import json
from copy import deepcopy
from decimal import Decimal
from pathlib import Path
from typing import cast

import pytest

from tests.calibration.pedagogical import semantic_gate_v5_2 as gate_v5_2
from tests.calibration.pedagogical.offline_calibration_v5 import (
    v5_contract_sha256,
)
from tests.calibration.pedagogical.pairwise_output_contract_v5_2_3 import (
    EXPECTED_V5_2_3_PAIRWISE_OUTPUT_CONTRACT_SHA256,
    V523PairwiseParserError,
    V523PairwiseParserErrorCode,
    parse_v5_2_3_pairwise_call_result,
    v5_2_3_pairwise_output_contract_sha256,
)
from tests.calibration.pedagogical.pairwise_output_contract_v5_2_4 import (
    EXPECTED_V5_2_4_PAIRWISE_OUTPUT_CONTRACT_SHA256,
    LIVE_PROVIDER_RECALIBRATION_AUTHORIZED,
    MAX_PAIRWISE_DIFFERENCE_OBSERVATION_CHARACTERS,
    MAX_PAIRWISE_LOCATOR_CHARACTERS,
    MAX_PAIRWISE_RATIONALE_CHARACTERS,
    MAX_PAIRWISE_STRUCTURED_OUTPUT_BYTES,
    OLD_PAIRWISE_LOCATOR_CHARACTERS,
    V524PairwiseParserError,
    V524PairwiseParserErrorCode,
    parse_v5_2_4_pairwise_call_result,
    process_anthropic_v5_2_4_pairwise_response,
    v5_2_4_pairwise_output_contract_sha256,
    v5_2_4_pairwise_output_schema,
)
from tests.calibration.pedagogical.pairwise_runner_v5_2_2 import (
    PairwiseRunnerError,
    PairwiseRunnerErrorCode,
    extract_pairwise_projection_metadata,
)
from tests.calibration.pedagogical.pricing import (
    EXPECTED_PRICING_SNAPSHOT_SHA256,
    pricing_snapshot_sha256,
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
from tests.calibration.pedagogical.semantic_pilot_freeze_v5 import (
    EXPECTED_PEDAGOGICAL_TRANSFER_SCOPE_SHA256,
    pedagogical_transfer_scope_sha256,
)
from tests.providers.anthropic.contracts import (
    AnthropicScoringResponse,
    AnthropicStopReason,
)

_REPO_ROOT = Path(__file__).resolve().parents[2]
_V523_ARTIFACT_DIR = (
    _REPO_ROOT / "artifacts/calibration/12.16-g2-v5-2-3-live-pairwise"
)
_V523_SAFE_REPORT_SHA256 = (
    "83e6276a5cf8204e92863e00bddd94f06d34ba49c4c7344271d01d5597c13209"
)
_V523_LEDGER_SHA256 = (
    "0a671ec0dc262b5727e9baba164f5b39dba97746a6fd740ae13ae2eb07e938fd"
)


def _pairwise_spec() -> V5LogicalCallSpec:
    return next(
        item
        for item in build_v5_2_new_calls()
        if item.call.call_id == SCN_01_PAIRWISE_CALL_ID
    )


def _pairwise_payload() -> dict[str, object]:
    return {
        "differences": [
            {
                "locator_a": "A.section-1",
                "locator_b": "B.section-1",
                "observation": "A is clearer on the evaluated criterion.",
                "significance": "MATERIAL",
                "favored_candidate": "A",
            },
            {
                "locator_a": "A.section-2",
                "locator_b": "B.section-2",
                "observation": "No other material distinction is present.",
                "significance": "NON_MATERIAL",
                "favored_candidate": "NEITHER",
            },
            {
                "locator_a": "A.section-3",
                "locator_b": "B.section-3",
                "observation": "Both remain relevant to the requested scope.",
                "significance": "NON_MATERIAL",
                "favored_candidate": "NEITHER",
            },
        ],
        "decision": "A_BETTER",
        "confidence": "HIGH",
        "rationale": "A has the only material difference on the criterion.",
    }


def _pairwise_json(payload: dict[str, object] | None = None) -> str:
    return json.dumps(
        _pairwise_payload() if payload is None else payload,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    )


def _set_difference_text(field: str, value: str) -> str:
    payload = _pairwise_payload()
    differences = cast(list[dict[str, object]], payload["differences"])
    differences[2][field] = value
    return _pairwise_json(payload)


def _sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_exact_locator_80_fixture_reproduces_v5_2_3_defect() -> None:
    output = _set_difference_text("locator_a", "L" * 80)
    with pytest.raises(V523PairwiseParserError) as captured:
        parse_v5_2_3_pairwise_call_result(
            _pairwise_spec(),
            output,
            stop_reason=AnthropicStopReason.END_TURN,
        )
    diagnostic = captured.value.diagnostic
    assert diagnostic.error_code is V523PairwiseParserErrorCode.OUT_OF_BOUNDS
    assert diagnostic.field_path == "$.differences[2].locator_a"
    assert diagnostic.expected_constraint == "trimmed length 1..64"
    assert diagnostic.observed_length == 80
    assert diagnostic.observed_value is None


@pytest.mark.parametrize("field", ["locator_a", "locator_b"])
@pytest.mark.parametrize("length", [64, 65, 80, 127, 128])
def test_v5_2_4_locator_boundaries_pass_without_truncation(
    field: str,
    length: int,
) -> None:
    outcome = parse_v5_2_4_pairwise_call_result(
        _pairwise_spec(),
        _set_difference_text(field, "L" * length),
        stop_reason=AnthropicStopReason.END_TURN,
    )
    observed = getattr(outcome.differences[2], field)
    assert len(observed) == length
    assert observed == "L" * length


@pytest.mark.parametrize("field", ["locator_a", "locator_b"])
def test_v5_2_4_locator_new_max_plus_one_fails_closed(field: str) -> None:
    with pytest.raises(V524PairwiseParserError) as captured:
        parse_v5_2_4_pairwise_call_result(
            _pairwise_spec(),
            _set_difference_text(field, "L" * 129),
            stop_reason=AnthropicStopReason.END_TURN,
        )
    diagnostic = captured.value.diagnostic
    assert diagnostic.error_code is V524PairwiseParserErrorCode.OUT_OF_BOUNDS
    assert diagnostic.field_path == f"$.differences[2].{field}"
    assert diagnostic.expected_constraint == "trimmed length 1..128"
    assert diagnostic.observed_length == 129
    assert diagnostic.observed_value is None


@pytest.mark.parametrize("length", [191, 255, 256])
def test_v5_2_4_observation_boundaries_pass_without_truncation(length: int) -> None:
    outcome = parse_v5_2_4_pairwise_call_result(
        _pairwise_spec(),
        _set_difference_text("observation", "O" * length),
        stop_reason=AnthropicStopReason.END_TURN,
    )
    assert outcome.differences[2].observation == "O" * length


def test_v5_2_4_observation_max_plus_one_fails_closed() -> None:
    with pytest.raises(V524PairwiseParserError) as captured:
        parse_v5_2_4_pairwise_call_result(
            _pairwise_spec(),
            _set_difference_text("observation", "O" * 257),
            stop_reason=AnthropicStopReason.END_TURN,
        )
    assert captured.value.diagnostic.field_path == "$.differences[2].observation"
    assert captured.value.diagnostic.observed_length == 257


@pytest.mark.parametrize("length", [239, 240])
def test_v5_2_4_rationale_boundaries_pass_without_truncation(length: int) -> None:
    payload = _pairwise_payload()
    payload["rationale"] = "R" * length
    outcome = parse_v5_2_4_pairwise_call_result(
        _pairwise_spec(),
        _pairwise_json(payload),
        stop_reason=AnthropicStopReason.END_TURN,
    )
    assert outcome.rationale == "R" * length


def test_v5_2_4_rationale_max_plus_one_fails_closed() -> None:
    payload = _pairwise_payload()
    payload["rationale"] = "R" * 241
    with pytest.raises(V524PairwiseParserError) as captured:
        parse_v5_2_4_pairwise_call_result(
            _pairwise_spec(),
            _pairwise_json(payload),
            stop_reason=AnthropicStopReason.END_TURN,
        )
    assert captured.value.diagnostic.field_path == "$.rationale"
    assert captured.value.diagnostic.observed_length == 241


def test_v5_2_4_total_structured_output_size_boundary() -> None:
    base = _pairwise_json()
    padding = MAX_PAIRWISE_STRUCTURED_OUTPUT_BYTES - len(base.encode("utf-8"))
    at_maximum = " " * padding + base
    assert len(at_maximum.encode("utf-8")) == MAX_PAIRWISE_STRUCTURED_OUTPUT_BYTES
    outcome = parse_v5_2_4_pairwise_call_result(
        _pairwise_spec(),
        at_maximum,
        stop_reason=AnthropicStopReason.END_TURN,
    )
    assert outcome.decision.value == "A_BETTER"

    with pytest.raises(V524PairwiseParserError) as captured:
        parse_v5_2_4_pairwise_call_result(
            _pairwise_spec(),
            " " + at_maximum,
            stop_reason=AnthropicStopReason.END_TURN,
        )
    diagnostic = captured.value.diagnostic
    assert (
        diagnostic.error_code
        is V524PairwiseParserErrorCode.STRUCTURED_OUTPUT_TOO_LARGE
    )
    assert diagnostic.field_path == "$"
    assert diagnostic.observed_value == MAX_PAIRWISE_STRUCTURED_OUTPUT_BYTES + 1


def test_v5_2_4_schema_inventory_is_complete_and_bounded() -> None:
    schema = v5_2_4_pairwise_output_schema()
    properties = cast(dict[str, object], schema["properties"])
    differences = cast(dict[str, object], properties["differences"])
    item = cast(dict[str, object], differences["items"])
    item_properties = cast(dict[str, object], item["properties"])
    assert set(item_properties) == {
        "locator_a",
        "locator_b",
        "observation",
        "significance",
        "favored_candidate",
    }
    assert set(properties) == {"differences", "decision", "confidence", "rationale"}
    assert cast(dict[str, object], item_properties["locator_a"])["maxLength"] == 128
    assert cast(dict[str, object], item_properties["locator_b"])["maxLength"] == 128
    assert cast(dict[str, object], item_properties["observation"])["maxLength"] == 256
    assert cast(dict[str, object], properties["rationale"])["maxLength"] == 240
    assert schema["additionalProperties"] is False
    assert item["additionalProperties"] is False


def test_nested_payload_passes_and_ambiguous_nested_flat_fails_closed() -> None:
    envelope = next(
        item
        for item in build_v5_2_transfer_envelopes()
        if item.call_id == SCN_01_PAIRWISE_CALL_ID
    )
    metadata = extract_pairwise_projection_metadata(envelope.input_payload)
    assert len(metadata.source_projection_ids) == 2
    ambiguous = deepcopy(envelope.input_payload)
    ambiguous["candidate_a_id"] = "legacy-a"
    with pytest.raises(PairwiseRunnerError) as captured:
        extract_pairwise_projection_metadata(ambiguous)
    assert captured.value.code is PairwiseRunnerErrorCode.AMBIGUOUS_NESTED_AND_FLAT


def test_pairwise_semantic_ambiguity_fails_closed() -> None:
    payload = _pairwise_payload()
    payload["decision"] = "BETTER"
    with pytest.raises(V524PairwiseParserError) as captured:
        parse_v5_2_4_pairwise_call_result(
            _pairwise_spec(),
            _pairwise_json(payload),
            stop_reason=AnthropicStopReason.END_TURN,
        )
    assert (
        captured.value.diagnostic.error_code
        is V524PairwiseParserErrorCode.AMBIGUOUS_ALIAS
    )
    assert captured.value.diagnostic.field_path == "$.decision"


def test_safe_usage_is_persisted_before_v5_2_4_parse() -> None:
    records: list[dict[str, object]] = []
    outcome = process_anthropic_v5_2_4_pairwise_response(
        spec=_pairwise_spec(),
        response=AnthropicScoringResponse(
            output_text=_set_difference_text("locator_a", "L" * 80),
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
    assert all(record["raw_response_persisted"] is False for record in records)
    assert all("output_text" not in record for record in records)


def test_v5_2_3_carry_forward_is_hash_bound_and_complete_4_of_4() -> None:
    report_path = _V523_ARTIFACT_DIR / "safe_report.json"
    ledger_path = _V523_ARTIFACT_DIR / "ledger.json"
    assert _sha256_file(report_path) == _V523_SAFE_REPORT_SHA256
    assert _sha256_file(ledger_path) == _V523_LEDGER_SHA256
    report = cast(dict[str, object], json.loads(report_path.read_text(encoding="utf-8")))
    ledger = cast(dict[str, object], json.loads(ledger_path.read_text(encoding="utf-8")))
    assert report["strong_score"] == 4
    assert report["weak_score"] == 1
    assert report["mixed_score"] == 0
    assert report["pairwise_scn_06"] == "A_BETTER"
    assert report["carry_forward_reissued"] is False
    assert report["carry_forward_retransmitted"] is False
    assert report["raw_response_persistence"] == "NONE"
    assert strong_carry_forward_audit().eligible is True
    assert mixed_carry_forward_audit().eligible is True

    calls = cast(list[dict[str, object]], ledger["calls"])
    scn_06 = next(item for item in calls if item["call_id"] == SCN_06_PAIRWISE_CALL_ID)
    safe = cast(dict[str, object], scn_06["safe_response_record"])
    assert scn_06["status"] == "COMPLETED"
    assert safe["pairwise_disposition"] == "A_BETTER"
    assert safe["parser_schema_status"] == "PASS"
    assert safe["raw_response_persisted"] is False
    assert scn_06["transfer_payload_sha256"] == (
        EXPECTED_V5_2_TRANSFER_PROJECTION_SHA256_BY_ID[SCN_06_PAIRWISE_CALL_ID]
    )


def test_scn_01_authorization_identities_and_single_call_budget_are_unchanged() -> None:
    call_spec = next(
        item for item in build_v5_2_call_specs() if item.call_id == SCN_01_PAIRWISE_CALL_ID
    )
    assert call_spec.sha256() == (
        "d4143eca0ac6ba40152eecdc5c37cfa7c2f74b3cda39774db79feec54689c0ca"
    )
    assert call_spec.sha256() == EXPECTED_V5_2_CALL_SPEC_SHA256_BY_ID[call_spec.call_id]
    assert call_spec.transfer_projection_sha256 == (
        "8cfea454d79472cd04f9274f8e960db4fa7c7e69b562b7b9f9d673c01acc9b0d"
    )
    assert call_spec.transfer_projection_sha256 == (
        EXPECTED_V5_2_TRANSFER_PROJECTION_SHA256_BY_ID[call_spec.call_id]
    )
    assert pedagogical_transfer_scope_sha256() == (
        "c65e6460969d3eee4a5fb6a5d99e0a9bfbf3a253efc111ebb64e4af788df0e93"
    )
    assert (
        pedagogical_transfer_scope_sha256()
        == EXPECTED_PEDAGOGICAL_TRANSFER_SCOPE_SHA256
    )
    budget_item = next(
        item for item in estimate_v5_2_budget().items if item.call_id == call_spec.call_id
    )
    assert budget_item.proposed_ceiling_usd == Decimal("0.055600")


def test_unchanged_contract_identities_and_live_state() -> None:
    assert v5_logical_matrix_sha256() == EXPECTED_V5_MATRIX_SHA256
    assert v5_contract_sha256() == EXPECTED_V5_SCORER_CONTRACT_SHA256
    assert pricing_snapshot_sha256() == EXPECTED_PRICING_SNAPSHOT_SHA256
    assert v5_2_gate_contract_sha256() == EXPECTED_V5_2_GATE_CONTRACT_SHA256
    assert LIVE_PROVIDER_RECALIBRATION_AUTHORIZED is False
    assert gate_v5_2.LIVE_PROVIDER_RECALIBRATION_AUTHORIZED is False


def test_v5_2_4_contract_profile_and_hash_are_frozen() -> None:
    assert OLD_PAIRWISE_LOCATOR_CHARACTERS == 64
    assert MAX_PAIRWISE_LOCATOR_CHARACTERS == 128
    assert MAX_PAIRWISE_DIFFERENCE_OBSERVATION_CHARACTERS == 256
    assert MAX_PAIRWISE_RATIONALE_CHARACTERS == 240
    assert MAX_PAIRWISE_STRUCTURED_OUTPUT_BYTES == 8_192
    assert (
        v5_2_3_pairwise_output_contract_sha256()
        == EXPECTED_V5_2_3_PAIRWISE_OUTPUT_CONTRACT_SHA256
    )
    assert EXPECTED_V5_2_4_PAIRWISE_OUTPUT_CONTRACT_SHA256 != "TO_BE_COMPUTED"
    assert (
        v5_2_4_pairwise_output_contract_sha256()
        == EXPECTED_V5_2_4_PAIRWISE_OUTPUT_CONTRACT_SHA256
    )
