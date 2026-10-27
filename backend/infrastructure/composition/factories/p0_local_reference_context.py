"""Reauthenticates local passage and separate canonical notion through Application."""
from collections.abc import Callable, Mapping
from typing import TYPE_CHECKING

from backend.modules.pedagogical_design.contracts.dto.assessment_bundle import items, object_data
from backend.modules.work_orchestration.application.queries.p0_local_reference_context import (
    ReadP0LocalReferenceContext,
)

if TYPE_CHECKING:
    from backend.infrastructure.composition.factories.local_browser import Read15RuntimeTarget


def build_local_reference_resolver(target: "Read15RuntimeTarget", admission: ReadP0LocalReferenceContext,
    *, revalidate: Callable[[], object]) -> Callable[[Mapping[str, object], Mapping[str, object]], Mapping[str, object]]:
    def resolve(selection: Mapping[str, object], selected_reference: Mapping[str, object]) -> Mapping[str, object]:
        from backend.infrastructure.composition.factories.institutional_catalog import (
            bts_alignment,
            stmg_alignment,
        )
        from backend.infrastructure.composition.factories.r6_all_notions import (
            exact_notion_evidence,
        )

        revalidate()
        selected = object_data(selected_reference, {"notion_id", "passage_ref"})
        notion_id = str(selected["notion_id"])
        if selection.get("notion_refs") not in ([notion_id], (notion_id,)):
            raise ValueError("P0_LOCAL_CONTEXT_EXACT_SOURCE_AND_NOTION_REQUIRED")
        with exact_notion_evidence(target) as inbound:
            inspected = inbound.inspect(notion_id)
        passages = [{**passage, "notion_ref": notion_id} for passage in items(inspected["items"], 256)]
        matched = [p for p in passages if p["passage_ref"] == selected["passage_ref"]]
        if len(matched) != 1:
            raise ValueError("P0_REFERENCE_NOT_FOUND")
        reference = {"notion_id": notion_id, **{key: matched[0][key] for key in (
            "object_ref", "object_kind", "passage_ref", "version_or_checksum")}}
        def canonical_resolver(context: Mapping[str, object], anchor: Mapping[str, object]) -> Mapping[str, object]:
            native = bts_alignment if context.get("contract_id") == "BTS-INSTITUTIONAL-CONTEXT-1.0" else stmg_alignment
            return native(target, selection=dict(context), reference=dict(anchor))
        if reference["object_kind"] == "NOTION":
            raise ValueError("P0_LOCAL_CONTEXT_DISCIPLINARY_SOURCE_REQUIRED")
        return admission.resolve(selection=selection, reference=reference, passages=passages, canonical_resolver=canonical_resolver)
    return resolve
