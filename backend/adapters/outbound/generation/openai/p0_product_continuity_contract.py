"""Closed continuity contracts; no I/O, SDK, grant or live authority.

Only protected composition supplies private campaign anchors. P1/G1 retain
their original predicates; each reservation is validated against its origin.
"""
from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import cast

from backend.adapters.outbound.generation.openai.p0_normal_policy import (
    HASH_FIELDS,
    canonical,
    closed,
    digest,
    money,
    sha,
    utc,
    validate_grant,
)
from backend.adapters.outbound.generation.openai.p0_product_ledger import SLOT_FIELDS
from backend.adapters.outbound.generation.openai.p0_product_policy import (
    P1_HASHES,
    validate_permission,
)
from backend.infrastructure.composition.factories.p0_normal_profile_contract import (
    DECISION_CONTEXT_FIELDS,
    DELEGATION_FIELDS,
    DESCRIPTORS,
    PROFILE_CONTEXT_FIELDS,
    absolute,
    bind_profile,
    descriptor,
)

MANIFEST_FIELDS = {"schema", "implementation_decision_sha256", "conditions_sha256",
    "root_permission_sha256", "root_lock_sha256", "parent_permission_sha256",
    "campaign_namespace_sha256", "campaign_window", "campaign_limits",
    "common_identities", "ancestors", "historical_reservations", "continuity_anchor"}
ANCHOR_FIELDS = {"schema", "implementation_decision", "conditions", "root_permission_sha256",
    "campaign_namespace_sha256", "required_historical_reservations"}
WITNESS_FIELDS = {"permission_sha256", "namespace_sha256", "request_sha256", "reserved_usd", "metadata_evidence"}
NODE_FIELDS = {"permission_sha256", "parent_permission_sha256", "permission",
    "profile_envelope", "owner_decision"}
PROFILE3_FIELDS = PROFILE_CONTEXT_FIELDS | {"continuity_manifest", "continuity_anchor",
    "source_admission_owner_decision", "continuity_enabled"}
DECISION3_FIELDS = DECISION_CONTEXT_FIELDS | {"continuity_manifest_sha256", "continuity_anchor_sha256",
    "parent_permission_sha256", "source_admission_owner_decision_sha256"}
COMMON_KEYS = {"runtime_sha256", "receipt_root_sha256", "saved_root_native_sha256",
    "operator_delegation_sha256", "tariff_sha256", "tokenizer_manifest_sha256",
    "institutional_catalog_sha256"}
LIMIT_KEYS = {"max_calls", "per_call_ceiling_usd", "cumulative_ceiling_usd",
    "max_output_tokens", "count_calls", "review_calls", "modify_calls", "retry",
    "fallback", "parallelism"}
EVENT_FIELDS = {"schema", "grant_sha256", "request_sha256", "preflight_sha256",
    "namespace_sha256", "state", "timestamp_utc", "provider_attempts",
    "response_status", "response_artifact_sha256", "usage", "reserved_usd",
    "observed_cost_status"}
EVENT_ORDER = ("RESERVED", "PROVIDER_ATTEMPTED", "RESPONSE_CAPTURED", "PARSED", "CONSUMED")


def mapping(value: object, code: str) -> Mapping[str, object]:
    if not isinstance(value, Mapping):
        raise ValueError(code)
    return value


@dataclass(frozen=True)
class OriginProof:
    """All mappings and their file SHA are freshly revalidated by the FS loader."""
    permission: Mapping[str, object]
    envelope: Mapping[str, object]
    decision: Mapping[str, object]
    delegation: Mapping[str, object]
    operator: Mapping[str, object]
    saved_root_native_sha256: str

    @property
    def permission_sha256(self) -> str:
        return sha(canonical(self.permission))


@dataclass(frozen=True)
class BoundChain:
    manifest: Mapping[str, object]
    anchor: Mapping[str, object]
    origins: tuple[OriginProof, ...]  # root through exact current tip

    @property
    def current(self) -> OriginProof:
        return self.origins[-1]

    @property
    def root(self) -> OriginProof:
        return self.origins[0]


