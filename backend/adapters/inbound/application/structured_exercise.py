"""Local original authoring boundary; it has no persistence or provider capability."""
from collections.abc import Mapping

from backend.modules.pedagogical_design.application.commands.prepare_structured_exercise import (
    PrepareStructuredExercise,
)
from backend.modules.work_orchestration.contracts.dto.saved_production import SavedProduction


class StructuredExerciseInbound:
    def __init__(self, command: PrepareStructuredExercise) -> None:
        self.command = command

    def prepare(self, dispatch: Mapping[str, object], content: Mapping[str, object]) -> SavedProduction:
        return self.command.execute(dispatch, content)
