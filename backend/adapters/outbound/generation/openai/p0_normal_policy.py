"""Pure normal P0 grant/preflight checks; no I/O, secret or live authority."""
from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Mapping
from datetime import datetime, timedelta
from decimal import Decimal, InvalidOperation
from typing import cast

MODEL = "gpt-5.6-terra"
ENDPOINT = "https://api.openai.com/v1/responses"
GRANT_FIELDS = {
    "schema", "operation", "owner_decision_sha256", "baseline_commit", "source_tree_sha256",
    "package_sha256", "runtime_sha256", "preparation_sha256", "context_sha256",
    "reference_set_sha256", "request_sha256", "request_bytes", "profile_sha256",
    "output_schema_sha256", "tokenizer_manifest_sha256", "tariff_sha256",
    "receipt_root_sha256", "namespace_sha256", "issued_at_utc", "expires_at_utc",
    "provider", "model", "endpoint", "reasoning", "tier", "max_output_tokens", "max_calls",
    "count_calls", "review_calls", "modify_calls", "retry", "fallback", "parallelism",
    "ceiling_usd", "live_authorized", "transfer_authorized",
}
HASH_FIELDS = {key for key in GRANT_FIELDS if key.endswith("_sha256")}
BODY_FIELDS = {"background", "model", "instructions", "input", "max_output_tokens", "service_tier",
               "store", "stream", "reasoning", "tools", "tool_choice", "text"}
TARIFF_FIELDS = {"schema", "provider", "model", "tier", "input_usd_per_million",
                 "output_usd_per_million", "input_multiplier", "evidence_sha256",
                 "owner_admission_sha256", "retrieved_at_utc"}
TOKENIZER_FIELDS = {"schema", "model", "recognition", "encoding", "manifest_sha256",
                   "request_sha256", "model_mapping_sha256", "encoding_sha256", "all_string_values_and_keys_tokens",
                   "serialized_json_tokens", "network_forbidden_during_count", "provider_calls"}