def validate_historical_witnesses(chain: BoundChain, records: Sequence[Mapping[str, object]]) -> None:
    witnesses = chain.manifest["historical_reservations"]
    if not isinstance(witnesses, list) or not witnesses or len(witnesses) > 14:
        raise ValueError("P0_CONTINUITY_HISTORICAL_WITNESSES_REQUIRED")
    known_origins = {proof.permission_sha256 for proof in chain.origins}
    namespaces: set[str] = set()
    required_witnesses = chain.anchor["required_historical_reservations"]
    if not isinstance(required_witnesses, list) or not required_witnesses:
        raise ValueError("P0_CONTINUITY_PRIVATE_ANCHOR_REQUIRED")
    for raw in witnesses:
        witness = mapping(raw, "P0_CONTINUITY_HISTORICAL_WITNESS")
        closed(witness, WITNESS_FIELDS, "P0_CONTINUITY_HISTORICAL_WITNESS_FIELDS")
        descriptor(witness["metadata_evidence"])
        if (witness["permission_sha256"] not in known_origins
                or not digest(witness["namespace_sha256"]) or not digest(witness["request_sha256"])
                or witness["namespace_sha256"] in namespaces):
            raise ValueError("P0_CONTINUITY_HISTORICAL_WITNESS_BINDING")
        money(witness["reserved_usd"])
        namespaces.add(str(witness["namespace_sha256"]))
        matching = [record for record in records if record["namespace_sha256"] == witness["namespace_sha256"]]
        if (len(matching) != 1 or any(matching[0][key] != witness[key]
                for key in ("permission_sha256", "namespace_sha256", "request_sha256"))
                or money(matching[0]["reserved_usd"]) != money(witness["reserved_usd"])):
            raise ValueError("P0_CONTINUITY_ATTESTED_RESERVATION_MISSING_OR_CHANGED")
    if any(canonical(required) not in {canonical(value) for value in witnesses}
           for required in required_witnesses):
        raise ValueError("P0_CONTINUITY_KNOWN_ORIGIN_RESERVATION_REQUIRED")
    # Loader must read each exact metadata_evidence file, validate its SHA and
    # closed historical schema, and compare campaign/origin/ns/request/cost.
    # Those file bytes are not opened or asserted authentic by this pure seam.


def reject_orphan_namespaces(chain: BoundChain, records: Sequence[Mapping[str, object]], *,
                             normal_namespaces: Mapping[str, Mapping[str, object] | None]) -> None:
    """No attribution of an unrelated namespace to this campaign by directory.

    For every normal-receipt namespace discovered by the adapter, an unknown
    namespace needs an exact DISPATCH grant to classify. Missing or unrelated
    origin means ambiguity STOP, never an added charge or ignored old reserve.
    """
    slots = {record["namespace_sha256"] for record in records}
    for namespace, capture in normal_namespaces.items():
        if not digest(namespace):
            raise ValueError("P0_CONTINUITY_NORMAL_NAMESPACE_AMBIGUOUS")
        if namespace in slots:
            continue
        if capture is None:
            raise ValueError("P0_CONTINUITY_NORMAL_CAMPAIGN_UNIDENTIFIED")
        grant = mapping(capture.get("grant"), "P0_CONTINUITY_NORMAL_CAMPAIGN_UNIDENTIFIED")
        matched = [proof for proof in chain.origins if all(grant.get(key) == proof.permission[key]
            for key in (HASH_FIELDS & proof.permission.keys()) | {"baseline_commit"})]
        if len(matched) != 1 or grant.get("namespace_sha256") != namespace:
            raise ValueError("P0_CONTINUITY_NORMAL_CAMPAIGN_UNIDENTIFIED")
        validate_grant(grant, identities={key: grant[key] for key in HASH_FIELDS | {"baseline_commit", "request_bytes"}},
            now=utc(grant["issued_at_utc"]))
        # A grant of an exact known origin is this campaign, yet its slot is
        # absent: do not invent a replacement record or a smaller budget.
        raise ValueError("P0_CONTINUITY_CAMPAIGN_RECEIPT_ORPHAN")


