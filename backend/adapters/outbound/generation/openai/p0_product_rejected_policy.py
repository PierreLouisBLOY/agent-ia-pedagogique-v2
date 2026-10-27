"""V2 source receipt binding; existing P1/G1 finance predicates unchanged."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import datetime, timedelta
from decimal import Decimal

from backend.adapters.outbound.generation.openai.p0_normal_policy import (
    ENDPOINT,
    HASH_FIELDS,
    MODEL,
    canonical,
    closed,
    digest,
    money,
    sha,
    utc,
    validate_grant,
)
from backend.adapters.outbound.generation.openai.p0_product_policy import (
    CONSENT_FIELDS,
    F1_FIELDS,
    LOCAL_ADOPTION_FIELDS,
    LOCAL_SOURCE_FIELDS,
    P1_HASHES,
    PREVIEW_FIELDS,
    REFERENCE_FIELDS,
    SOURCE_FIELDS,
    check_budget,
    validate_permission,
)

REJECTED_ADOPTION_FIELDS = LOCAL_ADOPTION_FIELDS | {
    "continuity_manifest_sha256",
    "continuity_anchor_sha256",
    "source_admission_owner_decision_sha256",
    "rejected_disposition_sha256",
}


def derive_grant4(
    *,
    permission: Mapping[str, object],
    permission_identities: Mapping[str, object],
    grant_identities: Mapping[str, object],
    preview: Mapping[str, object],
    consent: Mapping[str, object],
    nonce_sha256: str,
    family: str,
    level: str,
    reserved: Sequence[Decimal],
    now: datetime,
    fresh_preflight: Mapping[str, object],
    application_source_receipts: Sequence[Mapping[str, object]],
    local_context_adoption: Mapping[str, object] | None = None,
) -> dict[str, object]:
    validate_permission(
        permission, identities=permission_identities, now=now, family=family, level=level
    )
    closed(consent, CONSENT_FIELDS, "P1_CONSENT_FIELDS")
    closed(preview, PREVIEW_FIELDS, "P1_PREVIEW_FIELDS")
    if consent["transfer_accepted"] is not True or consent["cost_bound_accepted"] is not True:
        raise ValueError("P1_CONSENT_REQUIRED")
    if (
        not isinstance(consent["command_id"], str)
        or len(consent["command_id"]) != 32
        or any(val not in "0123456789abcdef" for val in consent["command_id"])
    ):
        raise ValueError("P1_COMMAND_ID")
    issued, expiry = utc(preview["issued_at_utc"]), utc(preview["expires_at_utc"])
    raw = preview["request_body_utf8"]
    if (
        preview["schema"] != "P0-PRODUCT-CONSENT-PREVIEW-1.0"
        or not isinstance(raw, str)
        or sha(raw.encode()) != preview["request_sha256"]
        or len(raw.encode()) != preview["request_bytes"]
        or not issued <= now < expiry
        or not timedelta(0) < expiry - issued <= timedelta(minutes=15)
    ):
        raise ValueError("P1_PREVIEW_BINDING")
    if (
        not digest(nonce_sha256)
        or consent["preview_sha256"] != sha(canonical(preview))
        or consent["preparation_ref"] != preview["preparation_ref"]
        or consent["preparation_sha256"] != preview["preparation_sha256"]
        or preview["permission_sha256"] != sha(canonical(permission))
        or not now < utc(preview["expires_at_utc"])
    ):
        raise ValueError("P1_CONSENT_BINDING")
    closed(fresh_preflight, F1_FIELDS, "P1_FRESH_PREFLIGHT_FIELDS")
    if (
        canonical(fresh_preflight) != canonical(preview["preflight"])
        or fresh_preflight["schema"] != "P0-NORMAL-PREFLIGHT-1.0"
        or fresh_preflight["status"] != "LOCAL_POLICY_CHECKED"
        or fresh_preflight["request_sha256"] != preview["request_sha256"]
        or fresh_preflight["request_bytes"] != preview["request_bytes"]
        or fresh_preflight["tariff_sha256"] != permission["tariff_sha256"]
        or money(fresh_preflight["cost_bound_usd"]) != money(preview["cost_bound_usd"])
        or money(fresh_preflight["ceiling_usd"]) != money(permission["per_call_ceiling_usd"])
    ):
        raise ValueError("P1_FRESH_PREFLIGHT_BINDING")
    validate_source_receipts4(
        permission, application_source_receipts, local_context_adoption=local_context_adoption
    )
    if canonical(list(application_source_receipts)) != canonical(preview["source_receipts"]):
        raise ValueError("P1_SOURCE_RECEIPTS_CHANGED")
    if (
        sha(canonical([receipt["reference"] for receipt in application_source_receipts]))
        != preview["reference_set_sha256"]
    ):
        raise ValueError("P1_SOURCE_REFERENCE_SET_BINDING")
    check_budget(permission, reserved, money(fresh_preflight["cost_bound_usd"]))
    identities = dict(grant_identities)
    if set(identities) != HASH_FIELDS | {"baseline_commit", "request_bytes"}:
        raise ValueError("P1_G1_IDENTITIES")
    for key in P1_HASHES & HASH_FIELDS | {"baseline_commit"}:
        if identities[key] != permission[key]:
            raise ValueError("P1_G1_PERMISSION_BINDING")
    for key in (
        "preparation_sha256",
        "context_sha256",
        "reference_set_sha256",
        "request_sha256",
        "request_bytes",
    ):
        if identities[key] != preview[key]:
            raise ValueError("P1_G1_PREVIEW_BINDING")
    namespace = sha(
        canonical(
            {
                "permission_sha256": sha(canonical(permission)),
                "preview_sha256": sha(canonical(preview)),
                "command_id": consent["command_id"],
                "nonce_sha256": nonce_sha256,
            }
        )
    )
    if identities["namespace_sha256"] != namespace:
        raise ValueError("P1_G1_NAMESPACE")
    grant = {
        **identities,
        "schema": "P0-NORMAL-CREATE-GRANT-1.0",
        "operation": "CREATE",
        "provider": "OPENAI",
        "model": MODEL,
        "endpoint": ENDPOINT,
        "reasoning": "low",
        "tier": "default",
        "max_output_tokens": 4096,
        "max_calls": 1,
        "count_calls": 0,
        "review_calls": 0,
        "modify_calls": 0,
        "retry": 0,
        "fallback": "NONE",
        "parallelism": 1,
        "ceiling_usd": permission["per_call_ceiling_usd"],
        "live_authorized": True,
        "transfer_authorized": True,
        "issued_at_utc": now.isoformat(),
        "expires_at_utc": min(
            now + timedelta(minutes=120), utc(permission["expires_at_utc"])
        ).isoformat(),
    }
    validate_grant(grant, identities=identities, now=now)
    return grant


def validate_source_receipts4(
    permission: Mapping[str, object],
    receipts: Sequence[Mapping[str, object]],
    *,
    local_context_adoption: Mapping[str, object] | None = None,
) -> None:
    # Actual receipts must be emitted by the authenticated Application query.
    # This pure prototype validates their contract, not their SQL authenticity.
    if (
        local_context_adoption is None
        or local_context_adoption.get("profile_schema") != "P0-NORMAL-PROFILE-4.0"
    ):
        raise ValueError("P1_REJECTED_CONTEXT_PROFILE_REQUIRED")
    if not receipts or len(receipts) > 8:
        raise ValueError("P1_SOURCE_RECEIPTS_REQUIRED")
    identities: set[str] = set()
    for receipt in receipts:
        is_local = receipt.get("schema") == "P0-SOURCE-ADMISSION-RECEIPT-2.0"
        source_owner = permission["owner_decision_sha256"]
        if local_context_adoption is not None and not is_local:
            raise ValueError("P1_LOCAL_CONTEXT_RECEIPT_REQUIRED")
        closed(
            receipt, LOCAL_SOURCE_FIELDS if is_local else SOURCE_FIELDS, "P1_SOURCE_RECEIPT_FIELDS"
        )
        if is_local:
            if local_context_adoption is None:
                raise ValueError("P1_LOCAL_CONTEXT_PROFILE_REQUIRED")
            continuity = local_context_adoption.get("profile_schema") == "P0-NORMAL-PROFILE-4.0"
            closed(
                local_context_adoption,
                REJECTED_ADOPTION_FIELDS if continuity else LOCAL_ADOPTION_FIELDS,
                "P1_LOCAL_CONTEXT_ADOPTION_FIELDS",
            )
            if continuity:
                if any(
                    not digest(local_context_adoption[k])
                    for k in REJECTED_ADOPTION_FIELDS - LOCAL_ADOPTION_FIELDS
                ):
                    raise ValueError("P1_CONTINUITY_ADOPTION_BINDING")
                source_owner = local_context_adoption["source_admission_owner_decision_sha256"]
            if (
                local_context_adoption["profile_schema"]
                != ("P0-NORMAL-PROFILE-4.0" if continuity else "P0-NORMAL-PROFILE-2.0")
                or local_context_adoption["owner_decision_schema"]
                != (
                    "P0-NORMAL-OWNER-DECISION-4.0" if continuity else "P0-NORMAL-OWNER-DECISION-2.0"
                )
                or local_context_adoption["profile_sha256"] != permission["profile_sha256"]
                or local_context_adoption["owner_decision_sha256"]
                != permission["owner_decision_sha256"]
                or local_context_adoption["local_reference_context_manifest_sha256"]
                != receipt["local_reference_context_manifest_sha256"]
                or receipt["source_scope_status"] != "OWNER_ADMITTED_EXACT_LOCAL_CONTEXT"
                or any(not digest(receipt[key]) for key in LOCAL_SOURCE_FIELDS - SOURCE_FIELDS)
            ):
                raise ValueError("P1_LOCAL_CONTEXT_ADOPTION_BINDING")
        reference = receipt["reference"]
        if not isinstance(reference, Mapping):
            raise ValueError("P1_SOURCE_REFERENCE")
        closed(reference, REFERENCE_FIELDS, "P1_SOURCE_REFERENCE_FIELDS")
        if (
            receipt["schema"]
            != (
                "P0-SOURCE-ADMISSION-RECEIPT-2.0" if is_local else "P0-SOURCE-ADMISSION-RECEIPT-1.0"
            )
            or receipt["transmission_admission"] != "OWNER_ADMITTED_LOCAL_CONTENT_ONLY"
            or receipt["source_scope_status"]
            not in (
                {"OWNER_ADMITTED_EXACT_LOCAL_CONTEXT"}
                if is_local
                else {"CANONICAL_NOTION_ONLY", "EXACT_CONTEXT_ADMITTED"}
            )
            or receipt["admission_manifest_sha256"]
            != permission["source_admission_manifest_sha256"]
            or receipt["owner_admission_sha256"] != source_owner
            or not digest(receipt["admission_scope_sha256"])
            or not digest(receipt["institutional_resolution_sha256"])
            or not isinstance(receipt["available_authority"], str)
            or not receipt["available_authority"]
            or len(receipt["available_authority"]) > 200
            or not isinstance(receipt["provenance"], Mapping)
            or not isinstance(receipt["source_status"], Mapping)
            or any(not isinstance(val, str) or not val for val in reference.values())
            or not digest(reference["excerpt_sha256"])
        ):
            raise ValueError("P1_SOURCE_ADMISSION_BINDING")
        key = sha(canonical(reference))
        if key in identities:
            raise ValueError("P1_SOURCE_DUPLICATE")
        identities.add(key)
