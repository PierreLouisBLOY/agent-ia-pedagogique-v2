"""Pure preimplementation P1/consent/G1 derivation; no I/O or live authority."""
from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from datetime import datetime, timedelta
from decimal import Decimal
from typing import cast

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

P1_FIELDS = {"schema", "owner_decision_sha256", "baseline_commit", "source_tree_sha256", "package_sha256",
    "runtime_sha256", "profile_sha256", "output_schema_sha256", "tokenizer_manifest_sha256", "tariff_sha256",
    "receipt_root_sha256", "permission_namespace_sha256", "operator_delegation_sha256",
    "source_admission_manifest_sha256", "local_operator_delegation_accepted",
    "issued_at_utc", "expires_at_utc", "allowed_families",
    "allowed_levels", "institutional_catalog_sha256", "selected_admitted_sources_only",
    "excluded_oracles_and_private_evidence", "require_exact_local_consent", "provider", "model", "endpoint",
    "reasoning", "tier", "max_output_tokens", "max_calls", "count_calls", "review_calls", "modify_calls",
    "retry", "fallback", "parallelism", "per_call_ceiling_usd", "cumulative_ceiling_usd", "live_authorized",
    "transfer_authorized"}
P1_HASHES = {key for key in P1_FIELDS if key.endswith("_sha256")}
FAMILIES = {"COURSE", "EXERCISE", "OPEN_QUESTIONS", "QCM", "QUIZ", "ASSESSMENT"}
LEVELS = {"FIRST_STMG", "FINAL_STMG", "BTS_CG_YEAR_1", "BTS_CG_YEAR_2"}
CONSENT_FIELDS = {"command_id", "preparation_ref", "preparation_sha256", "preview_sha256",
                  "transfer_accepted", "cost_bound_accepted"}
PREVIEW_FIELDS = {"schema", "permission_sha256", "preparation_ref", "preparation_sha256", "context_sha256",
                  "reference_set_sha256", "request_sha256", "request_bytes", "request_body_utf8", "cost_bound_usd",
                  "issued_at_utc", "expires_at_utc", "preflight", "source_receipts"}
SOURCE_FIELDS = {"schema", "reference", "available_authority", "provenance", "source_status",
                 "admission_manifest_sha256", "admission_scope_sha256", "owner_admission_sha256",
                 "institutional_resolution_sha256", "source_scope_status", "transmission_admission"}
LOCAL_SOURCE_FIELDS = SOURCE_FIELDS | {"local_reference_context_manifest_sha256", "selection_sha256",
    "canonical_notion_entry_scope_sha256", "canonical_institutional_resolution_sha256"}
LOCAL_ADOPTION_FIELDS = {"profile_schema", "owner_decision_schema", "profile_sha256", "owner_decision_sha256",
    "local_reference_context_manifest_sha256"}
CONTINUITY_ADOPTION_FIELDS = LOCAL_ADOPTION_FIELDS | {"continuity_manifest_sha256", "continuity_anchor_sha256",
    "source_admission_owner_decision_sha256"}
REFERENCE_FIELDS = {"evidence_id", "source_ref", "locator", "checksum_or_version", "excerpt_sha256", "provenance_label"}
F1_FIELDS = {"schema", "request_sha256", "request_bytes", "tokenizer_sha256", "tariff_sha256", "local_text_tokens",
             "structural_reserve_tokens", "input_upper_tokens", "max_output_tokens", "cost_bound_usd", "ceiling_usd",
             "count_calls", "retry", "fallback", "status"}


