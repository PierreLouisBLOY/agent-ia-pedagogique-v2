"""Application admission projections, all synthetic and never official sources."""
import copy
import hashlib

import pytest

from backend.modules.pedagogical_design.contracts.dto.assessment_bundle import fingerprint
from backend.modules.work_orchestration.application.queries.p0_source_admission import (
    ReadP0SourceAdmission,
)


def admitted_fixture():
    text = "Synthetic canonical notion, not an official source."
    passage = {"notion_ref": "notion:test", "object_ref": "notion:test", "object_kind": "NOTION",
        "passage_ref": "search-chunk:test", "version_or_checksum": "a" * 64,
        "excerpt": text, "excerpt_truncated": False, "provenance": {"authority_absolute": False},
        "source_status": {"identity_status": "UNKNOWN", "lifecycle_status": "ACTIVE"}}
    entry = {"notion_ref": passage["notion_ref"], "source_ref": passage["object_ref"], "object_kind": "NOTION",
        "locator": passage["passage_ref"], "checksum_or_version": passage["version_or_checksum"],
        "excerpt_sha256": hashlib.sha256(text.encode()).hexdigest(), "provenance": passage["provenance"],
        "source_status": passage["source_status"], "available_authority": "UNKNOWN",
        "authority_basis": "NOT_ATTESTED_BY_APPLICATION"}
    entry["admission_scope_sha256"] = fingerprint(entry)
    manifest = {"schema": "P0-SOURCE-ADMISSION-MANIFEST-1.0", "status": "NON_ADOPTE",
        "application_inventory_sha256": "b" * 64, "catalogue_sha256": "c" * 64,
        "entries": [entry], "exclusions": [], "source_scope_sha256": fingerprint([entry])}
    ref = {"evidence_id": "evidence:" + "a" * 32, "source_ref": passage["object_ref"],
        "locator": passage["passage_ref"], "checksum_or_version": passage["version_or_checksum"],
        "excerpt_sha256": entry["excerpt_sha256"], "provenance_label": "LOCAL_NO_OFFICIAL_AUTHORITY"}
    resolution = {"status": "RESOLVED_ADMITTED", "reference_scope": {"status": "CANONICAL_NOTION_ONLY",
        "object_ref": ref["source_ref"], "passage_ref": ref["locator"], "version_or_checksum": ref["checksum_or_version"]}}
    request = {"context": {"institutional_resolution": resolution}, "references": [ref], "evidence": {ref["evidence_id"]: text}}
    return manifest, passage, request, resolution


def query(manifest, adopted="d" * 64):
    return ReadP0SourceAdmission(manifest, manifest_sha256="d" * 64,
        adopted_manifest_sha256=adopted, owner_admission_sha256="e" * 64)


def test_exact_owner_adopted_native_unknown_source_remains_unknown():
    manifest, passage, request, resolution = admitted_fixture()
    result = query(manifest).execute(request=request, passages=[passage], resolution=resolution)
    assert result[0]["available_authority"] == "UNKNOWN"
    assert result[0]["source_status"]["identity_status"] == "UNKNOWN"
    assert result[0]["transmission_admission"] == "OWNER_ADMITTED_LOCAL_CONTENT_ONLY"
    assert result[0]["reference"] == request["references"][0]


def test_non_adopted_current_manifest_cannot_admit_itself():
    manifest, _, _, _ = admitted_fixture()
    with pytest.raises(ValueError, match="OWNER_ADMISSION_REQUIRED"):
        query(manifest, adopted="0" * 64)


@pytest.mark.parametrize("key,value", [("excerpt", "Changed"), ("excerpt_truncated", True),
    ("object_kind", "RESOURCE"), ("version_or_checksum", "b" * 64), ("authority", "OFFICIAL"),
    ("source_status", {"identity_status": "VERIFIED"}), ("provenance", {"authority_absolute": True}),
    ("is_private_evidence", True), ("is_oracle", True), ("is_teacher_reference", True)])
def test_native_source_mutations_refuse_before_any_provider(key, value):
    manifest, passage, request, resolution = admitted_fixture()
    passage[key] = value
    with pytest.raises(ValueError):
        query(manifest).execute(request=request, passages=[passage], resolution=resolution)


@pytest.mark.parametrize("mutation", ["not_listed", "duplicate", "scope_hash", "entry_hash", "context_gap", "context_change"])
def test_admission_is_exact_and_never_propagated_from_context_or_active(mutation):
    manifest, passage, request, resolution = admitted_fixture()
    passages = [passage]
    if mutation == "not_listed":
        passage["notion_ref"] = "notion:outside"
    elif mutation == "duplicate":
        passages.append(copy.deepcopy(passage))
    elif mutation == "scope_hash":
        manifest["source_scope_sha256"] = "0" * 64
    elif mutation == "entry_hash":
        manifest["entries"][0]["admission_scope_sha256"] = "0" * 64
        manifest["source_scope_sha256"] = fingerprint(manifest["entries"])
    elif mutation == "context_gap":
        resolution["status"] = "CONTENT_GAP"
    else:
        resolution = {**resolution, "depth": "changed"}
    with pytest.raises(ValueError):
        query(manifest).execute(request=request, passages=passages, resolution=resolution)