def _permission(proof: OriginProof) -> None:
    permission = proof.permission
    families, levels = permission.get("allowed_families"), permission.get("allowed_levels")
    if not isinstance(families, list) or not families or not isinstance(levels, list) or not levels:
        raise ValueError("P0_CONTINUITY_ORIGIN_SCOPE")
    identities = {key: permission.get(key) for key in P1_HASHES | {"baseline_commit"}}
    # Historical window validation is intentionally at its own issue time.
    validate_permission(permission, identities=identities, now=utc(permission["issued_at_utc"]),
        family=str(families[0]), level=str(levels[0]))
    profile = mapping(proof.envelope.get("profile"), "P0_CONTINUITY_PROFILE")
    if profile.get("schema") in {"P0-NORMAL-PROFILE-1.0", "P0-NORMAL-PROFILE-2.0"}:
        bind_profile(proof.envelope, permission=permission, decision=proof.decision,
            delegation=proof.delegation, operator=proof.operator)
    elif profile.get("schema") != "P0-NORMAL-PROFILE-3.0":
        raise ValueError("P0_CONTINUITY_PROFILE_SCHEMA")
    if not digest(proof.saved_root_native_sha256):
        raise ValueError("P0_CONTINUITY_SAVED_ROOT_IDENTITY")
    # Native identities and package hashes are external freshly read facts,
    # never established merely by these claimed identities.


