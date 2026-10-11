"""Application command for local structured P0 candidates; it never dispatches a provider."""

from __future__ import annotations

import hashlib
from collections.abc import Mapping

from backend.modules.pedagogical_design.contracts.dto.assessment_bundle import (
    items,
    object_data,
)
from backend.modules.pedagogical_design.contracts.dto.p0_production import P0Production
from backend.modules.pedagogical_design.contracts.dto.program_authority import (
    require_supported_claims,
)


class CreateP0Candidate:
    def execute(
        self,
        data: Mapping[str, object],
        *,
        evidence: Mapping[str, str],
        required_facts: tuple[str, ...] = (),
    ) -> P0Production:
        candidate = P0Production(data)
        self.validate_content(candidate)
        references = items(candidate.data["references"], 8)
        expected_ids = {str(reference["evidence_id"]) for reference in references}
        if set(evidence) != expected_ids or not evidence:
            raise ValueError("P0_EVIDENCE_INSUFFICIENT")
        for reference in references:
            evidence_id = str(reference["evidence_id"])
            excerpt = evidence[evidence_id]
            if not excerpt or hashlib.sha256(excerpt.encode("utf-8")).hexdigest() != reference[
                "excerpt_sha256"
            ]:
                raise ValueError("P0_EVIDENCE_CHANGED")
        joined = "\n".join(evidence.values()).casefold()
        if any(not fact.strip() or fact.casefold() not in joined for fact in required_facts):
            raise ValueError("P0_REQUIRED_FACT_MISSING")
        return candidate

    @staticmethod
    def validate_content(candidate: P0Production) -> None:
        """Shared structural/authority checks; never asserts source freshness."""
        context = object_data(candidate.data["context"])
        text = "\n".join(str(row[key]) for field, keys in (
            ("sections", ("heading", "text")), ("questions", ("prompt",)),
            ("corrections", ("expected_answer", "rationale")))
            for row in items(candidate.data[field], 60) for key in keys)
        require_supported_claims(text, context.get("institutional_resolution"))
        if context.get("institutional") is not None and context["resource_type"] == "COURSE" and "course_chapter" not in candidate.data:
            from backend.modules.pedagogical_design.contracts.dto.course_policy import (
                validate_course_structure,
            )

            validate_course_structure(candidate.data["sections"])
        limitations = candidate.data["limitations"]
        if not isinstance(limitations, tuple) or not any(
            "CANDIDATE" in str(item) for item in limitations
        ):
            raise ValueError("P0_CANDIDATE_LIMITATION_REQUIRED")


class ReviseP0Candidate:
    def execute(
        self,
        parent: P0Production,
        data: Mapping[str, object],
        *,
        evidence: Mapping[str, str],
        required_facts: tuple[str, ...] = (),
    ) -> P0Production:
        candidate = CreateP0Candidate().execute(
            data, evidence=evidence, required_facts=required_facts
        )
        lineage = object_data(candidate.data["lineage"])
        if (
            candidate.production_ref != parent.production_ref
            or lineage["parent_version_ref"] != parent.version_ref
            or candidate.version_ref == parent.version_ref
        ):
            raise ValueError("P0_REVISION_LINEAGE")
        return candidate


class ReviseSavedP0Candidate:
    """Explicit local edit of an authenticated parent, not evidence revalidation."""

    def execute(self, parent: P0Production, data: Mapping[str, object]) -> P0Production:
        candidate = P0Production(data)
        CreateP0Candidate.validate_content(candidate)
        lineage = object_data(candidate.data["lineage"])
        old_lineage = object_data(parent.data["lineage"])
        if (candidate.production_ref != parent.production_ref
                or candidate.version_ref == parent.version_ref
                or lineage["parent_version_ref"] != parent.version_ref
                or {k: v for k, v in lineage.items() if k != "parent_version_ref"}
                != {k: v for k, v in old_lineage.items() if k != "parent_version_ref"}
                or candidate.data["context"] != parent.data["context"]
                or candidate.data["references"] != parent.data["references"]):
            raise ValueError("P0_SAVED_REVISION_BINDING")
        return candidate
