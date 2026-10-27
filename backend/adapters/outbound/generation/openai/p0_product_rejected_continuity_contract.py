"""V2 pure known-rejection contracts. No I/O, grant, parser or live effect."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from contextlib import AbstractContextManager
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import Literal, Protocol, cast

from backend.adapters.outbound.generation.openai.p0_normal_policy import (
    BODY_FIELDS,
    TARIFF_FIELDS,
    canonical,
    closed,
    digest,
    money,
    recover_binding,
    sha,
    utc,
)
from backend.adapters.outbound.generation.openai.p0_product_continuity_contract import (
    ANCHOR_FIELDS,
    COMMON_KEYS,
    EVENT_FIELDS,
    LIMIT_KEYS,
    MANIFEST_FIELDS,
    NODE_FIELDS,
    BoundChain,
    OriginProof,
    bind_chain,
    mapping,
    validate_historical_witnesses,
    validate_slot,
)
from backend.adapters.outbound.generation.openai.p0_product_policy import (
    F1_FIELDS,
    P1_HASHES,
    validate_permission,
)
from backend.infrastructure.composition.factories.p0_normal_profile_contract import descriptor
from backend.infrastructure.composition.factories.p0_rejected_profile_contract import bind_profile4

RejectedReadPhaseKind = Literal["PREVIEW", "ACCEPT", "GENERATE"]


class P0RejectedReadPhasePort(Protocol):
    """Private composition port; the context yields no authority value."""

    def phase(self, kind: RejectedReadPhaseKind) -> AbstractContextManager[None]: ...


REJECTED_ORDER = ("RESERVED", "PROVIDER_ATTEMPTED", "RESPONSE_CAPTURED", "PARSING_REJECTED")
REJECTED_FILES = set(REJECTED_ORDER) | {"DISPATCH", "RESULT"}
TARGET_FIELDS = {
    "permission_sha256",
    "namespace_sha256",
    "request_sha256",
    "request_bytes",
    "reserved_usd",
    "output_text_sha256",
}
MANIFEST2_FIELDS = MANIFEST_FIELDS | {"rejected_dispositions"}
ANCHOR2_FIELDS = ANCHOR_FIELDS | {"original_anchor", "required_rejected_dispositions"}
DISPOSITION_FIELDS = {
    "schema",
    "disposition",
    "target_attempt",
    "observed_evidence",
    "observed_evidence_sha256",
    "adoption_decision",
    "owner_orientation_adoption",
    "owner_diagnostic",
    "source_origin_manifest_sha256",
    "operation",
    "no_grant_reuse",
    "preserve_reservation",
    "no_runtime_mutation",
}
EVIDENCE_FIELDS = {
    "schema",
    "observation_state",
    "campaign_namespace_sha256",
    "root_permission_sha256",
    "origin_permission_sha256",
    "namespace_sha256",
    "request_sha256",
    "request_bytes",
    "reserved_usd",
    "slot_sha256",
    "grant_sha256",
    "preview_sha256",
    "command_id",
    "dispatch_capture_sha256",
    "dispatch_payload_sha256",
    "preflight_sha256",
    "result_sha256",
    "output_text_sha256",
    "response_status",
    "provider_attempts",
    "event_sha256s",
    "event_timestamps",
    "usage",
    "disposition",
    "local_rejection_code",
    "owner_orientation_adoption",
    "owner_diagnostic",
    "transport_metadata_scope",
    "qualification",
    "timestamp_utc",
    "inspection_plan_sha256",
}
DISPOSITION = "TENTATIVE_CAPTUREE_REJETEE_A_CONSERVER_ET_COMPTER"
TRANSPORT_SCOPE = "NOT_RETAINED_TIER_AND_INCOMPLETE_REASON"
CAPTURE_FIELDS = {
    "schema",
    "grant_sha256",
    "dispatch_sha256",
    "request_sha256",
    "preflight_sha256",
    "namespace_sha256",
    "grant",
    "dispatch",
    "body",
    "preflight",
}


@dataclass(frozen=True)
class BoundChainV2(BoundChain):
    disposition: Mapping[str, object]
    evidence: Mapping[str, object]


def target(value: object) -> Mapping[str, object]:
    data = mapping(value, "P0_REJECTED_TARGET")
    closed(data, TARGET_FIELDS, "P0_REJECTED_TARGET_FIELDS")
    if (
        any(not digest(data[key]) for key in TARGET_FIELDS - {"request_bytes", "reserved_usd"})
        or type(data["request_bytes"]) is not int
        or not 0 < data["request_bytes"] < 250000
    ):
        raise ValueError("P0_REJECTED_TARGET_TYPES")
    money(data["reserved_usd"])
    return data


def validate_evidence(value: Mapping[str, object]) -> None:
    closed(value, EVIDENCE_FIELDS, "P0_REJECTED_EVIDENCE_FIELDS")
    fixed = {
        "schema": "P0-PRODUCT-KNOWN-REJECTED-EVIDENCE-1.0",
        "observation_state": "OBSERVED_NOT_ADOPTED",
        "response_status": "completed",
        "provider_attempts": 1,
        "disposition": DISPOSITION,
        "local_rejection_code": "P0_RICH_COURSE_NOTION_UNKNOWN",
        "transport_metadata_scope": TRANSPORT_SCOPE,
        "qualification": "REJECTED_NOT_CONSUMED",
    }
    if any(value[key] != val or type(value[key]) is not type(val) for key, val in fixed.items()):
        raise ValueError("P0_REJECTED_EVIDENCE_POLICY")
    hashes = {key for key in EVIDENCE_FIELDS if key.endswith("_sha256")}
    if any(not digest(value[key]) for key in hashes):
        raise ValueError("P0_REJECTED_EVIDENCE_HASH")
    if (
        type(value["request_bytes"]) is not int
        or not 0 < value["request_bytes"] < 250000
        or not isinstance(value["command_id"], str)
        or len(value["command_id"]) != 32
        or any(c not in "0123456789abcdef" for c in value["command_id"])
    ):
        raise ValueError("P0_REJECTED_EVIDENCE_TYPE")
    money(value["reserved_usd"])
    utc(value["timestamp_utc"])
    for key in ("owner_orientation_adoption", "owner_diagnostic"):
        descriptor(value[key])
    event_hashes = mapping(value["event_sha256s"], "P0_REJECTED_EVIDENCE_EVENTS")
    times = mapping(value["event_timestamps"], "P0_REJECTED_EVIDENCE_EVENTS")
    closed(event_hashes, set(REJECTED_ORDER), "P0_REJECTED_EVIDENCE_EVENTS")
    closed(times, set(REJECTED_ORDER), "P0_REJECTED_EVIDENCE_EVENTS")
    if any(not digest(val) for val in event_hashes.values()):
        raise ValueError("P0_REJECTED_EVIDENCE_EVENTS")
    for timestamp in times.values():
        utc(timestamp)
    usage = mapping(value["usage"], "P0_REJECTED_USAGE")
    closed(
        usage,
        {
            "input_tokens",
            "cached_input_tokens",
            "cache_write_input_tokens",
            "output_tokens",
            "reasoning_tokens",
            "total_tokens",
        },
        "P0_REJECTED_USAGE",
    )
    if any(val is not None and (type(val) is not int or val < 0) for val in usage.values()):
        raise ValueError("P0_REJECTED_USAGE")
    for part, total in (
        ("cached_input_tokens", "input_tokens"),
        ("cache_write_input_tokens", "input_tokens"),
        ("reasoning_tokens", "output_tokens"),
    ):
        if (
            usage[part] is not None
            and usage[total] is not None
            and cast(int, usage[part]) > cast(int, usage[total])
        ):
            raise ValueError("P0_REJECTED_USAGE")
    if usage["output_tokens"] is not None and cast(int, usage["output_tokens"]) > 4096:
        raise ValueError("P0_REJECTED_USAGE")
    if all(
        usage[key] is not None for key in ("input_tokens", "output_tokens", "total_tokens")
    ) and usage["total_tokens"] != cast(int, usage["input_tokens"]) + cast(
        int, usage["output_tokens"]
    ):
        raise ValueError("P0_REJECTED_USAGE")


def validate_disposition(disposition: Mapping[str, object], evidence: Mapping[str, object]) -> None:
    closed(disposition, DISPOSITION_FIELDS, "P0_REJECTED_DISPOSITION_FIELDS")
    validate_evidence(evidence)
    selected = target(disposition["target_attempt"])
    if (
        disposition["schema"] != "P0-PRODUCT-KNOWN-REJECTED-DISPOSITION-1.0"
        or disposition["disposition"] != DISPOSITION
        or disposition["operation"] != "READ_ONLY_RECONCILIATION"
        or any(
            disposition[key] is not True
            for key in ("no_grant_reuse", "preserve_reservation", "no_runtime_mutation")
        )
        or not digest(disposition["source_origin_manifest_sha256"])
    ):
        raise ValueError("P0_REJECTED_DISPOSITION_POLICY")
    for key in (
        "observed_evidence",
        "adoption_decision",
        "owner_orientation_adoption",
        "owner_diagnostic",
    ):
        descriptor(disposition[key])
    if (
        canonical(disposition["adoption_decision"])
        != canonical(disposition["owner_orientation_adoption"])
        or any(
            canonical(disposition[key]) != canonical(evidence[key])
            for key in ("owner_orientation_adoption", "owner_diagnostic")
        )
        or disposition["observed_evidence_sha256"] != sha(canonical(evidence))
        or descriptor(disposition["observed_evidence"])["sha256"] != sha(canonical(evidence))
        or any(
            selected[key]
            != evidence[{"permission_sha256": "origin_permission_sha256"}.get(key, key)]
            for key in TARGET_FIELDS
        )
    ):
        raise ValueError("P0_REJECTED_DISPOSITION_BINDING")


def validate_captured_rejection(
    chain: BoundChain,
    record: Mapping[str, object],
    *,
    selected: Mapping[str, object],
    files: Mapping[str, Mapping[str, object]],
    raw_hashes: Mapping[str, str],
    tariff: Mapping[str, object],
) -> None:
    """Checks retained bytes only; never reparse, recover, repair or qualify text."""
    target(selected)
    if set(files) != REJECTED_FILES or set(raw_hashes) != REJECTED_FILES:
        raise ValueError("P0_REJECTED_EXACT_EVENT_SET_REQUIRED")
    if any(
        not digest(raw_hashes[key]) or raw_hashes[key] != sha(canonical(files[key]))
        for key in REJECTED_FILES
    ):
        raise ValueError("P0_REJECTED_RAW_HASH_BINDING")
    origin = validate_slot(
        chain,
        record,
        file_name=str(chain.manifest["campaign_namespace_sha256"])
        + ".P1."
        + str(record["preview_sha256"])
        + ".json",
    )
    grant = mapping(record["grant"], "P0_REJECTED_GRANT")
    if (
        any(
            record[key] != selected[key]
            for key in ("permission_sha256", "namespace_sha256", "request_sha256")
        )
        or grant["request_bytes"] != selected["request_bytes"]
        or money(record["reserved_usd"]) != money(selected["reserved_usd"])
    ):
        raise ValueError("P0_REJECTED_SLOT_TARGET_BINDING")
    capture = files["DISPATCH"]
    closed(capture, CAPTURE_FIELDS, "P0_REJECTED_CAPTURE_FIELDS")
    dispatch = mapping(capture["dispatch"], "P0_REJECTED_CAPTURE_DISPATCH")
    proof = mapping(capture["preflight"], "P0_REJECTED_CAPTURE_PREFLIGHT")
    closed(proof, F1_FIELDS, "P0_REJECTED_CAPTURE_PREFLIGHT_FIELDS")
    body = capture["body"]
    if (
        not isinstance(body, str)
        or len(body.encode()) != selected["request_bytes"]
        or sha(body.encode()) != selected["request_sha256"]
        or capture["schema"] != "P0-NORMAL-DISPATCH-CAPTURE-1.0"
        or canonical(capture["grant"]) != canonical(grant)
        or capture["grant_sha256"] != record["grant_sha256"]
        or capture["request_sha256"] != record["request_sha256"]
        or capture["namespace_sha256"] != record["namespace_sha256"]
        or capture["dispatch_sha256"] != sha(canonical(dispatch))
        or capture["preflight_sha256"] != sha(canonical(proof))
        or capture["preflight_sha256"] != record["preflight_sha256"]
    ):
        raise ValueError("P0_REJECTED_CAPTURE_BINDING")
    from backend.adapters.outbound.generation.openai.p0_normal_receipt import decode

    wire = decode(body.encode())
    closed(wire, BODY_FIELDS, "P0_REJECTED_HISTORICAL_BODY_FIELDS")
    form = mapping(
        mapping(wire["text"], "P0_REJECTED_BODY_FORMAT")["format"], "P0_REJECTED_BODY_FORMAT"
    )
    if (
        wire["model"] != grant["model"]
        or wire["reasoning"] != {"effort": "low"}
        or wire["service_tier"] != "default"
        or wire["tools"] != []
        or wire["tool_choice"] != "none"
        or any(wire[key] is not False for key in ("background", "stream", "store"))
        or type(wire["max_output_tokens"]) is not int
        or wire["max_output_tokens"] != 4096
        or set(form) != {"name", "type", "strict", "schema"}
        or form["name"] != "p0_pedagogical_content"
        or form["type"] != "json_schema"
        or form["strict"] is not True
        or sha(canonical(form["schema"])) != grant["output_schema_sha256"]
        or dispatch.get("context_sha256") != grant["context_sha256"]
        or sha(canonical(dispatch)) != grant["preparation_sha256"]
        or sha(canonical(dispatch.get("context"))) != grant["context_sha256"]
        or sha(canonical(dispatch.get("references"))) != grant["reference_set_sha256"]
    ):
        raise ValueError("P0_REJECTED_HISTORICAL_BODY_BINDING")
    fixed = {
        "schema": "P0-NORMAL-PREFLIGHT-1.0",
        "structural_reserve_tokens": 10000,
        "max_output_tokens": 4096,
        "count_calls": 0,
        "retry": 0,
        "fallback": "NONE",
        "status": "LOCAL_POLICY_CHECKED",
    }
    if (
        any(proof[key] != val or type(proof[key]) is not type(val) for key, val in fixed.items())
        or proof["request_sha256"] != record["request_sha256"]
        or proof["request_bytes"] != grant["request_bytes"]
        or type(proof["local_text_tokens"]) is not int
        or proof["local_text_tokens"] < 1
        or type(proof["input_upper_tokens"]) is not int
        or proof["input_upper_tokens"] != proof["local_text_tokens"] + 10000
        or proof["input_upper_tokens"] > 40000
        or not digest(proof["tokenizer_sha256"])
        or proof["tariff_sha256"] != grant["tariff_sha256"]
        or sha(canonical(tariff)) != grant["tariff_sha256"]
        or money(proof["ceiling_usd"]) != money(grant["ceiling_usd"])
        or money(proof["cost_bound_usd"]) != money(record["reserved_usd"])
    ):
        raise ValueError("P0_REJECTED_HISTORICAL_PREFLIGHT_BINDING")
    closed(tariff, TARIFF_FIELDS, "P0_REJECTED_TARIFF_FIELDS")
    if (
        tariff["schema"] != "P0-NORMAL-TARIFF-1.0"
        or tariff["model"] != grant["model"]
        or tariff["provider"] != "OPENAI"
        or tariff["tier"] != "default"
        or not digest(tariff["evidence_sha256"])
        or not digest(tariff["owner_admission_sha256"])
        or money(tariff["input_multiplier"]) < 1
        or utc(tariff["retrieved_at_utc"]) > utc(grant["issued_at_utc"])
    ):
        raise ValueError("P0_REJECTED_TARIFF_BINDING")
    expected_cost = (
        Decimal(proof["input_upper_tokens"])
        * money(tariff["input_usd_per_million"])
        * money(tariff["input_multiplier"])
        + Decimal(4096) * money(tariff["output_usd_per_million"])
    ) / Decimal(1000000)
    if expected_cost != money(record["reserved_usd"]) or expected_cost > money(
        origin.permission["per_call_ceiling_usd"]
    ):
        raise ValueError("P0_REJECTED_HISTORICAL_FINANCIAL_BINDING")
    artifact = files["RESULT"]
    text = recover_binding(
        artifact=artifact,
        grant_sha256=str(record["grant_sha256"]),
        request_sha256=str(record["request_sha256"]),
        dispatch_sha256=str(capture["dispatch_sha256"]),
    )
    if sha(text.encode()) != selected["output_text_sha256"]:
        raise ValueError("P0_REJECTED_OUTPUT_HASH_BINDING")
    previous = utc(grant["issued_at_utc"])
    for state in REJECTED_ORDER:
        event = files[state]
        closed(event, EVENT_FIELDS, "P0_REJECTED_EVENT_FIELDS")
        timestamp = utc(event["timestamp_utc"])
        if (
            event["schema"] != "P0-NORMAL-TECHNICAL-RECEIPT-1.0"
            or event["state"] != state
            or any(
                event[key] != record[key]
                for key in (
                    "grant_sha256",
                    "request_sha256",
                    "preflight_sha256",
                    "namespace_sha256",
                )
            )
            or money(event["reserved_usd"]) != money(record["reserved_usd"])
            or type(event["provider_attempts"]) is not int
            or event["provider_attempts"] != (0 if state == "RESERVED" else 1)
            or event["observed_cost_status"] != "NOT_ESTABLISHED"
            or not previous <= timestamp < utc(grant["expires_at_utc"])
        ):
            raise ValueError("P0_REJECTED_EVENT_BINDING")
        if state == "RESPONSE_CAPTURED":
            if (
                event["response_status"] != "completed"
                or event["response_artifact_sha256"] != raw_hashes["RESULT"]
                or canonical(event["usage"]) != canonical(artifact["usage"])
            ):
                raise ValueError("P0_REJECTED_RESPONSE_BINDING")
        elif any(
            event[key] is not None
            for key in ("response_status", "response_artifact_sha256", "usage")
        ):
            raise ValueError("P0_REJECTED_NON_RESPONSE_FIELDS")
        previous = timestamp


def observed_evidence(
    chain: BoundChain,
    record: Mapping[str, object],
    *,
    files: Mapping[str, Mapping[str, object]],
    raw_hashes: Mapping[str, str],
    selected: Mapping[str, object],
    plan_sha256: str,
    orientation: Mapping[str, object],
    diagnostic: Mapping[str, object],
    now: datetime,
) -> dict[str, object]:
    """Only called after native checks; this pure projection does not adopt it."""
    capture, artifact = files["DISPATCH"], files["RESULT"]
    result = {
        "schema": "P0-PRODUCT-KNOWN-REJECTED-EVIDENCE-1.0",
        "observation_state": "OBSERVED_NOT_ADOPTED",
        "campaign_namespace_sha256": chain.manifest["campaign_namespace_sha256"],
        "root_permission_sha256": chain.root.permission_sha256,
        "origin_permission_sha256": record["permission_sha256"],
        "namespace_sha256": record["namespace_sha256"],
        "request_sha256": record["request_sha256"],
        "request_bytes": selected["request_bytes"],
        "reserved_usd": record["reserved_usd"],
        "slot_sha256": sha(canonical(record)),
        "grant_sha256": record["grant_sha256"],
        "preview_sha256": record["preview_sha256"],
        "command_id": record["command_id"],
        "dispatch_capture_sha256": raw_hashes["DISPATCH"],
        "dispatch_payload_sha256": capture["dispatch_sha256"],
        "preflight_sha256": record["preflight_sha256"],
        "result_sha256": raw_hashes["RESULT"],
        "output_text_sha256": selected["output_text_sha256"],
        "response_status": "completed",
        "provider_attempts": 1,
        "event_sha256s": {key: raw_hashes[key] for key in REJECTED_ORDER},
        "event_timestamps": {key: files[key]["timestamp_utc"] for key in REJECTED_ORDER},
        "usage": artifact["usage"],
        "disposition": DISPOSITION,
        "local_rejection_code": "P0_RICH_COURSE_NOTION_UNKNOWN",
        "owner_orientation_adoption": dict(orientation),
        "owner_diagnostic": dict(diagnostic),
        "transport_metadata_scope": TRANSPORT_SCOPE,
        "qualification": "REJECTED_NOT_CONSUMED",
        "timestamp_utc": now.isoformat(),
        "inspection_plan_sha256": plan_sha256,
    }
    validate_evidence(result)
    return result


def bind_chain_v2(
    manifest: Mapping[str, object],
    ancestors: Sequence[OriginProof],
    current: OriginProof,
    *,
    anchor: Mapping[str, object],
    original_anchor: Mapping[str, object],
    ancestor_manifests: Mapping[str, Mapping[str, object]],
    disposition: Mapping[str, object],
    evidence: Mapping[str, object],
) -> BoundChainV2:
    """Closed exact prefix; the factory verifies external adoption separately."""
    closed(manifest, MANIFEST2_FIELDS, "P0_REJECTED_MANIFEST_FIELDS")
    closed(anchor, ANCHOR2_FIELDS, "P0_REJECTED_ANCHOR_FIELDS")
    closed(original_anchor, ANCHOR_FIELDS, "P0_REJECTED_ORIGINAL_ANCHOR_FIELDS")
    validate_disposition(disposition, evidence)
    selected_descriptor = descriptor(
        mapping(current.envelope["profile"], "P0_REJECTED_PROFILE")["rejected_disposition"]
    )
    for values in (manifest["rejected_dispositions"], anchor["required_rejected_dispositions"]):
        if (
            not isinstance(values, list)
            or len(values) != 1
            or canonical(values[0]) != canonical(selected_descriptor)
        ):
            raise ValueError("P0_REJECTED_SINGLE_DISPOSITION_REQUIRED")
    if (
        manifest["schema"] != "P0-PRODUCT-CONTINUITY-MANIFEST-2.0"
        or anchor["schema"] != "P0-PRODUCT-CONTINUITY-ANCHOR-2.0"
        or descriptor(anchor["original_anchor"])["sha256"] != sha(canonical(original_anchor))
        or canonical(anchor["required_historical_reservations"])
        != canonical(original_anchor["required_historical_reservations"])
        or not cast(list[object], anchor["required_historical_reservations"])
        or manifest["conditions_sha256"] != descriptor(anchor["conditions"])["sha256"]
        or manifest["implementation_decision_sha256"]
        != descriptor(anchor["implementation_decision"])["sha256"]
        or descriptor(manifest["continuity_anchor"])["sha256"] != sha(canonical(anchor))
        or any(
            anchor[key] != original_anchor[key] or manifest[key] != anchor[key]
            for key in ("root_permission_sha256", "campaign_namespace_sha256")
        )
    ):
        raise ValueError("P0_REJECTED_ANCHOR_BINDING")
    nodes = manifest["ancestors"]
    if (
        not isinstance(nodes, list)
        or not ancestors
        or len(nodes) != len(ancestors)
        or len(nodes) > 14
    ):
        raise ValueError("P0_REJECTED_CHAIN_REQUIRED")
    previous: str | None = None
    seen: set[str] = set()
    for index, (raw_node, proof) in enumerate(zip(nodes, ancestors, strict=True)):
        node = mapping(raw_node, "P0_REJECTED_NODE")
        closed(node, NODE_FIELDS, "P0_REJECTED_NODE_FIELDS")
        if (
            proof.permission_sha256 in seen
            or node["permission_sha256"] != proof.permission_sha256
            or node["parent_permission_sha256"] != previous
            or descriptor(node["profile_envelope"])["sha256"] != sha(canonical(proof.envelope))
            or canonical(node["permission"]) != canonical(proof.envelope["permission"])
            or canonical(node["owner_decision"]) != canonical(proof.envelope["decision"])
        ):
            raise ValueError("P0_REJECTED_NODE_BINDING")
        profile = mapping(proof.envelope["profile"], "P0_REJECTED_PROFILE")
        schema = profile.get("schema")
        if schema == "P0-NORMAL-PROFILE-3.0":
            prior = ancestor_manifests.get(proof.permission_sha256)
            if prior is None:
                raise ValueError("P0_REJECTED_ANCESTOR_MANIFEST_MISSING")
            bind_chain(
                prior,
                ancestors[:index],
                proof,
                ancestor_manifests=ancestor_manifests,
                anchor=original_anchor,
            )
        elif schema == "P0-NORMAL-PROFILE-4.0":
            prior = ancestor_manifests.get(proof.permission_sha256)
            if prior is None:
                raise ValueError("P0_REJECTED_ANCESTOR_MANIFEST_MISSING")
            bind_chain_v2(
                prior,
                ancestors[:index],
                proof,
                anchor=anchor,
                original_anchor=original_anchor,
                ancestor_manifests=ancestor_manifests,
                disposition=disposition,
                evidence=evidence,
            )
        elif index == 0 and schema in {"P0-NORMAL-PROFILE-1.0", "P0-NORMAL-PROFILE-2.0"}:
            from backend.infrastructure.composition.factories.p0_normal_profile_contract import (
                bind_profile,
            )

            bind_profile(
                proof.envelope,
                permission=proof.permission,
                decision=proof.decision,
                delegation=proof.delegation,
                operator=proof.operator,
            )
        else:
            raise ValueError("P0_REJECTED_ORIGIN_VERSION")
        if schema in {"P0-NORMAL-PROFILE-3.0", "P0-NORMAL-PROFILE-4.0"}:
            prior = ancestor_manifests[proof.permission_sha256]
            if (
                canonical(prior["ancestors"]) != canonical(nodes[:index])
                or prior["root_permission_sha256"] != manifest["root_permission_sha256"]
                or any(
                    canonical(witness)
                    not in {
                        canonical(v)
                        for v in cast(list[object], manifest["historical_reservations"])
                    }
                    for witness in cast(list[object], prior["historical_reservations"])
                )
            ):
                raise ValueError("P0_REJECTED_ANCESTOR_PREFIX")
        seen.add(proof.permission_sha256)
        previous = proof.permission_sha256
    root = ancestors[0]
    if (
        current.permission_sha256 in seen
        or manifest["parent_permission_sha256"] != previous
        or manifest["root_permission_sha256"] != root.permission_sha256
        or manifest["root_lock_sha256"]
        != sha(canonical({"permission_sha256": root.permission_sha256}))
        or selected_descriptor["sha256"] != sha(canonical(disposition))
    ):
        raise ValueError("P0_REJECTED_ROOT_TIP_BINDING")
    bind_profile4(current, manifest=manifest, anchor=anchor, disposition=disposition)
    common = mapping(manifest["common_identities"], "P0_REJECTED_COMMON")
    limits = mapping(manifest["campaign_limits"], "P0_REJECTED_LIMITS")
    window = mapping(manifest["campaign_window"], "P0_REJECTED_WINDOW")
    closed(common, COMMON_KEYS, "P0_REJECTED_COMMON_FIELDS")
    closed(limits, LIMIT_KEYS, "P0_REJECTED_LIMIT_FIELDS")
    closed(window, {"issued_at_utc", "expires_at_utc"}, "P0_REJECTED_WINDOW_FIELDS")
    root_profile = mapping(root.envelope["profile"], "P0_REJECTED_ROOT_PROFILE")
    for proof in (*ancestors, current):
        permission = proof.permission
        profile = mapping(proof.envelope["profile"], "P0_REJECTED_PROFILE")
        families, levels = permission.get("allowed_families"), permission.get("allowed_levels")
        if (
            not isinstance(families, list)
            or not families
            or not isinstance(levels, list)
            or not levels
        ):
            raise ValueError("P0_REJECTED_PERMISSION_SCOPE")
        validate_permission(
            permission,
            identities={key: permission.get(key) for key in P1_HASHES | {"baseline_commit"}},
            now=utc(permission["issued_at_utc"]),
            family=str(families[0]),
            level=str(levels[0]),
        )
        if (
            permission["permission_namespace_sha256"] != manifest["campaign_namespace_sha256"]
            or any(
                permission.get(key) != common[key]
                for key in COMMON_KEYS - {"saved_root_native_sha256"}
            )
            or proof.saved_root_native_sha256 != common["saved_root_native_sha256"]
            or any(
                permission[key] != limits[key] or limits[key] != root.permission[key]
                for key in LIMIT_KEYS
            )
            or any(window[key] != root.permission[key] for key in window)
            or not utc(window["issued_at_utc"])
            <= utc(permission["issued_at_utc"])
            < utc(permission["expires_at_utc"])
            <= utc(window["expires_at_utc"])
            or not set(families) <= set(cast(list[str], root.permission["allowed_families"]))
            or not set(levels) <= set(cast(list[str], root.permission["allowed_levels"]))
            or any(profile[key] != root_profile[key] for key in ("saved_root", "receipt_root"))
            or canonical(profile["runtime"]) != canonical(root_profile["runtime"])
            or profile["institutional_catalog_sha256"] != common["institutional_catalog_sha256"]
            or any(
                canonical(profile[key]) != canonical(root_profile[key])
                for key in (
                    "operator_delegation",
                    "tokenizer_manifest",
                    "tariff",
                    "tariff_evidence",
                )
            )
        ):
            raise ValueError("P0_REJECTED_COMMON_CHANGED")
    profile = mapping(current.envelope["profile"], "P0_REJECTED_PROFILE")
    owners = [
        proof
        for proof in ancestors
        if sha(canonical(proof.decision))
        == descriptor(profile["source_admission_owner_decision"])["sha256"]
    ]
    if len(owners) != 1 or canonical(profile["source_admission_owner_decision"]) != canonical(
        owners[0].envelope["decision"]
    ):
        raise ValueError("P0_REJECTED_SOURCE_OWNER_BINDING")
    original = mapping(owners[0].envelope["profile"], "P0_REJECTED_SOURCE_PROFILE")
    for key in ("source_admission_manifest", "local_reference_context_manifest"):
        if canonical(profile[key]) != canonical(original[key]):
            raise ValueError("P0_REJECTED_SOURCE_ADMISSION_CHANGED")
    origin = next(
        (
            proof
            for proof in ancestors
            if proof.permission_sha256 == evidence["origin_permission_sha256"]
        ),
        None,
    )
    if (
        origin is None
        or evidence["root_permission_sha256"] != root.permission_sha256
        or evidence["campaign_namespace_sha256"] != manifest["campaign_namespace_sha256"]
        or descriptor(
            mapping(origin.envelope["profile"], "P0_REJECTED_CAPTURE_ORIGIN")["source_manifest"]
        )["sha256"]
        != disposition["source_origin_manifest_sha256"]
    ):
        raise ValueError("P0_REJECTED_EVIDENCE_ORIGIN_BINDING")
    return BoundChainV2(manifest, anchor, (*ancestors, current), disposition, evidence)


def reservation_totals(
    chain: BoundChain, records: Sequence[Mapping[str, object]]
) -> tuple[int, Decimal, Decimal]:
    validate_historical_witnesses(chain, records)
    total = sum((money(record["reserved_usd"]) for record in records), Decimal(0))
    ceiling = money(chain.root.permission["cumulative_ceiling_usd"])
    if len(records) > cast(int, chain.root.permission["max_calls"]) or total > ceiling:
        raise ValueError("P0_REJECTED_OVERBUDGET")
    for key in ("namespace_sha256", "preview_sha256", "command_id"):
        if len({record[key] for record in records}) != len(records):
            raise ValueError("P0_REJECTED_AMBIGUOUS_SLOTS")
    return len(records), total, ceiling


def snapshot_v2(
    chain: BoundChainV2, records: Sequence[Mapping[str, object]], *, now: datetime
) -> dict[str, object]:
    count, total, ceiling = reservation_totals(chain, records)
    profile = mapping(chain.current.envelope["profile"], "P0_REJECTED_PROFILE")
    return {
        "schema": "P0-PRODUCT-CAMPAIGN-SNAPSHOT-2.0",
        "state": "CURRENT_RESERVATIONS_RECONCILED",
        "timestamp_utc": now.isoformat(),
        "root_permission_sha256": chain.root.permission_sha256,
        "current_permission_sha256": chain.current.permission_sha256,
        "campaign_namespace_sha256": chain.manifest["campaign_namespace_sha256"],
        "slots_reserved": count,
        "reserved_budget_usd": str(total),
        "remaining_calls": cast(int, chain.root.permission["max_calls"]) - count,
        "remaining_reserved_budget_usd": str(ceiling - total),
        "financial_basis": "RESERVATIONS_NOT_BILLED_COST",
        "live_enabled": profile["continuity_enabled"] is True
        and utc(chain.current.permission["issued_at_utc"])
        <= now
        < utc(chain.current.permission["expires_at_utc"]),
        "known_rejected_count": 1,
        "consumed_count": count - 1,
        "disposition_sha256": sha(canonical(chain.disposition)),
        "inspection_scope": "EXACT_ADOPTED_CAMPAIGN_READ_ONLY",
        "historic_transport_scope": TRANSPORT_SCOPE,
        "course_qualification": "NOT_COMPLETED",
        "current_context_contract_scope": "EXACT_ADOPTED_SOURCE_CONTEXTS_ONLY",
        "observation_plan_sha256": chain.evidence["inspection_plan_sha256"],
    }
