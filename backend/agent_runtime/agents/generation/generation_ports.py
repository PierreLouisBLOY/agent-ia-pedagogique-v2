from __future__ import annotations

from typing import Protocol, runtime_checkable

from backend.agent_runtime.agents.generation.generation_model import (
    GenerationPortRequest,
    GenerationPortResult,
)


@runtime_checkable
class GenerationPort(Protocol):
    def generate(
        self,
        *,
        request: GenerationPortRequest,
    ) -> GenerationPortResult:
        ...
