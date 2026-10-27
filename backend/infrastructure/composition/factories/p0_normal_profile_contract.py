"""Closed reviewed normal profile/decision binding; no I/O or active grant."""
from collections.abc import Mapping
from pathlib import PureWindowsPath

from backend.adapters.outbound.generation.openai.p0_normal_policy import (
    canonical,
    closed,
    digest,
    sha,
)

PROFILE_FIELDS = {"schema", "baseline_commit", "source_manifest", "package", "runtime", "saved_root", "receipt_root",
    "source_admission_manifest", "operator_delegation", "tokenizer_manifest", "tariff", "tariff_evidence",
    "institutional_catalog_sha256", "credential_ref"}
DESCRIPTORS = {"source_manifest", "package", "source_admission_manifest", "operator_delegation", "tokenizer_manifest", "tariff", "tariff_evidence"}
DECISION_FIELDS = {"schema", "status", "profile_sha256", "permission_policy_sha256", "source_admission_manifest_sha256",
    "operator_delegation_sha256", "tokenizer_manifest_sha256", "tariff_sha256", "excluded_oracles_and_private_evidence",
    "source_authority_unknown_preserved", "local_operator_delegation_accepted"}
PROFILE_CONTEXT_FIELDS = PROFILE_FIELDS | {"local_reference_context_manifest"}
DECISION_CONTEXT_FIELDS = DECISION_FIELDS | {"local_reference_context_manifest_sha256"}
PROFILE_CONTINUITY_FIELDS = PROFILE_CONTEXT_FIELDS | {"continuity_manifest", "continuity_anchor",
    "source_admission_owner_decision", "continuity_enabled"}
DECISION_CONTINUITY_FIELDS = DECISION_CONTEXT_FIELDS | {"continuity_manifest_sha256", "continuity_anchor_sha256",
    "parent_permission_sha256", "source_admission_owner_decision_sha256"}
DELEGATION_FIELDS = {"schema", "windows_sid", "windows_profile", "credential_ref", "local_operator_delegation_accepted"}


def absolute(value: object) -> str:
    if (not isinstance(value, str) or not value or len(value) > 4096
            or not PureWindowsPath(value).is_absolute() or len(PureWindowsPath(value).drive) != 2
            or PureWindowsPath(value).drive[1] != ":"):
        raise ValueError("P0_NORMAL_ABSOLUTE_PATH_REQUIRED")
    return value


def descriptor(value: object) -> Mapping[str, object]:
    if not isinstance(value, Mapping):
        raise ValueError("P0_NORMAL_DESCRIPTOR_REQUIRED")
    closed(value, {"path", "sha256"}, "P0_NORMAL_DESCRIPTOR_FIELDS")
    absolute(value["path"])
    if not digest(value["sha256"]):
        raise ValueError("P0_NORMAL_DESCRIPTOR_IDENTITY")
    return value


