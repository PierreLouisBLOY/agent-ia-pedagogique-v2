"""Closed technical gate for the exact owner-approved pilot, outside normal product composition.

No SQL, production repository, secret lookup, provider client, or COUNT operation.
The caller must durably consume the campaign namespace before credential acquisition.
"""
from __future__ import annotations

import hashlib
import json
import subprocess
import threading
from collections.abc import Callable
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any, cast

ROOT = Path(__file__).resolve().parent
ARTIFACT = ROOT / "MEGA_LOT_POST_20D6B49_20261004"
BASELINE = "d7bae43c4791f706df859043efbc230076ee0884"
CAMPAIGN = "79c46f0f9e538c4d864d0a880e0f1bef780304eaf8fec6247c1c99449eaa0732"
AMENDMENT_SHA = "c028361edaaf3d8fd6381c283ba833ad99380964f8306af0559451f9b345a7a2"
MODEL = "gpt-5.6-terra"
ENDPOINT = "https://api.openai.com/v1/responses"
PER_CALL = Decimal("0.140000")
GLOBAL = Decimal("1.960000")


def canonical(value: object) -> bytes:
    return json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":"), allow_nan=False).encode()


def sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def unique(pairs: list[tuple[str, object]]) -> dict[str, Any]:
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("DUPLICATE_KEY_REFUSED")
        result[key] = value
    return result


def local_count(body: dict[str, Any]) -> dict[str, Any]:
    python = ROOT / "MEGA_TOKENIZER_ACQUISITION_20261004/venv/Scripts/python.exe"
    result = subprocess.run([str(python), "-B", str(ROOT / "mega_tokenizer_count.py")],
        input=canonical({"model": body["model"], "request": body}), capture_output=True, timeout=30, check=False)
    if result.returncode:
        raise ValueError("DETERMINISTIC_TOKENIZER_REQUIRED")
    return cast(dict[str, Any], json.loads(result.stdout))


def preflight(raw: bytes, tariff: dict[str, Any], *, expected_sha: str | None, count: Callable[[dict[str, Any]], dict[str, Any]] | None = None) -> dict[str, Any]:
    if not isinstance(raw, bytes) or not 0 < len(raw) < 250000:
        raise ValueError("REQUEST_BYTES_REFUSED")
    if expected_sha is not None and sha(raw) != expected_sha:
        raise ValueError("EXACT_REQUEST_CHANGED")
    body = json.loads(raw, object_pairs_hook=unique)
    expected_fields = {"background", "model", "instructions", "input", "max_output_tokens", "service_tier",
        "store", "stream", "reasoning", "tools", "tool_choice", "text"}
    if (type(body) is not dict or set(body) != expected_fields or canonical(body) != raw
        or body["model"] != MODEL or body["reasoning"] != {"effort": "low"}
        or body["service_tier"] != "default" or body["tools"] != [] or body["tool_choice"] != "none"
        or any(body[k] is not False for k in ("store", "stream", "background"))
        or type(body["max_output_tokens"]) is not int or body["max_output_tokens"] != 4096
        or type(body["input"]) is not str or type(body["instructions"]) is not str):
        raise ValueError("CAMPAIGN_REQUEST_FLAGS_REFUSED")
    if tariff["model"] != MODEL or (tariff["input_usd_per_million"], tariff["output_usd_per_million"],
        tariff["cache_write_input_factor"], tariff["conservative_input_usd_per_million"]) != ("2.00", "12.00", "1.25", "2.50"):
        raise ValueError("OFFICIAL_TARIFF_CHANGED")
    counted = (count or local_count)(body)
    if (counted["model"] != MODEL or counted["recognition"] != "OFFICIAL_UNMODIFIED_PACKAGE_RESOLVER"
        or counted["encoding"] != "o200k_base" or counted["network_forbidden_during_count"] is not True
        or type(counted["local_text_tokens"]) is not int or counted["local_text_tokens"] < 1):
        raise ValueError("DETERMINISTIC_TOKENIZER_REQUIRED")
    upper = counted["local_text_tokens"] + 10000
    if upper > 40000:
        raise ValueError("INPUT_PLUS_RESERVE_EXCEEDED")
    cost = (Decimal(upper) * Decimal("2.50") + Decimal(4096) * Decimal("12.00")) / Decimal(1000000)
    if cost > PER_CALL:
        raise ValueError("FINANCIAL_BOUND_EXCEEDED")
    return {"schema": "MEGA-NO-COUNT-PREFLIGHT-1.0", "baseline": BASELINE, "campaign": CAMPAIGN,
        "request_sha256": sha(raw), "request_bytes": len(raw), "tokenizer_evidence": counted,
        "structural_reserve_tokens": 10000, "input_upper_tokens": upper, "max_output_tokens": 4096,
        "tariff": tariff, "max_cost_usd": str(cost), "ceiling_usd": str(PER_CALL),
        "count_calls": 0, "status": "PASS_EXECUTED", "retry": 0, "fallback": "NONE"}


class Budget:
    """One campaign, serial, consumed before effect, pessimistic reservations never released."""
    def __init__(self) -> None:
        self.reserved = Decimal(0)
        self.consumed: set[tuple[str, str]] = set()
        self.generated: set[str] = set()
        self.busy = False
        self.lock = threading.Lock()

    def reserve(self, scenario: str, operation: str, proof: dict[str, Any]) -> None:
        with self.lock:
            if scenario not in {f"M{i:02}" for i in range(1, 8)} or operation not in {"CREATE", "REVIEW"}:
                raise ValueError("UNAPPROVED_OPERATION")
            if self.busy:
                raise ValueError("PARALLELISM_REFUSED")
            if (scenario, operation) in self.consumed:
                raise ValueError("REPLAY_REFUSED")
            if operation == "REVIEW" and scenario not in self.generated:
                raise ValueError("REVIEW_WITHOUT_EXACT_GENERATION")
            cost = Decimal(proof["max_cost_usd"])
            if not cost.is_finite() or cost <= 0 or cost > PER_CALL or self.reserved + cost > GLOBAL:
                raise ValueError("CAMPAIGN_BUDGET_EXCEEDED")
            self.reserved += cost
            self.consumed.add((scenario, operation))
            self.busy = True

    def finish(self, scenario: str, operation: str, *, confirmed: bool) -> None:
        with self.lock:
            if operation == "CREATE" and confirmed:
                self.generated.add(scenario)
            self.busy = False


def stamp() -> str:
    return datetime.now(UTC).isoformat()


if __name__ == "__main__":
    tariff = json.loads((ROOT / "MEGA_TOKENIZER_ACQUISITION_20261004/03_CURRENT_OFFICIAL_TARIFF.json").read_text())
    proposal = json.loads((ARTIFACT / "A6_OWNER_LIVE_GATE.json").read_text())
    proofs = []
    for scope in proposal["scenarios"]:
        raw = (ARTIFACT / "live-payloads" / (scope["scenario_id"] + "_GENERATE.json")).read_bytes()
        proofs.append({"scenario_id": scope["scenario_id"], **preflight(raw, tariff, expected_sha=scope["generation_sha256"])})
    out = ARTIFACT / "B_NO_COUNT_PREFLIGHT_20261004"
    out.mkdir(exist_ok=True)
    (out / "03_CREATE_PREFLIGHTS.json").write_text(json.dumps(proofs, indent=2) + "\n", "utf-8")
    print(json.dumps([{k: p[k] for k in ("scenario_id", "request_sha256", "input_upper_tokens", "max_cost_usd", "status")} for p in proofs], indent=2))
