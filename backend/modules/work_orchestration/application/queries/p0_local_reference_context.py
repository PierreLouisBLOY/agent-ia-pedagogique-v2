"""Reviewed pure Application successor prototype; no SQL/FS/provider authority."""
from collections.abc import Callable, Mapping, Sequence
from typing import cast

from backend.modules.knowledge_reference.contracts.dto.stmg_frames import STMG_FRAMES
from backend.modules.pedagogical_context.contracts.dto.bts_institutional import (
    validate_bts_selection,
)
from backend.modules.pedagogical_context.contracts.dto.stmg_institutional import validate_selection
from backend.modules.pedagogical_design.contracts.dto.assessment_bundle import (
    as_plain,
    fingerprint,
    items,
    object_data,
)
from backend.modules.work_orchestration.application.queries.p0_source_admission import (
    ReadP0SourceAdmission,
)

FIELDS = {"schema", "status", "source_admission_manifest_sha256", "runtime_sha256",
          "institutional_catalogue_sha256", "bindings"}
BINDING_FIELDS = {"selection", "selection_sha256", "source_entry_scope_sha256",
                  "canonical_notion_entry_scope_sha256", "canonical_resolution_sha256"}
SCOPE_FIELDS = {"schema", "object_ref", "object_kind", "passage_ref", "version_or_checksum", "status",
    "context_enrichment", "admission_basis", "available_authority", "authority_basis", "manifest_sha256",
    "owner_admission_sha256", "source_entry_scope_sha256", "canonical_notion_entry_scope_sha256",
    "canonical_institutional_resolution_sha256"}


def canonical_scope(entry: Mapping[str, object], contract_id: object) -> dict[str, object]:
    result = {"object_ref": entry["source_ref"], "object_kind": "NOTION", "passage_ref": entry["locator"],
        "version_or_checksum": entry["checksum_or_version"], "status": "CANONICAL_NOTION_ONLY", "context_enrichment": False}
    if contract_id == "STMG-RESOLUTION-1.0":
        result["relationships"] = []
    elif contract_id != "BTS-RESOLUTION-1.0":
        raise ValueError("P0_LOCAL_CONTEXT_CANONICAL_RESOLUTION_CHANGED")
    return result


