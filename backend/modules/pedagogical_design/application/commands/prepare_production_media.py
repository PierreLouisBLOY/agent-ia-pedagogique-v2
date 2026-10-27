"""Application media authoring accepts explicit briefs/bytes, never paths or URLs."""
from collections.abc import Mapping
from secrets import token_hex

from backend.modules.materialization_export.application.services.media_asset import MediaAssetWorker
from backend.modules.pedagogical_design.application.commands.create_p0_candidate import (
    ReviseP0Candidate,
    ReviseSavedP0Candidate,
)
from backend.modules.pedagogical_design.contracts.dto.assessment_bundle import (
    as_plain,
    fingerprint,
    items,
    object_data,
)
from backend.modules.pedagogical_design.contracts.dto.production_media import (
    MEDIA_PLAN_CONTRACT,
    MEDIA_PRODUCTION_CONTRACT,
    ProductionMediaPlan,
    dependencies,
)
from backend.modules.pedagogical_design.contracts.dto.visual_brief import VisualBrief
from backend.modules.validation_control.application.commands.validate_p0 import ValidateP0Command
from backend.modules.work_orchestration.contracts.dto.p0_production_read_view import (
    P0ProductionReadView,
)
from backend.modules.work_orchestration.contracts.dto.saved_production import (
    SAVED_P0_CONTRACT,
    SavedProduction,
)


