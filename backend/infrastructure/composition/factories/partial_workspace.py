"""Local capture composition contains no generation, consent or budget binding."""
import hashlib
from pathlib import Path
from secrets import token_urlsafe

from backend.adapters.inbound.api.partial_workspace import PartialWorkspaceEndpoint
from backend.adapters.inbound.application.format_reference import FormatReferenceInbound
from backend.adapters.inbound.application.partial_workspace import PartialWorkspaceInbound
from backend.adapters.outbound.export.lot1_word import Lot1OOXMLWordWriter
from backend.adapters.outbound.export.stmg_reference_word import STMGReferenceWordWriter
from backend.adapters.outbound.persistence.format_reference import LocalFormatReferenceStore
from backend.adapters.outbound.persistence.partial_workspace import LocalPartialWorkspace
from backend.infrastructure.filesystem import read_file_nofollow
from backend.modules.materialization_export.application.services.partial_workspace import (
    PartialWorkspaceService,
)
from backend.modules.materialization_export.ports.outbound.word_writer import WordWriter
from backend.modules.pedagogical_design.contracts.dto.assessment_bundle import object_data
from backend.modules.resource_library.application.commands.register_format_reference import (
    RegisterFormatReference,
)
from backend.modules.resource_library.application.queries.read_format_reference import (
    ReadFormatReference,
)
from backend.modules.resource_library.contracts.dto.format_reference import FormatReference


def build_partial_workspace(manifest: Path, manifest_sha256: str, root: Path, *,
                            word_profile: str = "captured", register_reference: bool = False) -> PartialWorkspaceEndpoint:
    workspace = LocalPartialWorkspace(manifest, manifest_sha256, root)
    if word_profile not in {"captured", "stmg-format-001"}:
        raise ValueError("PARTIAL_WORD_PROFILE_REJECTED")
    writer: WordWriter = Lot1OOXMLWordWriter()
    profile = None
    reader = None
    if word_profile == "stmg-format-001":
        admission = object_data(workspace.read_format_admission(), {"schema", "target_root", "role",
            "source_root", "source_locator", "decision_file", "record", "identification"})
        record = FormatReference(admission["record"])
        source_root = Path(str(admission["source_root"]))
        if (admission["schema"] != "FORMAT-REFERENCE-LOCAL-ADMISSION-1.0"
                or admission["role"] != "ISOLATED_FORMAT_REFERENCE_TEST"
                or admission["target_root"] != str(root)
                or type(admission["source_locator"]) is not str):
            raise ValueError("FORMAT_REFERENCE_TARGET_REJECTED")
        decision = workspace._path(admission["decision_file"])
        def verify_decision() -> None:
            if hashlib.sha256(read_file_nofollow(decision, allowed_root=workspace.artifact_root,
                    maximum_bytes=65536)).hexdigest() != record.as_dict()["decision_sha256"]:
                raise ValueError("FORMAT_REFERENCE_DECISION_CHANGED")
        verify_decision()
        store = LocalFormatReferenceStore(root, source_root)
        inbound = FormatReferenceInbound(RegisterFormatReference(store, record, enabled=register_reference),
            ReadFormatReference(store, record))
        identification_raw = object_data(admission["identification"],
            {"level", "theme", "chapter", "question", "finality", "notions"})
        if any(type(v) is not str or not 1 <= len(v) <= 1000 for v in identification_raw.values()):
            raise ValueError("FORMAT_REFERENCE_IDENTIFICATION")
        identification = {k: str(v) for k, v in identification_raw.items()}
        if register_reference:
            inbound.register(record, str(admission["source_locator"]))
        profile = {"profile": word_profile, "revision": "1.2", "reference_id": record.reference_id,
            "reference_version": record.version_ref, "source_sha256": record.as_dict()["source_sha256"],
            "identification": identification, "geometry": "A4-720twips-header-footer-PAGE",
            "synthesis_column_widths_twips": [2400, 4300, 3380],
            "opc_serialization": "DEFAULT_NAMESPACES_LOCAL_TREE",
            "student_traceability": "KNOWN_NOTES_IN_CUSTOM_PROPERTIES",
            "student_title": "CHAPTER_WITHOUT_REVISION_SUFFIX",
            "section_heading_color": "4F81BD"}
        def read_reference() -> dict[str, object]:
            if workspace.read_format_admission() != admission:
                raise ValueError("FORMAT_REFERENCE_ADMISSION_CHANGED")
            verify_decision()
            observed = inbound.read(record.reference_id)
            if observed.as_dict() != record.as_dict():
                raise ValueError("FORMAT_REFERENCE_IDENTITY_CHANGED")
            return {"record": observed.as_dict(), "version_ref": observed.version_ref,
                "binary_verified": True, "scope": "ISOLATED_LIBRARY_ONLY"}
        reader = read_reference
        reader()
        writer = STMGReferenceWordWriter(identification, profile)
    elif register_reference:
        raise ValueError("FORMAT_REFERENCE_EXPLICIT_PROFILE_REQUIRED")
    return PartialWorkspaceEndpoint(PartialWorkspaceInbound(
        PartialWorkspaceService(workspace, writer, export_profile=profile, reference_reader=reader)), token_urlsafe(32))
