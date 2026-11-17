"""Explicit pins, read-only Application composition; no import capability is exposed."""
from collections.abc import Mapping
from pathlib import Path

from backend.infrastructure.composition.factories.documentary_library import (
    build_documentary_library,
)
from backend.modules.pedagogical_design.contracts.dto.assessment_bundle import object_data
from backend.modules.resource_library.application.services.documentary_course_selection import (
    DocumentaryCourseSelectionApplication,
)


def build_documentary_course_selection(descriptor: Mapping[str, object]) -> DocumentaryCourseSelectionApplication:
    data = object_data(descriptor, {"database", "data_root", "database_sha256", "archive_sha256", "snapshot_sha256"})
    database, root = Path(str(data["database"])), Path(str(data["data_root"]))
    if not database.is_absolute() or not root.is_absolute():
        raise ValueError("DOCUMENTARY_ABSOLUTE_PATH_REQUIRED")
    inbound = build_documentary_library(database=database, data_root=root)
    return DocumentaryCourseSelectionApplication(inbound.execute,
        database_sha256=str(data["database_sha256"]), archive_sha256=str(data["archive_sha256"]),
        snapshot_sha256=str(data["snapshot_sha256"]))
