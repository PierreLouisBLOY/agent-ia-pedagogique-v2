"""One voluntary pilot confirmation; temporal authority belongs to an injected port.

This Application service never reads files, reserves budget, or reaches a provider.
The finalizer must serialize its durable pending receipt and fresh checks under
the original LOCK before it can expose the normal effect gate.
"""
from __future__ import annotations

import hashlib
import json
import threading
from collections.abc import Callable, Mapping, Sequence
from datetime import UTC, datetime, timedelta
from typing import cast

from backend.modules.pedagogical_design.contracts.dto.assessment_bundle import object_data

_BASE = {"command_id", "preparation_ref", "preparation_sha256"}
_ACCEPT = _BASE | {"preview_sha256", "transfer_accepted", "cost_bound_accepted",
    "double_execution_cost_risk_accepted"}
_PREVIEW = {"schema", "recipe_sha256", "preparation_ref", "preparation_sha256",
    "context_sha256", "reference_set_sha256", "request_sha256", "request_bytes",
    "request_body_utf8", "provider", "model", "endpoint", "cost_bound_usd",
    "source_receipts", "request_parameters", "financial_evidence",
    "issued_at_utc", "expires_at_utc"}
_PARAMETERS = {"model", "max_output_tokens", "reasoning", "service_tier",
    "store", "stream", "background", "tools", "tool_choice"}
_FINANCIAL = {"tariff_sha256", "tokenizer_manifest_sha256",
    "admission_sha256", "input_upper_tokens", "max_output_tokens",
    "input_usd_per_million", "input_multiplier", "output_usd_per_million",
    "cost_bound_usd", "admission_status"}


def _canonical(value: object) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"),
        allow_nan=False).encode("utf-8")


def _sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _utc(value: object) -> datetime:
    if not isinstance(value, str):
        raise ValueError("P1_PILOT_UTC_REQUIRED")
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError:
        raise ValueError("P1_PILOT_UTC_REQUIRED") from None
    if parsed.tzinfo is None or parsed.utcoffset() != timedelta(0):
        raise ValueError("P1_PILOT_UTC_REQUIRED")
    return parsed


