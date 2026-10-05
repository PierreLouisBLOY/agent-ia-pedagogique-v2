"""A typed Application entry point for local M01 authoring, without storage access."""
from collections.abc import Callable, Mapping

from backend.modules.pedagogical_context.contracts.dto.p0_context import P0Context
from backend.modules.pedagogical_design.application.commands.reframe_course import (
    ReframeCourseCommand,
)
from backend.modules.work_orchestration.contracts.dto.saved_production import SavedProduction


class ReframeCourseInbound:
    def __init__(self, resolve: Callable[[Mapping[str, object], Mapping[str, object]], Mapping[str, object]]) -> None:
        self.resolve = resolve

    def execute(self, parent: SavedProduction, context: Mapping[str, object], *, title: str, sections: object,
                reference_selection: Mapping[str, object], evidence: Mapping[str, str]) -> SavedProduction:
        requested = P0Context(context)
        if requested.institutional is None:
            raise ValueError("P0_INSTITUTIONAL_CONTEXT_REQUIRED")
        confirmed = requested.as_dict()
        confirmed["institutional_resolution"] = dict(self.resolve(requested.institutional, reference_selection))
        return ReframeCourseCommand().execute(parent, P0Context(confirmed), title=title, sections=sections, evidence=evidence)
