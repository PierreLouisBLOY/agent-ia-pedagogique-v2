"""Closed profile4 and external adoption checks; no I/O or live authority."""

from __future__ import annotations

from collections.abc import Mapping

from backend.adapters.outbound.generation.openai.p0_normal_policy import (
    canonical,
    closed,
    digest,
    sha,
)
from backend.adapters.outbound.generation.openai.p0_product_continuity_contract import (
    DECISION3_FIELDS,
    PROFILE3_FIELDS,
    OriginProof,
    mapping,
)
from backend.infrastructure.composition.factories.p0_normal_profile_contract import (
    DELEGATION_FIELDS,
    DESCRIPTORS,
    absolute,
    descriptor,
)

PROFILE4_FIELDS = PROFILE3_FIELDS | {"rejected_disposition"}
DECISION4_FIELDS = DECISION3_FIELDS | {"rejected_disposition_sha256", "continuity_version"}
EXTERNAL_FIELDS = {
    "schema",
    "operation",
    "book",
    "owner_evidence",
    "expected_owner_evidence_sha256",
}
BOOK_FIELDS = {"schema", "operation", "components"}
BOOK_COMPONENTS = {
    "observed_evidence_sha256",
    "disposition_sha256",
    "anchor2_sha256",
    "manifest2_sha256",
    "profile4_OFF_sha256",
    "profile4_ON_sha256",
    "source_manifest_sha256",
    "package_sha256",
}
OWNER_EVIDENCE_FIELDS = {
    "schema",
    "source",
    "question_call_id",
    "proposal_sha256",
    "answer_exact",
    "scope",
    "human_cryptographic_signature_claimed",
}
PLAN_COMPONENTS = {"inspection_plan_sha256", "source_manifest_sha256", "package_sha256"}


def validate_external_adoption(
    control: Mapping[str, object],
    *,
    book: Mapping[str, object],
    owner_evidence: Mapping[str, object],
    owner_raw_sha256: str,
    expected_owner_raw_sha256: str,
    components: Mapping[str, object],
    operation: str,
) -> None:
    """Expected human capture SHA is a trusted composition input, never HTTP.

    Neither an approved flag nor a free-form answer is authority. The exact
    capture must be supplied separately and bind the entire external book.
    No component adopts or refers back to this control/capture document.
    """
    closed(
        control,
        EXTERNAL_FIELDS
        | ({"profile_envelopes"} if operation == "OFF_ON_COMPONENT_REBIND" else set()),
        "P0_REJECTED_EXTERNAL_FIELDS",
    )
    closed(book, BOOK_FIELDS, "P0_REJECTED_BOOK_FIELDS")
    closed(owner_evidence, OWNER_EVIDENCE_FIELDS, "P0_REJECTED_OWNER_EVIDENCE_FIELDS")
    expected_fields = PLAN_COMPONENTS if operation == "INSPECTION_ONLY" else BOOK_COMPONENTS
    actual = mapping(book["components"], "P0_REJECTED_BOOK_COMPONENTS")
    closed(actual, expected_fields, "P0_REJECTED_BOOK_COMPONENT_FIELDS")
    closed(components, expected_fields, "P0_REJECTED_ACTUAL_COMPONENT_FIELDS")
    if (
        operation not in {"INSPECTION_ONLY", "OFF_ON_COMPONENT_REBIND"}
        or control["schema"] != "P0-KNOWN-REJECTED-EXTERNAL-ADOPTION-1.0"
        or book["schema"] != "P0-KNOWN-REJECTED-COMPONENT-BOOK-1.0"
        or control["operation"] != operation
        or book["operation"] != operation
        or any(not digest(value) for key, value in actual.items() if key != "manifest2_sha256")
        or canonical(actual) != canonical(components)
        or descriptor(control["book"])["sha256"] != sha(canonical(book))
        or not digest(expected_owner_raw_sha256)
        or owner_raw_sha256 != expected_owner_raw_sha256
        or control["expected_owner_evidence_sha256"] != expected_owner_raw_sha256
        or descriptor(control["owner_evidence"])["sha256"] != expected_owner_raw_sha256
        or owner_evidence["schema"] != "LU-OWNER-KNOWN-REJECTED-EXACT-ADOPTION-1.0"
        or owner_evidence["source"] != "DIRECT_HUMAN_ASYNC_QUESTION_REPLY"
        or not isinstance(owner_evidence["question_call_id"], str)
        or not owner_evidence["question_call_id"]
        or owner_evidence["scope"] != operation
        or owner_evidence["proposal_sha256"] != sha(canonical(book))
        or owner_evidence["answer_exact"] != "ADOPTED_EXACT_COMPONENTS"
        or owner_evidence["human_cryptographic_signature_claimed"] is not False
    ):
        raise ValueError("P0_REJECTED_EXTERNAL_ADOPTION_BINDING")
    if operation == "OFF_ON_COMPONENT_REBIND":
        manifests = mapping(actual["manifest2_sha256"], "P0_REJECTED_MANIFEST_PAIR")
        envelopes = mapping(control["profile_envelopes"], "P0_REJECTED_ENVELOPE_PAIR")
        closed(manifests, {"off", "on"}, "P0_REJECTED_MANIFEST_PAIR")
        closed(envelopes, {"off", "on"}, "P0_REJECTED_ENVELOPE_PAIR")
        if (
            any(not digest(value) for value in manifests.values())
            or manifests["off"] == manifests["on"]
        ):
            raise ValueError("P0_REJECTED_MANIFEST_PAIR")
        for value in envelopes.values():
            descriptor(value)


