"""Reuse the delivered normal parser and output guards without executing AG03."""
from __future__ import annotations

from collections.abc import Mapping
from datetime import UTC, datetime
from typing import cast

from backend.adapters.outbound.generation.openai.p0_normal_agents import (
    agent_preparation,
    guard_and_bind,
    parse_content,
)
from backend.adapters.outbound.generation.openai.p0_normal_policy import canonical
from backend.agent_runtime.agents.generation.generation_coordinator import GenerationCoordinator
from backend.agent_runtime.agents.generation.generation_model import (
    GenerationOperation,
    GenerationPortRequest,
    GenerationPortResult,
    GenerationPortResultStatus,
)
from backend.modules.pedagogical_design.contracts.dto.p0_production import P0Production


class _NoGeneration:
    def generate(self, *, request: GenerationPortRequest) -> GenerationPortResult:
        raise RuntimeError("LOCAL_CAPTURE_GENERATION_FORBIDDEN")


class NormalCapturedContentValidation:
    def parse(self, text: str, dispatch: Mapping[str, object]) -> Mapping[str, object]:
        return parse_content(text, dispatch)

    def bind(self, dispatch: Mapping[str, object], content: Mapping[str, object]
             ) -> tuple[P0Production, Mapping[str, object]]:
        now = datetime.now(UTC)
        lineage = cast(Mapping[str, object], dispatch["lineage"])
        result = GenerationPortResult(str(lineage["source_step_id"]), GenerationOperation.GENERATE,
            GenerationPortResultStatus.SUCCEEDED,
            structured_payload=parse_content(canonical(content).decode(), dispatch))
        checks: dict[str, object] = {}
        bound = guard_and_bind(dispatch, GenerationCoordinator(_NoGeneration()),
            agent_preparation(dispatch, now), result, observer=lambda value: checks.update(value))
        return P0Production(bound), checks