def validate_permission(permission: Mapping[str, object], *, identities: Mapping[str, object],
                        now: datetime, family: str, level: str) -> None:
    closed(permission, P1_FIELDS, "P1_FIELDS")
    fixed = {"schema": "P0-PRODUCT-CREATE-PERMISSION-1.0", "provider": "OPENAI", "model": MODEL,
        "endpoint": ENDPOINT, "reasoning": "low", "tier": "default", "fallback": "NONE",
        "selected_admitted_sources_only": True, "excluded_oracles_and_private_evidence": True,
        "require_exact_local_consent": True, "local_operator_delegation_accepted": True,
        "live_authorized": True, "transfer_authorized": True}
    if any(permission[key] != value or type(permission[key]) is not type(value) for key, value in fixed.items()):
        raise ValueError("P1_POLICY")
    for key, val in {"max_output_tokens": 4096, "count_calls": 0, "review_calls": 0, "modify_calls": 0,
                     "retry": 0, "parallelism": 1}.items():
        if type(permission[key]) is not int or permission[key] != val:
            raise ValueError("P1_OPERATIONS")
    calls = permission["max_calls"]
    if type(calls) is not int or not 1 <= calls <= 14:
        raise ValueError("P1_CALLS")
    if any(not digest(permission[key]) for key in P1_HASHES):
        raise ValueError("P1_HASHES")
    if not isinstance(permission["baseline_commit"], str) or re.fullmatch(r"[0-9a-f]{40}", permission["baseline_commit"]) is None:
        raise ValueError("P1_BASELINE")
    if set(identities) != P1_HASHES | {"baseline_commit"} or any(permission[key] != val for key, val in identities.items()):
        raise ValueError("P1_BINDING")
    for key, allowed, selection in (("allowed_families", FAMILIES, family), ("allowed_levels", LEVELS, level)):
        values = permission[key]
        if (not isinstance(values, (list, tuple)) or not values or any(type(val) is not str for val in values)
                or len(values) != len(set(values)) or not set(values) <= allowed or selection not in values):
            raise ValueError("P1_CONTEXT_SCOPE")
    issued, expiry = utc(permission["issued_at_utc"]), utc(permission["expires_at_utc"])
    if now.tzinfo is None or not issued <= now < expiry or not timedelta(0) < expiry - issued <= timedelta(days=30):
        raise ValueError("P1_TIME")
    per, total = money(permission["per_call_ceiling_usd"]), money(permission["cumulative_ceiling_usd"])
    if per > Decimal("0.140000") or total > Decimal(calls) * per:
        raise ValueError("P1_CEILING")


def check_budget(permission: Mapping[str, object], reserved: Sequence[Decimal], next_cost: Decimal) -> None:
    # Pure calculation only. Runtime must hold its cross-process Windows lock.
    if (not next_cost.is_finite() or next_cost <= 0 or any(not value.is_finite() or value <= 0 for value in reserved)
            or len(reserved) >= cast(int, permission["max_calls"])
            or next_cost > money(permission["per_call_ceiling_usd"])
            or sum(reserved, Decimal(0)) + next_cost > money(permission["cumulative_ceiling_usd"])):
        raise ValueError("P1_BUDGET_STOP")


