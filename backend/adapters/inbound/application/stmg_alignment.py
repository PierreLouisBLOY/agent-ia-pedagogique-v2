"""Agent/UI consumers receive bounded Application projections, never SQLite."""
from collections.abc import Mapping

from backend.modules.knowledge_reference.application.queries.stmg_alignment import ReadSTMGAlignment


class STMGAlignmentInbound:
    def __init__(self, query: ReadSTMGAlignment) -> None:
        self.query = query

    def catalog(self, *, question_fingerprints: bool = False) -> dict[str, object]:
        return self.query.snapshot(question_fingerprints=question_fingerprints)

    def resolve(self, selection: Mapping[str, object], reference: Mapping[str, object], *,
                mode: str = "LEGACY", focus_witness: bool = False) -> dict[str, object]:
        return self.query.resolve(selection, reference, mode=mode, focus_witness=focus_witness)

    def matrix(self) -> dict[str, object]:
        return self.query.matrix()
