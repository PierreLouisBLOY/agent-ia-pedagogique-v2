"""Pure selected notion aliases; structural binding grants no admission authority."""
from __future__ import annotations

from typing import TYPE_CHECKING

from backend.modules.pedagogical_design.contracts.dto.assessment_bundle import (
    fingerprint,
    items,
    nonempty,
    object_data,
)

if TYPE_CHECKING:
    from backend.modules.pedagogical_context.contracts.dto.p0_context import P0Context


def course_notion_rows(context: P0Context) -> list[dict[str, str]]:
    """Application resolves the selection; this helper only checks its exact shape."""
    from backend.modules.pedagogical_context.contracts.dto.p0_context import (
        P0_NOTION_COURSE_CONTEXT_CONTRACT,
    )

    if context.data["contract_id"] != P0_NOTION_COURSE_CONTEXT_CONTRACT:
        raise ValueError("P0_NOTION_COURSE_CONTEXT_REQUIRED")
    context.require_institutional_dispatch()
    selection = context.institutional
    if selection is None:
        raise ValueError("P0_NOTION_COURSE_CONTEXT_REQUIRED")
    resolution = object_data(context.data["institutional_resolution"])
    if (resolution.get("contract_id") != "STMG-RESOLUTION-1.0"
            or resolution.get("selection_sha256") != fingerprint(selection)):
        raise ValueError("P0_NOTION_COURSE_RESOLUTION_BINDING")
    selected = selection.get("notion_refs")
    if (not isinstance(selected, (tuple, list)) or not 1 <= len(selected) <= 16
            or any(not isinstance(ref, str) or not ref for ref in selected)
            or len(set(selected)) != len(selected)):
        raise ValueError("P0_NOTION_COURSE_SELECTION")
    rows = items(resolution.get("notions"), 16)
    by_ref: dict[str, str] = {}
    for row in rows:
        row = object_data(row, {"notion_ref", "label"})
        ref = nonempty(row["notion_ref"], 200)
        if ref in by_ref:
            raise ValueError("P0_NOTION_COURSE_RESOLUTION_DUPLICATE")
        by_ref[ref] = nonempty(row["label"], 2000)
    if set(by_ref) != set(selected):
        raise ValueError("P0_NOTION_COURSE_RESOLUTION_COVERAGE")
    labels = {" ".join(label.casefold().split()) for label in by_ref.values()}
    if len(labels) != len(by_ref):
        raise ValueError("P0_NOTION_COURSE_LABEL_AMBIGUOUS")
    return [{"id": "N" + str(number), "label": by_ref[str(ref)], "notion_ref": str(ref)}
            for number, ref in enumerate(selected, 1)]
