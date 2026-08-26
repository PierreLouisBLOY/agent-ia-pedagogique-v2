from __future__ import annotations

from collections.abc import Mapping
from typing import cast

from backend.agent_runtime.sandbox import (
    ResolvedSandboxPath,
    SandboxRelativePath,
    SandboxRootRef,
)
from backend.agent_runtime.tools import PreparedToolExecution, ToolExecutionOutcome


class RecordingToolExecutor:
    def __init__(
        self,
        outcome: object,
        *,
        error: Exception | None = None,
    ) -> None:
        self.outcome = outcome
        self.error = error
        self.calls: list[PreparedToolExecution] = []

    def execute(
        self,
        *,
        execution: PreparedToolExecution,
    ) -> ToolExecutionOutcome:
        self.calls.append(execution)
        if self.error is not None:
            raise self.error
        return cast(ToolExecutionOutcome, self.outcome)


class RecordingSandboxFilesystem:
    def __init__(
        self,
        resolutions: Mapping[str, tuple[ResolvedSandboxPath, ...]],
    ) -> None:
        self._resolutions = dict(resolutions)
        self._indices: dict[str, int] = {}
        self.resolve_calls: list[tuple[SandboxRootRef, SandboxRelativePath]] = []
        self.inspect_calls: list[ResolvedSandboxPath] = []

    def resolve(
        self,
        *,
        root_ref: SandboxRootRef,
        relative_path: SandboxRelativePath,
    ) -> ResolvedSandboxPath:
        self.resolve_calls.append((root_ref, relative_path))
        sequence = self._resolutions.get(relative_path.value)
        if sequence is None:
            raise RuntimeError("missing fake sandbox resolution")
        index = self._indices.get(relative_path.value, 0)
        if index >= len(sequence):
            raise RuntimeError("unexpected extra sandbox resolution")
        self._indices[relative_path.value] = index + 1
        return sequence[index]

    def inspect(
        self,
        *,
        resolved_path: ResolvedSandboxPath,
    ) -> ResolvedSandboxPath:
        self.inspect_calls.append(resolved_path)
        return resolved_path