def _profile3(proof: OriginProof, manifest: Mapping[str, object], anchor: Mapping[str, object]) -> None:
    closed(proof.envelope, {"schema", "profile", "permission", "decision"}, "P0_CONTINUITY_ENVELOPE_FIELDS")
    if proof.envelope["schema"] != "P0-NORMAL-PROFILE-ENVELOPE-1.0":
        raise ValueError("P0_CONTINUITY_ENVELOPE_SCHEMA")
    profile = mapping(proof.envelope.get("profile"), "P0_CONTINUITY_PROFILE")
    closed(profile, PROFILE3_FIELDS, "P0_CONTINUITY_PROFILE_FIELDS")
    closed(proof.decision, DECISION3_FIELDS, "P0_CONTINUITY_DECISION_FIELDS")
    if (profile["schema"] != "P0-NORMAL-PROFILE-3.0"
            or type(profile["continuity_enabled"]) is not bool
            or proof.decision["schema"] != "P0-NORMAL-OWNER-DECISION-3.0"
            or proof.decision["status"] != "ADOPTED"):
        raise ValueError("P0_CONTINUITY_PROFILE_ADOPTION")
    if any(proof.decision[k] is not True for k in
            ("excluded_oracles_and_private_evidence", "source_authority_unknown_preserved",
             "local_operator_delegation_accepted")):
        raise ValueError("P0_CONTINUITY_OWNER_DISPOSITION")
    baseline = profile["baseline_commit"]
    if (not isinstance(baseline, str) or len(baseline) != 40
            or any(char not in "0123456789abcdef" for char in baseline)
            or baseline != proof.permission["baseline_commit"]):
        raise ValueError("P0_CONTINUITY_BASELINE")
    for key in DESCRIPTORS | {"local_reference_context_manifest", "continuity_manifest", "continuity_anchor", "source_admission_owner_decision"}:
        descriptor(profile[key])
    for key in ("saved_root", "receipt_root"):
        absolute(profile[key])
    if str(profile["saved_root"]).casefold() == str(profile["receipt_root"]).casefold():
        raise ValueError("P0_CONTINUITY_DISTINCT_STORES")
    runtime = mapping(profile["runtime"], "P0_CONTINUITY_RUNTIME")
    closed(runtime, {"path", "data_root", "sha256"}, "P0_CONTINUITY_RUNTIME_FIELDS")
    absolute(runtime["path"])
    absolute(runtime["data_root"])
    if runtime["sha256"] != proof.permission["runtime_sha256"]:
        raise ValueError("P0_CONTINUITY_RUNTIME_BINDING")
    if profile["institutional_catalog_sha256"] != proof.permission["institutional_catalog_sha256"]:
        raise ValueError("P0_CONTINUITY_PROFILE_CATALOG_BINDING")
    for component in ("operator_delegation", "tokenizer_manifest", "tariff", "source_admission_manifest"):
        if descriptor(profile[component])["sha256"] != proof.permission[component + "_sha256"]:
            raise ValueError("P0_CONTINUITY_PROFILE_COMMON_BINDING")
    credential = profile["credential_ref"]
    if (not isinstance(credential, str) or not credential or len(credential) > 128
            or credential.startswith("sk-")):
        raise ValueError("P0_CONTINUITY_LOGICAL_CREDENTIAL")
    closed(proof.delegation, DELEGATION_FIELDS, "P0_CONTINUITY_DELEGATION_FIELDS")
    if (proof.delegation["schema"] != "P0-LOCAL-OPERATOR-DELEGATION-1.0"
            or proof.delegation["local_operator_delegation_accepted"] is not True
            or proof.delegation["credential_ref"] != credential
            or any(proof.delegation[key] != proof.operator.get(key) for key in ("windows_sid", "windows_profile"))
            or sha(canonical(proof.delegation)) != descriptor(profile["operator_delegation"])["sha256"]):
        raise ValueError("P0_CONTINUITY_DELEGATION_BINDING")
    expected = {
        "profile_sha256": sha(canonical(profile)),
        "permission_policy_sha256": sha(canonical({k: v for k, v in proof.permission.items()
                                                  if k != "owner_decision_sha256"})),
        "continuity_manifest_sha256": sha(canonical(manifest)),
        "continuity_anchor_sha256": sha(canonical(anchor)),
        "parent_permission_sha256": manifest["parent_permission_sha256"],
        "source_admission_owner_decision_sha256":
            descriptor(profile["source_admission_owner_decision"])["sha256"],
    }
    for key in ("source_admission_manifest", "local_reference_context_manifest",
                "operator_delegation", "tokenizer_manifest", "tariff"):
        expected[key + "_sha256"] = descriptor(profile[key])["sha256"]
    if any(proof.decision[key] != value for key, value in expected.items()):
        raise ValueError("P0_CONTINUITY_PROFILE_BINDING")
    if (descriptor(profile["continuity_manifest"])["sha256"] != sha(canonical(manifest))
            or descriptor(profile["continuity_anchor"])["sha256"] != sha(canonical(anchor))
            or descriptor(manifest["continuity_anchor"])["sha256"] != sha(canonical(anchor))
            or proof.permission["profile_sha256"] != expected["profile_sha256"]
            or descriptor(proof.envelope["decision"])["sha256"] != sha(canonical(proof.decision))
            or proof.permission["owner_decision_sha256"] != sha(canonical(proof.decision))
            or descriptor(proof.envelope["permission"])["sha256"] != proof.permission_sha256):
        raise ValueError("P0_CONTINUITY_ENVELOPE_BINDING")
    if canonical(profile["continuity_anchor"]) != canonical(manifest["continuity_anchor"]):
        raise ValueError("P0_CONTINUITY_ANCHOR_DESCRIPTOR_BINDING")
    # This pure prototype neither opens paths nor resolves a credential.
    # The adapter must also check all exact file and native identities.


