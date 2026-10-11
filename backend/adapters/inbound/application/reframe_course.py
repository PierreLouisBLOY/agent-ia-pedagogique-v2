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
                reference_selection: Mapping[str, object], evidence: Mapping[str, str],
                course_chapter: Mapping[str, object] | None = None,
                reference_override: Mapping[str, object] | None = None) -> SavedProduction:
        requested = P0Context(context)
        if requested.institutional is None:
            raise ValueError("P0_INSTITUTIONAL_CONTEXT_REQUIRED")
        confirmed = requested.as_dict()
        resolution = dict(self.resolve(requested.institutional, reference_selection))
        confirmed["institutional_resolution"] = resolution
        if reference_override is not None:
            scope = resolution.get("reference_scope", {})
            if not isinstance(scope, Mapping) or scope.get("status") != "CANONICAL_NOTION_ONLY" or any(
                reference_override.get(target) != scope.get(key) for key, target in (
                    ("object_ref", "source_ref"), ("passage_ref", "locator"), ("version_or_checksum", "checksum_or_version"))):
                raise ValueError("COURSE_REFERENCE_SUCCESSOR_BINDING")
        return ReframeCourseCommand().execute(parent, P0Context(confirmed), title=title, sections=sections,
            evidence=evidence, course_chapter=course_chapter, reference_override=reference_override)
