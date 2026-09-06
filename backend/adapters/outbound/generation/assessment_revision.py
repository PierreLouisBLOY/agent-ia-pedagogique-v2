"""R3 uses the existing generic section transport; no edits to frozen R2 mapping."""
import json
from collections.abc import Mapping

from backend.agent_runtime.agents.generation import GenerationPort
from backend.infrastructure.composition.bindings.r3_agents import transform
from backend.modules.pedagogical_design.contracts.dto.assessment_bundle import object_data
from backend.modules.pedagogical_design.contracts.dto.assessment_revision import (
    AssessmentRevisionRequest,
)


def parse_revision_result(payload: Mapping[str, object]) -> Mapping[str, object]:
    sections = object_data(payload.get("sections"), {"R3_RESULT_JSON"})
    raw = sections["R3_RESULT_JSON"]
    if not isinstance(raw, str) or len(raw.encode("utf-8")) > 128 * 1024:
        raise ValueError("R3_GENERATION_OUTPUT")
    def pairs(values: list[tuple[str, object]]) -> dict[str, object]:
        output: dict[str, object] = {}
        for key, value in values:
            if key in output:
                raise ValueError("R3_DUPLICATE_KEY")
            output[key] = value
        return output
    def invalid(value: str) -> object:
        raise ValueError("R3_NON_FINITE")
    def depth(value: object, level: int = 0) -> None:
        if level > 16:
            raise ValueError("R3_DEPTH")
        if isinstance(value, dict):
            for item in value.values():
                depth(item, level + 1)
        elif isinstance(value, list):
            for item in value:
                depth(item, level + 1)
    data = json.loads(raw, object_pairs_hook=pairs, parse_constant=invalid)
    depth(data)
    return object_data(data)


class AssessmentRevisionAdapter:
    def __init__(self, port: GenerationPort) -> None:
        self._port = port

    def propose(self, request: AssessmentRevisionRequest) -> Mapping[str, object]:
        return parse_revision_result(transform(self._port, request))