def derive_grant(*, permission: Mapping[str, object], permission_identities: Mapping[str, object],
                 grant_identities: Mapping[str, object], preview: Mapping[str, object],
                 consent: Mapping[str, object], nonce_sha256: str, family: str, level: str,
                 reserved: Sequence[Decimal], now: datetime, fresh_preflight: Mapping[str, object],
                 application_source_receipts: Sequence[Mapping[str, object]],
                 local_context_adoption: Mapping[str, object] | None = None) -> dict[str, object]:
    validate_permission(permission, identities=permission_identities, now=now, family=family, level=level)
    closed(consent, CONSENT_FIELDS, "P1_CONSENT_FIELDS")
    closed(preview, PREVIEW_FIELDS, "P1_PREVIEW_FIELDS")
    if consent["transfer_accepted"] is not True or consent["cost_bound_accepted"] is not True:
        raise ValueError("P1_CONSENT_REQUIRED")
    if (not isinstance(consent["command_id"], str) or len(consent["command_id"]) != 32
            or any(val not in "0123456789abcdef" for val in consent["command_id"])):
        raise ValueError("P1_COMMAND_ID")
    issued, expiry = utc(preview["issued_at_utc"]), utc(preview["expires_at_utc"])
    raw = preview["request_body_utf8"]
    if (preview["schema"] != "P0-PRODUCT-CONSENT-PREVIEW-1.0" or not isinstance(raw, str)
            or sha(raw.encode()) != preview["request_sha256"] or len(raw.encode()) != preview["request_bytes"]
            or not issued <= now < expiry or not timedelta(0) < expiry - issued <= timedelta(minutes=15)):
        raise ValueError("P1_PREVIEW_BINDING")
    if (not digest(nonce_sha256) or consent["preview_sha256"] != sha(canonical(preview))
            or consent["preparation_ref"] != preview["preparation_ref"]
            or consent["preparation_sha256"] != preview["preparation_sha256"]
            or preview["permission_sha256"] != sha(canonical(permission))
            or not now < utc(preview["expires_at_utc"])):
        raise ValueError("P1_CONSENT_BINDING")
    closed(fresh_preflight, F1_FIELDS, "P1_FRESH_PREFLIGHT_FIELDS")
    if (canonical(fresh_preflight) != canonical(preview["preflight"])
            or fresh_preflight["schema"] != "P0-NORMAL-PREFLIGHT-1.0"
            or fresh_preflight["status"] != "LOCAL_POLICY_CHECKED"
            or fresh_preflight["request_sha256"] != preview["request_sha256"]
            or fresh_preflight["request_bytes"] != preview["request_bytes"]
            or fresh_preflight["tariff_sha256"] != permission["tariff_sha256"]
            or money(fresh_preflight["cost_bound_usd"]) != money(preview["cost_bound_usd"])
            or money(fresh_preflight["ceiling_usd"]) != money(permission["per_call_ceiling_usd"])):
        raise ValueError("P1_FRESH_PREFLIGHT_BINDING")
    validate_source_receipts(permission, application_source_receipts, local_context_adoption=local_context_adoption)
    if canonical(list(application_source_receipts)) != canonical(preview["source_receipts"]):
        raise ValueError("P1_SOURCE_RECEIPTS_CHANGED")
    if sha(canonical([receipt["reference"] for receipt in application_source_receipts])) != preview["reference_set_sha256"]:
        raise ValueError("P1_SOURCE_REFERENCE_SET_BINDING")
    check_budget(permission, reserved, money(fresh_preflight["cost_bound_usd"]))
    identities = dict(grant_identities)
    if set(identities) != HASH_FIELDS | {"baseline_commit", "request_bytes"}:
        raise ValueError("P1_G1_IDENTITIES")
    for key in P1_HASHES & HASH_FIELDS | {"baseline_commit"}:
        if identities[key] != permission[key]:
            raise ValueError("P1_G1_PERMISSION_BINDING")
    for key in ("preparation_sha256", "context_sha256", "reference_set_sha256", "request_sha256", "request_bytes"):
        if identities[key] != preview[key]:
            raise ValueError("P1_G1_PREVIEW_BINDING")
    namespace = sha(canonical({"permission_sha256": sha(canonical(permission)), "preview_sha256": sha(canonical(preview)),
                               "command_id": consent["command_id"], "nonce_sha256": nonce_sha256}))
    if identities["namespace_sha256"] != namespace:
        raise ValueError("P1_G1_NAMESPACE")
    grant = {**identities, "schema": "P0-NORMAL-CREATE-GRANT-1.0", "operation": "CREATE", "provider": "OPENAI",
        "model": MODEL, "endpoint": ENDPOINT, "reasoning": "low", "tier": "default", "max_output_tokens": 4096,
        "max_calls": 1, "count_calls": 0, "review_calls": 0, "modify_calls": 0, "retry": 0,
        "fallback": "NONE", "parallelism": 1, "ceiling_usd": permission["per_call_ceiling_usd"],
        "live_authorized": True, "transfer_authorized": True, "issued_at_utc": now.isoformat(),
        "expires_at_utc": min(now + timedelta(minutes=120), utc(permission["expires_at_utc"])).isoformat()}
    validate_grant(grant, identities=identities, now=now)
    return grant