def bind_profile4(
    proof: OriginProof,
    *,
    manifest: Mapping[str, object],
    anchor: Mapping[str, object],
    disposition: Mapping[str, object],
) -> Mapping[str, object]:
    """Profile4 is explicit; it is never converted or presented as profile3."""
    closed(
        proof.envelope,
        {"schema", "profile", "permission", "decision"},
        "P0_REJECTED_ENVELOPE_FIELDS",
    )
    profile = mapping(proof.envelope["profile"], "P0_REJECTED_PROFILE")
    closed(profile, PROFILE4_FIELDS, "P0_REJECTED_PROFILE_FIELDS")
    closed(proof.decision, DECISION4_FIELDS, "P0_REJECTED_DECISION_FIELDS")
    if (
        proof.envelope["schema"] != "P0-NORMAL-PROFILE-ENVELOPE-1.0"
        or profile["schema"] != "P0-NORMAL-PROFILE-4.0"
        or proof.decision["schema"] != "P0-NORMAL-OWNER-DECISION-4.0"
        or proof.decision["status"] != "ADOPTED"
        or type(profile["continuity_enabled"]) is not bool
        or type(proof.decision["continuity_version"]) is not int
        or proof.decision["continuity_version"] != 2
    ):
        raise ValueError("P0_REJECTED_PROFILE_ADOPTION")
    for key in DESCRIPTORS | {
        "local_reference_context_manifest",
        "continuity_manifest",
        "continuity_anchor",
        "source_admission_owner_decision",
        "rejected_disposition",
    }:
        descriptor(profile[key])
    for key in ("saved_root", "receipt_root"):
        absolute(profile[key])
    if str(profile["saved_root"]).casefold() == str(profile["receipt_root"]).casefold():
        raise ValueError("P0_REJECTED_DISTINCT_STORES")
    runtime = mapping(profile["runtime"], "P0_REJECTED_RUNTIME")
    closed(runtime, {"path", "data_root", "sha256"}, "P0_REJECTED_RUNTIME_FIELDS")
    absolute(runtime["path"])
    absolute(runtime["data_root"])
    if (
        runtime["sha256"] != proof.permission["runtime_sha256"]
        or profile["baseline_commit"] != proof.permission["baseline_commit"]
        or profile["institutional_catalog_sha256"]
        != proof.permission["institutional_catalog_sha256"]
        or not isinstance(profile["credential_ref"], str)
        or not 1 <= len(profile["credential_ref"]) <= 128
        or profile["credential_ref"].startswith("sk-")
    ):
        raise ValueError("P0_REJECTED_PROFILE_COMMON_BINDING")
    closed(proof.delegation, DELEGATION_FIELDS, "P0_REJECTED_DELEGATION_FIELDS")
    if (
        proof.delegation["schema"] != "P0-LOCAL-OPERATOR-DELEGATION-1.0"
        or proof.delegation["local_operator_delegation_accepted"] is not True
        or proof.delegation["credential_ref"] != profile["credential_ref"]
        or any(
            proof.delegation[key] != proof.operator.get(key)
            for key in ("windows_sid", "windows_profile")
        )
        or sha(canonical(proof.delegation)) != descriptor(profile["operator_delegation"])["sha256"]
    ):
        raise ValueError("P0_REJECTED_OPERATOR_BINDING")
    expected: dict[str, object] = {
        "profile_sha256": sha(canonical(profile)),
        "permission_policy_sha256": sha(
            canonical(
                {
                    key: value
                    for key, value in proof.permission.items()
                    if key != "owner_decision_sha256"
                }
            )
        ),
        "continuity_manifest_sha256": sha(canonical(manifest)),
        "continuity_anchor_sha256": sha(canonical(anchor)),
        "parent_permission_sha256": manifest["parent_permission_sha256"],
        "rejected_disposition_sha256": sha(canonical(disposition)),
        "source_admission_owner_decision_sha256": descriptor(
            profile["source_admission_owner_decision"]
        )["sha256"],
    }
    for key in (
        "source_admission_manifest",
        "local_reference_context_manifest",
        "operator_delegation",
        "tokenizer_manifest",
        "tariff",
    ):
        expected[key + "_sha256"] = descriptor(profile[key])["sha256"]
        if (
            key != "local_reference_context_manifest"
            and proof.permission[key + "_sha256"] != expected[key + "_sha256"]
        ):
            raise ValueError("P0_REJECTED_PERMISSION_COMPONENT_BINDING")
    if (
        any(proof.decision[key] != value for key, value in expected.items())
        or any(
            proof.decision[key] is not True
            for key in (
                "excluded_oracles_and_private_evidence",
                "source_authority_unknown_preserved",
                "local_operator_delegation_accepted",
            )
        )
        or descriptor(profile["continuity_manifest"])["sha256"] != sha(canonical(manifest))
        or descriptor(profile["continuity_anchor"])["sha256"] != sha(canonical(anchor))
        or descriptor(profile["rejected_disposition"])["sha256"] != sha(canonical(disposition))
        or proof.permission["profile_sha256"] != expected["profile_sha256"]
        or proof.permission["owner_decision_sha256"] != sha(canonical(proof.decision))
        or descriptor(proof.envelope["decision"])["sha256"] != sha(canonical(proof.decision))
        or descriptor(proof.envelope["permission"])["sha256"] != proof.permission_sha256
        or canonical(profile["continuity_anchor"]) != canonical(manifest["continuity_anchor"])
    ):
        raise ValueError("P0_REJECTED_PROFILE_COMPONENT_BINDING")
    return profile
