"""Bounded discovery followed by an explicit, independent ResourceRef lookup."""

from __future__ import annotations

from dataclasses import dataclass

from backend.core_contracts.outcome import ApplicationOutcome, OutcomeStatus
from backend.modules.resource_library.application.dto.input import GetResourceRequest
from backend.modules.resource_library.application.dto.input.search_local import SearchLocalRequest
from backend.modules.resource_library.application.dto.output.local_search_view import (
    LocalSearchItem,
    LocalSearchView,
    SearchOpenStatus,
)
from backend.modules.resource_library.domain.errors import InvalidResourceRefError
from backend.modules.resource_library.domain.value_objects import ResourceRef
from backend.modules.resource_library.ports.inbound import ResourceLibraryInbound
from backend.modules.resource_library.ports.outbound.local_search import LocalSearchPort
from backend.shared_kernel.correlation import CorrelationId


@dataclass(frozen=True, slots=True)
class SearchLocalQuery:
    search: LocalSearchPort
    resources: ResourceLibraryInbound

    def __post_init__(self) -> None:
        if not isinstance(self.search, LocalSearchPort):
            raise TypeError("LocalSearchPort required")
        if not isinstance(self.resources, ResourceLibraryInbound):
            raise TypeError("ResourceLibraryInbound required")

    def search_local(
        self, *, request: SearchLocalRequest, correlation_id: CorrelationId,
    ) -> ApplicationOutcome[LocalSearchView, object]:
        if type(request) is not SearchLocalRequest or type(correlation_id) is not CorrelationId:
            raise TypeError("typed search request and correlation required")
        window = self.search.admitted_window(
            text=request.text, result_limit=request.limit, candidate_limit=100,
        )
        if len(window.passages) > request.limit:
            raise ValueError("SEARCH_WINDOW_OVERFLOW")
        items = []
        for position, passage in enumerate(window.passages, 1):
            view = None
            status = SearchOpenStatus.NOT_RESOURCE
            if passage.object_kind == "RESOURCE":
                try:
                    reference = ResourceRef(passage.object_ref)
                except (InvalidResourceRefError, TypeError):
                    status = SearchOpenStatus.INVALID_RESOURCE_REF
                else:
                    outcome = self.resources.get_resource(
                        request=GetResourceRequest(reference), correlation_id=correlation_id,
                    )
                    if (
                        outcome.correlation_id != correlation_id or outcome.side_effects
                        or outcome.application_failure is not None
                        or outcome.validation_result is not None
                        or outcome.operation_ref is not None or outcome.task_ref is not None
                    ):
                        raise ValueError("RESOURCE_LINK_FAILED")
                    if outcome.success and outcome.data is not None and not outcome.business_errors:
                        view = outcome.data
                        status = SearchOpenStatus.OPENABLE
                    elif not outcome.success and outcome.business_errors and all(
                        error.code.value == "RES_NOT_FOUND" for error in outcome.business_errors
                    ) and outcome.data is None:
                        status = SearchOpenStatus.RESOURCE_NOT_FOUND
                    else:
                        raise ValueError("RESOURCE_LINK_FAILED")
            items.append(LocalSearchItem(position, passage, view, status))
        return ApplicationOutcome(
            outcome_status=OutcomeStatus.SUCCESS, success=True, correlation_id=correlation_id,
            data=LocalSearchView(
                tuple(items), window.window_full, window.more_admitted_in_window,
            ),
        )