def validate_source_receipts(permission: Mapping[str, object], receipts: Sequence[Mapping[str, object]], *,
                             local_context_adoption: Mapping[str, object] | None = None) -> None:
    # Actual receipts must be emitted by the authenticated Application query.
    # This pure prototype validates their contract, not their SQL authenticity.
    if not receipts or len(receipts) > 8:
        raise ValueError("P1_SOURCE_RECEIPTS_REQUIRED")
    identities: set[str] = set()
    for receipt in receipts:
        is_local = receipt.get("schema") == "P0-SOURCE-ADMISSION-RECEIPT-2.0"
        source_owner = permission["owner_decision_sha256"]
        if local_context_adoption is not None and not is_local:
            raise ValueError("P1_LOCAL_CONTEXT_RECEIPT_REQUIRED")
        closed(receipt, LOCAL_SOURCE_FIELDS if is_local else SOURCE_FIELDS, "P1_SOURCE_RECEIPT_FIELDS")
        if is_local:
            if local_context_adoption is None:
                raise ValueError("P1_LOCAL_CONTEXT_PROFILE_REQUIRED")
            continuity = local_context_adoption.get("profile_schema") == "P0-NORMAL-PROFILE-3.0"
            closed(local_context_adoption, CONTINUITY_ADOPTION_FIELDS if continuity else LOCAL_ADOPTION_FIELDS, "P1_LOCAL_CONTEXT_ADOPTION_FIELDS")
            if continuity:
                if any(not digest(local_context_adoption[k]) for k in CONTINUITY_ADOPTION_FIELDS - LOCAL_ADOPTION_FIELDS):
                    raise ValueError("P1_CONTINUITY_ADOPTION_BINDING")
                source_owner = local_context_adoption["source_admission_owner_decision_sha256"]
            if (local_context_adoption["profile_schema"] != ("P0-NORMAL-PROFILE-3.0" if continuity else "P0-NORMAL-PROFILE-2.0")
                    or local_context_adoption["owner_decision_schema"] != ("P0-NORMAL-OWNER-DECISION-3.0" if continuity else "P0-NORMAL-OWNER-DECISION-2.0")
                    or local_context_adoption["profile_sha256"] != permission["profile_sha256"]
                    or local_context_adoption["owner_decision_sha256"] != permission["owner_decision_sha256"]
                    or local_context_adoption["local_reference_context_manifest_sha256"] != receipt["local_reference_context_manifest_sha256"]
                    or receipt["source_scope_status"] != "OWNER_ADMITTED_EXACT_LOCAL_CONTEXT"
                    or any(not digest(receipt[key]) for key in LOCAL_SOURCE_FIELDS - SOURCE_FIELDS)):
                raise ValueError("P1_LOCAL_CONTEXT_ADOPTION_BINDING")
        reference = receipt["reference"]
        if not isinstance(reference, Mapping):
            raise ValueError("P1_SOURCE_REFERENCE")
        closed(reference, REFERENCE_FIELDS, "P1_SOURCE_REFERENCE_FIELDS")
        if (receipt["schema"] != ("P0-SOURCE-ADMISSION-RECEIPT-2.0" if is_local else "P0-SOURCE-ADMISSION-RECEIPT-1.0")
                or receipt["transmission_admission"] != "OWNER_ADMITTED_LOCAL_CONTENT_ONLY"
                or receipt["source_scope_status"] not in ({"OWNER_ADMITTED_EXACT_LOCAL_CONTEXT"} if is_local else {"CANONICAL_NOTION_ONLY", "EXACT_CONTEXT_ADMITTED"})
                or receipt["admission_manifest_sha256"] != permission["source_admission_manifest_sha256"]
                or receipt["owner_admission_sha256"] != source_owner
                or not digest(receipt["admission_scope_sha256"])
                or not digest(receipt["institutional_resolution_sha256"])
                or not isinstance(receipt["available_authority"], str) or not receipt["available_authority"]
                or len(receipt["available_authority"]) > 200
                or not isinstance(receipt["provenance"], Mapping) or not isinstance(receipt["source_status"], Mapping)
                or any(not isinstance(val, str) or not val for val in reference.values())
                or not digest(reference["excerpt_sha256"])):
            raise ValueError("P1_SOURCE_ADMISSION_BINDING")
        key = sha(canonical(reference))
        if key in identities:
            raise ValueError("P1_SOURCE_DUPLICATE")
        identities.add(key)
