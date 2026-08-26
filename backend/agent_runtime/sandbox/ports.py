from __future__ import annotations

from typing import Protocol, runtime_checkable

from backend.agent_runtime.sandbox.model import (
    ResolvedSandboxPath,
    SandboxRelativePath,
    SandboxRootRef,
)


@runtime_checkable
class SandboxFilesystemPort(Protocol):
    """Trusted filesystem boundary; C intentionally provides no implementation."""

    def resolve(
        self,
        *,
        root_ref: SandboxRootRef,
        relative_path: SandboxRelativePath,
    ) -> ResolvedSandboxPath:
        ...

    def inspect(
        self,
        *,
        resolved_path: ResolvedSandboxPath,
    ) -> ResolvedSandboxPath:
        ...
