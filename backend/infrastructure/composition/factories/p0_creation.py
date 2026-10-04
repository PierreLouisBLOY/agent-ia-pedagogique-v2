"""Authenticates selected references through existing Application readers only."""
import hashlib
import json
from collections.abc import Mapping
from typing import TYPE_CHECKING

from backend.adapters.inbound.api.p0_creation import P0CreationEndpoint
from backend.modules.pedagogical_design.contracts.dto.assessment_bundle import items, object_data
from backend.modules.pedagogical_design.ports.outbound.p0_generation import P0GenerationPort
from backend.modules.work_orchestration.application.services.p0_creation import P0CreationService

if TYPE_CHECKING:
    from backend.infrastructure.composition.factories.local_browser import Read15RuntimeTarget


def build_p0_creation(target: "Read15RuntimeTarget", nonce: str,
                      generation: P0GenerationPort | None = None) -> tuple[P0CreationService, P0CreationEndpoint]:
    # Local import avoids the existing target/factory dependency cycle.
    from backend.infrastructure.composition.factories.r6_p0 import (
        R6_EXACT_SOURCE_BINDINGS,
        load_p0_exact_reference,
        load_p0_reference,
    )

    def reference(selection: Mapping[str, object]) -> Mapping[str, object]:
        if set(selection) == {"query", "passage_ref"}:
            loaded = load_p0_reference(target, query=str(selection["query"]),
                passage_ref=str(selection["passage_ref"]), correlation_id="p0.reference")
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

    service = P0CreationService(reference, generation=generation)
    metadata: list[dict[str, object]] = [{"resource_ref": binding.resource_ref, "resource_version_ref": binding.resource_version_ref,
                 "title": binding.canonical_title, "scenarios": list(binding.scenarios),
                 "authority": "NONE", "lifecycle_status": binding.lifecycle_status,
                 "validation_status": binding.validation_status} for binding in R6_EXACT_SOURCE_BINDINGS]
    endpoint = P0CreationEndpoint(service.execute, service.read, metadata, nonce=nonce)
    return service, endpoint