def bind_chain(manifest: Mapping[str, object], ancestors: Sequence[OriginProof],
               current: OriginProof, *, ancestor_manifests: Mapping[str, Mapping[str, object]],
               anchor: Mapping[str, object] | None = None) -> BoundChain:
    closed(manifest, MANIFEST_FIELDS, "P0_CONTINUITY_MANIFEST_FIELDS")
    if anchor is None:
        raise ValueError("P0_CONTINUITY_PRIVATE_ANCHOR_REQUIRED")
    closed(anchor, ANCHOR_FIELDS, "P0_CONTINUITY_ANCHOR_FIELDS")
    required = anchor["required_historical_reservations"]
    if (anchor["schema"] != "P0-PRODUCT-CONTINUITY-ANCHOR-1.0"
            or not digest(anchor["root_permission_sha256"])
            or not digest(anchor["campaign_namespace_sha256"])
            or not isinstance(required, list) or not required or len(required) > 14):
        raise ValueError("P0_CONTINUITY_PRIVATE_ANCHOR_REQUIRED")
    for raw in required:
        witness = mapping(raw, "P0_CONTINUITY_HISTORICAL_WITNESS")
        closed(witness, WITNESS_FIELDS, "P0_CONTINUITY_HISTORICAL_WITNESS_FIELDS")
        descriptor(witness["metadata_evidence"])
        if (witness["permission_sha256"] != anchor["root_permission_sha256"]
                or not digest(witness["namespace_sha256"]) or not digest(witness["request_sha256"])):
            raise ValueError("P0_CONTINUITY_ANCHOR_ORIGIN_BINDING")
        money(witness["reserved_usd"])
    if (manifest["schema"] != "P0-PRODUCT-CONTINUITY-MANIFEST-1.0"
            or manifest["conditions_sha256"] != descriptor(anchor["conditions"])["sha256"]
            or manifest["implementation_decision_sha256"] != descriptor(anchor["implementation_decision"])["sha256"]
            or manifest["root_permission_sha256"] != anchor["root_permission_sha256"]
            or manifest["campaign_namespace_sha256"] != anchor["campaign_namespace_sha256"]
            or descriptor(manifest["continuity_anchor"])["sha256"] != sha(canonical(anchor))):
        raise ValueError("P0_CONTINUITY_IMPLEMENTATION_DECISION")
    nodes = manifest["ancestors"]
    if not isinstance(nodes, list) or not ancestors or len(nodes) != len(ancestors) or len(nodes) > 14:
        raise ValueError("P0_CONTINUITY_CHAIN_REQUIRED")
    seen: set[str] = set()
    previous: str | None = None
    for index, (raw, proof) in enumerate(zip(nodes, ancestors, strict=True)):
        node = mapping(raw, "P0_CONTINUITY_NODE")
        closed(node, NODE_FIELDS, "P0_CONTINUITY_NODE_FIELDS")
        permission_hash = proof.permission_sha256
        if (permission_hash in seen or node["permission_sha256"] != permission_hash
                or node["parent_permission_sha256"] != previous
                or descriptor(node["permission"])["sha256"] != permission_hash
                or descriptor(node["profile_envelope"])["sha256"] != sha(canonical(proof.envelope))
                or descriptor(node["owner_decision"])["sha256"] != sha(canonical(proof.decision))):
            raise ValueError("P0_CONTINUITY_CHAIN_BINDING")
        if (canonical(node["permission"]) != canonical(proof.envelope["permission"])
                or canonical(node["owner_decision"]) != canonical(proof.envelope["decision"])):
            raise ValueError("P0_CONTINUITY_ORIGIN_DESCRIPTOR_BINDING")
        _permission(proof)
        profile = mapping(proof.envelope["profile"], "P0_CONTINUITY_PROFILE")
        if profile["schema"] == "P0-NORMAL-PROFILE-3.0":
            prior = ancestor_manifests.get(permission_hash)
            if prior is None:
                raise ValueError("P0_CONTINUITY_ANCESTOR_MANIFEST_MISSING")
            # Recursive binding is to an exact shorter prefix, never latest.
            bind_chain(prior, ancestors[:index], proof, ancestor_manifests=ancestor_manifests, anchor=anchor)
            if (canonical(prior["ancestors"]) != canonical(nodes[:index])
                    or prior["root_permission_sha256"] != manifest["root_permission_sha256"]):
                raise ValueError("P0_CONTINUITY_ANCESTOR_PREFIX")
            present_witnesses = {canonical(value) for value in cast(list[object], manifest["historical_reservations"])}
            if any(canonical(value) not in present_witnesses
                   for value in cast(list[object], prior["historical_reservations"])):
                raise ValueError("P0_CONTINUITY_ANCESTOR_WITNESS_REMOVED")
        elif index != 0:
            raise ValueError("P0_CONTINUITY_NON_VERSIONED_SUCCESSOR")
        seen.add(permission_hash)
        previous = permission_hash
    if (manifest["root_permission_sha256"] != ancestors[0].permission_sha256
            or manifest["parent_permission_sha256"] != previous
            or current.permission_sha256 in seen
            or manifest["root_lock_sha256"] != sha(canonical(
                {"permission_sha256": ancestors[0].permission_sha256}))):
        raise ValueError("P0_CONTINUITY_ROOT_TIP_BINDING")
    _permission(current)
    _profile3(current, manifest, anchor)
    root = ancestors[0]
    common = mapping(manifest["common_identities"], "P0_CONTINUITY_COMMON")
    closed(common, COMMON_KEYS, "P0_CONTINUITY_COMMON_FIELDS")
    window = mapping(manifest["campaign_window"], "P0_CONTINUITY_WINDOW")
    closed(window, {"issued_at_utc", "expires_at_utc"}, "P0_CONTINUITY_WINDOW_FIELDS")
    limits = mapping(manifest["campaign_limits"], "P0_CONTINUITY_LIMITS")
    closed(limits, LIMIT_KEYS, "P0_CONTINUITY_LIMIT_FIELDS")
    if (window["issued_at_utc"] != root.permission["issued_at_utc"]
            or window["expires_at_utc"] != root.permission["expires_at_utc"]
            or any(limits[key] != root.permission[key] for key in LIMIT_KEYS)):
        raise ValueError("P0_CONTINUITY_ROOT_LIMITS")
    for proof in (*ancestors, current):
        permission = proof.permission
        profile = mapping(proof.envelope["profile"], "P0_CONTINUITY_PROFILE")
        if (permission["permission_namespace_sha256"] != manifest["campaign_namespace_sha256"]
                or any(permission.get(key) != common[key] for key in COMMON_KEYS - {"saved_root_native_sha256"})
                or proof.saved_root_native_sha256 != common["saved_root_native_sha256"]
                or not utc(root.permission["issued_at_utc"]) <= utc(permission["issued_at_utc"])
                    < utc(permission["expires_at_utc"]) <= utc(root.permission["expires_at_utc"])
                or any(permission[key] != limits[key] for key in LIMIT_KEYS)
                or not set(cast(list[str], permission["allowed_families"])) <= set(cast(list[str], root.permission["allowed_families"]))
                or not set(cast(list[str], permission["allowed_levels"])) <= set(cast(list[str], root.permission["allowed_levels"]))):
            raise ValueError("P0_CONTINUITY_COMMON_CHANGED")
        root_profile = mapping(root.envelope["profile"], "P0_CONTINUITY_PROFILE")
        if (profile["saved_root"] != root_profile["saved_root"]
                or profile["receipt_root"] != root_profile["receipt_root"]):
            raise ValueError("P0_CONTINUITY_STORE_CHANGED")
        if canonical(profile["runtime"]) != canonical(root_profile["runtime"]):
            raise ValueError("P0_CONTINUITY_RUNTIME_LOCATION_CHANGED")
        if profile["institutional_catalog_sha256"] != common["institutional_catalog_sha256"]:
            raise ValueError("P0_CONTINUITY_PROFILE_CATALOG_BINDING")
        for component in ("operator_delegation", "tokenizer_manifest", "tariff", "tariff_evidence"):
            if canonical(profile[component]) != canonical(root_profile[component]):
                raise ValueError("P0_CONTINUITY_PROFILE_COMMON_CHANGED")
    current_profile = mapping(current.envelope["profile"], "P0_CONTINUITY_PROFILE")
    source_owner = descriptor(current_profile["source_admission_owner_decision"])["sha256"]
    sources = [p for p in ancestors if sha(canonical(p.decision)) == source_owner]
    if len(sources) != 1:
        raise ValueError("P0_CONTINUITY_SOURCE_OWNER_UNKNOWN")
    if canonical(current_profile["source_admission_owner_decision"]) != canonical(sources[0].envelope["decision"]):
        raise ValueError("P0_CONTINUITY_SOURCE_OWNER_DESCRIPTOR_BINDING")
    original = mapping(sources[0].envelope["profile"], "P0_CONTINUITY_PROFILE")
    for key in ("source_admission_manifest", "local_reference_context_manifest"):
        if (descriptor(current_profile[key])["sha256"] != descriptor(original[key])["sha256"]
                or (key == "source_admission_manifest"
                    and current.permission["source_admission_manifest_sha256"] != descriptor(original[key])["sha256"])):
            raise ValueError("P0_CONTINUITY_SOURCE_ADMISSION_CHANGED")
    return BoundChain(manifest, anchor, (*ancestors, current))