class ReadP0LocalReferenceContext:
    """Local owner admission does not promote the native disciplinary authority.

    The profile supplies a separate adopted exact manifest. The default and all
    old resolver/permission paths are unchanged. Inputs are Application captures.
    """
    def __init__(self, manifest: Mapping[str, object], *, manifest_sha256: str,
                 adopted_manifest_sha256: str, owner_admission_sha256: str,
                 sources: ReadP0SourceAdmission, runtime_sha256: str,
                 institutional_catalogue_sha256: str) -> None:
        data = object_data(as_plain(manifest), FIELDS)
        hashes = (manifest_sha256, adopted_manifest_sha256, owner_admission_sha256,
                  runtime_sha256, institutional_catalogue_sha256)
        if (data["schema"] != "P0-LOCAL-REFERENCE-CONTEXT-MANIFEST-1.0" or data["status"] != "NON_ADOPTE"
                or not all(sources._hash(value) for value in hashes)
                or manifest_sha256 != adopted_manifest_sha256 or fingerprint(data) != manifest_sha256
                or data["source_admission_manifest_sha256"] != sources.manifest_sha256
                or owner_admission_sha256 != sources.owner_sha256
                or data["runtime_sha256"] != runtime_sha256
                or data["institutional_catalogue_sha256"] != institutional_catalogue_sha256):
            raise ValueError("P0_LOCAL_CONTEXT_OWNER_BINDING_REQUIRED")
        by_scope = {str(entry["admission_scope_sha256"]): entry for entry in sources.entries}
        if len(by_scope) != len(sources.entries):
            raise ValueError("P0_LOCAL_CONTEXT_SOURCE_SCOPE_AMBIGUOUS")
        bindings = items(data["bindings"], 20000)
        if not bindings:
            raise ValueError("P0_LOCAL_CONTEXT_BINDINGS_REQUIRED")
        self.bindings: dict[tuple[str, str], dict[str, object]] = {}
        for binding in bindings:
            object_data(binding, BINDING_FIELDS)
            selection = object_data(binding["selection"])
            if selection.get("contract_id") == "BTS-INSTITUTIONAL-CONTEXT-1.0":
                validate_bts_selection(selection, level=str(selection.get("local_year")), discipline="Comptabilité et gestion")
            elif selection.get("contract_id") == "STMG-INSTITUTIONAL-CONTEXT-1.0":
                frame = STMG_FRAMES.get(str(selection.get("frame")))
                if frame is None:
                    raise ValueError("P0_LOCAL_CONTEXT_SELECTION_CHANGED")
                validate_selection(selection, level=frame[0], discipline=frame[6])
            if (selection.get("contract_id") not in {"STMG-INSTITUTIONAL-CONTEXT-1.0", "BTS-INSTITUTIONAL-CONTEXT-1.0"}
                    or fingerprint(selection) != binding["selection_sha256"]
                    or not sources._hash(binding["canonical_resolution_sha256"])):
                raise ValueError("P0_LOCAL_CONTEXT_SELECTION_CHANGED")
            selected = by_scope.get(str(binding["source_entry_scope_sha256"]))
            canonical = by_scope.get(str(binding["canonical_notion_entry_scope_sha256"]))
            if (selected is None or canonical is None or selected["object_kind"] not in {"PEDAGOGICAL_CONTENT", "METHOD"}
                    or canonical["object_kind"] != "NOTION" or canonical["source_ref"] != canonical["notion_ref"]
                    or selected["notion_ref"] != canonical["notion_ref"]
                    or selection.get("notion_refs") != [selected["notion_ref"]]):
                raise ValueError("P0_LOCAL_CONTEXT_EXACT_SOURCE_AND_NOTION_REQUIRED")
            key = (str(binding["selection_sha256"]), str(binding["source_entry_scope_sha256"]))
            if key in self.bindings:
                raise ValueError("P0_LOCAL_CONTEXT_BINDING_AMBIGUOUS")
            self.bindings[key] = binding
        self.sources = sources
        self.by_scope = by_scope
        self.manifest_sha256, self.owner_sha256 = manifest_sha256, owner_admission_sha256

    def resolve(self, *, selection: Mapping[str, object], reference: Mapping[str, object],
                passages: Sequence[Mapping[str, object]],
                canonical_resolver: Callable[[Mapping[str, object], Mapping[str, object]], Mapping[str, object]]) -> dict[str, object]:
        from hashlib import sha256

        selected = [p for p in passages if all(p.get(key) == reference.get(key) for key in (
            "object_ref", "object_kind", "passage_ref", "version_or_checksum"))]
        if len(selected) != 1:
            raise ValueError("P0_LOCAL_CONTEXT_SOURCE_AMBIGUOUS_OR_ABSENT")
        actual = selected[0]
        key = (str(reference.get("notion_id")), *(str(actual[k]) for k in ("object_ref", "passage_ref", "version_or_checksum")))
        source = self.sources.index.get(cast(tuple[str, str, str, str], key))
        if source is None:
            raise ValueError("P0_LOCAL_CONTEXT_SOURCE_NOT_ADOPTED")
        binding = self.bindings.get((fingerprint(selection), str(source["admission_scope_sha256"])))
        if binding is None or as_plain(binding["selection"]) != as_plain(selection):
            raise ValueError("P0_LOCAL_CONTEXT_SELECTION_NOT_ADOPTED")
        canonical_entry = self.by_scope[str(binding["canonical_notion_entry_scope_sha256"])]
        canonical_passages = [p for p in passages if all(p.get(key) == canonical_entry[target] for key, target in (
            ("object_ref", "source_ref"), ("object_kind", "object_kind"), ("passage_ref", "locator"), ("version_or_checksum", "checksum_or_version")))]
        if len(canonical_passages) != 1:
            raise ValueError("P0_LOCAL_CONTEXT_CANONICAL_SOURCE_AMBIGUOUS_OR_ABSENT")
        for entry, passage in ((source, actual), (canonical_entry, canonical_passages[0])):
            text = passage.get("excerpt")
            if (passage.get("notion_ref") != entry["notion_ref"]
                    or passage.get("excerpt_truncated") is not False or not isinstance(text, str) or not 1 <= len(text) <= 4000
                    or any(passage.get(flag) is True for flag in ("is_private_evidence", "is_oracle", "is_teacher_reference"))
                    or sha256(text.encode("utf-8")).hexdigest() != entry["excerpt_sha256"]
                    or as_plain(passage.get("provenance", {})) != as_plain(entry["provenance"])
                    or as_plain(passage.get("source_status", {})) != as_plain(entry["source_status"])
                    or passage.get("authority", "UNKNOWN") != entry["available_authority"]
                    or passage.get("authority_basis", "NOT_ATTESTED_BY_APPLICATION") != entry["authority_basis"]):
                raise ValueError("P0_LOCAL_CONTEXT_NATIVE_SOURCE_CHANGED_OR_EXCLUDED")
        canonical_reference = {"notion_id": canonical_entry["notion_ref"], **{key: canonical_passages[0][key] for key in (
            "object_ref", "object_kind", "passage_ref", "version_or_checksum")}}
        resolution = object_data(as_plain(canonical_resolver(selection, canonical_reference)))
        scope = object_data(resolution.get("reference_scope", {}))
        if (resolution.get("contract_id") != ("BTS-RESOLUTION-1.0" if selection.get("contract_id") == "BTS-INSTITUTIONAL-CONTEXT-1.0" else "STMG-RESOLUTION-1.0")
                or resolution.get("status") != "RESOLVED_ADMITTED" or resolution.get("selection_sha256") != fingerprint(selection)
                or scope != canonical_scope(canonical_entry, resolution.get("contract_id"))
                or fingerprint(resolution) != binding["canonical_resolution_sha256"]):
            raise ValueError("P0_LOCAL_CONTEXT_CANONICAL_RESOLUTION_CHANGED")
        return {**resolution, "reference_scope": {"schema": "P0-EXACT-LOCAL-REFERENCE-SCOPE-1.0",
            **{key: actual[key] for key in ("object_ref", "object_kind", "passage_ref", "version_or_checksum")},
            "status": "OWNER_ADMITTED_EXACT_LOCAL_CONTEXT", "context_enrichment": False,
            "admission_basis": "OWNER_ADMITTED_EXACT_LOCAL_CONTEXT", "available_authority": source["available_authority"],
            "authority_basis": source["authority_basis"], "manifest_sha256": self.manifest_sha256,
            "owner_admission_sha256": self.owner_sha256, "source_entry_scope_sha256": source["admission_scope_sha256"],
            "canonical_notion_entry_scope_sha256": canonical_entry["admission_scope_sha256"],
            "canonical_institutional_resolution_sha256": binding["canonical_resolution_sha256"]}}

    def execute(self, *, request: Mapping[str, object], passages: Sequence[Mapping[str, object]],
                resolution: Mapping[str, object]) -> list[dict[str, object]]:
        """Separate source gate: caller supplies a freshly resolved native binding.

        _exact_source_receipts is extracted unchanged from legacy execute after
        its historical context checks. Legacy execute still rejects this status.
        """
        scope = object_data(resolution.get("reference_scope", {}))
        if scope.get("status") != "OWNER_ADMITTED_EXACT_LOCAL_CONTEXT":
            raise ValueError("P0_LOCAL_CONTEXT_SOURCE_RECEIPT_BINDING_CHANGED")
        object_data(scope, SCOPE_FIELDS)
        context = object_data(request["context"])
        selection = object_data(context.get("institutional", {}))
        captured = context.get("institutional_resolution")
        binding = self.bindings.get((fingerprint(selection), str(scope.get("source_entry_scope_sha256"))))
        if (not isinstance(captured, Mapping) or as_plain(captured) != as_plain(resolution)
                or resolution.get("status") != "RESOLVED_ADMITTED" or binding is None
                or resolution.get("selection_sha256") != fingerprint(selection)
                or scope.get("schema") != "P0-EXACT-LOCAL-REFERENCE-SCOPE-1.0"
                or scope.get("manifest_sha256") != self.manifest_sha256
                or scope.get("owner_admission_sha256") != self.owner_sha256
                or scope.get("admission_basis") != "OWNER_ADMITTED_EXACT_LOCAL_CONTEXT"
                or scope.get("context_enrichment") is not False
                or scope.get("canonical_notion_entry_scope_sha256") != binding["canonical_notion_entry_scope_sha256"]
                or scope.get("canonical_institutional_resolution_sha256") != binding["canonical_resolution_sha256"]):
            raise ValueError("P0_LOCAL_CONTEXT_SOURCE_RECEIPT_BINDING_CHANGED")
        source = self.by_scope[str(binding["source_entry_scope_sha256"])]
        canonical_entry = self.by_scope[str(binding["canonical_notion_entry_scope_sha256"])]
        native = {**resolution, "reference_scope": canonical_scope(canonical_entry, resolution.get("contract_id"))}
        if fingerprint(native) != binding["canonical_resolution_sha256"]:
            raise ValueError("P0_LOCAL_CONTEXT_CANONICAL_RESOLUTION_CHANGED")
        references = items(request["references"], 8)
        if (len(references) != 1 or any(scope[key] != source[target] for key, target in (
                ("object_ref", "source_ref"), ("object_kind", "object_kind"), ("passage_ref", "locator"), ("version_or_checksum", "checksum_or_version")))
                or any(references[0].get(key) != source[target] for key, target in (
                ("source_ref", "source_ref"), ("locator", "locator"), ("checksum_or_version", "checksum_or_version"), ("excerpt_sha256", "excerpt_sha256")))):
            raise ValueError("P0_LOCAL_CONTEXT_EXACT_SOURCE_RECEIPT_CHANGED")
        if (scope.get("available_authority") != source["available_authority"]
                or scope.get("authority_basis") != source["authority_basis"]
                or scope.get("object_kind") != source["object_kind"]):
            raise ValueError("P0_LOCAL_CONTEXT_SOURCE_RECEIPT_AUTHORITY_CHANGED")
        # Prototype uses the exact future shared helper. No legacy status is
        # rewritten and no private/unknown source check is relaxed.
        receipts = self.sources._exact_source_receipts(request=request, passages=passages, resolution=resolution)
        if len(receipts) != 1 or receipts[0]["admission_scope_sha256"] != binding["source_entry_scope_sha256"]:
            raise ValueError("P0_LOCAL_CONTEXT_EXACT_SOURCE_RECEIPT_CHANGED")
        return [{**receipt, "schema": "P0-SOURCE-ADMISSION-RECEIPT-2.0",
            "local_reference_context_manifest_sha256": self.manifest_sha256,
            "selection_sha256": binding["selection_sha256"],
            "canonical_notion_entry_scope_sha256": binding["canonical_notion_entry_scope_sha256"],
            "canonical_institutional_resolution_sha256": binding["canonical_resolution_sha256"]} for receipt in receipts]

    def metadata(self) -> list[dict[str, object]]:
        return [{"schema": "P0-LOCAL-REFERENCE-CONTEXT-ROW-1.0", "selection": as_plain(binding["selection"]), "selection_sha256": binding["selection_sha256"],
            "notion_id": self.by_scope[str(binding["source_entry_scope_sha256"])]["notion_ref"],
            "object_ref": self.by_scope[str(binding["source_entry_scope_sha256"])]["source_ref"],
            "object_kind": self.by_scope[str(binding["source_entry_scope_sha256"])]["object_kind"],
            "passage_ref": self.by_scope[str(binding["source_entry_scope_sha256"])]["locator"],
            "version_or_checksum": self.by_scope[str(binding["source_entry_scope_sha256"])]["checksum_or_version"],
            "excerpt_sha256": self.by_scope[str(binding["source_entry_scope_sha256"])]["excerpt_sha256"],
            "available_authority": self.by_scope[str(binding["source_entry_scope_sha256"])]["available_authority"],
            "authority_basis": self.by_scope[str(binding["source_entry_scope_sha256"])]["authority_basis"],
            "provenance": as_plain(self.by_scope[str(binding["source_entry_scope_sha256"])]["provenance"]),
            "source_status": as_plain(self.by_scope[str(binding["source_entry_scope_sha256"])]["source_status"]),
            "canonical_notion_reference": self._anchor_metadata(self.by_scope[str(binding["canonical_notion_entry_scope_sha256"])]),
            "source_entry_scope_sha256": binding["source_entry_scope_sha256"],
            "canonical_notion_entry_scope_sha256": binding["canonical_notion_entry_scope_sha256"],
            "canonical_institutional_resolution_sha256": binding["canonical_resolution_sha256"],
            "context_enrichment": False, "admission_basis": "OWNER_ADMITTED_EXACT_LOCAL_CONTEXT", "manifest_sha256": self.manifest_sha256}
            for binding in self.bindings.values()]

    @staticmethod
    def _anchor_metadata(entry: Mapping[str, object]) -> dict[str, object]:
        return {"notion_id": entry["notion_ref"], "object_ref": entry["source_ref"], "object_kind": entry["object_kind"],
            "passage_ref": entry["locator"], "version_or_checksum": entry["checksum_or_version"],
            "excerpt_sha256": entry["excerpt_sha256"], "provenance": as_plain(entry["provenance"]),
            "source_status": as_plain(entry["source_status"]), "available_authority": entry["available_authority"],
            "authority_basis": entry["authority_basis"]}
