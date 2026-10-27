"""Local publication only, with no generation or financial capability."""
from collections.abc import Mapping
from typing import Protocol

from backend.modules.work_orchestration.contracts.dto.saved_production import SavedProduction


class RecoveredCapturePublication(Protocol):
    def save(self, record: SavedProduction) -> Mapping[str, object]: ...
    def reopen(self, production_ref: str, version_ref: str) -> SavedProduction: ...