def validate_slot(chain: BoundChain, record: Mapping[str, object], *, file_name: str) -> OriginProof:
    closed(record, SLOT_FIELDS, "P0_CONTINUITY_SLOT_FIELDS")
    origins = {proof.permission_sha256: proof for proof in chain.origins}
    origin = origins.get(str(record["permission_sha256"]))
    if origin is None:
        raise ValueError("P0_CONTINUITY_UNKNOWN_PERMISSION")
    grant = mapping(record["grant"], "P0_CONTINUITY_GRANT_REQUIRED")
    if (record["schema"] != "P0-PRODUCT-BUDGET-SLOT-1.0"
            or record["grant_sha256"] != sha(canonical(grant))
            or record["namespace_sha256"] != grant.get("namespace_sha256")
            or record["request_sha256"] != grant.get("request_sha256")
            or file_name != str(chain.manifest["campaign_namespace_sha256"]) + ".P1." + str(record["preview_sha256"]) + ".json"
            or any(not digest(record[key]) for key in
                   ("preview_sha256", "grant_sha256", "namespace_sha256", "request_sha256", "preflight_sha256"))
            or not isinstance(record["command_id"], str)
            or len(record["command_id"]) != 32
            or any(c not in "0123456789abcdef" for c in record["command_id"])
            or money(record["reserved_usd"]) > money(origin.permission["per_call_ceiling_usd"])):
        raise ValueError("P0_CONTINUITY_SLOT_BINDING")
    if any(grant.get(key) != origin.permission[key]
           for key in (HASH_FIELDS & origin.permission.keys()) | {"baseline_commit"}):
        raise ValueError("P0_CONTINUITY_ORIGIN_GRANT_BINDING")
    validate_grant(grant, identities={key: grant[key] for key in HASH_FIELDS | {"baseline_commit", "request_bytes"}},
        now=utc(grant["issued_at_utc"]))
    if not (utc(origin.permission["issued_at_utc"]) <= utc(grant["issued_at_utc"])
            < utc(grant["expires_at_utc"]) <= utc(origin.permission["expires_at_utc"])):
        raise ValueError("P0_CONTINUITY_GRANT_ORIGIN_WINDOW")
    return origin


