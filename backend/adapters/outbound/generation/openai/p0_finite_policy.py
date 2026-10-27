"""Closed finite-chain authority, separate from historical CREATE contracts."""

from collections.abc import Mapping, Sequence
from datetime import datetime, timedelta
from decimal import Decimal
from typing import cast

from backend.adapters.outbound.generation.openai.p0_normal_policy import (
    TARIFF_FIELDS,
    TOKENIZER_FIELDS,
    canonical,
    closed,
    digest,
    money,
    sha,
    utc,
)
from backend.adapters.outbound.generation.openai.p0_product_policy import FAMILIES, LEVELS

POLICY = "P0-FINITE-CHAIN-POLICY-2.0"
SLOT = "P0-FINITE-CHAIN-SLOT-2.0"
GRANT = "P0-FINITE-CHAIN-GRANT-2.0"
ROLES = ("PROPOSE", "REVIEW_INITIAL", "CORRECT", "REVIEW_CORRECTED")
FIELDS = {
    "schema",
    "normal_permission_sha256",
    "normal_envelope_sha256",
    "campaign_namespace_sha256",
    "receipt_root_sha256",
    "root_lock_sha256",
    "root_lock_identity_sha256",
    "package_sha256",
    "runtime_sha256",
    "source_tree_sha256",
    "institutional_catalog_sha256",
    "tariff_sha256",
    "tokenizer_manifest_sha256",
    "price_evidence_sha256",
    "issued_at_utc",
    "expires_at_utc",
    "allowed_families",
    "allowed_levels",
    "max_chains",
    "maximum_effects",
    "roles",
    "per_effect_ceiling_usd",
    "cumulative_ceiling_usd",
    "max_output_tokens",
    "input_upper_tokens",
    "preview_minutes",
    "authority_minutes",
    "retry",
    "fallback",
    "max_campaign_effects",
    "retained_origins",
}
DECISION_FIELDS = {
    "schema",
    "status",
    "policy_sha256",
    "normal_envelope_sha256",
    "price_evidence_sha256",
    "financial_evidence_admitted",
    "historical_uncertainty_preserved",
    "additional_finite_right_accepted",
}
GRANT_FIELDS = {
    "schema",
    "policy_sha256",
    "owner_decision_sha256",
    "normal_permission_sha256",
    "campaign_namespace_sha256",
    "namespace_sha256",
    "chain_command_id",
    "effect_id",
    "ordinal",
    "role",
    "preview_sha256",
    "consent_sha256",
    "plan_sha256",
    "parent_sha256",
    "request_sha256",
    "request_bytes",
    "preflight_sha256",
    "issued_at_utc",
    "authority_issued_at_utc",
    "expires_at_utc",
    "ceiling_usd",
    "step_id",
}
SLOT_FIELDS = {
    "schema",
    "permission_sha256",
    "preview_sha256",
    "command_id",
    "grant",
    "grant_sha256",
    "namespace_sha256",
    "request_sha256",
    "preflight_sha256",
    "reserved_usd",
}


