from __future__ import annotations

from collections.abc import Mapping

from backend.agent_runtime.agents.generation import (
    GenerationPortError,
    GenerationPortRequest,
    GenerationPortResult,
)


class RecordingGenerationPort:
    """Provider-neutral test double keyed only by the prepared source step."""

    def __init__(
        self,
        results: Mapping[str, GenerationPortResult] | None = None,
        errors: Mapping[str, GenerationPortError] | None = None,
    ) -> None:
        self.results = dict(results or {})
        self.errors = dict(errors or {})
        self.calls: list[GenerationPortRequest] = []

    def generate(self, *, request: GenerationPortRequest) -> GenerationPortResult:
        self.calls.append(request)
        if request.source_step_id in self.errors:
            raise self.errors[request.source_step_id]
        try:
            return self.results[request.source_step_id]
        except KeyError as error:
            raise AssertionError(
                f"no test generation result for {request.source_step_id}"
            ) from error


class ScenarioArtifacts:
    """In-memory scenario association, not a persistence or dispatch API."""

    def __init__(self) -> None:
        self._by_ref: dict[str, object] = {}

    def publish(self, reference: str, artifact: object) -> None:
        if not reference or reference in self._by_ref:
            raise ValueError("scenario reference must be non-empty and unique")
        self._by_ref[reference] = artifact

    def resolve(self, reference: str) -> object:
        return self._by_ref[reference]

    def references(self) -> tuple[str, ...]:
        return tuple(self._by_ref)
