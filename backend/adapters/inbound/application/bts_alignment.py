"""Bounded Application projection, without storage or promotion authority."""
from collections.abc import Mapping

from backend.modules.knowledge_reference.application.queries.bts_alignment import ReadBTSAlignment


class BTSAlignmentInbound:
    def __init__(self, query: ReadBTSAlignment) -> None:
        self.query = query

    def catalog(self) -> list[dict[str, object]]:
        return self.query.snapshot()

    def resolve(self, selection: Mapping[str, object], reference: Mapping[str, object]) -> dict[str, object]:
        return self.query.resolve(selection, reference)