class P0PilotOnDemandConsentService:
    """Closed Application command; opening an overview never starts an authority."""

    def __init__(self, *,
                 prepared_reader: Callable[[str, str], Mapping[str, object]],
                 admission_reader: Callable[[Mapping[str, object]], Sequence[Mapping[str, object]]],
                 stable_preview: Callable[[Mapping[str, object], Sequence[Mapping[str, object]]],
                                          Mapping[str, object]],
                 finalize: Callable[[Mapping[str, object], Sequence[Mapping[str, object]],
                                     Mapping[str, object], Mapping[str, object], datetime],
                                    dict[str, object]],
                 clock: Callable[[], datetime] = lambda: datetime.now(UTC)) -> None:
        self._prepared = prepared_reader
        self._admission = admission_reader
        self._stable = stable_preview
        self._finalize = finalize
        self._clock = clock
        self._mutex = threading.RLock()
        self._pending: tuple[str, dict[str, object]] | None = None
        self._used: set[str] = set()

    def execute(self, operation: str, payload: Mapping[str, object]) -> dict[str, object]:
        # One in-process command at a time. The durable pending receipt under
        # the original LOCK supplies the separate cross-process exclusion.
        with self._mutex:
            return self._execute(operation, payload)

    def _execute(self, operation: str, payload: Mapping[str, object]) -> dict[str, object]:
        if operation not in {"consent_preview", "consent_generate"}:
            raise ValueError("P1_PILOT_CONSENT_OPERATION_REJECTED")
        data = object_data(payload, _BASE if operation == "consent_preview" else _ACCEPT)
        command = data["command_id"]
        ref = data["preparation_ref"]
        pin = data["preparation_sha256"]
        if (type(command) is not str or len(command) != 32
            or any(char not in "0123456789abcdef" for char in command)
            or type(ref) is not str or not ref.startswith("prep:") or len(ref) != 37
            or any(char not in "0123456789abcdef" for char in ref[5:])
            or type(pin) is not str or len(pin) != 64
            or any(char not in "0123456789abcdef" for char in pin)):
            raise ValueError("P1_PILOT_CONSENT_IDENTITY_REJECTED")
        request = self._prepared(ref, pin)
        sources = self._admission(request)
        now = self._clock()
        if now.tzinfo is None or now.utcoffset() != timedelta(0):
            raise ValueError("P1_PILOT_UTC_CLOCK_REQUIRED")
        if operation == "consent_preview":
            if command in self._used:
                raise ValueError("P1_PILOT_COMMAND_ALREADY_USED")
            preview = dict(self._stable(request, sources))
            preview.update(issued_at_utc=now.isoformat(),
                expires_at_utc=(now + timedelta(minutes=15)).isoformat(),
                preparation_ref=ref, preparation_sha256=pin)
            if set(preview) != _PREVIEW or preview["schema"] != "P1-PILOT-STABLE-PREVIEW-1.0":
                raise ValueError("P1_PILOT_STABLE_PREVIEW_REJECTED")
            raw = preview["request_body_utf8"]
            body = json.loads(raw) if isinstance(raw, str) else None
            parameters = preview["request_parameters"]
            evidence = preview["financial_evidence"]
            if (type(raw) is not str or len(raw.encode("utf-8")) != preview["request_bytes"]
                or _sha(raw.encode("utf-8")) != preview["request_sha256"]
                or not isinstance(body, dict)
                or not isinstance(parameters, dict) or set(parameters) != _PARAMETERS
                or any(body.get(key) != parameters[key] for key in _PARAMETERS)
                or parameters != {"model": "gpt-5.6-terra", "max_output_tokens": 4096,
                    "reasoning": {"effort": "low"}, "service_tier": "default",
                    "store": False, "stream": False, "background": False,
                    "tools": [], "tool_choice": "none"}
                or not isinstance(evidence, dict) or set(evidence) != _FINANCIAL
                or any(type(evidence[key]) is not str or len(evidence[key]) != 64
                    or any(char not in "0123456789abcdef" for char in evidence[key])
                    for key in ("tariff_sha256", "tokenizer_manifest_sha256",
                                "admission_sha256"))
                or evidence["input_upper_tokens"] != 29857
                or evidence["max_output_tokens"] != 4096
                or evidence["input_usd_per_million"] != "2.00"
                or evidence["input_multiplier"] != "1.25"
                or evidence["output_usd_per_million"] != "12.00"
                or evidence["cost_bound_usd"] != preview["cost_bound_usd"]
                or evidence["admission_status"] != "OWNER_ADMITTED_EXACT_PILOT"
                or preview["provider"] != "OPENAI" or preview["model"] != "gpt-5.6-terra"
                or preview["endpoint"] != "https://api.openai.com/v1/responses"
                or preview["cost_bound_usd"] != "0.1237945"
                or not isinstance(preview["source_receipts"], list)
                or _canonical(preview["source_receipts"]) != _canonical(sources)):
                raise ValueError("P1_PILOT_STABLE_PREVIEW_REJECTED")
            digest = _sha(_canonical(preview))
            self._pending = (digest, preview)
            return {"state": "LOCAL_OPERATOR_CONSENT_REQUIRED", "preview": preview,
                "preview_sha256": digest, "provider_attempts": 0,
                "review_state": "NOT_RUN", "source_status": "RESERVE",
                "consent_actor": "LOCAL_OPERATOR_DELEGATED",
                "transfer_destination": {"provider": "OPENAI", "model": "gpt-5.6-terra",
                    "endpoint": "https://api.openai.com/v1/responses",
                    "recipe_sha256": preview["recipe_sha256"]}}
        if (command in self._used or self._pending is None
            or self._pending[0] != data["preview_sha256"]
            or any(data[key] is not True for key in (
                "transfer_accepted", "cost_bound_accepted",
                "double_execution_cost_risk_accepted"))):
            raise ValueError("P1_PILOT_EXACT_CONSENT_REQUIRED")
        preview = self._pending[1]
        if (preview["preparation_ref"] != ref or preview["preparation_sha256"] != pin
            or not _utc(cast(str, preview["issued_at_utc"])) <= now
            < _utc(cast(str, preview["expires_at_utc"]))
            or _canonical(dict(self._stable(request, sources))) != _canonical({
                key: value for key, value in preview.items()
                if key not in {"issued_at_utc", "expires_at_utc",
                               "preparation_ref", "preparation_sha256"}})):
            raise ValueError("P1_PILOT_STABLE_PREVIEW_CHANGED")
        # In-process replay is closed before any side effect. The injected
        # finalizer also enforces cross-process pending and child uniqueness.
        self._pending = None
        self._used.add(command)
        return self._finalize(request, sources, preview, data, now)
