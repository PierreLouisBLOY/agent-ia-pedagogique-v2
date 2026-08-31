"""Hash-only audit of reusable G2 OpenAI outputs."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path

from tests.calibration.pedagogical.legacy_call_plan import (
    PEDAGOGICAL_CALIBRATION_CALL_MATRIX,
    PEDAGOGICAL_CALIBRATION_PLAN_VERSION,
    RAW_OUTPUT_DIRECTORY,
    CalibrationProvider,
    CalibrationWorkload,
)


@dataclass(frozen=True, slots=True)
class PriorOpenAISuccessAudit:
    success_count: int
    raw_hash_valid_count: int
    schema_parsable_count: int
    linked_call_count: int
    within_retention_count: int
    reusable: bool


def audit_prior_openai_successes(
    root: Path,
    *,
    now: datetime | None = None,
    retention_days: int = 7,
) -> PriorOpenAISuccessAudit:
    """Inspect only hashes and schema shape; never return provider raw content."""

    if retention_days < 1:
        raise ValueError("retention_days must be positive")
    reference_time = now or datetime.now(UTC)
    if reference_time.tzinfo is None:
        raise ValueError("now must be timezone-aware")
    ledger_path = root / "artifacts/calibration/12.16-g2/ledger.json"
    try:
        ledger = json.loads(ledger_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError):
        return PriorOpenAISuccessAudit(0, 0, 0, 0, 0, False)
    if (
        type(ledger) is not dict
        or ledger.get("plan_version") != PEDAGOGICAL_CALIBRATION_PLAN_VERSION
        or type(ledger.get("calls")) is not list
    ):
        return PriorOpenAISuccessAudit(0, 0, 0, 0, 0, False)

    planned = {call.call_id: call for call in PEDAGOGICAL_CALIBRATION_CALL_MATRIX}
    completed = [
        record
        for record in ledger["calls"]
        if type(record) is dict
        and record.get("provider") == CalibrationProvider.OPENAI.value
        and record.get("status") == "COMPLETED"
    ]
    raw_root = (root / RAW_OUTPUT_DIRECTORY).resolve()
    hash_valid = 0
    schema_parsable = 0
    linked = 0
    retained = 0
    for record in completed:
        call_id = record.get("call_id")
        call = planned.get(call_id) if type(call_id) is str else None
        if call is not None and call.workload is not CalibrationWorkload.REVIEW:
            linked += 1

        relative_path = record.get("raw_output_path")
        expected_digest = record.get("raw_output_sha256")
        if type(relative_path) is not str or type(expected_digest) is not str:
            continue
        raw_path = (root / relative_path).resolve()
        if raw_root not in raw_path.parents:
            continue
        try:
            payload = raw_path.read_bytes()
        except OSError:
            continue
        if hashlib.sha256(payload).hexdigest() != expected_digest:
            continue
        hash_valid += 1
        if _generation_payload_is_parsable(payload):
            schema_parsable += 1

        completed_at = record.get("completed_at")
        if type(completed_at) is str:
            try:
                timestamp = datetime.fromisoformat(completed_at)
            except ValueError:
                continue
            if timestamp.tzinfo is not None:
                age = reference_time - timestamp
                if timedelta(0) <= age <= timedelta(days=retention_days):
                    retained += 1

    count = len(completed)
    reusable = count > 0 and all(
        item == count for item in (hash_valid, schema_parsable, linked, retained)
    )
    return PriorOpenAISuccessAudit(
        success_count=count,
        raw_hash_valid_count=hash_valid,
        schema_parsable_count=schema_parsable,
        linked_call_count=linked,
        within_retention_count=retained,
        reusable=reusable,
    )


def _generation_payload_is_parsable(payload: bytes) -> bool:
    try:
        value = json.loads(payload)
    except (UnicodeError, json.JSONDecodeError):
        return False
    if type(value) is not dict or set(value) != {
        "outcome",
        "sections",
        "warnings",
        "uncertainties",
    }:
        return False
    return (
        value["outcome"] in {"OUTPUT", "INSUFFICIENT_EVIDENCE"}
        and type(value["sections"]) is list
        and type(value["warnings"]) is list
        and type(value["uncertainties"]) is list
    )
