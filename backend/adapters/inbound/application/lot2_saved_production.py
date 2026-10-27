"""R4 inbound successor for already authenticated, exact saved R6 P0 bundles."""

from __future__ import annotations

from collections.abc import Mapping

from backend.adapters.inbound.application.saved_production import SavedProductionInbound
from backend.modules.pedagogical_design.contracts.dto.assessment_bundle import (
    identifier,
    object_data,
)
from backend.modules.work_orchestration.contracts.dto.p0_codesign_trace import (
    SAVED_CODESIGN_CONTRACT,
)
from backend.modules.work_orchestration.contracts.dto.saved_production import SavedProduction


class Lot2SavedProductionInbound(SavedProductionInbound):
    def read_local_p0(self, production_ref: str, version_ref: str) -> SavedProduction:
        """Application-only read callback; no client can submit a stored bundle."""
        return self.service.read_local_p0(production_ref, version_ref)

    def execute(
        self, operation: str, production_ref: str = "", version_ref: str = "",
        *, body: Mapping[str, object] | None = None, kind: str = "",
        correlation: str,
    ) -> dict[str, object] | bytes:
        if operation == "list":
            return super().execute(operation, production_ref, version_ref,
                                   body=body, kind=kind, correlation=correlation)
        if operation == "save":
            values = dict(body or {})
            if set(values) != {"production_ref", "version_ref"} or self.source is None:
                raise ValueError("R4_SOURCE_NOT_AVAILABLE")
            production = identifier(values["production_ref"], "prod")
            version = identifier(values["version_ref"], "ver")
            record = self.source(production, version)
            if record.p0_bundle is None:
                return super().execute(operation, production_ref, version_ref,
                                       body=body, kind=kind, correlation=correlation)
            if record.data["origin"] != "LOCAL_APPLICATION":
                raise ValueError("R4_SOURCE_NOT_AVAILABLE")
            lineage: list[SavedProduction] = []
            seen = {version}
            parent_ref = object_data(record.p0_bundle.data["lineage"])["parent_version_ref"]
            while isinstance(parent_ref, str):
                parent_version = identifier(parent_ref, "ver")
                if parent_version in seen or len(lineage) >= 32:
                    raise ValueError("R4_SOURCE_NOT_AVAILABLE")
                seen.add(parent_version)
                parent = self.source(production, parent_version)
                if (parent.production_ref != production or parent.version_ref != parent_version
                        or parent.p0_bundle is None or parent.data["origin"] != "LOCAL_APPLICATION"):
                    raise ValueError("R4_SOURCE_NOT_AVAILABLE")
                lineage.append(parent)
                parent_ref = object_data(parent.p0_bundle.data["lineage"])["parent_version_ref"]
            for parent in reversed(lineage):
                self.service.save(parent)
            return super().execute(operation, production_ref, version_ref,
                                   body=body, kind=kind, correlation=correlation)
        record = self.service.store.load(production_ref, version_ref)
        if operation == "edit":
            values = dict(body or {})
            if (set(values) != {"action_id", "record_sha256", "question_id", "prompt", "expected_answer", "rationale"}
                    or any(not isinstance(v, str) for v in values.values())):
                raise ValueError("R4_REQUEST_REJECTED")
            return self.service.edit_local_chapter(production_ref, version_ref,
                action_id=identifier(values["action_id"], "action"),
                expected_sha256=str(values["record_sha256"]), question_id=str(values["question_id"]),
                prompt=str(values["prompt"]), expected_answer=str(values["expected_answer"]),
                rationale=str(values["rationale"]))
        if operation == "compare":
            if body:
                raise ValueError("R4_REQUEST_REJECTED")
            return self.service.compare_local_chapter(production_ref, version_ref, kind)
        if record.p0_bundle is None:
            return super().execute(operation, production_ref, version_ref,
                                   body=body, kind=kind, correlation=correlation)
        # Store.load revalidates the full SavedProduction envelope and its exact
        # student view against the P0 bundle. CAP-R02's historical R2 view remains
        # unchanged; the P0 read is this authenticated Application record.
        if operation == "open":
            return self.service.open(production_ref, version_ref)
        if operation in {"preview", "word"}:
            if (
                (record.p0_bundle.context.resource_type == "COURSE" and kind != "student"
                 and not (kind == "correction" and ("course_chapter" in record.p0_bundle.data
                    or record.data["contract_id"] == SAVED_CODESIGN_CONTRACT)))
                or (record.p0_bundle.context.resource_type != "ASSESSMENT" and kind == "marking")
            ):
                raise ValueError("R4_EXPORT_KIND")
            if operation == "preview":
                return self.exporter.preview(record, kind).as_dict()
            return self.exporter.execute(record, kind)
        if operation == "validate":
            values = dict(body or {})
            if set(values) != {"action_id", "record_sha256"}:
                raise ValueError("R4_REQUEST_REJECTED")
            return self.service.validate_p0(
                production_ref, version_ref,
                identifier(values["action_id"], "action"), str(values["record_sha256"]),
            )
        # P0 promotion needs a separate canonical decision. Save and structural
        # validation cannot silently grant that authority.
        raise ValueError("R4_VALIDATION_REQUIRED")
