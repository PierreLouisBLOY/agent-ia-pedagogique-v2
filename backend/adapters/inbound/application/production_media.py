"""Thin Application boundary for the versioned media preparation command."""
from collections.abc import Mapping

from backend.modules.pedagogical_design.application.commands.prepare_production_media import (
    PrepareProductionMediaCommand,
)
from backend.modules.work_orchestration.contracts.dto.saved_production import SavedProduction


class ProductionMediaInbound:
    def __init__(self, command: PrepareProductionMediaCommand) -> None:
        self.command = command

    def execute(self, parent: SavedProduction, proposals: object, *, evidence: Mapping[str, str] | None = None,
                no_media_reason: str | None = None) -> SavedProduction:
        return self.command.execute(parent, proposals, evidence=evidence, no_media_reason=no_media_reason)
