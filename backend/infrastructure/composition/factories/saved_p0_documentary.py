"""Reuse an authenticated historical P0 assembly without restoring authority."""
from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path

from backend.infrastructure.composition.factories.local_browser import build_saved_application
from backend.modules.pedagogical_design.application.commands.reassemble_p0_candidate import (
    DossierPartition,
    ReassembleP0Candidate,
)
from backend.modules.pedagogical_design.contracts.dto.assessment_bundle import object_data
from backend.modules.work_orchestration.contracts.dto.p0_production_read_view import (
    P0ProductionReadView,
)
from backend.modules.work_orchestration.contracts.dto.saved_production import (
    SAVED_P0_CONTRACT,
    SavedProduction,
)


def admit_saved_p0_documentary(
    source_root: Path, target_root: Path, *, production_ref: str, version_ref: str,
    expected_record_sha256: str, create: bool = False,
) -> dict[str, object]:
    source = build_saved_application(source_root)
    opened = source.execute("open", production_ref, version_ref,
                            correlation="p0.documentary.source")
    if not isinstance(opened, dict) or opened["record_sha256"] != expected_record_sha256:
        raise ValueError("P0_DOCUMENTARY_SOURCE_IDENTITY")
    return admit_p0_documentary_record(object_data(opened["record"]), target_root,
        expected_record_sha256=expected_record_sha256, create=create)


def admit_p0_documentary_record(
    record_data: Mapping[str, object], target_root: Path, *,
    expected_record_sha256: str, create: bool = False,
) -> dict[str, object]:
    """Consume an Application export across local Windows contexts, with its pin.

    The caller passes the declared owner identity, never the observed digest.
    No historical authority survives this documentary-only handoff.
    """
    original = SavedProduction(record_data)
    if original.sha256 != expected_record_sha256:
        raise ValueError("P0_DOCUMENTARY_SOURCE_IDENTITY")
    if original.data["contract_id"] != SAVED_P0_CONTRACT:
        raise ValueError("P0_DOCUMENTARY_SOURCE_KIND")
    data = original.mutable_copy()
    data["origin"] = "IMPORTED_DOCUMENTARY"
    data["reviews"] = []
    data["validations"] = []
    data["provenance"] = {**object_data(data["provenance"]), "HISTORICAL_RECORD": original.sha256}
    reservations = data["reservations"]
    if not isinstance(reservations, list):
        raise ValueError("P0_DOCUMENTARY_RESERVATIONS")
    data["reservations"] = [*reservations,
        "Assemblage P0 historique importé sans session, validation ou promotion restaurée.",
        "Le sujet reçu et le corrigé/barème de référence gardent leurs origines distinctes.",
        "Les références professeur ne sont pas des réponses produites par le fournisseur."]
    documentary = SavedProduction(data)
    target = build_saved_application(target_root, create=create)
    saved = target.admit_documentary(documentary)
    reopened = target.execute("open", original.production_ref, original.version_ref,
                              correlation="p0.documentary.reopen")
    if not isinstance(reopened, dict) or reopened["record_sha256"] != documentary.sha256:
        raise ValueError("P0_DOCUMENTARY_REOPEN_IDENTITY")
    return {"saved": saved, "record_sha256":documentary.sha256,
            "source_record_sha256":original.sha256,
            "bundle_sha256":original.p0_bundle.sha256 if original.p0_bundle else None,
            "active_authority":reopened["active_authority"],
            "historical_reports_copied":False, "provider_calls":0}


def reassemble_p0_documentary_record(
    record_data: Mapping[str, object], target_root: Path, *, expected_record_sha256: str,
    expected_bundle_sha256: str, version_ref: str, partitions: tuple[DossierPartition, ...],
    plan_sha256: str, create: bool = False,
) -> dict[str, object]:
    """Application handoff with explicit parent pins and documentary-only successor."""
    original = SavedProduction(record_data)
    if original.sha256 != expected_record_sha256 or original.p0_bundle is None:
        raise ValueError("P0_DOCUMENTARY_SOURCE_IDENTITY")
    child = ReassembleP0Candidate().execute(original.p0_bundle,
        expected_sha256=expected_bundle_sha256, version_ref=version_ref, partitions=partitions)
    data = original.mutable_copy()
    data.update({"bundle": child.mutable_copy(),
        "view": dict(P0ProductionReadView.from_bundle(child).data),
        "origin": "IMPORTED_DOCUMENTARY", "reviews": [], "validations": [],
        "provenance": {"ASSEMBLY_PARENT": original.sha256,
                       "ASSEMBLY_SOURCE": expected_bundle_sha256, "ASSEMBLY_PLAN": plan_sha256}})
    documentary = SavedProduction(data)
    target = build_saved_application(target_root, create=create)
    saved = target.admit_documentary(documentary)
    reopened = target.execute("open", child.production_ref, child.version_ref,
                              correlation="p0.assembly.reopen")
    if not isinstance(reopened, dict) or reopened["record_sha256"] != documentary.sha256:
        raise ValueError("P0_DOCUMENTARY_REOPEN_IDENTITY")
    return {"saved": saved, "record_sha256": documentary.sha256,
            "bundle_sha256": child.sha256, "parent_record_sha256": original.sha256,
            "parent_bundle_sha256": expected_bundle_sha256,
            "active_authority": reopened["active_authority"], "provider_calls": 0}
