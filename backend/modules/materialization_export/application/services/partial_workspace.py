"""A partial local document has no generation, validation or promotion operations."""
from collections.abc import Callable

from backend.modules.materialization_export.application.services.partial_inventory import (
    partial_inventory,
)
from backend.modules.materialization_export.application.services.partial_projection import (
    partial_document,
)
from backend.modules.materialization_export.application.services.partial_revision import (
    revise_partial,
)
from backend.modules.materialization_export.ports.outbound.partial_workspace import (
    PartialWorkspace,
)
from backend.modules.materialization_export.ports.outbound.word_writer import WordWriter
from backend.modules.pedagogical_design.contracts.dto.assessment_bundle import (
    fingerprint,
)


class PartialWorkspaceService:
    def __init__(self, workspace: PartialWorkspace, writer: WordWriter, *,
                 export_profile: dict[str, object] | None = None,
                 reference_reader: Callable[[], dict[str, object]] | None = None) -> None:
        self.workspace = workspace
        self.writer = writer
        self.export_profile = export_profile
        self.reference_reader = reference_reader

    def execute(self, operation: str, *, kind: str = "student",
                source_sha256: str | None = None,
                expected_projection_sha256: str | None = None) -> dict[str, object] | bytes:
        if operation not in {"open", "save", "preview", "word", "inventory", "reference"}:
            raise ValueError("PARTIAL_OPERATION_REJECTED")
        reference = self.reference_reader() if self.reference_reader is not None else None
        if operation == "reference":
            if reference is None:
                raise ValueError("FORMAT_REFERENCE_NOT_SELECTED")
            return reference
        capture = self.workspace.read()
        documents = {name: partial_document(capture, name) for name in ("student", "correction")}
        base_documents = documents
        plan = self.workspace.read_revision()
        revision = None
        if plan is not None:
            documents, revision = revise_partial(documents, plan, capture.request.text_sha256)
        projected = {name: value.as_dict() for name, value in documents.items()}
        projection_sha256 = fingerprint(projected if self.export_profile is None else {
            "documents": projected, "export_profile": self.export_profile})
        saved = self.workspace.is_saved(projection_sha256)
        if self.workspace.read_revision() != plan:
            raise ValueError("PARTIAL_REVISION_CHANGED")
        if operation == "inventory":
            inventory = partial_inventory(capture, base_documents)
            if revision is not None:
                return {"capture_inventory": inventory, "revision": revision,
                    "projection_sha256": projection_sha256}
            return inventory
        if operation == "save":
            if (source_sha256 != capture.request.text_sha256
                    or expected_projection_sha256 != projection_sha256):
                raise ValueError("PARTIAL_IDENTITY_CHANGED")
            self.workspace.save(capture, projection_sha256)
            saved = self.workspace.is_saved(projection_sha256)
        if operation in {"open", "save"}:
            result: dict[str, object] = {"status": "PARTIAL_UNVALIDATED", "command_id": capture.request.command_id,
                "source_sha256": capture.request.text_sha256, "source_bytes": capture.request.text_bytes,
                "request_sha256": capture.request.request_sha256,
                "version_ref": "capture:" + projection_sha256,
                "projection_sha256": projection_sha256,
                "saved": saved, "effect_permitted": False}
            if revision is not None:
                result["revision"] = revision
            if self.export_profile is not None:
                result["export_profile"] = self.export_profile
            return result
        if kind not in documents:
            raise ValueError("PARTIAL_DOCUMENT_REJECTED")
        document = documents[kind]
        if operation == "preview":
            return document.as_dict()
        if not saved:
            raise ValueError("PARTIAL_SAVE_REQUIRED")
        return self.writer.write(document)
