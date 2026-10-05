"""Authenticates selected references through existing Application readers only."""
import hashlib
import json
from collections.abc import Mapping
from typing import TYPE_CHECKING

from backend.adapters.inbound.api.p0_creation import P0CreationEndpoint
from backend.modules.pedagogical_design.contracts.dto.assessment_bundle import items, object_data
from backend.modules.pedagogical_design.ports.outbound.p0_generation import P0GenerationPort
from backend.modules.quality_evaluation.ports.outbound.p0_review import P0ReviewPort
from backend.modules.work_orchestration.application.services.p0_creation import P0CreationService

if TYPE_CHECKING:
    from backend.infrastructure.composition.factories.local_browser import Read15RuntimeTarget


def build_p0_creation(target: "Read15RuntimeTarget", nonce: str,
                      generation: P0GenerationPort | None = None, review: P0ReviewPort | None = None) -> tuple[P0CreationService, P0CreationEndpoint]:
    # Local import avoids the existing target/factory dependency cycle.
    from backend.infrastructure.composition.factories.r6_p0 import (
        R6_EXACT_SOURCE_BINDINGS,
        load_p0_exact_reference,
        load_p0_reference,
    )

    def exact_passage(selection: Mapping[str, object]) -> dict[str, object]:
        from backend.infrastructure.composition.factories.r6_all_notions import (
            exact_notion_evidence,
        )

        with exact_notion_evidence(target) as inbound:
            inspected = inbound.inspect(str(selection["notion_id"]))
        matches = [p for p in items(inspected["items"], 256) if p["passage_ref"] == selection["passage_ref"]]
        if len(matches) != 1:
            raise ValueError("P0_REFERENCE_NOT_FOUND")
        return matches[0]

    def reference(selection: Mapping[str, object]) -> Mapping[str, object]:
        if set(selection) == {"notion_id", "passage_ref"}:
            passage = exact_passage(selection)
            if passage["object_kind"] not in {"NOTION", "PEDAGOGICAL_CONTENT", "METHOD"}:
                raise ValueError("P0_TEACHER_SOURCE_FORBIDDEN")
            if passage["excerpt_truncated"] or not passage["excerpt"]:
                raise ValueError("P0_REFERENCE_INCOMPLETE")
            excerpt = str(passage["excerpt"])
            from backend.modules.pedagogical_design.contracts.dto.p0_production import (
                P0_PROVENANCE_LABEL,
            )

            return {"reference": {
                "evidence_id": "evidence:" + hashlib.sha256(str(passage["passage_ref"]).encode()).hexdigest()[:32],
                "source_ref": passage["object_ref"], "locator": passage["passage_ref"],
                "checksum_or_version": passage["version_or_checksum"],
                "excerpt_sha256": hashlib.sha256(excerpt.encode()).hexdigest(),
                "provenance_label": P0_PROVENANCE_LABEL,
            }, "excerpt": excerpt}
        if set(selection) == {"query", "passage_ref"}:
            loaded = load_p0_reference(target, query=str(selection["query"]),
                passage_ref=str(selection["passage_ref"]), correlation_id="p0.reference")
            if loaded["object_kind"] not in {"NOTION", "PEDAGOGICAL_CONTENT", "METHOD",
                                               "FRAMEWORK_ELEMENT", "OFFICIAL_OCCURRENCE"}:
                raise ValueError("P0_TEACHER_SOURCE_FORBIDDEN")
            return {"reference": loaded["reference"], "excerpt": loaded["excerpt"]}
        selected = object_data(selection, {"resource_ref", "resource_version_ref"})
        loaded = load_p0_exact_reference(target, resource_ref=str(selected["resource_ref"]),
                                        resource_version_ref=str(selected["resource_version_ref"]))
        exact = object_data(loaded["exact_source"])
        body = object_data(json.loads(str(exact["body"])))
        # Student material only. Never send the source correction/points as an oracle.
        statement = body.get("case") or body.get("statement") or body.get("prompt")
        if not isinstance(statement, str) or not statement:
            raise ValueError("P0_REFERENCE_STUDENT_SHAPE")
        questions = items(exact["questions"])
        excerpt = "\n".join([statement, *(str(object_data(q)["prompt"]) for q in questions)])
        descriptor = object_data(loaded["reference"])
        descriptor["excerpt_sha256"] = hashlib.sha256(excerpt.encode()).hexdigest()
        return {"reference": descriptor, "excerpt": excerpt}

    from backend.infrastructure.composition.factories.institutional_catalog import (
        bts_alignment,
        stmg_alignment,
    )

    def resolve_institutional(selection: Mapping[str, object], selected_reference: Mapping[str, object]) -> Mapping[str, object]:
        if set(selected_reference) != {"notion_id", "passage_ref"}:
            raise ValueError("P0_INSTITUTIONAL_EXACT_NOTION_SOURCE_REQUIRED")
        passage = exact_passage(selected_reference)
        # Identity is provided by the authenticated Application reader, never the UI.
        attested = {**selected_reference, **{key: passage[key] for key in (
            "object_ref", "object_kind", "passage_ref", "version_or_checksum")}}
        resolver = bts_alignment if selection.get("contract_id") == "BTS-INSTITUTIONAL-CONTEXT-1.0" else stmg_alignment
        return resolver(target, selection=dict(selection), reference=attested)

    service = P0CreationService(reference, generation=generation, review=review,
        institutional_resolver=resolve_institutional, exact_institutional_required=True)
    metadata: list[dict[str, object]] = [{"resource_ref": binding.resource_ref, "resource_version_ref": binding.resource_version_ref,
                 "title": binding.canonical_title, "scenarios": list(binding.scenarios),
                 "authority": "NONE", "lifecycle_status": binding.lifecycle_status,
                 "validation_status": binding.validation_status} for binding in R6_EXACT_SOURCE_BINDINGS]
    endpoint = P0CreationEndpoint(service.execute, service.read, metadata, nonce=nonce,
        generation_bound=generation is not None, review_bound=review is not None,
        institutional_catalog=lambda: {**stmg_alignment(target), **bts_alignment(target)})
    return service, endpoint
