"""Inbound Application surface for local preparation only; no dispatch authority."""
from collections.abc import Sequence

from backend.modules.work_orchestration.application.queries.stmg_local_activity import (
    PrepareSTMGLocalActivity,
)


class STMGLocalActivityInbound:
    def __init__(self, query: PrepareSTMGLocalActivity) -> None:
        self.query = query

    def metadata(self) -> list[dict[str, object]]:
        return self.query.metadata()

    def prepare(self, *, choice_sha256: str, selected_local_capacity_refs: Sequence[str] | None = None) -> dict[str, object]:
        return self.query.execute(choice_sha256, selected_local_capacity_refs=selected_local_capacity_refs)
