"""Exact local-content admission; consumes authenticated Application projections."""
from collections.abc import Mapping, Sequence
from typing import cast

from backend.modules.pedagogical_design.contracts.dto.assessment_bundle import (
    as_plain,
    fingerprint,
    items,
    object_data,
)

MANIFEST_FIELDS = {"schema", "status", "application_inventory_sha256", "catalogue_sha256",
                   "source_scope_sha256", "entries", "exclusions"}
ENTRY_FIELDS = {"notion_ref", "source_ref", "object_kind", "locator", "checksum_or_version",
                "excerpt_sha256", "provenance", "source_status", "available_authority", "authority_basis",
                "admission_scope_sha256"}


class ReadP0SourceAdmission:
    """The injected adoption proof is explicit, never inferred from ACTIVE/UNKNOWN.

    The manifest remains a NON_ADOPTE identity proposal; the separate owner proof
    must adopt its exact binary hash. No SQL, file, repository or HTTP is read here.
    """
    def __init__(self, manifest: Mapping[str, object], *, manifest_sha256: str,
                 adopted_manifest_sha256: str, owner_admission_sha256: str) -> None:
        self.manifest = object_data(as_plain(manifest), MANIFEST_FIELDS)
        if (self.manifest["schema"] != "P0-SOURCE-ADMISSION-MANIFEST-1.0"
                or self.manifest["status"] != "NON_ADOPTE"
                or manifest_sha256 != adopted_manifest_sha256
                or not self._hash(manifest_sha256) or not self._hash(owner_admission_sha256)):
            raise ValueError("P0_SOURCE_OWNER_ADMISSION_REQUIRED")
        self.entries = items(self.manifest["entries"], 20_000)
        if fingerprint(as_plain(self.entries)) != self.manifest["source_scope_sha256"]:
            raise ValueError("P0_SOURCE_SCOPE_CHANGED")
        self.index: dict[tuple[str, str, str, str], dict[str, object]] = {}
        for entry in self.entries:
            object_data(entry, ENTRY_FIELDS)
            if fingerprint({k: v for k, v in entry.items() if k != "admission_scope_sha256"}) != entry["admission_scope_sha256"]:
                raise ValueError("P0_SOURCE_ENTRY_CHANGED")
            key = tuple(str(entry[k]) for k in ("notion_ref", "source_ref", "locator", "checksum_or_version"))
            if key in self.index:
                raise ValueError("P0_SOURCE_MANIFEST_AMBIGUOUS")
            self.index[cast(tuple[str, str, str, str], key)] = entry
        self.manifest_sha256, self.owner_sha256 = manifest_sha256, owner_admission_sha256

    @staticmethod
    def _hash(value: object) -> bool:
        return isinstance(value, str) and len(value) == 64 and all(c in "0123456789abcdef" for c in value)

    def execute(self, *, request: Mapping[str, object], passages: Sequence[Mapping[str, object]],
                resolution: Mapping[str, object]) -> list[dict[str, object]]:
        context = object_data(request["context"])
        captured = context.get("institutional_resolution")
        if (not isinstance(captured, Mapping) or as_plain(captured) != as_plain(resolution)
                or resolution.get("status") != "RESOLVED_ADMITTED"):
            raise ValueError("P0_SOURCE_INSTITUTIONAL_ADMISSION_REQUIRED")
        scope = object_data(resolution.get("reference_scope", {}))
        if scope.get("status") not in {"CANONICAL_NOTION_ONLY", "EXACT_CONTEXT_ADMITTED"}:
            raise ValueError("P0_SOURCE_CONTEXT_GAP")
        evidence = object_data(request["evidence"])
        result = []
        for ref in items(request["references"], 8):
            selected = [p for p in passages if all(p.get(k) == ref[target] for k, target in (
                ("object_ref", "source_ref"), ("passage_ref", "locator"), ("version_or_checksum", "checksum_or_version")))]
            if len(selected) != 1:
                raise ValueError("P0_SOURCE_NOT_IN_ADOPTED_MANIFEST")
            passage = selected[0]
            key = (str(passage.get("notion_ref")), *(str(ref[k]) for k in ("source_ref", "locator", "checksum_or_version")))
            entry = self.index.get(cast(tuple[str, str, str, str], key))
            if entry is None:
                raise ValueError("P0_SOURCE_NOT_IN_ADOPTED_MANIFEST")
            text = evidence.get(str(ref["evidence_id"]))
            if (passage.get("object_kind") not in {"NOTION", "PEDAGOGICAL_CONTENT", "METHOD"}
                    or passage.get("excerpt_truncated") is not False or not isinstance(text, str) or not text
                    or passage.get("excerpt") != text or len(text) > 4000
                    or any(passage.get(flag) is True for flag in ("is_private_evidence", "is_oracle", "is_teacher_reference"))):
                raise ValueError("P0_SOURCE_COMPLETE_NON_ORACLE_REQUIRED")
            import hashlib
            excerpt_sha = hashlib.sha256(text.encode("utf-8")).hexdigest()
            authority = passage.get("authority", "UNKNOWN")
            actual = {"source_ref": passage["object_ref"], "object_kind": passage["object_kind"],
                "locator": passage["passage_ref"], "checksum_or_version": passage["version_or_checksum"],
                "excerpt_sha256": excerpt_sha, "provenance": as_plain(passage.get("provenance", {})),
                "source_status": as_plain(passage.get("source_status", {})), "available_authority": authority,
                "authority_basis": passage.get("authority_basis", "NOT_ATTESTED_BY_APPLICATION")}
            if (any(as_plain(entry[k]) != v for k, v in actual.items()) or ref["excerpt_sha256"] != excerpt_sha
                    or any(scope.get(k) != ref[target] for k, target in (
                        ("object_ref", "source_ref"), ("passage_ref", "locator"), ("version_or_checksum", "checksum_or_version")))):
                raise ValueError("P0_SOURCE_ADMISSION_CHANGED")
            result.append({"schema": "P0-SOURCE-ADMISSION-RECEIPT-1.0", "reference": as_plain(ref),
                "available_authority": authority, "provenance": actual["provenance"], "source_status": actual["source_status"],
                "admission_manifest_sha256": self.manifest_sha256, "admission_scope_sha256": entry["admission_scope_sha256"],
                "owner_admission_sha256": self.owner_sha256, "institutional_resolution_sha256": fingerprint(resolution),
                "source_scope_status": scope["status"], "transmission_admission": "OWNER_ADMITTED_LOCAL_CONTENT_ONLY"})
        if not result:
            raise ValueError("P0_SOURCE_RECEIPTS_REQUIRED")
        return result
