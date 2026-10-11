"""Binds exact preparation and source admission through Application readers only."""
from collections.abc import Mapping
from typing import TYPE_CHECKING

from backend.adapters.inbound.api.p0_creation import P0CreationEndpoint
from backend.adapters.outbound.generation.openai.p0_product import P0ProductGenerationAdapter
from backend.modules.pedagogical_design.contracts.dto.assessment_bundle import (
    fingerprint,
    items,
    object_data,
)
from backend.modules.work_orchestration.application.queries.p0_source_admission import (
    ReadP0SourceAdmission,
)
from backend.modules.work_orchestration.application.services.p0_consent import P0ConsentService
from backend.modules.work_orchestration.application.services.p0_creation import P0CreationService

if TYPE_CHECKING:
    from backend.infrastructure.composition.factories.local_browser import Read15RuntimeTarget


def bind_product_consent(service: P0CreationService, endpoint: P0CreationEndpoint, *,
                         target: "Read15RuntimeTarget", generation: P0ProductGenerationAdapter,
                         admission: ReadP0SourceAdmission) -> None:
    if service.generation is not generation:
        raise ValueError("P0_PRODUCT_GENERATION_BINDING")

    def prepared(ref: str, checksum: str) -> Mapping[str, object]:
        value = service.prepared.get(ref)
        if value is None or fingerprint(value) != checksum:
            raise ValueError("P0_PREPARATION_CHANGED")
        return value

    def sources(request: Mapping[str, object]) -> list[dict[str, object]]:
        from backend.infrastructure.composition.factories.institutional_catalog import (
            bts_alignment,
            stmg_alignment,
        )
        from backend.infrastructure.composition.factories.r6_all_notions import (
            exact_notion_evidence,
        )

        context = object_data(request["context"])
        selection = object_data(context.get("institutional", {}))
        notions = selection.get("notion_refs")
        if not isinstance(notions, (list, tuple)) or not notions:
            raise ValueError("P0_SOURCE_INSTITUTIONAL_ADMISSION_REQUIRED")
        refs = items(request["references"], 8)
        if len(refs) != 1:
            raise ValueError("P0_PRODUCT_SINGLE_SELECTED_SOURCE_REQUIRED")
        ref = refs[0]
        matched = []
        with exact_notion_evidence(target) as inbound:
            for notion in notions:
                inspected = inbound.inspect(str(notion))
                for passage in items(inspected["items"], 256):
                    if passage["object_ref"] == ref["source_ref"] and passage["passage_ref"] == ref["locator"]:
                        matched.append({**passage, "notion_ref": str(notion)})
        if len(matched) != 1:
            raise ValueError("P0_SOURCE_NOT_IN_ADOPTED_MANIFEST")
        passage = matched[0]
        attested = {"notion_id": passage["notion_ref"], **{key: passage[key] for key in (
            "object_ref", "object_kind", "passage_ref", "version_or_checksum")}}
        resolver = bts_alignment if selection.get("contract_id") == "BTS-INSTITUTIONAL-CONTEXT-1.0" else stmg_alignment
        resolved = resolver(target, selection=selection, reference=attested)
        return admission.execute(request=request, passages=matched, resolution=resolved)

    consent = P0ConsentService(prepared_reader=prepared, admission_reader=sources, permission=generation,
        generate=lambda command: service.execute("generate", command))
    endpoint.consent_execute = consent.execute
