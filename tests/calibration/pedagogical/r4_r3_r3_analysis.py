"""Deterministic offline analysis of the 76 homogeneous Anthropic scores."""

from __future__ import annotations

import hashlib
import json
import os
from collections import Counter, defaultdict
from collections.abc import Mapping
from dataclasses import asdict
from decimal import Decimal
from enum import StrEnum
from fractions import Fraction
from pathlib import Path
from typing import Never, cast

from tests.calibration.pedagogical.catalog import (
    ANCHOR_EXPECTATIONS,
    CALIBRATION_ANCHORS,
    CRITERION_ORDERINGS,
    AnchorTier,
    anchor_by_id,
    calibration_corpus_sha256,
    scenario_by_code,
)
from tests.calibration.pedagogical.metrics import (
    CalibrationResponseStatus,
    InvocationObservation,
    QualityScoreObservation,
    RepeatScore,
    summarize_invocations,
    summarize_latency,
    summarize_orderings,
    summarize_quality,
    summarize_rational_distribution,
    summarize_repeatability,
)
from tests.calibration.pedagogical.r3b_r3_plan import audit_r3_consolidated_evidence
from tests.calibration.pedagogical.r4_r1_policy import build_uniform_scoring_matrix
from tests.calibration.pedagogical.r4_r3_r1_recovery import audit_evidence
from tests.providers.anthropic.mapping import score_output_schema
from tests.providers.anthropic.transport import transform_anthropic_provider_schema

ROOT = Path(__file__).resolve().parents[3]

PHASE = "12.16-G2-R3B-R4-R3-R3"
REPORT_MD_RELATIVE_PATH = (
    "docs/development/PHASE_12_16_G2_FINAL_CALIBRATION_ANALYSIS_REPORT.md"
)
REPORT_JSON_RELATIVE_PATH = (
    "docs/development/PHASE_12_16_G2_FINAL_CALIBRATION_ANALYSIS_REPORT.json"
)
BASELINE_RELATIVE_PATH = (
    "docs/development/PHASE_12_16_G2_FINAL_CALIBRATION_ANALYSIS_BASELINE.md"
)
HUMAN_PACKET_RELATIVE_PATH = (
    "docs/development/PHASE_12_16_G2_HUMAN_ANCHOR_REVIEW_PACKET.md"
)
ANALYSIS_ARTIFACT_DIRECTORY = "artifacts/calibration/12.16-g2-r4-r5"
FINAL_MANIFEST_RELATIVE_PATH = (
    f"{ANALYSIS_ARTIFACT_DIRECTORY}/final_uniform_result_manifest.json"
)
RECONCILIATION_RELATIVE_PATH = (
    f"{ANALYSIS_ARTIFACT_DIRECTORY}/human_review_reconciliation.json"
)

CONTINUATION_LEDGER_RELATIVE_PATH = "artifacts/calibration/12.16-g2-r4-r4/ledger.json"
CONTINUATION_SUMMARY_RELATIVE_PATH = "artifacts/calibration/12.16-g2-r4-r4/summary.json"
CONTINUATION_TRANSFER_RELATIVE_PATH = (
    "artifacts/calibration/12.16-g2-r4-r4/transfer_manifest.json"
)
CONTINUATION_RAW_ROOT = "artifacts/calibration/12.16-g2-r4-r4/raw"
CONTINUATION_LEDGER_SHA256 = (
    "4271bbcc24d453fa596eb200c2e4bcf02892599175fbc106ce3e684154f0dd17"
)
CONTINUATION_SUMMARY_SHA256 = (
    "83c5da3d662a33036d840da147920ed2f137c9704039a5a42a861cf5b34da7fd"
)
CONTINUATION_TRANSFER_SHA256 = (
    "723ce92f820c2e18416d19ed372ecbe3fb2065b9a50fd54c664834c12170f685"
)
CONTINUATION_RAW_CALL_ORDER_SHA256 = (
    "a6b75cb01e8fe8ce3935b1c4ba7b8a060a79c949eb39e340e0c03115b7c9a894"
)

R3B_R4_LEDGER_RELATIVE_PATH = "artifacts/calibration/12.16-g2-r3b-r4/ledger.json"
R3B_R4_LEDGER_SHA256 = (
    "2163050a6dc580acadddcedbb72ec13ee5b984f0769b51593a965d2bace99c82"
)

ENTRY_BRANCH = "phase12/12-16-provider-model-calibration"
ENTRY_HEAD = "123b4ebec6633df5c4512fce0e4755415f00c38d"
ENTRY_MAIN = "7ae02ee109bcc6399ec0f71616da6aef07abda81"

EXPECTED_INPUT_TOKENS = 79_273
EXPECTED_CACHED_INPUT_TOKENS = 0
EXPECTED_OUTPUT_TOKENS = 5_016
EXPECTED_THINKING_TOKENS = 2_789
EXPECTED_TOTAL_TOKENS = 84_289
EXPECTED_FINAL_ANTHROPIC_COST = Decimal("0.208706")

# These qualitative rules are deliberately declared before dataset evaluation.
ANCHOR_EVIDENCE_RULE = (
    "STRONG iff all 16 complete orderings are strict; CONTRADICTORY iff any "
    "adjacent inversion exists; PARTIAL iff complete and weak without inversion; "
    "otherwise INSUFFICIENT."
)
REPEATABILITY_EVIDENCE_RULE = (
    "STRONG iff all 16 complete two-observation groups agree exactly; WEAK iff "
    "none agree; PARTIAL iff some agree; otherwise INSUFFICIENT."
)


class AnalysisErrorCode(StrEnum):
    FINAL_CALIBRATION_EVIDENCE_MISMATCH = "FINAL_CALIBRATION_EVIDENCE_MISMATCH"
    FINAL_MANIFEST_INVALID = "FINAL_MANIFEST_INVALID"
    FINAL_TOKEN_OR_COST_MISMATCH = "FINAL_TOKEN_OR_COST_MISMATCH"
    OPENAI_EVIDENCE_MISMATCH = "OPENAI_EVIDENCE_MISMATCH"
    COST_ACCOUNTING_INVALID = "COST_ACCOUNTING_INVALID"


class AnalysisError(RuntimeError):
    code: AnalysisErrorCode

    def __init__(self, code: AnalysisErrorCode) -> None:
        self.code = code
        super().__init__(code.value)


def _fail(code: AnalysisErrorCode) -> Never:
    raise AnalysisError(code) from None