def validate_events(record: Mapping[str, object], events: Mapping[str, Mapping[str, object]],
                    ) -> None:
    """Add lifecycle checks after the adapter's actual normal confirmed()."""
    if ("UNKNOWN" in events or "PARSING_REJECTED" in events
            or set(events) != set(EVENT_ORDER)):
        raise ValueError("P0_CONTINUITY_OUTCOME_RECONCILIATION_REQUIRED")
    grant = mapping(record["grant"], "P0_CONTINUITY_GRANT_REQUIRED")
    previous = utc(grant["issued_at_utc"])
    for state in EVENT_ORDER:
        event = events[state]
        closed(event, EVENT_FIELDS, "P0_CONTINUITY_EVENT_FIELDS")
        timestamp = utc(event["timestamp_utc"])
        is_response = state == "RESPONSE_CAPTURED"
        if (event["schema"] != "P0-NORMAL-TECHNICAL-RECEIPT-1.0"
                or event["state"] != state
                or event["grant_sha256"] != record["grant_sha256"]
                or event["request_sha256"] != record["request_sha256"]
                or event["preflight_sha256"] != record["preflight_sha256"]
                or event["namespace_sha256"] != record["namespace_sha256"]
                or money(event["reserved_usd"]) != money(record["reserved_usd"])
                or event["provider_attempts"] != (0 if state == "RESERVED" else 1)
                or type(event["provider_attempts"]) is not int
                or event["observed_cost_status"] != "NOT_ESTABLISHED"
                or not previous <= timestamp < utc(grant["expires_at_utc"])
                or (is_response and event["response_status"] != "completed")
                or (not is_response and any(event[key] is not None
                    for key in ("response_status", "response_artifact_sha256", "usage")))):
            raise ValueError("P0_CONTINUITY_EVENT_BINDING")
        if is_response and (not digest(event["response_artifact_sha256"]) or not isinstance(event["usage"], Mapping)):
            raise ValueError("P0_CONTINUITY_RESPONSE_BINDING")
        previous = timestamp


