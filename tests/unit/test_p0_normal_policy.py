"""Entirely synthetic records and token counts; no live authority, SDK, or I/O."""
import copy
from datetime import UTC, datetime
from decimal import Decimal

import pytest

from backend.adapters.outbound.generation.openai.p0_normal_policy import (
    ENDPOINT,
    HASH_FIELDS,
    MODEL,
    canonical,
    recover_binding,
    sha,
    validate_grant,
)
from backend.adapters.outbound.generation.openai.p0_normal_policy import (
    preflight as _preflight,
)

NOW = datetime(2026, 10, 11, 12, 0, tzinfo=UTC)


def preflight(raw, grant, tariff, tokenizer):
    return _preflight(raw, grant, tariff, tokenizer, now=NOW)


def fixture():
    schema = {"type": "object", "additionalProperties": False, "properties": {}, "required": []}
    body = {"background": False, "model": MODEL, "instructions": "TEST_ONLY, aucune requête live.",
            "input": "DONNEES_FICTIVES_TEST_ONLY", "max_output_tokens": 4096, "service_tier": "default",
            "store": False, "stream": False, "reasoning": {"effort": "low"}, "tools": [],
            "tool_choice": "none", "text": {"format": {"name": "p0_pedagogical_content", "schema": schema,
                                                       "strict": True, "type": "json_schema"}}}
    raw = canonical(body)
    tariff = {"schema": "P0-NORMAL-TARIFF-1.0", "provider": "OPENAI", "model": MODEL, "tier": "default",
              "input_usd_per_million": "2.00", "output_usd_per_million": "12.00", "input_multiplier": "1.25",
              "evidence_sha256": "b" * 64, "owner_admission_sha256": "c" * 64,
              "retrieved_at_utc": "2026-10-11T11:00:00+00:00"}
    grant = {key: "a" * 64 for key in HASH_FIELDS}
    grant.update(schema="P0-NORMAL-CREATE-GRANT-1.0", operation="CREATE", baseline_commit="1" * 40,
                 request_sha256=sha(raw), request_bytes=len(raw), output_schema_sha256=sha(canonical(schema)),
                 tariff_sha256=sha(canonical(tariff)), issued_at_utc="2026-10-11T11:00:00+00:00",
                 expires_at_utc="2026-10-11T13:00:00+00:00", provider="OPENAI", model=MODEL,
                 endpoint=ENDPOINT, reasoning="low", tier="default", max_output_tokens=4096, max_calls=1,
                 count_calls=0, review_calls=0, modify_calls=0, retry=0, fallback="NONE", parallelism=1,
                 ceiling_usd="0.140000", live_authorized=True, transfer_authorized=True)
    identities = {key: grant[key] for key in HASH_FIELDS | {"baseline_commit", "request_bytes"}}
    tokenizer = {"schema": "P0-NORMAL-TOKENIZER-PROOF-1.0", "model": MODEL,
                 "recognition": "OFFICIAL_UNMODIFIED_PACKAGE_RESOLVER", "encoding": "o200k_base",
                 "request_sha256": sha(raw), "manifest_sha256": "a" * 64,
                 "model_mapping_sha256": "d" * 64, "encoding_sha256": "e" * 64,
                 "all_string_values_and_keys_tokens": 900, "serialized_json_tokens": 1000,
                 "network_forbidden_during_count": True, "provider_calls": 0}
    return grant, identities, body, raw, tariff, tokenizer


def test_synthetic_nominal_has_majorant_without_zero_or_provider_count():
    grant, ids, _, raw, tariff, tokenizer = fixture()
    assert str(validate_grant(grant, identities=ids, now=NOW)) == "0.140000"
    proof = preflight(raw, grant, tariff, tokenizer)
    assert proof["input_upper_tokens"] == 11000 and Decimal(proof["cost_bound_usd"]) == Decimal("0.0766520")
    assert proof["count_calls"] == proof["retry"] == 0 and proof["fallback"] == "NONE"


@pytest.mark.parametrize("key", sorted(HASH_FIELDS | {"baseline_commit", "request_bytes"}))
def test_every_factory_verified_identity_is_bound(key):
    grant, ids, *_ = fixture()
    ids[key] = ids[key] + 1 if key == "request_bytes" else "9" * len(ids[key])
    with pytest.raises(ValueError, match="GRANT_BINDING"):
        validate_grant(grant, identities=ids, now=NOW)


@pytest.mark.parametrize("key,value", [
    ("schema", "MEGA-GRANT-1.0"), ("operation", "REVIEW"), ("provider", "OTHER"),
    ("endpoint", ENDPOINT + "/input_tokens"), ("model", "other-model"), ("reasoning", "high"),
    ("tier", "flex"), ("max_calls", True), ("count_calls", 1), ("review_calls", 1),
    ("modify_calls", 1), ("retry", 1), ("fallback", "AUTO"), ("parallelism", 2),
    ("live_authorized", False), ("transfer_authorized", False), ("ceiling_usd", "NaN"),
    ("ceiling_usd", "0.140001"), ("issued_at_utc", "2026-10-11T12:00:01+00:00"),
    ("expires_at_utc", "2026-10-11T12:00:00+00:00"), ("expires_at_utc", "2026-10-11T14:00:00+00:00"),
    ("issued_at_utc", "2026-10-11T11:00:00"), ("issued_at_utc", "2026-10-11T13:00:00+02:00"),
])
def test_policy_time_and_integer_mutations_refuse(key, value):
    grant, ids, *_ = fixture()
    grant[key] = value
    with pytest.raises(ValueError):
        validate_grant(grant, identities=ids, now=NOW)


