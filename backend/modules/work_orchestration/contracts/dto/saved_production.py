"""Durable documentary envelope, never a restored session or authority."""
from __future__ import annotations

import re
from collections.abc import Mapping
from dataclasses import dataclass

from backend.modules.pedagogical_design.contracts.dto.assessment_bundle import (
    AssessmentBundle,
    as_plain,
    encoded,
    fingerprint,
    items,
    object_data,
)
from backend.modules.pedagogical_design.contracts.dto.p0_production import P0Production
from backend.modules.work_orchestration.contracts.dto.p0_production_read_view import (
    P0ProductionReadView,
)
from backend.modules.work_orchestration.contracts.dto.production_read_view import ProductionReadView
from backend.shared_kernel._safe_data import freeze_safe_mapping

SAVED_CONTRACT = "SAVED-PRODUCTION-1.0"
SAVED_P0_CONTRACT = "SAVED-PRODUCTION-P0-1.0"


@dataclass(frozen=True, slots=True)
class SavedProduction:
    data: Mapping[str, object]

    def __post_init__(self) -> None:
        data = object_data(self.data, {"contract_id", "view", "bundle", "reviews", "validations",
                                      "origin", "provenance", "reservations"})
        if data["contract_id"] not in {SAVED_CONTRACT, SAVED_P0_CONTRACT}:
            raise ValueError("SAVED_CONTRACT")
        view_data = object_data(data["view"])
        if data["contract_id"] == SAVED_CONTRACT:
            lineage = object_data(view_data.get("lineage"))
            view: ProductionReadView | P0ProductionReadView = ProductionReadView(
                str(view_data.get("production_ref")),
                str(view_data.get("version_ref")),
                str(lineage.get("conversation_id")),
                view_data,
            )
            legacy_bundle = (
                AssessmentBundle(object_data(data["bundle"])) if data["bundle"] else None
            )
            if legacy_bundle is not None and (
                (legacy_bundle.production_ref, legacy_bundle.version_ref)
                != (view.production_ref, view.version_ref)
                or as_plain(legacy_bundle.data["subject"])
                != {"content": view.data["content"], "sections": as_plain(view.data["sections"])}
                or as_plain(legacy_bundle.data["pedagogical_context"])
                != as_plain(view.data["pedagogical_context"])
                or as_plain(legacy_bundle.data["references"])
                != as_plain(view.data["references"])
            ):
                raise ValueError("SAVED_VERSION_MISMATCH")
            active_bundle_sha = legacy_bundle.sha256 if legacy_bundle else None
        else:
            view = P0ProductionReadView(view_data)
            p0_bundle = P0Production(object_data(data["bundle"]))
            expected_view = P0ProductionReadView.from_bundle(p0_bundle)
            if (
                (p0_bundle.production_ref, p0_bundle.version_ref)
                != (view.production_ref, view.version_ref)
                or as_plain(expected_view.data) != as_plain(view.data)
            ):
                raise ValueError("SAVED_VERSION_MISMATCH")
            active_bundle_sha = p0_bundle.sha256
        for field in ("reviews", "validations"):
            for report in items(data[field], 32):
                if (report.get("production_ref"), report.get("version_ref")) != (
                    view.production_ref, view.version_ref
                ) or report.get("bundle_sha256") != active_bundle_sha:
                    raise ValueError("SAVED_REPORT_MISMATCH")
        if data["origin"] not in {"LOCAL_APPLICATION", "IMPORTED_DOCUMENTARY"}:
            raise ValueError("SAVED_ORIGIN")
        provenance = object_data(data["provenance"])
        if len(provenance) > 16 or any(
            re.fullmatch(r"[A-Z][A-Z0-9_]{0,63}", k) is None
            or not isinstance(v, str) or re.fullmatch(r"[0-9a-f]{64}", v) is None
            for k, v in provenance.items()
        ) or (data["origin"] == "IMPORTED_DOCUMENTARY" and not provenance):
            raise ValueError("SAVED_PROVENANCE")
        if not isinstance(data["reservations"], (list, tuple)) or len(data["reservations"]) > 16:
            raise ValueError("SAVED_RESERVATIONS")
        if any(not isinstance(v, str) or not 1 <= len(v) <= 1000 for v in data["reservations"]):
            raise ValueError("SAVED_RESERVATIONS")
        if len(encoded(data)) > 512 * 1024:
            raise ValueError("SAVED_SIZE")
        object.__setattr__(self, "data", freeze_safe_mapping(data))

    @property
    def production_ref(self) -> str:
        return str(object_data(self.data["view"])["production_ref"])

    @property
    def version_ref(self) -> str:
        return str(object_data(self.data["view"])["version_ref"])

    @property
    def sha256(self) -> str:
        return fingerprint(self.data)

    @property
    def view(self) -> ProductionReadView | P0ProductionReadView:
        data = object_data(self.data["view"])
        if self.data["contract_id"] == SAVED_P0_CONTRACT:
            return P0ProductionReadView(data)
        return ProductionReadView(self.production_ref, self.version_ref,
            str(object_data(data["lineage"])["conversation_id"]), data)

    @property
    def bundle(self) -> AssessmentBundle | None:
        if self.data["contract_id"] == SAVED_P0_CONTRACT:
            return None
        return AssessmentBundle(object_data(self.data["bundle"])) if self.data["bundle"] else None

    @property
    def p0_bundle(self) -> P0Production | None:
        if self.data["contract_id"] != SAVED_P0_CONTRACT:
            return None
        return P0Production(object_data(self.data["bundle"]))

    def mutable_copy(self) -> dict[str, object]:
        return object_data(as_plain(self.data))
