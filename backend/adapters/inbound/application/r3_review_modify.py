"""Explicit Application inbound; no filesystem, credential, HTTP or provider access."""
from collections.abc import Mapping

from backend.modules.work_orchestration.contracts.dto.r3_review_modify import R3Command
from backend.modules.work_orchestration.ports.inbound.r3_review_modify import R3UseCases


class R3ApplicationInbound:
    def __init__(self, service: R3UseCases) -> None:
        self._service = service

    def command(self, operation: str, body: Mapping[str, object]) -> dict[str, object]:
        return self._service.execute(R3Command(operation, body))

    def assessment(self, production_ref: str, version_ref: str) -> dict[str, object]:
        return self._service.assessment(production_ref, version_ref)

    def report(self, reference: str, *, review: bool = False) -> dict[str, object]:
        return self._service.report(reference, review=review)
