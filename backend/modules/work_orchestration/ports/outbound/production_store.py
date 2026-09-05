"""Read-only exact-version access, scoped to one conversation."""
from typing import Protocol

from backend.modules.work_orchestration.contracts.dto.production_read_view import ProductionReadView


class ProductionStore(Protocol):
    def read_version(self, *, conversation_id: str, production_ref: str,
                     version_ref: str) -> ProductionReadView | None: ...

    def contains_production(self, *, conversation_id: str, production_ref: str) -> bool: ...
