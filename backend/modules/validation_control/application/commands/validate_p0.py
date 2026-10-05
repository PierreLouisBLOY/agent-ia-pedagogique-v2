"""Structural R6 P0 validation; semantic promotion remains a separate decision."""

from __future__ import annotations

from backend.modules.pedagogical_design.contracts.dto.assessment_bundle import (
    fingerprint,
    object_data,
)
from backend.modules.pedagogical_design.contracts.dto.p0_production import P0Production


class ValidateP0Command:
    def execute(
        self, bundle: P0Production, *, parent: P0Production | None = None
    ) -> dict[str, object]:
        lineage = object_data(bundle.data["lineage"])
        if parent is not None and (
            bundle.production_ref != parent.production_ref
            or lineage["parent_version_ref"] != parent.version_ref
        ):
            raise ValueError("P0_REVISION_LINEAGE")
        if parent is None and lineage["parent_version_ref"] is not None:
            raise ValueError("P0_PARENT_REQUIRED")
        report: dict[str, object] = {
            "contract_id": "R6-P0-VALIDATION-1.0",
            "production_ref": bundle.production_ref,
            "version_ref": bundle.version_ref,
            "bundle_sha256": bundle.sha256,
            "status": "PASS",
            "checks": (
                "P0_SCHEMA",
                "P0_PROJECTIONS",
                "P0_REFERENCE_TRACEABILITY",
                "P0_VERSION_LINEAGE",
            ),
            "promotion": "NOT_PERFORMED",
        }
        if bundle.context.institutional is not None:
            resolution = object_data(bundle.context.data["institutional_resolution"])
            report["institutional_status"] = resolution["status"]
            report["institutional_resolution_sha256"] = fingerprint(resolution)
            report["dispatch_permitted"] = resolution["status"] == "RESOLVED_ADMITTED"
            report["pedagogical_acceptance"] = "NOT_PERFORMED"
            if bundle.context.resource_type == "COURSE":
                if "course_chapter" in bundle.data:
                    from backend.modules.pedagogical_design.contracts.dto.course_chapter import (
                        CourseChapter,
                    )

                    chapter = CourseChapter(object_data(bundle.data["course_chapter"]))
                    chapter.bind_context(bundle.context)
                    report["course_policy"] = "COURSE-CHAPTER-1.0"
                    report["course_checks"] = chapter.checks()
                    report["visual_review"] = "REQUIRED_NOT_ATTESTED"
                else:
                    from backend.modules.pedagogical_design.contracts.dto.course_policy import (
                        validate_course_structure,
                    )

                    validate_course_structure(bundle.data["sections"])
                    report["course_policy"] = "COURSE-EXPLAINED-1.0"
                    report["course_benchmark"] = "INCOMPLETE_FOR_BENCHMARK"
        return report
