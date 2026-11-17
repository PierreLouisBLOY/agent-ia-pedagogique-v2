"""Pure Application read of configured, pinned real-organization proposals."""
from collections.abc import Mapping

from backend.modules.pedagogical_context.contracts.dto.real_course_thread import RealCourseThread
from backend.modules.pedagogical_design.contracts.dto.assessment_bundle import object_data


class ReadCourseThreads:
    def __init__(self, threads: tuple[RealCourseThread, ...]) -> None:
        ids = [t.organization_id for t in threads]
        if len(threads) > 16 or len(set(ids)) != len(ids):
            raise ValueError("P0_REAL_ORGANIZATION_CATALOGUE")
        self.threads = threads

    def catalogue(self) -> list[dict[str, object]]:
        return [t.summary() for t in self.threads]

    def read(self, selection: Mapping[str, object]) -> dict[str, object]:
        data = object_data(selection, {"organization_id", "dossier_sha256"})
        found = [t for t in self.threads if t.organization_id == data["organization_id"]]
        if len(found) != 1 or found[0].sha256 != data["dossier_sha256"]:
            raise ValueError("P0_REAL_ORGANIZATION_CHANGED")
        return found[0].as_dict()