@dataclass(frozen=True)
class OwnPending:
    """Only minted internally by accept() on that living broker instance."""
    broker_identity: object
    permission_sha256: str
    command_id: str
    grant_sha256: str
    namespace_sha256: str
    request_sha256: str
    preflight_sha256: str
    dispatch_sha256: str
    expires_at_utc: str


def allow_own_transition(chain: BoundChain, record: Mapping[str, object], pending: OwnPending | None, *,
                         broker_identity: object, dispatch_sha256: str, now: datetime,
                         existing_p0_events: Sequence[str]) -> bool:
    if pending is None:
        return False
    exact = {"permission_sha256": chain.current.permission_sha256,
        "command_id": record["command_id"], "grant_sha256": record["grant_sha256"],
        "namespace_sha256": record["namespace_sha256"], "request_sha256": record["request_sha256"],
        "preflight_sha256": record["preflight_sha256"], "dispatch_sha256": dispatch_sha256}
    return (pending.broker_identity is broker_identity
        and record["permission_sha256"] == chain.current.permission_sha256
        and all(getattr(pending, key) == value for key, value in exact.items())
        and not existing_p0_events and now.tzinfo is not None
        and now < utc(pending.expires_at_utc)
        and utc(mapping(record["grant"], "P0_CONTINUITY_GRANT_REQUIRED")["issued_at_utc"])
            <= now < utc(mapping(record["grant"], "P0_CONTINUITY_GRANT_REQUIRED")["expires_at_utc"]))


def metadata(chain: BoundChain, records: Sequence[Mapping[str, object]], *, now: datetime) -> dict[str, object]:
    """Reservation arithmetic only; the adapter validates under retained LOCK."""
    validate_historical_witnesses(chain, records)
    reserved = [money(record["reserved_usd"]) for record in records]
    permission = chain.root.permission
    calls = cast(int, permission["max_calls"])
    total = money(permission["cumulative_ceiling_usd"])
    if len(reserved) > calls or sum(reserved, Decimal(0)) > total:
        raise ValueError("P0_CONTINUITY_OVERBUDGET")
    for key in ("namespace_sha256", "command_id", "preview_sha256"):
        if len({record[key] for record in records}) != len(records):
            raise ValueError("P0_CONTINUITY_AMBIGUOUS_SLOTS")
    current_profile = mapping(chain.current.envelope["profile"], "P0_CONTINUITY_PROFILE")
    available = (current_profile["continuity_enabled"] is True
        and utc(chain.current.permission["issued_at_utc"]) <= now < utc(chain.current.permission["expires_at_utc"]))
    return {"schema": "P0-PRODUCT-CAMPAIGN-SNAPSHOT-1.0", "state": "CURRENT_VALIDATED",
        "timestamp_utc": now.isoformat(), "root_permission_sha256": chain.root.permission_sha256,
        "current_permission_sha256": chain.current.permission_sha256,
        "campaign_namespace_sha256": chain.manifest["campaign_namespace_sha256"],
        "slots_reserved": len(reserved), "reserved_budget_usd": str(sum(reserved, Decimal(0))),
        "remaining_calls": calls - len(reserved), "remaining_reserved_budget_usd": str(total - sum(reserved, Decimal(0))),
        "financial_basis": "RESERVATIONS_NOT_BILLED_COST", "live_enabled": available}


def assert_current_recovery(chain: BoundChain, record: Mapping[str, object]) -> None:
    if record["permission_sha256"] != chain.current.permission_sha256:
        raise ValueError("P0_CONTINUITY_OLD_GRANT_CURRENT_RECOVERY_REFUSED")


def require_effect_enabled(chain: BoundChain, *, now: datetime, family: str, level: str) -> None:
    profile = mapping(chain.current.envelope["profile"], "P0_CONTINUITY_PROFILE")
    if profile["continuity_enabled"] is not True:
        raise ValueError("P0_CONTINUITY_NOT_ACTIVATED")
    permission = chain.current.permission
    validate_permission(permission,
        identities={key: permission[key] for key in P1_HASHES | {"baseline_commit"}}, now=now,
        family=family, level=level)
