"""Inbound boundary for a pinned original local chapter blueprint."""

from backend.modules.pedagogical_design.application.commands.assemble_chapter import AssembleChapter
from backend.modules.pedagogical_design.contracts.dto.assessment_bundle import object_data
from backend.modules.work_orchestration.contracts.dto.p0_production_read_view import (
    P0ProductionReadView,
)
from backend.modules.work_orchestration.contracts.dto.saved_production import SavedProduction


class ChapterAssemblyInbound:
    def __init__(self, command: AssembleChapter) -> None:
        self.command = command

    def prepare(self, blueprint: object, provenance: dict[str, object]) -> SavedProduction:
        bundle = self.command.execute(blueprint)
        return SavedProduction(
            {
                "contract_id": "SAVED-PRODUCTION-P0-1.0",
                "view": object_data(P0ProductionReadView.from_bundle(bundle).data),
                "bundle": bundle.mutable_copy(),
                "reviews": [],
                "validations": [],
                "origin": "LOCAL_APPLICATION",
                "provenance": provenance,
                "reservations": [],
            }
        )