def validate_policy(
    policy: Mapping[str, object],
    decision: Mapping[str, object],
    permission: Mapping[str, object],
    *,
    now: datetime,
    proposed: bool = False,
) -> None:
    closed(policy, FIELDS, "P0_CHAIN_POLICY_FIELDS")
    closed(decision, DECISION_FIELDS, "P0_CHAIN_DECISION_FIELDS")
    if (
        policy["schema"] != POLICY
        or decision["schema"] != "P0-FINITE-CHAIN-ADOPTION-2.0"
        or decision["status"] != ("PROPOSED" if proposed else "ADOPTED")
        or decision["policy_sha256"] != sha(canonical(policy))
        or decision["normal_envelope_sha256"] != policy["normal_envelope_sha256"]
        or decision["price_evidence_sha256"] != policy["price_evidence_sha256"]
        or decision["financial_evidence_admitted"] is not (not proposed)
        or decision["historical_uncertainty_preserved"] is not True
        or decision["additional_finite_right_accepted"] is not (not proposed)
    ):
        raise ValueError("P0_CHAIN_ADOPTION_REQUIRED")
    if any(not digest(policy[key]) for key in FIELDS if key.endswith("_sha256")):
        raise ValueError("P0_CHAIN_IDENTITIES_REQUIRED")
    if (
        policy["normal_permission_sha256"] != sha(canonical(permission))
        or policy["campaign_namespace_sha256"] != permission["permission_namespace_sha256"]
        or any(
            policy[key] != permission[key]
            for key in (
                "receipt_root_sha256",
                "runtime_sha256",
                "institutional_catalog_sha256",
                "tariff_sha256",
                "tokenizer_manifest_sha256",
            )
        )
    ):
        raise ValueError("P0_CHAIN_CAMPAIGN_BINDING")
    for key in ("allowed_families", "allowed_levels"):
        values = policy[key]
        if (
            not isinstance(values, (list, tuple))
            or not values
            or any(not isinstance(v, str) for v in values)
            or len(values) != len(set(values))
            or not set(values) <= (FAMILIES if key == "allowed_families" else LEVELS)
        ):
            raise ValueError("P0_CHAIN_SCOPE")
    if (
        type(policy["max_chains"]) is not int
        or policy["max_chains"] != 1
        or type(policy["maximum_effects"]) is not int
        or policy["maximum_effects"] != 4
        or list(cast(Sequence[object], policy["roles"])) != list(ROLES)
        or policy["fallback"] != "NONE"
    ):
        raise ValueError("P0_CHAIN_OPERATIONS")
    for key, expected in (
        ("max_output_tokens", 4096),
        ("input_upper_tokens", 36000),
        ("preview_minutes", 15),
        ("authority_minutes", 60),
        ("retry", 0),
    ):
        if type(policy[key]) is not int or policy[key] != expected:
            raise ValueError("P0_CHAIN_LIMITS")
    start, end = utc(policy["issued_at_utc"]), utc(policy["expires_at_utc"])
    if not start <= now < end or not timedelta(0) < end - start <= timedelta(days=30):
        raise ValueError("P0_CHAIN_POLICY_EXPIRED")
    per, total = money(policy["per_effect_ceiling_usd"]), money(policy["cumulative_ceiling_usd"])
    if (
        per > Decimal("0.14")
        or total > Decimal("1.96")
        or total < per
        or type(policy["max_campaign_effects"]) is not int
        or not 1 <= policy["max_campaign_effects"] <= 14
    ):
        raise ValueError("P0_CHAIN_CAMPAIGN_CEILING")
    if (
        not isinstance(policy["retained_origins"], (list, tuple))
        or len(policy["retained_origins"]) > 14
    ):
        raise ValueError("P0_CHAIN_RETAINED_ORIGINS")


def financial_proof(
    raw: bytes,
    *,
    policy: Mapping[str, object],
    tariff: Mapping[str, object],
    tokenizer: Mapping[str, object],
) -> dict[str, object]:
    closed(tariff, TARIFF_FIELDS, "P0_CHAIN_TARIFF_FIELDS")
    closed(tokenizer, TOKENIZER_FIELDS, "P0_CHAIN_TOKENIZER_FIELDS")
    if (
        not 0 < len(raw) < 250000
        or sha(raw) != tokenizer["request_sha256"]
        or sha(canonical(tariff)) != policy["tariff_sha256"]
        or tariff["schema"] != "P0-NORMAL-TARIFF-1.0"
        or tariff["provider"] != "OPENAI"
        or tariff["model"] != "gpt-5.6-terra"
        or tariff["tier"] != "default"
        or tariff["evidence_sha256"] != policy["price_evidence_sha256"]
        or not digest(tariff["owner_admission_sha256"])
        or not digest(tariff["evidence_sha256"])
        or tokenizer["schema"] != "P0-NORMAL-TOKENIZER-PROOF-1.0"
        or tokenizer["manifest_sha256"] != policy["tokenizer_manifest_sha256"]
        or tokenizer["model"] != tariff["model"]
        or tokenizer["encoding"] != "o200k_base"
        or tokenizer["recognition"] != "OFFICIAL_UNMODIFIED_PACKAGE_RESOLVER"
        or tokenizer["network_forbidden_during_count"] is not True
        or type(tokenizer["provider_calls"]) is not int
        or tokenizer["provider_calls"] != 0
        or any(not digest(tokenizer[key]) for key in ("model_mapping_sha256", "encoding_sha256"))
    ):
        raise ValueError("P0_CHAIN_FINANCIAL_EVIDENCE_REQUIRED")
    if utc(tariff["retrieved_at_utc"]) > utc(policy["issued_at_utc"]):
        raise ValueError("P0_CHAIN_TARIFF_POSTDATES_POLICY")
    counts = [
        tokenizer[key] for key in ("all_string_values_and_keys_tokens", "serialized_json_tokens")
    ]
    if any(type(value) is not int or value <= 0 for value in counts):
        raise ValueError("P0_CHAIN_TOKEN_COUNT")
    upper = max(cast(list[int], counts)) + 10000
    if upper > cast(int, policy["input_upper_tokens"]):
        raise ValueError("P0_CHAIN_INPUT_BOUND")
    multiplier = money(tariff["input_multiplier"])
    if multiplier < 1:
        raise ValueError("P0_CHAIN_CACHE_DISCOUNT_REFUSED")
    cost = (
        Decimal(upper) * money(tariff["input_usd_per_million"]) * multiplier
        + Decimal(4096) * money(tariff["output_usd_per_million"])
    ) / Decimal(1000000)
    if cost > money(policy["per_effect_ceiling_usd"]):
        raise ValueError("P0_CHAIN_EFFECT_COST_BOUND")
    return {
        "schema": "P0-FINITE-CHAIN-PREFLIGHT-1.0",
        "request_sha256": sha(raw),
        "request_bytes": len(raw),
        "tariff_sha256": policy["tariff_sha256"],
        "tokenizer_sha256": sha(canonical(tokenizer)),
        "input_upper_tokens": upper,
        "max_output_tokens": 4096,
        "cost_bound_usd": str(cost),
        "provider_count_calls": 0,
        "cache_discount": "NONE",
    }


