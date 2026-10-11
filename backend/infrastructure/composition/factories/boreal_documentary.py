"""Offline documentary admission into the existing saved-production Application boundary."""
from pathlib import Path

from backend.adapters.outbound.resource_library.boreal_documentary import (
    normalize_boreal_documentary,
)
from backend.infrastructure.composition.factories.local_browser import build_saved_application


def admit_boreal_documentary(artifact_root: Path, scope_root: Path, saved_root: Path,
                           *, create: bool = False) -> dict[str, object]:
    record, mapping = normalize_boreal_documentary(artifact_root, scope_root)
    application = build_saved_application(saved_root, create=create)
    saved = application.admit_documentary(record)
    opened = application.execute("open", record.production_ref, record.version_ref,
                                 correlation="boreal-documentary-admission")
    if not isinstance(opened, dict) or opened["record_sha256"] != record.sha256:
        raise ValueError("BOREAL_DOCUMENTARY_REOPEN_MISMATCH")
    return {**mapping, "save": saved, "active_authority": opened["active_authority"],
            "new_actions": opened["new_actions"]}
