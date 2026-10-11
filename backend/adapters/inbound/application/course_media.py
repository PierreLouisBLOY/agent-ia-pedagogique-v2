"""Application boundary for explicit local media materialization, never path loading."""
from collections.abc import Mapping

from backend.modules.materialization_export.application.services.media_asset import MediaAssetWorker
from backend.modules.materialization_export.contracts.dto.media_asset import MediaAsset
from backend.modules.pedagogical_design.contracts.dto.visual_brief import VisualBrief


class CourseMediaInbound:
    def __init__(self, worker: MediaAssetWorker) -> None:
        self.worker = worker

    def execute(self, proposal: Mapping[str, object], *, production_ref: str, documents: set[str],
                concepts: set[str], capabilities: set[str], notions: set[str],
                admitted_bytes: bytes | None = None, admission: Mapping[str, object] | None = None) -> MediaAsset:
        brief = VisualBrief(proposal)
        brief.bind(production_ref, documents=documents, concepts=concepts, capabilities=capabilities, notions=notions)
        return self.worker.execute(brief, admitted_bytes=admitted_bytes, admission=admission)