def validate_slot(
    record: Mapping[str, object],
    *,
    policy: Mapping[str, object],
    decision_sha256: str,
    permission_sha256: str,
    prefix: str,
    file_name: str,
) -> None:
    closed(record, SLOT_FIELDS, "P0_CHAIN_SLOT_FIELDS")
    grant = record["grant"]
    if not isinstance(grant, Mapping):
        raise ValueError("P0_CHAIN_GRANT_REQUIRED")
    closed(grant, GRANT_FIELDS, "P0_CHAIN_GRANT_FIELDS")
    ordinal = grant["ordinal"]
    if (
        record["schema"] != SLOT
        or grant["schema"] != GRANT
        or record["permission_sha256"] != permission_sha256
        or grant["normal_permission_sha256"] != permission_sha256
        or grant["policy_sha256"] != sha(canonical(policy))
        or grant["owner_decision_sha256"] != decision_sha256
        or type(ordinal) is not int
        or not 0 <= ordinal < 4
        or grant["role"] != ROLES[ordinal]
        or grant["campaign_namespace_sha256"] != policy["campaign_namespace_sha256"]
        or any(not digest(grant[key]) for key in GRANT_FIELDS if key.endswith("_sha256"))
        or any(
            record[key] != grant[key]
            for key in ("namespace_sha256", "request_sha256", "preflight_sha256")
        )
        or record["command_id"] != grant["effect_id"]
        or record["preview_sha256"]
        != sha(
            canonical(
                {
                    "chain": grant["chain_command_id"],
                    "ordinal": ordinal,
                    "policy": grant["policy_sha256"],
                }
            )
        )
        or record["grant_sha256"] != sha(canonical(grant))
        or file_name != prefix + str(record["preview_sha256"]) + ".json"
        or money(record["reserved_usd"]) > money(policy["per_effect_ceiling_usd"])
        or money(grant["ceiling_usd"]) != money(policy["per_effect_ceiling_usd"])
    ):
        raise ValueError("P0_CHAIN_SLOT_BINDING")
    for key in ("chain_command_id", "effect_id"):
        value = grant[key]
        if (
            not isinstance(value, str)
            or len(value) != 32
            or any(c not in "0123456789abcdef" for c in value)
        ):
            raise ValueError("P0_CHAIN_COMMAND_IDENTITY")
    step = grant["step_id"]
    if (
        not isinstance(step, str)
        or len(step) != 37
        or not step.startswith("step:")
        or any(c not in "0123456789abcdef" for c in step[5:])
    ):
        raise ValueError("P0_CHAIN_STEP_IDENTITY")
    if (
        type(grant["request_bytes"]) is not int
        or not 0 < grant["request_bytes"] < 250000
        or not utc(policy["issued_at_utc"])
        <= utc(grant["authority_issued_at_utc"])
        <= utc(grant["issued_at_utc"])
        < utc(grant["expires_at_utc"])
        <= utc(policy["expires_at_utc"])
        or utc(grant["expires_at_utc"]) - utc(grant["authority_issued_at_utc"])
        > timedelta(minutes=60)
    ):
        raise ValueError("P0_CHAIN_GRANT_WINDOW")
