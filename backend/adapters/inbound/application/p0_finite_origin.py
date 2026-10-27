from collections.abc import Mapping

from backend.modules.work_orchestration.application.queries.p0_finite_origin import ReadFiniteOrigin


class FiniteOriginInbound:
    def __init__(self, query: ReadFiniteOrigin) -> None:
        self.query = query

    def inspect(self) -> Mapping[str, object]:
        return self.query.execute()