def bind_profile(envelope: Mapping[str, object], *, permission: Mapping[str, object], decision: Mapping[str, object],
                 delegation: Mapping[str, object], operator: Mapping[str, object]) -> Mapping[str, object]:
    closed(envelope, {"schema", "profile", "permission", "decision"}, "P0_NORMAL_ENVELOPE_FIELDS")
    if envelope["schema"] != "P0-NORMAL-PROFILE-ENVELOPE-1.0":
        raise ValueError("P0_NORMAL_ENVELOPE_SCHEMA")
    for key in ("permission", "decision"):
        descriptor(envelope[key])
    profile = envelope["profile"]
    if not isinstance(profile, Mapping):
        raise ValueError("P0_NORMAL_PROFILE_REQUIRED")
    continuity = profile.get("schema") == "P0-NORMAL-PROFILE-3.0"
    contextual = profile.get("schema") == "P0-NORMAL-PROFILE-2.0" or continuity
    closed(profile, PROFILE_CONTINUITY_FIELDS if continuity else (PROFILE_CONTEXT_FIELDS if contextual else PROFILE_FIELDS), "P0_NORMAL_PROFILE_FIELDS")
    if profile["schema"] not in {"P0-NORMAL-PROFILE-1.0", "P0-NORMAL-PROFILE-2.0", "P0-NORMAL-PROFILE-3.0"}:
        raise ValueError("P0_NORMAL_PROFILE_SCHEMA")
    baseline = profile["baseline_commit"]
    if not isinstance(baseline, str) or len(baseline) != 40 or any(c not in "0123456789abcdef" for c in baseline):
        raise ValueError("P0_NORMAL_BASELINE_REQUIRED")
    for key in DESCRIPTORS | ({"local_reference_context_manifest"} if contextual else set()):
        descriptor(profile[key])
    if continuity:
        if type(profile["continuity_enabled"]) is not bool:
            raise ValueError("P0_NORMAL_CONTINUITY_FLAG_REQUIRED")
        for key in ("continuity_manifest", "continuity_anchor", "source_admission_owner_decision"):
            descriptor(profile[key])
    for key in ("saved_root", "receipt_root"):
        absolute(profile[key])
    if str(profile["saved_root"]).casefold() == str(profile["receipt_root"]).casefold():
        raise ValueError("P0_NORMAL_DISTINCT_STORES_REQUIRED")
    runtime = profile["runtime"]
    if not isinstance(runtime, Mapping):
        raise ValueError("P0_NORMAL_RUNTIME_REQUIRED")
    closed(runtime, {"path", "data_root", "sha256"}, "P0_NORMAL_RUNTIME_FIELDS")
    absolute(runtime["path"])
    absolute(runtime["data_root"])
    if not digest(runtime["sha256"]) or not digest(profile["institutional_catalog_sha256"]):
        raise ValueError("P0_NORMAL_IDENTITY_REQUIRED")
    credential = profile["credential_ref"]
    if not isinstance(credential, str) or not credential or len(credential) > 128 or credential.startswith("sk-"):
        raise ValueError("P0_NORMAL_LOGICAL_CREDENTIAL_REQUIRED")
    closed(decision, DECISION_CONTINUITY_FIELDS if continuity else (DECISION_CONTEXT_FIELDS if contextual else DECISION_FIELDS), "P0_NORMAL_DECISION_FIELDS")
    decision_schema = "P0-NORMAL-OWNER-DECISION-3.0" if continuity else ("P0-NORMAL-OWNER-DECISION-2.0" if contextual else "P0-NORMAL-OWNER-DECISION-1.0")
    if decision["schema"] != decision_schema or decision["status"] != "ADOPTED":
        raise ValueError("P0_NORMAL_OWNER_DECISION_REQUIRED")
    for key in ("excluded_oracles_and_private_evidence", "source_authority_unknown_preserved", "local_operator_delegation_accepted"):
        if decision[key] is not True:
            raise ValueError("P0_NORMAL_OWNER_DISPOSITION_REQUIRED")
    expected: dict[str, object] = {"profile_sha256": sha(canonical(profile)), "permission_policy_sha256": sha(canonical({k:v for k,v in permission.items() if k != "owner_decision_sha256"}))}
    components = ("source_admission_manifest", "operator_delegation", "tokenizer_manifest", "tariff")
    for key in components + (("local_reference_context_manifest",) if contextual else ()):
        expected[key + "_sha256"] = descriptor(profile[key])["sha256"]
    if continuity:
        for key in ("continuity_manifest", "continuity_anchor", "source_admission_owner_decision"):
            expected[key + "_sha256"] = descriptor(profile[key])["sha256"]
        if not digest(decision["parent_permission_sha256"]):
            raise ValueError("P0_NORMAL_CONTINUITY_PARENT_REQUIRED")
    if any(decision[k] != v for k,v in expected.items()) or permission.get("profile_sha256") != expected["profile_sha256"]:
        raise ValueError("P0_NORMAL_OWNER_BINDING_CHANGED")
    if (descriptor(envelope["decision"])["sha256"] != permission.get("owner_decision_sha256")
            or descriptor(envelope["permission"])["sha256"] != sha(canonical(permission))):
        raise ValueError("P0_NORMAL_PERMISSION_BINDING_CHANGED")
    closed(delegation, DELEGATION_FIELDS, "P0_NORMAL_DELEGATION_FIELDS")
    if (delegation["schema"] != "P0-LOCAL-OPERATOR-DELEGATION-1.0"
            or delegation["local_operator_delegation_accepted"] is not True
            or delegation["credential_ref"] != credential
            or any(delegation[key] != operator.get(key) for key in ("windows_sid", "windows_profile"))):
        raise ValueError("P0_NORMAL_LOCAL_OPERATOR_NOT_DELEGATED")
    return profile
