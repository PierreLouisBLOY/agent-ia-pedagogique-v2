"""Pinned inputs through Application; reuse the normal R4 persistence callback."""

import hashlib
import json
from collections.abc import Callable
from pathlib import Path

from backend.adapters.inbound.application.chapter_assembly import ChapterAssemblyInbound
from backend.adapters.inbound.application.format_reference import FormatReferenceInbound
from backend.adapters.outbound.persistence.format_reference import LocalFormatReferenceStore
from backend.infrastructure.filesystem import assert_local_data_root, read_file_nofollow
from backend.modules.pedagogical_design.application.commands.assemble_chapter import AssembleChapter
from backend.modules.pedagogical_design.contracts.dto.assessment_bundle import (
    fingerprint,
    object_data,
)
from backend.modules.resource_library.application.commands.register_format_reference import (
    RegisterFormatReference,
)
from backend.modules.resource_library.application.queries.read_format_reference import (
    ReadFormatReference,
)
from backend.modules.resource_library.contracts.dto.format_reference import FormatReference
from backend.modules.work_orchestration.contracts.dto.saved_production import SavedProduction


def chapter_source(
    manifest: Path, sha256: str, root: Path, *, register: bool = False,
    read_saved: Callable[[str, str], SavedProduction] | None = None,
) -> Callable[[str, str], SavedProduction]:
    artifact_root = assert_local_data_root(manifest.parent)

    def pinned(path: Path, expected: str, maximum: int) -> bytes:
        raw = read_file_nofollow(path, allowed_root=artifact_root, maximum_bytes=maximum)
        if hashlib.sha256(raw).hexdigest() != expected:
            raise ValueError("ASSEMBLY_INPUT_CHANGED")
        return raw

    raw = pinned(manifest, sha256, 65536)
    m = object_data(
        json.loads(raw),
        {
            "schema",
            "blueprint",
            "blueprint_sha256",
            "decision",
            "format_source_root",
            "format_locator",
            "record",
            "target_root",
        },
    )
    if m["schema"] != "LOCAL-CHAPTER-MANIFEST-1.0" or m["target_root"] != str(root):
        raise ValueError("ASSEMBLY_MANIFEST_TARGET")
    record = FormatReference(m["record"])
    store = LocalFormatReferenceStore(root, Path(str(m["format_source_root"])))
    reference = FormatReferenceInbound(
        RegisterFormatReference(store, record, enabled=register), ReadFormatReference(store, record)
    )
    pinned(artifact_root / str(m["decision"]), str(record.as_dict()["decision_sha256"]), 65536)
    if register:
        reference.register(record, str(m["format_locator"]))

    def prepare() -> SavedProduction:
        pinned(manifest, sha256, 65536)
        pinned(artifact_root / str(m["decision"]), str(record.as_dict()["decision_sha256"]), 65536)
        observed = reference.read(record.reference_id)
        blueprint = json.loads(
            pinned(artifact_root / str(m["blueprint"]), str(m["blueprint_sha256"]), 256 * 1024)
        )
        fmt = object_data(object_data(object_data(blueprint)["chapter"])["assembly"])[
            "format_reference"
        ]
        if object_data(fmt) != {"record": observed.as_dict(), "version_ref": observed.version_ref}:
            raise ValueError("ASSEMBLY_FORMAT_RECORD_BINDING")
        return ChapterAssemblyInbound(AssembleChapter()).prepare(
            blueprint,
            {
                "BLUEPRINT_SHA256": str(m["blueprint_sha256"]),
                "MANIFEST_SHA256": sha256,
                "FORMAT_RECORD_SHA256": fingerprint(record.as_dict()),
            },
        )

    prepared = prepare()

    def source(production: str, version: str) -> SavedProduction:
        current = prepare()
        if (production, version) == (current.production_ref, current.version_ref):
            return current
        lineage = object_data(object_data(current.p0_bundle.data)["lineage"]) if current.p0_bundle else {}
        if read_saved is not None and production == prepared.production_ref:
            parent_ref = lineage.get("parent_version_ref")
            seen = {current.version_ref}
            while isinstance(parent_ref, str):
                # Same ancestry bound as the existing R4 save command.
                if parent_ref in seen or len(seen) > 32:
                    raise ValueError("ASSEMBLY_PARENT_BINDING")
                seen.add(parent_ref)
                parent = read_saved(production, parent_ref)
                if (type(parent) is not SavedProduction
                        or (parent.production_ref, parent.version_ref) != (production, parent_ref)
                        or parent.data["origin"] != "LOCAL_APPLICATION" or parent.p0_bundle is None):
                    raise ValueError("ASSEMBLY_PARENT_BINDING")
                if parent_ref == version:
                    return parent
                parent_ref = object_data(parent.p0_bundle.data["lineage"])["parent_version_ref"]
        raise ValueError("R4_NOT_FOUND")

    return source
