"""Closed Application invocation bridge for the M03 search use case."""

from __future__ import annotations

from typing import cast

from backend.agent_runtime.contracts import ContractMeta, UseCaseRequest, UseCaseResult
from backend.core_contracts.outcome import ApplicationOutcome
from backend.modules.resource_library.application.dto.input.search_local import SearchLocalRequest
from backend.modules.resource_library.application.dto.output.local_search_view import (
    LocalSearchView,
)
from backend.modules.resource_library.domain.value_objects.search_text import (
    InvalidSearchTextError,
    SearchText,
)
from backend.modules.resource_library.ports.inbound.local_search import LocalSearchInbound

SEARCH_USE_CASE_ID = "application.search_local_passages"


def search_data(view: LocalSearchView | None) -> dict[str, object] | None:
    if view is None:
        return None
    items = []
    for item in view.items:
        passage = item.passage
        resource = item.read15
        items.append({
            "position": item.position,
            "object_ref": passage.object_ref, "object_kind": passage.object_kind,
            "passage_ref": passage.passage_ref, "version_or_checksum": passage.version_or_checksum,
            "excerpt": passage.excerpt, "excerpt_truncated": passage.excerpt_truncated,
            "provenance": {
                "channel": "LEXICAL", "search_boundary": "sqlite-op11",
                "content_boundary": "sqlite-op13", "admission_policy": "F2A",
                "source_kind": "canonical_search_chunk", "freshness": "CURRENT",
                "authority_basis": "canonical-registry", "authority_absolute": False,
                "content_trust": "UNTRUSTED_CONTENT",
            },
            "read15": None if resource is None else {
                "resource_ref": resource.resource_ref.value,
                "resource_type": resource.resource_type,
                "canonical_title": resource.canonical_title,
                "availability_status": resource.availability_status,
            },
            "open_status": item.open_status.value,
            **({"source_status": passage.source_status.as_dict()} if passage.source_status is not None else {}),
        })
    return {"items": items, "window_full": view.window_full,
            "more_admitted_in_window": view.more_admitted_in_window}


class LocalSearchUseCaseInbound:
    def __init__(self, search: LocalSearchInbound) -> None:
        if not isinstance(search, LocalSearchInbound):
            raise TypeError("LocalSearchInbound required")
        self._search = search

    def invoke(self, *, request: UseCaseRequest) -> UseCaseResult[object, object]:
        if type(request) is not UseCaseRequest or request.use_case_id != SEARCH_USE_CASE_ID:
            raise ValueError("UNSUPPORTED_SEARCH_USE_CASE")
        if set(request.payload) != {"q", "limit"}:
            raise InvalidSearchTextError("SEARCH_REQUEST_REJECTED")
        typed = SearchLocalRequest(
            SearchText(cast(str, request.payload["q"])), cast(int, request.payload["limit"]),
        )
        result = self._search.search_local(request=typed, correlation_id=request.meta.correlation_id)
        if (
            result.correlation_id != request.meta.correlation_id or result.side_effects
            or result.operation_ref is not None or result.task_ref is not None
            or result.application_failure is not None or result.business_errors
            or result.validation_result is not None or not result.success or result.data is None
        ):
            raise ValueError("INVALID_SEARCH_OUTCOME")
        outcome: ApplicationOutcome[object, object] = ApplicationOutcome(
            outcome_status=result.outcome_status, success=result.success,
            correlation_id=result.correlation_id, data=search_data(result.data),
            business_errors=result.business_errors, validation_result=result.validation_result,
            application_failure=result.application_failure, warnings=result.warnings,
            side_effects=result.side_effects, operation_ref=result.operation_ref,
            task_ref=result.task_ref, subject_refs=result.subject_refs,
        )
        return UseCaseResult(
            meta=ContractMeta(
                schema_version=request.meta.schema_version, run_id=request.meta.run_id,
                step_id=request.meta.step_id, parent_step_id=request.meta.parent_step_id,
                correlation_id=request.meta.correlation_id, created_at=request.meta.created_at,
                actor=request.meta.actor, status=outcome.outcome_status,
                trace_flags=request.meta.trace_flags,
            ),
            use_case_id=request.use_case_id, outcome=outcome,
        )