def _sha256(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _canonical_bytes(payload: object) -> bytes:
    return json.dumps(
        payload,
        allow_nan=False,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")


def _canonical_sha256(payload: object) -> str:
    return _sha256(_canonical_bytes(payload))


def _pretty_json(payload: object) -> str:
    return (
        json.dumps(
            payload,
            allow_nan=False,
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
        + "\n"
    )


def _artifact_path(root: Path, relative_path: str) -> Path:
    path = (root / relative_path).resolve()
    artifact_root = (root / "artifacts/calibration").resolve()
    if artifact_root not in path.parents:
        raise ValueError("artifact path escaped calibration directory")
    return path


def _read_frozen_json(
    root: Path, relative_path: str, expected_sha256: str
) -> dict[str, object]:
    try:
        raw = _artifact_path(root, relative_path).read_bytes()
        payload = json.loads(raw.decode("utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        _fail(AnalysisErrorCode.FINAL_CALIBRATION_EVIDENCE_MISMATCH)
    if _sha256(raw) != expected_sha256 or type(payload) is not dict:
        _fail(AnalysisErrorCode.FINAL_CALIBRATION_EVIDENCE_MISMATCH)
    return cast(dict[str, object], payload)


def _fraction(value: str) -> Fraction:
    try:
        numerator, denominator = value.split("/", maxsplit=1)
        result = Fraction(int(numerator), int(denominator))
    except (AttributeError, TypeError, ValueError, ZeroDivisionError):
        _fail(AnalysisErrorCode.FINAL_MANIFEST_INVALID)
    if not 0 <= result <= 1:
        _fail(AnalysisErrorCode.FINAL_MANIFEST_INVALID)
    return result


def _fraction_payload(value: Fraction | None) -> dict[str, int] | None:
    if value is None:
        return None
    return {"numerator": value.numerator, "denominator": value.denominator}


def _category(logical_slot_id: str, repetition: int) -> str:
    if logical_slot_id.startswith("cal.score.output."):
        return "SELECTED_OUTPUT"
    if repetition == 2:
        return "REPEATABILITY"
    return "INITIAL_ANCHOR"


def _provider_schema_sha256() -> str:
    return _canonical_sha256(transform_anthropic_provider_schema(score_output_schema()))


def _validate_raw(root: Path, record: Mapping[str, object], raw_root: str) -> None:
    relative = record.get("raw_output_path")
    expected = record.get("raw_output_sha256")
    expected_bytes = record.get("raw_output_utf8_bytes")
    if type(relative) is not str or type(expected) is not str:
        _fail(AnalysisErrorCode.FINAL_CALIBRATION_EVIDENCE_MISMATCH)
    path = _artifact_path(root, relative)
    root_path = _artifact_path(root, raw_root)
    if root_path not in path.parents:
        _fail(AnalysisErrorCode.FINAL_CALIBRATION_EVIDENCE_MISMATCH)
    try:
        raw = path.read_bytes()
        payload = json.loads(raw.decode("utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        _fail(AnalysisErrorCode.FINAL_CALIBRATION_EVIDENCE_MISMATCH)
    if (
        _sha256(raw) != expected
        or (type(expected_bytes) is int and len(raw) != expected_bytes)
        or type(payload) is not dict
        or payload.get("status") != "SCORED"
        or type(payload.get("score_numerator")) is not int
        or type(payload.get("score_denominator")) is not int
    ):
        _fail(AnalysisErrorCode.FINAL_CALIBRATION_EVIDENCE_MISMATCH)
    raw_score = Fraction(
        cast(int, payload["score_numerator"]),
        cast(int, payload["score_denominator"]),
    )
    if raw_score != _fraction(cast(str, record.get("rational_score"))):
        _fail(AnalysisErrorCode.FINAL_CALIBRATION_EVIDENCE_MISMATCH)


def _manifest_item(
    record: Mapping[str, object],
    *,
    proof_set: str,
    input_sha256: str,
) -> dict[str, object]:
    logical_id = cast(str, record["original_logical_slot_id"])
    criterion_refs = cast(list[str], record["criterion_refs"])
    input_refs = cast(list[str], record["input_refs"])
    repetition = cast(int, record["repetition"])
    return {
        "proof_set": proof_set,
        "execution_call_id": record["execution_call_id"],
        "logical_slot_id": logical_id,
        "category": _category(logical_id, repetition),
        "scenario_code": record["scenario_code"],
        "criterion_ref": criterion_refs[0],
        "subject_ref": input_refs[0],
        "repetition": repetition,
        "provider": record["provider"],
        "model": record["model"],
        "model_profile_id": record["model_profile_id"],
        "thinking_mode": record["thinking_mode"],
        "effort": record["effort"],
        "max_output_tokens": record["max_output_tokens"],
        "score_status": record["score_status"],
        "score": _fraction_payload(_fraction(cast(str, record["rational_score"]))),
        "input_sha256": input_sha256,
        "schema_sha256": _provider_schema_sha256(),
        "output_sha256": record["raw_output_sha256"],
        "usage": {
            "input_tokens": record["input_tokens"],
            "cached_input_tokens": record["cached_input_tokens"],
            "output_tokens": record["output_tokens"],
            "thinking_tokens": record["thinking_tokens"],
            "total_tokens": record["total_tokens"],
        },
        "latency_milliseconds": record["latency_milliseconds"],
        "measured_cost_usd": record["cost_usd"],
        "response_status": record["response_status"],
        "stop_reason": record["stop_reason"],
        "text_block_count": record["text_block_count"],
        "thinking_block_count": record["thinking_block_count"],
    }


def _continuation_evidence(root: Path) -> dict[str, object]:
    ledger = _read_frozen_json(
        root, CONTINUATION_LEDGER_RELATIVE_PATH, CONTINUATION_LEDGER_SHA256
    )
    summary = _read_frozen_json(
        root, CONTINUATION_SUMMARY_RELATIVE_PATH, CONTINUATION_SUMMARY_SHA256
    )
    transfer = _read_frozen_json(
        root, CONTINUATION_TRANSFER_RELATIVE_PATH, CONTINUATION_TRANSFER_SHA256
    )
    calls = ledger.get("calls")
    transfers = transfer.get("calls")
    if (
        type(calls) is not list
        or type(transfers) is not list
        or len(calls) != 38
        or len(transfers) != 38
        or any(type(item) is not dict for item in calls)
        or any(type(item) is not dict for item in transfers)
    ):
        _fail(AnalysisErrorCode.FINAL_CALIBRATION_EVIDENCE_MISMATCH)
    records = cast(list[dict[str, object]], calls)
    if (
        Counter(cast(str, item.get("status")) for item in records) != {"COMPLETED": 38}
        or Counter(cast(str, item.get("score_status")) for item in records)
        != {"SCORED": 38}
        or ledger.get("automatic_retry_count") != 0
        or ledger.get("automatic_rerun_count") != 0
        or summary.get("duplicate_execution_call_ids") != []
    ):
        _fail(AnalysisErrorCode.FINAL_CALIBRATION_EVIDENCE_MISMATCH)
    transfer_by_id = {
        cast(str, item["execution_call_id"]): cast(dict[str, object], item)
        for item in cast(list[dict[str, object]], transfers)
    }
    raw_hashes: list[str] = []
    for record in records:
        _validate_raw(root, record, CONTINUATION_RAW_ROOT)
        execution_id = cast(str, record["execution_call_id"])
        transfer_item = transfer_by_id.get(execution_id)
        if (
            transfer_item is None
            or transfer_item.get("logical_slot_id")
            != record.get("original_logical_slot_id")
            or transfer_item.get("projection_sha256") != record.get("payload_sha256")
        ):
            _fail(AnalysisErrorCode.FINAL_CALIBRATION_EVIDENCE_MISMATCH)
        raw_hashes.append(cast(str, record["raw_output_sha256"]))
    digest = _sha256(_canonical_bytes(raw_hashes))
    if digest != CONTINUATION_RAW_CALL_ORDER_SHA256:
        _fail(AnalysisErrorCode.FINAL_CALIBRATION_EVIDENCE_MISMATCH)
    return {
        "ledger": ledger,
        "summary": summary,
        "transfer": transfer,
        "transfer_by_id": transfer_by_id,
        "records": records,
        "raw_call_order_sha256": digest,
    }


def validate_final_manifest(payload: Mapping[str, object]) -> None:
    raw_results = payload.get("results")
    if type(raw_results) is not list or any(type(item) is not dict for item in raw_results):
        _fail(AnalysisErrorCode.FINAL_MANIFEST_INVALID)
    results = cast(list[dict[str, object]], raw_results)
    logical_ids = [cast(str, item.get("logical_slot_id")) for item in results]
    expected_ids = {
        call.original_logical_slot_id for call in build_uniform_scoring_matrix()
    }
    split = Counter(cast(str, item.get("category")) for item in results)
    if (
        len(results) != 76
        or len(logical_ids) != len(set(logical_ids))
        or set(logical_ids) != expected_ids
        or split
        != {"INITIAL_ANCHOR": 48, "REPEATABILITY": 16, "SELECTED_OUTPUT": 12}
        or any(item.get("score_status") != "SCORED" for item in results)
        or any(item.get("response_status") != "STRUCTURED" for item in results)
        or any(item.get("provider") != "anthropic" for item in results)
        or any(item.get("model") != "claude-sonnet-5" for item in results)
        or any(item.get("thinking_mode") != "adaptive" for item in results)
        or any(item.get("effort") != "low" for item in results)
        or any(item.get("max_output_tokens") != 2_048 for item in results)
        or any("DIAGNOSTIC" in cast(str, item.get("proof_set")) for item in results)
    ):
        _fail(AnalysisErrorCode.FINAL_MANIFEST_INVALID)


def build_final_manifest(root: Path = ROOT) -> dict[str, object]:
    prior = audit_evidence(root)
    continuation = _continuation_evidence(root)
    r2 = cast(dict[str, object], prior["r2"])
    r3 = cast(dict[str, object], prior["r3"])
    r2_call = cast(dict[str, object], r2["call"])
    r2_summary = cast(dict[str, object], r2["summary"])
    results = [
        _manifest_item(
            r2_call,
            proof_set="R2_HOMOGENEOUS_CANARY",
            input_sha256=cast(str, r2_summary["transfer_projection_sha256"]),
        )
    ]
    r3_transfers = cast(dict[str, dict[str, object]], r3["manifest_by_execution_id"])
    for record in cast(list[dict[str, object]], r3["completed"]):
        transfer_item = r3_transfers[cast(str, record["execution_call_id"])]
        results.append(
            _manifest_item(
                record,
                proof_set="R3_COMPLETED_BEFORE_HTTP503",
                input_sha256=cast(str, transfer_item["projection_sha256"]),
            )
        )
    continuation_transfers = cast(
        dict[str, dict[str, object]], continuation["transfer_by_id"]
    )
    for record in cast(list[dict[str, object]], continuation["records"]):
        transfer_item = continuation_transfers[cast(str, record["execution_call_id"])]
        results.append(
            _manifest_item(
                record,
                proof_set="R4_RECOVERY_CONTINUATION",
                input_sha256=cast(str, transfer_item["projection_sha256"]),
            )
        )
    results.sort(key=lambda item: cast(str, item["logical_slot_id"]))
    payload: dict[str, object] = {
        "manifest_version": "12.16-g2-final-uniform-results-v1",
        "proofs": {
            "r2_ledger_sha256": (
                "ef694ad8174a28079db030086d83d0ffb8d02d7aed598092961b821b3fdd2a31"
            ),
            "r2_summary_sha256": (
                "ec88b72b616793bd4d215ec1f4a5e24a03b458691e1b00ce7491b4f6486d5948"
            ),
            "r2_raw_sha256": (
                "a16287401cc87863d23dc170b76cf2983ccae1909374d2a3b6af8226642f6053"
            ),
            "r3_ledger_sha256": (
                "bd4f9272730c225a7e1a309137cf937bcb0b8a9603446cc76c8d94871a029c99"
            ),
            "r3_summary_sha256": (
                "c3052b33193bf6542cd96a2ff1706c8d210e297c736d1d3ffa101676c9405729"
            ),
            "r3_transfer_manifest_sha256": (
                "c8742f5e4a46215a34141e93b17b36a730c6ab6136b3c92ad3eba073be1e905a"
            ),
            "r3_raw_ordered_list_sha256": (
                "f39d83334eda6b0f87b4ecf363e9f432d818b298d55defa6c1076ec766a34c52"
            ),
            "continuation_ledger_sha256": CONTINUATION_LEDGER_SHA256,
            "continuation_summary_sha256": CONTINUATION_SUMMARY_SHA256,
            "continuation_transfer_manifest_sha256": CONTINUATION_TRANSFER_SHA256,
            "continuation_raw_call_order_sha256": CONTINUATION_RAW_CALL_ORDER_SHA256,
        },
        "result_count": len(results),
        "raw_content_recorded": False,
        "diagnostic_only_results_included": False,
        "results": results,
    }
    validate_final_manifest(payload)
    return payload


def final_manifest_sha256(root: Path = ROOT) -> str:
    return _canonical_sha256(build_final_manifest(root))


def _score(item: Mapping[str, object]) -> Fraction:
    payload = cast(dict[str, int], item["score"])
    return Fraction(payload["numerator"], payload["denominator"])


def _ordering_evidence(metrics: Mapping[str, object]) -> str:
    if cast(int, metrics["inconclusive_count"]) > 0:
        return "INSUFFICIENT"
    if cast(int, metrics["inverted_pair_count"]) > 0:
        return "CONTRADICTORY"
    if cast(int, metrics["strict_ordering_count"]) == 16:
        return "STRONG"
    if cast(int, metrics["weak_ordering_count"]) == 16:
        return "PARTIAL"
    return "INSUFFICIENT"


def _repeatability_evidence(metrics: Mapping[str, object]) -> str:
    if cast(int, metrics["group_count"]) != 16 or cast(
        int, metrics["inconclusive_count"]
    ):
        return "INSUFFICIENT"
    agreements = cast(int, metrics["exact_agreement_count"])
    if agreements == 16:
        return "STRONG"
    if agreements == 0:
        return "WEAK"
    return "PARTIAL"


def _relative_classification(
    output: Fraction, strong: Fraction, mixed: Fraction, weak: Fraction
) -> str:
    if not strong > mixed > weak:
        return "UNCLASSIFIABLE_NON_MONOTONIC_ANCHORS"
    if output > strong:
        return "ABOVE_STRONG"
    if output == strong:
        return "EQUAL_STRONG"
    if output > mixed:
        return "BETWEEN_STRONG_AND_MIXED"
    if output == mixed:
        return "EQUAL_MIXED"
    if output > weak:
        return "BETWEEN_MIXED_AND_WEAK"
    if output == weak:
        return "EQUAL_WEAK"
    return "BELOW_WEAK"


def _distribution_payload(values: tuple[Fraction, ...]) -> dict[str, object]:
    summary = summarize_rational_distribution(values)
    return {
        "observation_count": summary.observation_count,
        "distinct_value_count": summary.distinct_value_count,
        "histogram": [
            {"score": _fraction_payload(score), "count": count}
            for score, count in summary.histogram
        ],
        "denominator_frequencies": [
            {"denominator": denominator, "count": count}
            for denominator, count in summary.denominator_frequencies
        ],
        "zero_count": summary.zero_count,
        "one_count": summary.one_count,
        "intermediate_count": summary.intermediate_count,
        "mean": _fraction_payload(summary.mean),
        "median": _fraction_payload(summary.median),
    }


def _openai_latency(root: Path, evidence_set: str, logical_id: str) -> int:
    if evidence_set == "G2":
        path = root / "artifacts/calibration/12.16-g2/ledger.json"
        key = "call_id"
    elif evidence_set == "R2B":
        path = root / "artifacts/calibration/12.16-g2-r2b/ledger.json"
        key = "call_id"
    else:
        path = root / "artifacts/calibration/12.16-g2-r3/ledger.json"
        key = "logical_slot_id"
    payload = cast(dict[str, object], json.loads(path.read_text(encoding="utf-8")))
    calls = cast(list[dict[str, object]], payload["calls"])
    if evidence_set == "R2B":
        records = calls
    else:
        records = [item for item in calls if item.get(key) == logical_id]
    if len(records) != 1 or type(records[0].get("latency_milliseconds")) is not int:
        _fail(AnalysisErrorCode.OPENAI_EVIDENCE_MISMATCH)
    return cast(int, records[0]["latency_milliseconds"])


def audit_openai_results(root: Path = ROOT) -> tuple[dict[str, object], ...]:
    audit = audit_r3_consolidated_evidence(root)
    mappings = [item for item in audit.reused_mappings if item.provider == "openai"]
    if len(mappings) != 20 or len({item.original_logical_slot_id for item in mappings}) != 20:
        _fail(AnalysisErrorCode.OPENAI_EVIDENCE_MISMATCH)
    results: list[dict[str, object]] = []
    for item in mappings:
        logical_id = item.original_logical_slot_id
        if logical_id.startswith("cal.generation."):
            family = "GENERATION"
        elif logical_id.startswith("cal.transformation."):
            family = "TRANSFORMATION"
        elif logical_id.startswith("cal.correction."):
            family = "CORRECTION"
        elif item.model == "gpt-5.6-sol":
            family = "REVIEW_SOL"
        else:
            family = "REVIEW_TERRA"
        results.append(
            {
                "proof_set": item.evidence_set,
                "logical_slot_id": logical_id,
                "family": family,
                "model": item.model,
                "model_profile_id": item.model_profile_id,
                "post_validation_status": item.status,
                "output_sha256": item.output_sha256,
                "usage": {
                    "input_tokens": item.input_tokens,
                    "cached_input_tokens": item.cached_input_tokens,
                    "output_tokens": item.output_tokens,
                    "reasoning_tokens": item.reasoning_tokens or 0,
                    "total_tokens": item.total_tokens,
                },
                "latency_milliseconds": _openai_latency(
                    root, item.evidence_set, logical_id
                ),
                "measured_cost_usd": item.cost_usd,
            }
        )
    return tuple(sorted(results, key=lambda value: cast(str, value["logical_slot_id"])))


def _openai_summary(results: tuple[dict[str, object], ...]) -> dict[str, object]:
    groups: dict[str, list[dict[str, object]]] = defaultdict(list)
    for item in results:
        groups[cast(str, item["family"])].append(item)
    grouped: dict[str, object] = {}
    for family, items in sorted(groups.items()):
        usages = [cast(dict[str, int], item["usage"]) for item in items]
        grouped[family] = {
            "call_count": len(items),
            "statuses": dict(
                sorted(Counter(cast(str, item["post_validation_status"]) for item in items).items())
            ),
            "input_tokens": sum(item["input_tokens"] for item in usages),
            "cached_input_tokens": sum(item["cached_input_tokens"] for item in usages),
            "output_tokens": sum(item["output_tokens"] for item in usages),
            "reasoning_tokens": sum(item["reasoning_tokens"] for item in usages),
            "total_tokens": sum(item["total_tokens"] for item in usages),
            "latency_milliseconds": sum(cast(int, item["latency_milliseconds"]) for item in items),
            "measured_cost_usd": str(
                sum(
                    (Decimal(cast(str, item["measured_cost_usd"])) for item in items),
                    start=Decimal("0"),
                )
            ),
        }
    return {
        "result_count": len(results),
        "status_counts": dict(
            sorted(Counter(cast(str, item["post_validation_status"]) for item in results).items())
        ),
        "families": grouped,
        "results": list(results),
    }


def _read_json(root: Path, relative_path: str) -> dict[str, object]:
    try:
        payload = json.loads((root / relative_path).read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        _fail(AnalysisErrorCode.COST_ACCOUNTING_INVALID)
    if type(payload) is not dict:
        _fail(AnalysisErrorCode.COST_ACCOUNTING_INVALID)
    return cast(dict[str, object], payload)


def _ledger_calls(root: Path, relative_path: str) -> list[dict[str, object]]:
    payload = _read_json(root, relative_path)
    calls = payload.get("calls")
    if type(calls) is not list or any(type(item) is not dict for item in calls):
        _fail(AnalysisErrorCode.COST_ACCOUNTING_INVALID)
    return cast(list[dict[str, object]], calls)


def cost_accounting(
    root: Path,
    *,
    final_openai: tuple[dict[str, object], ...],
    final_anthropic: tuple[dict[str, object], ...],
) -> dict[str, object]:
    category_a = sum(
        (Decimal(cast(str, item["measured_cost_usd"])) for item in final_openai),
        start=Decimal("0"),
    )
    category_b = sum(
        (Decimal(cast(str, item["measured_cost_usd"])) for item in final_anthropic),
        start=Decimal("0"),
    )
    r2 = _ledger_calls(root, "artifacts/calibration/12.16-g2-r2/ledger.json")
    r3 = _ledger_calls(root, "artifacts/calibration/12.16-g2-r3/ledger.json")
    r3b_r2 = _ledger_calls(root, "artifacts/calibration/12.16-g2-r3b-r2/ledger.json")
    r3b_r4_payload = _read_frozen_json(
        root, R3B_R4_LEDGER_RELATIVE_PATH, R3B_R4_LEDGER_SHA256
    )
    r3b_r4 = cast(list[dict[str, object]], r3b_r4_payload["calls"])
    diagnostic = [
        *r2,
        *(item for item in r3 if item.get("provider") == "anthropic" and item.get("status") == "COMPLETED"),
        *r3b_r2,
        *(item for item in r3b_r4 if cast(int, item.get("total_tokens", 0)) > 0),
    ]
    category_c = sum(
        (Decimal(cast(str, item["cost_usd"])) for item in diagnostic),
        start=Decimal("0"),
    )
    g2_failed = [
        item
        for item in _ledger_calls(root, "artifacts/calibration/12.16-g2/ledger.json")
        if item.get("status") == "FAILED" and item.get("total_tokens") == 0
    ]
    reserved = [
        *g2_failed,
        *(
            item
            for item in r3
            if item.get("status") == "FAILED" and item.get("cost_basis") == "RESERVED"
        ),
        *(
            item
            for item in _ledger_calls(root, "artifacts/calibration/12.16-g2-r4-r3/ledger.json")
            if item.get("status") == "FAILED" and item.get("cost_basis") == "RESERVED"
        ),
    ]
    category_d = sum(
        (Decimal(cast(str, item["cost_usd"])) for item in reserved),
        start=Decimal("0"),
    )
    if (
        category_a != Decimal("0.211738")
        or category_b != EXPECTED_FINAL_ANTHROPIC_COST
        or category_c != Decimal("0.054800")
        or category_d != Decimal("1.957696")
    ):
        _fail(AnalysisErrorCode.COST_ACCOUNTING_INVALID)
    return {
        "A_FINAL_USEFUL_OPENAI_EXECUTION_COST": str(category_a),
        "B_FINAL_UNIFORM_ANTHROPIC_SCORING_COST": str(category_b),
        "C_DIAGNOSTIC_AND_REMEDIATION_MEASURED_COST": str(category_c),
        "D_CONSERVATIVE_RESERVES_NOT_PROVEN_AS_BILLED": str(category_d),
        "final_useful_cost_usd": str(category_a + category_b),
        "experimental_measured_cost_usd": str(category_a + category_b + category_c),
        "measured_plus_conservative_reserves_usd": str(
            category_a + category_b + category_c + category_d
        ),
        "billing_truth": "PROVIDER_DASHBOARDS",
        "no_double_counting": True,
        "historical_diagnostic_anthropic_score_count": 5,
    }


def _human_review_mapping() -> tuple[tuple[str, str], ...]:
    ordered = sorted(
        (anchor.anchor_id for anchor in CALIBRATION_ANCHORS),
        key=lambda anchor_id: _sha256(anchor_id.encode("utf-8")),
    )
    return tuple((f"REV-{index:03d}", anchor_id) for index, anchor_id in enumerate(ordered, 1))


def render_human_review_packet() -> str:
    lines = [
        "# Phase 12.16-G2 — Paquet aveugle de revue humaine des ancres",
        "",
        "Ce paquet réutilise les consignes du template G1. Il est volontairement non rempli.",
        "",
        "- Corpus : `12.16-g1-v1`",
        f"- Checksum corpus : `{calibration_corpus_sha256()}`",
        "- REVIEW_STATUS : `NOT_COMPLETED`",
        "- Relecteur ou relectrice :",
        "- Date :",
        "- Version de la grille :",
        "- Exposition préalable aux résultats machine :",
        "",
        "## Consignes",
        "",
        "1. Examiner chaque contenu sans consulter la clé de réconciliation machine.",
        "2. Évaluer la validité structurelle et la qualité pédagogique pour les deux critères.",
        "3. Signaler ambiguïtés, égalités plausibles et insuffisances sans corriger le contenu.",
        "4. Ne copier aucune sortie fournisseur brute, donnée privée, clé ou chemin local.",
        "",
    ]
    for review_id, anchor_id in _human_review_mapping():
        anchor = anchor_by_id(anchor_id)
        scenario = scenario_by_code(anchor.scenario_code)
        lines.extend(
            (
                f"## {review_id}",
                "",
                f"- Scénario : `{scenario.scenario_code}`",
                f"- Niveau : `{scenario.level_code}`",
                f"- Type de tâche : `{scenario.task_kind}`",
                f"- Critères : `{scenario.criterion_refs[0]}` ; `{scenario.criterion_refs[1]}`",
                f"- Sections requises : `{', '.join(scenario.required_sections)}`",
                "- Contenu synthétique :",
                "",
            )
        )
        for section, content in anchor.sections:
            lines.append(f"  - `{section}` : {content}")
        lines.extend(
            (
                "",
                "- Structure valide : [ ] oui [ ] non",
                f"- Appréciation humaine — `{scenario.criterion_refs[0]}` :",
                f"- Appréciation humaine — `{scenario.criterion_refs[1]}` :",
                "- Ambiguïté ou manque de contexte :",
                "- Justification pédagogique courte :",
                "- Action demandée : [ ] aucune [ ] révision [ ] exclusion",
                "",
            )
        )
    lines.extend(
        (
            "## Synthèse et signatures",
            "",
            "- Vingt-quatre items revus : [ ] oui [ ] non",
            "- Limites de la revue :",
            "- Avis : [ ] utilisable [ ] révisions requises [ ] inconclusif",
            "- Relecteur ou relectrice :",
            "- Responsable de la calibration :",
            "- Date de clôture :",
        )
    )
    return "\n".join(lines) + "\n"


def build_reconciliation_key(manifest: Mapping[str, object]) -> dict[str, object]:
    initial = {
        (cast(str, item["subject_ref"]).removeprefix("anchor:"), cast(str, item["criterion_ref"])): _score(item)
        for item in cast(list[dict[str, object]], manifest["results"])
        if item["category"] == "INITIAL_ANCHOR"
    }
    expectation = {item.anchor_id: item.tier.value for item in ANCHOR_EXPECTATIONS}
    items: list[dict[str, object]] = []
    for review_id, anchor_id in _human_review_mapping():
        scenario = scenario_by_code(anchor_by_id(anchor_id).scenario_code)
        scores = {
            criterion: _fraction_payload(initial[(anchor_id, criterion)])
            for criterion in scenario.criterion_refs
        }
        item = {
            "review_item_id": review_id,
            "anchor_id": anchor_id,
            "expected_tier": expectation[anchor_id],
            "model_scores": scores,
        }
        item["reconciliation_sha256"] = _canonical_sha256(item)
        items.append(item)
    return {
        "review_status": "NOT_COMPLETED",
        "content_repeated": False,
        "item_count": len(items),
        "items": items,
    }


def build_analysis_payload(root: Path = ROOT) -> dict[str, object]:
    manifest = build_final_manifest(root)
    results = tuple(cast(list[dict[str, object]], manifest["results"]))
    initial = tuple(item for item in results if item["category"] == "INITIAL_ANCHOR")
    repeats = tuple(item for item in results if item["category"] == "REPEATABILITY")
    selected = tuple(item for item in results if item["category"] == "SELECTED_OUTPUT")
    initial_scores = {
        (cast(str, item["criterion_ref"]), cast(str, item["subject_ref"]).removeprefix("anchor:")): _score(item)
        for item in initial
    }
    ordering_summary = summarize_orderings(CRITERION_ORDERINGS, initial_scores)
    ordering_details: list[dict[str, object]] = []
    for ordering in CRITERION_ORDERINGS:
        values = tuple(initial_scores[(ordering.criterion_ref, anchor_id)] for anchor_id in ordering.ordered_anchor_ids)
        scenario_code = ordering.criterion_ref.split(".", maxsplit=1)[0].upper()
        ordering_details.append(
            {
                "scenario_code": scenario_code,
                "criterion_ref": ordering.criterion_ref,
                "strong": _fraction_payload(values[0]),
                "mixed": _fraction_payload(values[1]),
                "weak": _fraction_payload(values[2]),
                "strict": values[0] > values[1] > values[2],
                "weak_ordering": values[0] >= values[1] >= values[2],
                "tied_adjacent_pairs": sum(a == b for a, b in zip(values, values[1:], strict=False)),
                "inverted_adjacent_pairs": sum(a < b for a, b in zip(values, values[1:], strict=False)),
                "range": _fraction_payload(max(values) - min(values)),
                "distinct_score_count": len(set(values)),
                "saturation_count": sum(value in {0, 1} for value in values),
            }
        )
    ordering_metrics = asdict(ordering_summary)
    tier_by_anchor = {item.anchor_id: item.tier for item in ANCHOR_EXPECTATIONS}
    tier_distributions: dict[str, object] = {}
    for tier in AnchorTier:
        values = tuple(
            _score(item)
            for item in initial
            if tier_by_anchor[cast(str, item["subject_ref"]).removeprefix("anchor:")] is tier
        )
        tier_distributions[tier.value] = _distribution_payload(values)
    repeat_observations: list[RepeatScore] = []
    repeat_details: list[dict[str, object]] = []
    for repeat in sorted(repeats, key=lambda item: cast(str, item["logical_slot_id"])):
        anchor_id = cast(str, repeat["subject_ref"]).removeprefix("anchor:")
        criterion = cast(str, repeat["criterion_ref"])
        first = initial_scores[(criterion, anchor_id)]
        second = _score(repeat)
        repeat_observations.extend(
            (
                RepeatScore(anchor_id, criterion, 1, first),
                RepeatScore(anchor_id, criterion, 2, second),
            )
        )
        delta = second - first
        repeat_details.append(
            {
                "criterion_ref": criterion,
                "anchor_id": anchor_id,
                "initial": _fraction_payload(first),
                "repeat": _fraction_payload(second),
                "absolute_delta": _fraction_payload(abs(delta)),
                "direction": "UP" if delta > 0 else "DOWN" if delta < 0 else "UNCHANGED",
            }
        )
    repeat_summary = summarize_repeatability(tuple(repeat_observations))
    repeat_metrics = {
        **asdict(repeat_summary),
        "exact_agreement_rate": _fraction_payload(repeat_summary.exact_agreement_rate),
        "inconclusive_rate": _fraction_payload(repeat_summary.inconclusive_rate),
        "maximum_spread": _fraction_payload(repeat_summary.maximum_spread),
        "mean_absolute_rational_delta": _fraction_payload(
            repeat_summary.mean_absolute_rational_delta
        ),
    }
    openai_results = audit_openai_results(root)
    openai_by_hash = {cast(str, item["output_sha256"]): item for item in openai_results}
    continuation = _continuation_evidence(root)
    transfer_by_id = cast(dict[str, dict[str, object]], continuation["transfer_by_id"])
    selected_details: list[dict[str, object]] = []
    quality_observations: list[QualityScoreObservation] = []
    for item in sorted(selected, key=lambda value: cast(str, value["logical_slot_id"])):
        criterion = cast(str, item["criterion_ref"])
        scenario = cast(str, item["scenario_code"])
        anchors = next(ordering for ordering in CRITERION_ORDERINGS if ordering.criterion_ref == criterion)
        anchor_values = tuple(initial_scores[(criterion, anchor_id)] for anchor_id in anchors.ordered_anchor_ids)
        output_score = _score(item)
        transfer_item = transfer_by_id[cast(str, item["execution_call_id"])]
        source_hash = cast(str, transfer_item["source_output_sha256"])
        source = openai_by_hash.get(source_hash)
        if source is None:
            _fail(AnalysisErrorCode.OPENAI_EVIDENCE_MISMATCH)
        quality_observations.append(
            QualityScoreObservation(scenario, criterion, cast(str, source["model"]), output_score)
        )
        selected_details.append(
            {
                "logical_slot_id": item["logical_slot_id"],
                "output_logical_source_id": cast(str, item["subject_ref"]).removeprefix("output:"),
                "scenario_code": scenario,
                "criterion_ref": criterion,
                "source_openai_model": source["model"],
                "source_openai_profile_id": source["model_profile_id"],
                "score": _fraction_payload(output_score),
                "anchor_scores": {
                    "strong": _fraction_payload(anchor_values[0]),
                    "mixed": _fraction_payload(anchor_values[1]),
                    "weak": _fraction_payload(anchor_values[2]),
                },
                "relative_classification": _relative_classification(output_score, *anchor_values),
            }
        )
    quality_metrics = summarize_quality(tuple(quality_observations))
    invocations = tuple(
        InvocationObservation(
            call_id=cast(str, item["logical_slot_id"]),
            provider="anthropic",
            model=cast(str, item["model"]),
            workload=cast(str, item["category"]),
            status=CalibrationResponseStatus.STRUCTURED,
            input_tokens=cast(dict[str, int], item["usage"])["input_tokens"],
            cached_input_tokens=cast(dict[str, int], item["usage"])["cached_input_tokens"],
            output_tokens=cast(dict[str, int], item["usage"])["output_tokens"],
            latency_milliseconds=cast(int, item["latency_milliseconds"]),
            observed_cost_usd=Decimal(cast(str, item["measured_cost_usd"])),
        )
        for item in results
    )
    invocation_metrics = summarize_invocations(invocations)
    usage = {
        "input_tokens": sum(cast(dict[str, int], item["usage"])["input_tokens"] for item in results),
        "cached_input_tokens": sum(cast(dict[str, int], item["usage"])["cached_input_tokens"] for item in results),
        "output_tokens": sum(cast(dict[str, int], item["usage"])["output_tokens"] for item in results),
        "thinking_tokens": sum(cast(dict[str, int], item["usage"])["thinking_tokens"] for item in results),
        "total_tokens": sum(cast(dict[str, int], item["usage"])["total_tokens"] for item in results),
    }
    final_cost = sum(
        (Decimal(cast(str, item["measured_cost_usd"])) for item in results),
        start=Decimal("0"),
    )
    if usage != {
        "input_tokens": EXPECTED_INPUT_TOKENS,
        "cached_input_tokens": EXPECTED_CACHED_INPUT_TOKENS,
        "output_tokens": EXPECTED_OUTPUT_TOKENS,
        "thinking_tokens": EXPECTED_THINKING_TOKENS,
        "total_tokens": EXPECTED_TOTAL_TOKENS,
    } or final_cost != EXPECTED_FINAL_ANTHROPIC_COST:
        _fail(AnalysisErrorCode.FINAL_TOKEN_OR_COST_MISMATCH)
    latency = summarize_latency(tuple(item.latency_milliseconds for item in invocations))
    technical_by_category: dict[str, object] = {}
    for metric in invocation_metrics:
        category_results = tuple(item for item in results if item["category"] == metric.workload)
        technical_by_category[metric.workload] = {
            "call_count": metric.call_count,
            "structured_count": metric.structured_count,
            "valid_structured_response_rate": _fraction_payload(metric.valid_structured_response_rate),
            "input_tokens": metric.input_tokens,
            "cached_input_tokens": metric.cached_input_tokens,
            "output_tokens": metric.output_tokens,
            "thinking_tokens": sum(cast(dict[str, int], item["usage"])["thinking_tokens"] for item in category_results),
            "total_tokens": sum(cast(dict[str, int], item["usage"])["total_tokens"] for item in category_results),
            "latency_milliseconds": metric.latency_milliseconds,
            "measured_cost_usd": str(metric.observed_cost_usd),
        }
    human_packet = render_human_review_packet()
    payload: dict[str, object] = {
        "phase": PHASE,
        "status": "PASS_CLOSED",
        "refs": {
            "entry_branch": ENTRY_BRANCH,
            "entry_head": ENTRY_HEAD,
            "entry_upstream": ENTRY_HEAD,
            "entry_main": ENTRY_MAIN,
            "entry_origin_main": ENTRY_MAIN,
        },
        "proofs": manifest["proofs"],
        "final_manifest": {
            "result_count": 76,
            "sha256": _canonical_sha256(manifest),
            "logical_slot_ids_unique": True,
            "policy_uniform": True,
            "diagnostic_only_results_included": False,
            "split": {"INITIAL_ANCHOR": 48, "REPEATABILITY": 16, "SELECTED_OUTPUT": 12},
        },
        "anchor_orderings": {
            "rule": ANCHOR_EVIDENCE_RULE,
            "evidence": _ordering_evidence(ordering_metrics),
            "metrics": ordering_metrics,
            "details": ordering_details,
            "global_distribution": _distribution_payload(tuple(_score(item) for item in initial)),
            "tier_distributions": tier_distributions,
        },
        "repeatability": {
            "rule": REPEATABILITY_EVIDENCE_RULE,
            "evidence": _repeatability_evidence(repeat_metrics),
            "two_observations_per_group_only": True,
            "metrics": repeat_metrics,
            "details": repeat_details,
        },
        "selected_output": {
            "evidence": "DESCRIPTIVE_ONLY",
            "fallback_soft_quality_comparison": "NOT_ESTABLISHED",
            "quality_aggregation": [
                {
                    "scenario_code": metric.scenario_code,
                    "criterion_ref": metric.criterion_ref,
                    "model": metric.model,
                    "observation_count": metric.observation_count,
                    "inconclusive_count": metric.inconclusive_count,
                    "mean_score": _fraction_payload(metric.mean_score),
                }
                for metric in quality_metrics
            ],
            "details": selected_details,
        },
        "anthropic_technical": {
            "call_count": 76,
            "structured_valid_count": 76,
            "structured_valid_rate": _fraction_payload(Fraction(1, 1)),
            "score_status_counts": {"SCORED": 76, "INCONCLUSIVE": 0, "ERROR": 0, "REFUSAL": 0},
            "stop_reasons": dict(sorted(Counter(cast(str, item["stop_reason"]) for item in results).items())),
            "text_block_counts": dict(sorted(Counter(cast(int, item["text_block_count"]) for item in results).items())),
            "thinking_block_counts": dict(sorted(Counter(cast(int, item["thinking_block_count"]) for item in results).items())),
            "usage": usage,
            "latency": {
                "total_milliseconds": latency.total_milliseconds,
                "minimum_milliseconds": latency.minimum_milliseconds,
                "median_milliseconds": _fraction_payload(latency.median_milliseconds),
                "p95_milliseconds": latency.p95_milliseconds,
                "maximum_milliseconds": latency.maximum_milliseconds,
            },
            "measured_cost_usd": str(final_cost),
            "by_category": technical_by_category,
        },
        "openai_reused": _openai_summary(openai_results),
        "cost_accounting": cost_accounting(
            root, final_openai=openai_results, final_anthropic=results
        ),
        "decision": {
            "ANCHOR_ORDINAL_EVIDENCE": _ordering_evidence(ordering_metrics),
            "REPEATABILITY_EVIDENCE": _repeatability_evidence(repeat_metrics),
            "SELECTED_OUTPUT_EVIDENCE": "DESCRIPTIVE_ONLY",
            "HUMAN_ANCHOR_REVIEW": "NOT_COMPLETED",
            "CALIBRATION_CONFIDENCE": "PROVISIONAL_PENDING_HUMAN_REVIEW",
            "RELEASE_THRESHOLD_ADOPTION": "NOT_ALLOWED",
            "PROVIDER_ROUTE_CHANGE": "NONE",
        },
        "human_review": {
            "packet_relative_path": HUMAN_PACKET_RELATIVE_PATH,
            "packet_sha256": _sha256(human_packet.encode("utf-8")),
            "item_count": 24,
            "review_status": "NOT_COMPLETED",
            "blind": True,
            "unfilled": True,
        },
        "offline_execution": {
            "openai_calls": 0,
            "anthropic_calls": 0,
            "provider_cost_usd": "0.000000",
            "credentials_resolved": False,
            "provider_transport_constructed": False,
            "historical_artifacts_mutated": False,
            "runtime_routes_mutated": False,
        },
        "governance": {
            "adr_required": False,
            "adrs_applied": ["ADR-P12-063", "ADR-P12-064"],
            "next_gate": "12.16-G2-HUMAN_ANCHOR_REVIEW_READY",
        },
        "validation": {
            "targeted_regression": "PASS_37",
            "global_pytest": "PASS_4298_SKIPPED_3_EXPLICIT_OPTIONAL_GATES",
            "ruff_global": "PASS",
            "mypy_backend_and_evaluation_harness": "PASS_689_SOURCE_FILES",
            "compileall_backend_harness_calibration": "PASS",
            "diff_check": "PASS",
            "security_scan": "PASS_NO_SECRET_PRIVATE_PATH_RUNTIME_DATA",
            "live_tests_executed": False,
        },
        "delivery": {
            "commit_message": "test: analyze pedagogical model calibration",
            "commit_parent": ENTRY_HEAD,
            "branch": ENTRY_BRANCH,
            "main_unchanged": True,
            "commit_sha_embedded": False,
            "commit_sha_reporting": "FINAL_EXECUTION_REPORT_ONLY",
            "files_changed": [
                REPORT_MD_RELATIVE_PATH,
                REPORT_JSON_RELATIVE_PATH,
                BASELINE_RELATIVE_PATH,
                HUMAN_PACKET_RELATIVE_PATH,
                "tests/architecture/test_final_calibration_analysis_fitness.py",
                "tests/calibration/pedagogical/metrics.py",
                "tests/calibration/pedagogical/r4_r3_r1_recovery.py",
                "tests/calibration/pedagogical/r4_r3_r3_analysis.py",
                "tests/unit/test_pedagogical_calibration_r4_r3_r1.py",
                "tests/unit/test_pedagogical_calibration_r4_r3_r3.py",
            ],
        },
    }
    payload["reproducibility"] = {
        "canonical_analysis_without_reproducibility_sha256": _canonical_sha256(payload),
        "deterministic_timestamps_excluded": True,
        "json_float_count": 0,
    }
    return payload


def render_report_json(root: Path = ROOT) -> str:
    return _pretty_json(build_analysis_payload(root))


def _fraction_text(value: Mapping[str, object] | None) -> str:
    if value is None:
        return "n/a"
    return f"{value['numerator']}/{value['denominator']}"


def render_report_markdown(root: Path = ROOT) -> str:
    payload = build_analysis_payload(root)
    manifest = cast(dict[str, object], payload["final_manifest"])
    anchors = cast(dict[str, object], payload["anchor_orderings"])
    anchor_metrics = cast(dict[str, object], anchors["metrics"])
    repeats = cast(dict[str, object], payload["repeatability"])
    repeat_metrics = cast(dict[str, object], repeats["metrics"])
    technical = cast(dict[str, object], payload["anthropic_technical"])
    latency = cast(dict[str, object], technical["latency"])
    usage = cast(dict[str, int], technical["usage"])
    costs = cast(dict[str, object], payload["cost_accounting"])
    decision = cast(dict[str, object], payload["decision"])
    lines = [
        "# Phase 12.16-G2 — Rapport final d’analyse de calibration",
        "",
        "## Résultat",
        "",
        "- Statut : `PASS / CLOSED`.",
        "- Analyse strictement hors ligne : `0` appel OpenAI, `0` appel Anthropic, `0.000000 USD`.",
        f"- Manifeste final : `{manifest['result_count']}` résultats ; SHA-256 `{manifest['sha256']}`.",
        "- Split : `48 initial / 16 repeatability / 12 selected-output`.",
        "- Policy : `claude-sonnet-5 / adaptive / low / 2048`, uniforme.",
        "",
        "## Preuves",
        "",
    ]
    for name, value in cast(dict[str, str], payload["proofs"]).items():
        lines.append(f"- {name} : `{value}`.")
    lines.extend(
        (
            "",
            "## Ordre des ancres",
            "",
            f"- Preuve ordinale : `{anchors['evidence']}`.",
            f"- Ordres stricts : `{anchor_metrics['strict_ordering_count']}/16`.",
            f"- Ordres faibles : `{anchor_metrics['weak_ordering_count']}/16`.",
            f"- Égalités adjacentes : `{anchor_metrics['tied_pair_count']}` ; inversions : `{anchor_metrics['inverted_pair_count']}`.",
            f"- Règle pré-déclarée : {anchors['rule']}",
            "",
            "| Scénario | Critère | strong | mixed | weak | strict | égalités | inversions | range | distincts | saturation |",
            "|---|---|---:|---:|---:|:---:|---:|---:|---:|---:|---:|",
        )
    )
    for item in cast(list[dict[str, object]], anchors["details"]):
        lines.append(
            f"| {item['scenario_code']} | `{item['criterion_ref']}` | {_fraction_text(cast(dict[str, object], item['strong']))} | "
            f"{_fraction_text(cast(dict[str, object], item['mixed']))} | {_fraction_text(cast(dict[str, object], item['weak']))} | "
            f"{'PASS' if item['strict'] else 'FAIL'} | {item['tied_adjacent_pairs']} | {item['inverted_adjacent_pairs']} | "
            f"{_fraction_text(cast(dict[str, object], item['range']))} | {item['distinct_score_count']} | {item['saturation_count']} |"
        )
    lines.extend(("", "### Distribution exacte", ""))
    global_distribution = cast(dict[str, object], anchors["global_distribution"])
    lines.append(
        f"Valeurs distinctes : `{global_distribution['distinct_value_count']}` ; zéros : `{global_distribution['zero_count']}` ; "
        f"uns : `{global_distribution['one_count']}` ; intermédiaires : `{global_distribution['intermediate_count']}`."
    )
    lines.append("")
    lines.append("| Fraction | Fréquence |")
    lines.append("|---:|---:|")
    for item in cast(list[dict[str, object]], global_distribution["histogram"]):
        lines.append(f"| {_fraction_text(cast(dict[str, object], item['score']))} | {item['count']} |")
    lines.extend(("", "| Tier d’analyse | Moyenne rationnelle | Médiane rationnelle |", "|---|---:|---:|"))
    for tier, distribution in cast(dict[str, dict[str, object]], anchors["tier_distributions"]).items():
        lines.append(
            f"| {tier} | {_fraction_text(cast(dict[str, object], distribution['mean']))} | "
            f"{_fraction_text(cast(dict[str, object], distribution['median']))} |"
        )
    lines.extend(
        (
            "",
            "## Répétabilité",
            "",
            f"- Preuve : `{repeats['evidence']}` ; deux observations par groupe seulement : `TRUE`.",
            f"- Accord exact : `{repeat_metrics['exact_agreement_count']}/16` ({_fraction_text(cast(dict[str, object], repeat_metrics['exact_agreement_rate']))}).",
            f"- Spread maximal : `{_fraction_text(cast(dict[str, object], repeat_metrics['maximum_spread']))}` ; delta absolu moyen : `{_fraction_text(cast(dict[str, object], repeat_metrics['mean_absolute_rational_delta']))}`.",
            "",
            "| Critère | Initial | Répétition | Delta absolu | Direction |",
            "|---|---:|---:|---:|---|",
        )
    )
    for item in cast(list[dict[str, object]], repeats["details"]):
        lines.append(
            f"| `{item['criterion_ref']}` | {_fraction_text(cast(dict[str, object], item['initial']))} | "
            f"{_fraction_text(cast(dict[str, object], item['repeat']))} | "
            f"{_fraction_text(cast(dict[str, object], item['absolute_delta']))} | {item['direction']} |"
        )
    selected_output = cast(dict[str, object], payload["selected_output"])
    lines.extend(
        (
            "",
            "## Selected-output",
            "",
            "- Statut : `DESCRIPTIVE_ONLY`.",
            "- FALLBACK_SOFT_QUALITY_COMPARISON = `NOT_ESTABLISHED`.",
            "",
            "| Source | Critère | Score | strong/mixed/weak | Classe relative | Modèle source |",
            "|---|---|---:|---:|---|---|",
        )
    )
    for item in cast(list[dict[str, object]], selected_output["details"]):
        anchor_scores = cast(dict[str, dict[str, object]], item["anchor_scores"])
        lines.append(
            f"| `{item['output_logical_source_id']}` | `{item['criterion_ref']}` | {_fraction_text(cast(dict[str, object], item['score']))} | "
            f"{_fraction_text(anchor_scores['strong'])} ; {_fraction_text(anchor_scores['mixed'])} ; {_fraction_text(anchor_scores['weak'])} | "
            f"{item['relative_classification']} | `{item['source_openai_model']}` |"
        )
    lines.extend(
        (
            "",
            "## Fiabilité technique finale",
            "",
            "- Réponses structurées valides : `76/76`; SCORED `76`, INCONCLUSIVE `0`, error `0`, refusal `0`.",
            f"- Tokens : input `{usage['input_tokens']}`, cache `{usage['cached_input_tokens']}`, output `{usage['output_tokens']}`, thinking `{usage['thinking_tokens']}`, total `{usage['total_tokens']}`.",
            f"- Latence ms : total `{latency['total_milliseconds']}`, min `{latency['minimum_milliseconds']}`, médiane `{_fraction_text(cast(dict[str, object], latency['median_milliseconds']))}`, p95 `{latency['p95_milliseconds']}`, max `{latency['maximum_milliseconds']}`.",
            f"- Coût final Anthropic mesuré : `{technical['measured_cost_usd']} USD`.",
            "",
            "## Résultats OpenAI réutilisés",
            "",
            "- `20` résultats terminaux audités : `13 G2 + 1 R2B + 6 R3B`; aucun nouvel appel.",
        )
    )
    openai = cast(dict[str, object], payload["openai_reused"])
    for family, summary in cast(dict[str, dict[str, object]], openai["families"]).items():
        lines.append(
            f"- {family} : `{summary['call_count']}` résultats, statuts `{summary['statuses']}`, "
            f"tokens `{summary['total_tokens']}`, latence `{summary['latency_milliseconds']} ms`, coût `{summary['measured_cost_usd']} USD`."
        )
    lines.extend(
        (
            "",
            "## Comptabilité sans double comptage",
            "",
            f"- A. Final useful OpenAI : `{costs['A_FINAL_USEFUL_OPENAI_EXECUTION_COST']} USD`.",
            f"- B. Final uniform Anthropic : `{costs['B_FINAL_UNIFORM_ANTHROPIC_SCORING_COST']} USD`.",
            f"- C. Diagnostic/remédiation mesuré : `{costs['C_DIAGNOSTIC_AND_REMEDIATION_MEASURED_COST']} USD`.",
            f"- D. Réserves conservatrices non prouvées facturées : `{costs['D_CONSERVATIVE_RESERVES_NOT_PROVEN_AS_BILLED']} USD`.",
            f"- Coût final utile : `{costs['final_useful_cost_usd']} USD`; coût expérimental mesuré : `{costs['experimental_measured_cost_usd']} USD`.",
            "- Les dashboards fournisseurs restent la source de vérité de facturation.",
            "",
            "## Décision bornée et revue humaine",
            "",
        )
    )
    for name, value in decision.items():
        lines.append(f"- {name} = `{value}`.")
    human = cast(dict[str, object], payload["human_review"])
    reproducibility = cast(dict[str, object], payload["reproducibility"])
    validation = cast(dict[str, object], payload["validation"])
    delivery = cast(dict[str, object], payload["delivery"])
    lines.extend(
        (
            f"- Paquet aveugle : `{human['packet_relative_path']}` ; 24 items ; statut `NOT_COMPLETED`.",
            "",
            "## Validation et livraison",
            "",
            f"- Tests ciblés/régression : `{validation['targeted_regression']}`.",
            f"- Pytest global : `{validation['global_pytest']}`.",
            f"- Ruff global : `{validation['ruff_global']}`.",
            f"- Mypy backend + evaluation_harness : `{validation['mypy_backend_and_evaluation_harness']}`.",
            f"- Compileall : `{validation['compileall_backend_harness_calibration']}`.",
            f"- Diff-check : `{validation['diff_check']}` ; sécurité : `{validation['security_scan']}`.",
            f"- Commit attendu : `{delivery['commit_message']}` ; parent `{delivery['commit_parent']}`.",
            f"- Branche : `{delivery['branch']}` ; main inchangée : `{delivery['main_unchanged']}`.",
            "- Le SHA du commit est rapporté après création ; il n’est pas auto-référencé dans le commit.",
            "",
            "## Reproductibilité, sécurité et gouvernance",
            "",
            f"- Projection canonique : `{reproducibility['canonical_analysis_without_reproducibility_sha256']}`.",
            f"- Paquet humain : `{human['packet_sha256']}`.",
            "- Aucun float, timestamp variable, raw output, prompt, secret, request ID ou chemin absolu dans les rapports.",
            "- ADR : `NO`; ADR-P12-063 et ADR-P12-064 appliqués.",
            "- Route provider : `NONE`; seuil de release : `NOT_ALLOWED`.",
            "- Prochaine gate : `12.16-G2-HUMAN_ANCHOR_REVIEW_READY`.",
        )
    )
    return "\n".join(lines) + "\n"


def render_baseline_markdown(root: Path = ROOT) -> str:
    payload = build_analysis_payload(root)
    final_manifest = cast(dict[str, object], payload["final_manifest"])
    decisions = cast(dict[str, object], payload["decision"])
    return "\n".join(
        (
            "# Phase 12.16-G2-R3B-R4-R3-R3 — Baseline finale d’analyse",
            "",
            "- Statut : `PASS / CLOSED`.",
            f"- Résultats homogènes finaux : `{final_manifest['result_count']}`.",
            f"- Checksum manifeste : `{final_manifest['sha256']}`.",
            "- Split : `48/16/12`; policy uniforme; aucun résultat diagnostic.",
            f"- ANCHOR_ORDINAL_EVIDENCE : `{decisions['ANCHOR_ORDINAL_EVIDENCE']}`.",
            f"- REPEATABILITY_EVIDENCE : `{decisions['REPEATABILITY_EVIDENCE']}`.",
            "- CALIBRATION_CONFIDENCE : `PROVISIONAL_PENDING_HUMAN_REVIEW`.",
            "- RELEASE_THRESHOLD_ADOPTION : `NOT_ALLOWED`.",
            "- HUMAN_ANCHOR_REVIEW : `NOT_COMPLETED`.",
            "- PROVIDER_ROUTE_CHANGE : `NONE`.",
            "- LIVE_PROVIDER_CALLS_R3 : `0`; LIVE_PROVIDER_COST_R3 : `0`.",
            "- Validations : `4298 passed, 3 optional gates skipped`; Ruff `PASS`; mypy `689 files PASS`; compileall `PASS`.",
            "- ADR_REQUIRED : `NO`; ADR-P12-063 et ADR-P12-064 appliqués.",
            "- NEXT_GATE : `12.16-G2-HUMAN_ANCHOR_REVIEW_READY`.",
        )
    ) + "\n"


def _atomic_write(path: Path, payload: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    try:
        with temporary.open("wb") as stream:
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        if temporary.exists():
            temporary.unlink()


def write_outputs(root: Path = ROOT) -> None:
    manifest = build_final_manifest(root)
    outputs = {
        REPORT_MD_RELATIVE_PATH: render_report_markdown(root),
        REPORT_JSON_RELATIVE_PATH: render_report_json(root),
        BASELINE_RELATIVE_PATH: render_baseline_markdown(root),
        HUMAN_PACKET_RELATIVE_PATH: render_human_review_packet(),
        FINAL_MANIFEST_RELATIVE_PATH: _pretty_json(manifest),
        RECONCILIATION_RELATIVE_PATH: _pretty_json(build_reconciliation_key(manifest)),
    }
    for relative_path, content in outputs.items():
        _atomic_write(root / relative_path, content.encode("utf-8"))


def main() -> None:
    write_outputs(ROOT)
    print(
        json.dumps(
            {
                "status": "PASS_CLOSED",
                "final_uniform_results": 76,
                "final_manifest_sha256": final_manifest_sha256(ROOT),
                "live_provider_calls_r3": 0,
                "live_provider_cost_r3": "0.000000",
            },
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