class PrepareProductionMediaCommand:
    def __init__(self, worker: MediaAssetWorker) -> None:
        self.worker = worker

    def execute(self, parent: SavedProduction, proposals: object, *, evidence: Mapping[str, str] | None = None,
                no_media_reason: str | None = None) -> SavedProduction:
        original = parent.p0_bundle
        if original is None or "course_chapter" in original.data or parent.data["origin"] != "LOCAL_APPLICATION":
            raise ValueError("PRODUCTION_MEDIA_LOCAL_P0_REQUIRED")
        proposals = items(proposals, 8)
        if "media_plan" in original.data:
            required = {str(object_data(row["brief"])["visual_id"])
                        for row in items(object_data(original.data["media_plan"])["entries"], 8) if row["required"]}
            retained = {str(object_data(row.get("brief"))["visual_id"])
                        for row in proposals if row.get("required") is True}
            if not required <= retained:
                raise ValueError("PRODUCTION_MEDIA_REQUIRED_OMISSION_REJECTED")
        data = original.mutable_copy()
        data.update(contract_id=MEDIA_PRODUCTION_CONTRACT, version_ref="ver:" + token_hex(16))
        data["lineage"] = {**object_data(data["lineage"]), "parent_version_ref": original.version_ref}
        raw_reservations = parent.data["reservations"]
        if not isinstance(raw_reservations, (list, tuple)):
            raise ValueError("PRODUCTION_MEDIA_RESERVATIONS_INVALID")
        reservations = list(raw_reservations)
        additions = ["Revue sémantique et rendu des nouveaux médias à effectuer ; recette enseignante non effectuée."]
        if evidence is None:
            additions.append("HISTORICAL_EVIDENCE_NOT_REVALIDATED")
        reservations.extend(r for r in additions if r not in reservations)
        if len(reservations) > 16:
            raise ValueError("PRODUCTION_MEDIA_RESERVATIONS_FULL")
        provenance = object_data(parent.data["provenance"])
        suffix = str(data["version_ref"])[4:20].upper()
        if len(provenance) + 3 > 16:
            raise ValueError("PRODUCTION_MEDIA_PROVENANCE_FULL")
        if any(prefix + suffix in provenance for prefix in ("MEDIA_PARENT_RECORD_", "MEDIA_PARENT_BUNDLE_", "MEDIA_PLAN_")):
            raise ValueError("PRODUCTION_MEDIA_PROVENANCE_CONFLICT")
        known = dependencies(data)
        entries = []
        for row in proposals:
            object_data(row, {"brief", "required", "dependency_refs", "materialize", "admitted_bytes", "admission", "omission_reason"})
            brief = VisualBrief(object_data(row["brief"]))
            refs = row["dependency_refs"]
            if not isinstance(refs, (list, tuple)) or any(not isinstance(ref, str) or ref not in known for ref in refs):
                raise ValueError("PRODUCTION_MEDIA_DEPENDENCY_UNKNOWN")
            if len(refs) != len(set(refs)):
                raise ValueError("PRODUCTION_MEDIA_DEPENDENCY_DUPLICATE")
            entry: dict[str, object] = {"brief": as_plain(brief.data), "asset": None,
                "required": row["required"], "dependencies": {"context": data["context_sha256"], **{ref: known[ref] for ref in refs}},
                "omission_reason": row["omission_reason"]}
            # Validate context, audience and dependency binding before the renderer.
            provisional = {**entry, "omission_reason": row["omission_reason"] or "Préparation locale en cours."}
            plan = ProductionMediaPlan({"contract_id": MEDIA_PLAN_CONTRACT, "version_ref": data["version_ref"],
                "context_sha256": data["context_sha256"], "entries": [provisional], "no_media_reason": None})
            plan.bind(data)
            if type(row["materialize"]) is not bool:
                raise ValueError("PRODUCTION_MEDIA_MATERIALIZE")
            if row["materialize"]:
                raw = row["admitted_bytes"]
                admission = row["admission"]
                if raw is not None and not isinstance(raw, bytes):
                    raise ValueError("PRODUCTION_MEDIA_BYTES_REQUIRED")
                if admission is not None and not isinstance(admission, Mapping):
                    raise ValueError("PRODUCTION_MEDIA_ADMISSION_REQUIRED")
                asset = self.worker.execute(brief, admitted_bytes=raw, admission=admission)
                entry.update(asset=as_plain(asset.data), omission_reason=None)
            elif row["admitted_bytes"] is not None or row["admission"] is not None:
                raise ValueError("PRODUCTION_MEDIA_OMITTED_INPUT")
            entries.append(entry)
        data["media_plan"] = {"contract_id": MEDIA_PLAN_CONTRACT, "version_ref": data["version_ref"],
            "context_sha256": data["context_sha256"], "entries": entries, "no_media_reason": no_media_reason}
        child = (ReviseSavedP0Candidate().execute(original, data) if evidence is None else
                 ReviseP0Candidate().execute(original, data, evidence=evidence))
        validation = ValidateP0Command().execute(child, parent=original)
        if evidence is None:
            validation.update(sources="RESERVE", source_reason="HISTORICAL_EVIDENCE_NOT_REVALIDATED",
                              dispatch_permitted=False, active_authority="NONE_RESTORED")
        validation["media_controls"] = {"dependency_binding": "PASS", "asset_integrity": "PASS",
            "semantic_review": "NOT_RUN", "pixel_review": "NOT_RUN", "export_review": "NOT_RUN"}
        exact_plan = ProductionMediaPlan(object_data(data["media_plan"]))
        availability = {}
        for audience in ("student", "correction", "marking"):
            try:
                exact_plan.media(audience)
                availability[audience] = "AVAILABLE_OR_JUSTIFIED_OMISSION"
            except ValueError as exc:
                if not str(exc).startswith("PRODUCTION_MEDIA_REQUIRED_MISSING:"):
                    raise
                availability[audience] = str(exc)
        validation["media_export_availability"] = availability
        return SavedProduction({"contract_id": SAVED_P0_CONTRACT,
            "view": as_plain(P0ProductionReadView.from_bundle(child).data), "bundle": child.mutable_copy(),
            "reviews": [], "validations": [validation], "origin": "LOCAL_APPLICATION",
            "provenance": {**provenance, "MEDIA_PARENT_RECORD_" + suffix: parent.sha256,
                "MEDIA_PARENT_BUNDLE_" + suffix: original.sha256, "MEDIA_PLAN_" + suffix: fingerprint(data["media_plan"])},
            "reservations": reservations})