def canonical(value: object) -> bytes:
    def plain(item: object) -> object:
        if isinstance(item, Mapping):
            return {key: plain(val) for key, val in item.items()}
        if isinstance(item, (list, tuple)):
            return [plain(val) for val in item]
        return item
    return json.dumps(plain(value), ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()


def sha(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def closed(value: Mapping[str, object], fields: set[str], code: str) -> None:
    if not isinstance(value, Mapping) or set(value) != fields:
        raise ValueError(code)


def digest(value: object) -> bool:
    return isinstance(value, str) and re.fullmatch(r"[0-9a-f]{64}", value) is not None


def utc(value: object) -> datetime:
    if not isinstance(value, str):
        raise ValueError("UTC_REQUIRED")
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError:
        raise ValueError("UTC_REQUIRED") from None
    if parsed.tzinfo is None or parsed.utcoffset() != timedelta(0):
        raise ValueError("UTC_REQUIRED")
    return parsed


def money(value: object) -> Decimal:
    if not isinstance(value, str):
        raise ValueError("DECIMAL_STRING_REQUIRED")
    try:
        number = Decimal(value)
    except InvalidOperation:
        raise ValueError("DECIMAL_STRING_REQUIRED") from None
    if not number.is_finite() or number <= 0:
        raise ValueError("POSITIVE_FINITE_DECIMAL_REQUIRED")
    return number


def validate_grant(grant: Mapping[str, object], *, identities: Mapping[str, object], now: datetime) -> Decimal:
    closed(grant, GRANT_FIELDS, "GRANT_FIELDS")
    fixed = {"schema": "P0-NORMAL-CREATE-GRANT-1.0", "operation": "CREATE", "provider": "OPENAI",
             "model": MODEL, "endpoint": ENDPOINT, "reasoning": "low", "tier": "default",
             "fallback": "NONE", "live_authorized": True, "transfer_authorized": True}
    if any(grant[key] != value or type(grant[key]) is not type(value) for key, value in fixed.items()):
        raise ValueError("GRANT_POLICY")
    integer = {"max_output_tokens": 4096, "max_calls": 1, "count_calls": 0,
               "review_calls": 0, "modify_calls": 0, "retry": 0, "parallelism": 1}
    if any(type(grant[key]) is not int or grant[key] != value for key, value in integer.items()):
        raise ValueError("GRANT_OPERATIONS")
    if (any(not digest(grant[key]) for key in HASH_FIELDS)
            or not isinstance(grant["baseline_commit"], str)
            or re.fullmatch(r"[0-9a-f]{40}", grant["baseline_commit"]) is None
            or type(grant["request_bytes"]) is not int or not 0 < grant["request_bytes"] < 250000):
        raise ValueError("GRANT_IDENTITIES")
    required = HASH_FIELDS | {"baseline_commit", "request_bytes"}
    if set(identities) != required or any(grant[key] != identities[key] for key in required):
        raise ValueError("GRANT_BINDING")
    issued, expiry = utc(grant["issued_at_utc"]), utc(grant["expires_at_utc"])
    if now.tzinfo is None or not issued <= now < expiry or not timedelta(0) < expiry - issued <= timedelta(minutes=120):
        raise ValueError("GRANT_TIME")
    ceiling = money(grant["ceiling_usd"])
    if ceiling > Decimal("0.140000"):
        raise ValueError("GRANT_CEILING")
    return ceiling


def preflight(raw: bytes, grant: Mapping[str, object], tariff: Mapping[str, object], tokenizer: Mapping[str, object], *, now: datetime) -> dict[str, object]:
    def unique(pairs: list[tuple[str, object]]) -> dict[str, object]:
        if len(dict(pairs)) != len(pairs):
            raise ValueError("BODY_DUPLICATE_KEY")
        return dict(pairs)

    if (type(raw) is not bytes or len(raw) != grant["request_bytes"]
            or sha(raw) != grant["request_sha256"]):
        raise ValueError("BODY_BINDING")
    body = json.loads(raw, object_pairs_hook=unique, parse_constant=lambda _: (_ for _ in ()).throw(ValueError("BODY_NONFINITE")))
    closed(body, BODY_FIELDS, "BODY_FIELDS")
    if canonical(body) != raw:
        raise ValueError("BODY_CANONICAL")
    if (body["model"] != MODEL or body["reasoning"] != {"effort": "low"}
            or body["service_tier"] != "default" or body["tools"] != [] or body["tool_choice"] != "none"
            or any(body[key] is not False for key in ("background", "store", "stream"))
            or type(body["max_output_tokens"]) is not int or body["max_output_tokens"] != 4096
            or not isinstance(body["input"], str) or not isinstance(body["instructions"], str)):
        raise ValueError("BODY_POLICY")
    text = body["text"]
    if (not isinstance(text, dict) or set(text) != {"format"} or not isinstance(text["format"], dict)
            or set(text["format"]) != {"name", "schema", "strict", "type"}
            or text["format"]["name"] != "p0_pedagogical_content" or text["format"]["strict"] is not True
            or text["format"]["type"] != "json_schema"
            or sha(canonical(text["format"]["schema"])) != grant["output_schema_sha256"]):
        raise ValueError("BODY_SCHEMA")
    closed(tariff, TARIFF_FIELDS, "TARIFF_FIELDS")
    if (tariff["schema"] != "P0-NORMAL-TARIFF-1.0" or tariff["model"] != MODEL
            or tariff["provider"] != "OPENAI" or tariff["tier"] != "default"
            or not digest(tariff["evidence_sha256"]) or not digest(tariff["owner_admission_sha256"])
            or sha(canonical(tariff)) != grant["tariff_sha256"]):
        raise ValueError("TARIFF_BINDING")
    # The explicit owner admission must cover this new grant window. No reuse of
    # a historic tariff as an implicit current proof or invented freshness SLA.
    if not utc(tariff["retrieved_at_utc"]) <= utc(grant["issued_at_utc"]) <= now < utc(grant["expires_at_utc"]):
        raise ValueError("TARIFF_ADMITTED_PERIOD")
    multiplier = money(tariff["input_multiplier"])
    if multiplier < 1:
        raise ValueError("TARIFF_DISCOUNT_REFUSED")
    closed(tokenizer, TOKENIZER_FIELDS, "TOKENIZER_FIELDS")
    if (tokenizer["schema"] != "P0-NORMAL-TOKENIZER-PROOF-1.0" or tokenizer["model"] != MODEL
            or tokenizer["recognition"] != "OFFICIAL_UNMODIFIED_PACKAGE_RESOLVER"
            or tokenizer["encoding"] != "o200k_base" or tokenizer["network_forbidden_during_count"] is not True
            or tokenizer["request_sha256"] != grant["request_sha256"]
            or type(tokenizer["provider_calls"]) is not int or tokenizer["provider_calls"] != 0
            or any(not digest(tokenizer[key]) for key in ("manifest_sha256", "model_mapping_sha256", "encoding_sha256"))
            or tokenizer["manifest_sha256"] != grant["tokenizer_manifest_sha256"]
            or any(type(tokenizer[key]) is not int or cast(int, tokenizer[key]) < 1
                   for key in ("all_string_values_and_keys_tokens", "serialized_json_tokens"))):
        raise ValueError("TOKENIZER_REFUSED")
    text_tokens = max(cast(int, tokenizer["all_string_values_and_keys_tokens"]), cast(int, tokenizer["serialized_json_tokens"]))
    upper = text_tokens + 10000
    if upper > 40000:
        raise ValueError("INPUT_BOUND")
    cost = (Decimal(upper) * money(tariff["input_usd_per_million"]) * multiplier
            + Decimal(4096) * money(tariff["output_usd_per_million"])) / Decimal(1000000)
    ceiling = money(grant["ceiling_usd"])
    if cost > ceiling:
        raise ValueError("COST_BOUND")
    return {"schema": "P0-NORMAL-PREFLIGHT-1.0", "request_sha256": sha(raw), "request_bytes": len(raw),
            "tokenizer_sha256": sha(canonical(tokenizer)), "tariff_sha256": sha(canonical(tariff)),
            "local_text_tokens": text_tokens, "structural_reserve_tokens": 10000, "input_upper_tokens": upper,
            "max_output_tokens": 4096, "cost_bound_usd": str(cost), "ceiling_usd": str(ceiling),
            "count_calls": 0, "retry": 0, "fallback": "NONE", "status": "LOCAL_POLICY_CHECKED"}


def recover_binding(*, artifact: Mapping[str, object], grant_sha256: str,
                    request_sha256: str, dispatch_sha256: str) -> str:
    closed(artifact, {"schema", "grant_sha256", "request_sha256", "dispatch_sha256", "response_status", "output_text", "usage"}, "RECOVERY_FIELDS")
    if (artifact["schema"] != "P0-NORMAL-CONFIRMED-RESULT-1.0" or artifact["response_status"] != "completed"
            or any(not digest(value) for value in (grant_sha256, request_sha256, dispatch_sha256))
            or artifact["grant_sha256"] != grant_sha256 or artifact["request_sha256"] != request_sha256
            or artifact["dispatch_sha256"] != dispatch_sha256 or not isinstance(artifact["output_text"], str)
            or not artifact["output_text"]):
        raise ValueError("RECOVERY_BINDING")
    usage = artifact["usage"]
    if not isinstance(usage, Mapping):
        raise ValueError("RECOVERY_USAGE_FIELDS")
    closed(usage, {"input_tokens", "cached_input_tokens", "output_tokens", "reasoning_tokens", "total_tokens", "cache_write_input_tokens"}, "RECOVERY_USAGE_FIELDS")
    if any(value is not None and (type(value) is not int or value < 0) for value in usage.values()):
        raise ValueError("RECOVERY_USAGE_VALUES")
    for part, total in (("cached_input_tokens", "input_tokens"), ("cache_write_input_tokens", "input_tokens"),
                        ("reasoning_tokens", "output_tokens")):
        if usage[part] is not None and usage[total] is not None and cast(int, usage[part]) > cast(int, usage[total]):
            raise ValueError("RECOVERY_USAGE_INCOHERENT")
    if usage["output_tokens"] is not None and cast(int, usage["output_tokens"]) > 4096:
        raise ValueError("RECOVERY_USAGE_OUTPUT_BOUND")
    if all(usage[key] is not None for key in ("input_tokens", "output_tokens", "total_tokens")):
        if cast(int, usage["total_tokens"]) != cast(int, usage["input_tokens"]) + cast(int, usage["output_tokens"]):
            raise ValueError("RECOVERY_USAGE_INCOHERENT")
    return artifact["output_text"]
