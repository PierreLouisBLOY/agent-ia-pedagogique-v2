"""Local partial-document inbound; no agent gains a file or provider capability."""
from backend.modules.materialization_export.application.services.partial_workspace import (
    PartialWorkspaceService,
)


class PartialWorkspaceInbound:
    def __init__(self, service: PartialWorkspaceService) -> None:
        self.service = service

    def execute(self, operation: str, *, kind: str = "student",
                source_sha256: str | None = None,
                expected_projection_sha256: str | None = None) -> dict[str, object] | bytes:
        return self.service.execute(operation, kind=kind, source_sha256=source_sha256,
            expected_projection_sha256=expected_projection_sha256)