def test_unknown_field_and_incomplete_factory_identity_refuse():
    grant, ids, *_ = fixture()
    grant["credential"] = "TEST_ONLY_NOT_A_KEY"
    with pytest.raises(ValueError, match="GRANT_FIELDS"):
        validate_grant(grant, identities=ids, now=NOW)
    del grant["credential"]
    del ids["runtime_sha256"]
    with pytest.raises(ValueError, match="GRANT_BINDING"):
        validate_grant(grant, identities=ids, now=NOW)


@pytest.mark.parametrize("key,value", [("store", True), ("background", True), ("stream", True),
    ("tools", [{"type": "web_search"}]), ("tool_choice", "auto"), ("service_tier", "priority"),
    ("reasoning", {"effort": "high"}), ("max_output_tokens", True), ("model", "other")])
def test_even_rehashed_body_cannot_add_hidden_policy(key, value):
    grant, _, body, _, tariff, tokenizer = fixture()
    body[key] = value
    raw = canonical(body)
    grant.update(request_sha256=sha(raw), request_bytes=len(raw))
    tokenizer["request_sha256"] = sha(raw)
    with pytest.raises(ValueError, match="BODY_POLICY"):
        preflight(raw, grant, tariff, tokenizer)


@pytest.mark.parametrize("mutation", ["manifest", "request", "mapping", "recognition", "encoding", "model", "network", "provider_calls", "bool_tokens"])
def test_tokenizer_proof_cannot_be_replaced_or_sourced_from_provider(mutation):
    grant, _, _, raw, tariff, tokenizer = fixture()
    key, value = {"manifest": ("manifest_sha256", "0" * 64), "request": ("request_sha256", "0" * 64),
        "mapping": ("model_mapping_sha256", "unverified"), "recognition": ("recognition", "ASSUMED"),
        "encoding": ("encoding", "other"), "model": ("model", "other"),
        "network": ("network_forbidden_during_count", False), "provider_calls": ("provider_calls", 1),
        "bool_tokens": ("serialized_json_tokens", True)}[mutation]
    tokenizer[key] = value
    with pytest.raises(ValueError, match="TOKENIZER_REFUSED"):
        preflight(raw, grant, tariff, tokenizer)


@pytest.mark.parametrize("tokens,code", [(30001, "INPUT_BOUND"), (26340, "COST_BOUND")])
def test_financial_and_token_limits_are_independent(tokens, code):
    grant, _, _, raw, tariff, tokenizer = fixture()
    tokenizer["serialized_json_tokens"] = tokens
    with pytest.raises(ValueError, match=code):
        preflight(raw, grant, tariff, tokenizer)


def test_maximum_historical_price_boundary_is_below_technical_limit():
    grant, _, _, raw, tariff, tokenizer = fixture()
    tokenizer["serialized_json_tokens"] = 26339
    assert preflight(raw, grant, tariff, tokenizer)["cost_bound_usd"] == "0.1399995"


@pytest.mark.parametrize("mutation", ["hash", "negative", "nonfinite", "discount", "tier"])
def test_tariff_requires_bound_admitted_positive_majorant(mutation):
    grant, _, _, raw, tariff, tokenizer = fixture()
    if mutation == "hash":
        grant["tariff_sha256"] = "0" * 64
    else:
        key, value = {"negative": ("input_usd_per_million", "-1"), "nonfinite": ("output_usd_per_million", "Infinity"),
                      "discount": ("input_multiplier", "0.9"), "tier": ("tier", "flex")}[mutation]
        tariff[key] = value
        grant["tariff_sha256"] = sha(canonical(tariff))
    with pytest.raises(ValueError):
        preflight(raw, grant, tariff, tokenizer)


def artifact():
    return {"schema": "P0-NORMAL-CONFIRMED-RESULT-1.0", "grant_sha256": "a" * 64,
            "request_sha256": "b" * 64, "dispatch_sha256": "c" * 64, "response_status": "completed",
            "output_text": "DECLARED_SYNTHETIC_PROVIDER_DOUBLE_RESULT",
            "usage": {key: None for key in ("input_tokens", "cached_input_tokens", "output_tokens",
                                           "reasoning_tokens", "total_tokens", "cache_write_input_tokens")}}


def test_recovery_is_pure_confirmed_bytes_and_does_not_require_rearmed_authorization():
    before = artifact()
    data = copy.deepcopy(before)
    assert recover_binding(artifact=data, grant_sha256="a" * 64, request_sha256="b" * 64,
                           dispatch_sha256="c" * 64) == before["output_text"]
    assert data == before


@pytest.mark.parametrize("key,value", [("schema", "other"), ("grant_sha256", "0" * 64),
    ("request_sha256", "0" * 64), ("dispatch_sha256", "0" * 64),
    ("response_status", "UNKNOWN"), ("response_status", "incomplete"), ("output_text", "")])
def test_recovery_refuses_unknown_changed_or_unconfirmed_result(key, value):
    data = artifact()
    data[key] = value
    with pytest.raises(ValueError, match="RECOVERY_BINDING"):
        recover_binding(artifact=data, grant_sha256="a" * 64, request_sha256="b" * 64, dispatch_sha256="c" * 64)
