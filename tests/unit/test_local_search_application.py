from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime

import pytest

from backend.adapters.inbound.application.local_search import LocalSearchUseCaseInbound, search_data
from backend.agent_runtime.contracts import (
    AGENT_CONTRACT_SCHEMA_V1_0,
    ActorKind,
    ActorRef,
    ContractMeta,
    InvocationStatus,
    UseCaseRequest,
)
from backend.core_contracts.invocation import UseCaseContext
from backend.core_contracts.outcome import ApplicationOutcome, OutcomeStatus
from backend.modules.resource_library.application.dto.input.search_local import SearchLocalRequest
from backend.modules.resource_library.application.queries import GetResourceQuery
from backend.modules.resource_library.application.queries.search_local import SearchLocalQuery
from backend.modules.resource_library.domain.value_objects import ResourceRef
from backend.modules.resource_library.domain.value_objects.search_text import (
    InvalidSearchTextError,
    SearchText,
)
from backend.modules.resource_library.ports.outbound.local_search import (
    AdmittedLocalPassage,
    LocalSearchWindow,
)
from backend.shared_kernel.correlation import CorrelationId
from backend.shared_kernel.time import Instant

CORRELATION = CorrelationId("r1-test-correlation")


def invocation(payload: dict[str, object] | None = None) -> UseCaseRequest:
    return UseCaseRequest(
        meta=ContractMeta(
            schema_version=AGENT_CONTRACT_SCHEMA_V1_0, run_id="r1-test", step_id="search",
            parent_step_id=None, correlation_id=CORRELATION,
            created_at=Instant(datetime(2026, 9, 5, tzinfo=UTC)),
            actor=ActorRef(ActorKind.APPLICATION, "r1-test"), status=InvocationStatus.PLANNED,
        ), use_case_id="application.search_local_passages",
        payload=payload if payload is not None else {"q": "bilan", "limit": 10},
        actor_context=UseCaseContext(CORRELATION),
    )


def passage(ref: str = "notion:1", kind: str = "NOTION", number: int = 1) -> AdmittedLocalPassage:
    return AdmittedLocalPassage(ref, kind, f"chunk:{number}", "v1", "Bilan synthétique", False)


class WindowPort:
    def __init__(self, passages: tuple[AdmittedLocalPassage, ...] = ()) -> None:
        self.passages = passages
        self.calls = []

    def admitted_window(self, **kwargs: object) -> LocalSearchWindow:
        self.calls.append(kwargs)
        return LocalSearchWindow(self.passages, False, False)


class MissingStore:
    def __init__(self) -> None:
        self.calls = []

    def load_resource(self, reference: ResourceRef) -> None:
        self.calls.append(reference.value)
        return None


def test_empty_success_and_closed_window_request() -> None:
    port = WindowPort()
    outcome = SearchLocalQuery(port, GetResourceQuery(MissingStore())).search_local(
        request=SearchLocalRequest(SearchText("bilan"), 10), correlation_id=CORRELATION,
    )
    assert outcome.success and outcome.data.items == ()
    assert port.calls == [{"text": SearchText("bilan"), "result_limit": 10, "candidate_limit": 100}]
    assert search_data(outcome.data) == {
        "items": [], "window_full": False, "more_admitted_in_window": False,
    }


def test_non_resource_and_invalid_or_missing_resource_are_not_invented() -> None:
    port = WindowPort((
        passage(), passage("resource:é", "RESOURCE", 2), passage("resource:absent", "RESOURCE", 3),
    ))
    store = MissingStore()
    result = LocalSearchUseCaseInbound(SearchLocalQuery(port, GetResourceQuery(store))).invoke(
        request=invocation(),
    )
    assert [item["open_status"] for item in result.outcome.data["items"]] == [
        "NOT_RESOURCE", "INVALID_RESOURCE_REF", "RESOURCE_NOT_FOUND",
    ]
    assert store.calls == ["resource:absent"]
    assert all(item["read15"] is None for item in result.outcome.data["items"])
    assert [item["position"] for item in result.outcome.data["items"]] == [1, 2, 3]


@pytest.mark.parametrize("payload", [
    {"q": "bilan"}, {"q": "bilan", "limit": True}, {"q": "", "limit": 10},
    {"q": "bilan", "limit": 1, "filters": {}},
])
def test_inbound_rejects_payload_before_calling_ports(payload: dict[str, object]) -> None:
    port = WindowPort()
    with pytest.raises(InvalidSearchTextError):
        LocalSearchUseCaseInbound(SearchLocalQuery(port, GetResourceQuery(MissingStore()))).invoke(
            request=invocation(payload),
        )
    assert port.calls == []


def test_wrong_use_case_and_window_overflow_are_rejected() -> None:
    port = WindowPort((passage(), passage("notion:2", number=2)))
    inbound = LocalSearchUseCaseInbound(SearchLocalQuery(port, GetResourceQuery(MissingStore())))
    with pytest.raises(ValueError):
        inbound.invoke(request=replace(invocation(), use_case_id="application.other"))
    with pytest.raises(ValueError, match="OVERFLOW"):
        inbound.invoke(request=invocation({"q": "bilan", "limit": 1}))


@pytest.mark.parametrize("change", [
    {"object_ref": "../private"}, {"object_kind": "RESOURCE/URL"},
    {"passage_ref": ""}, {"version_or_checksum": "x" * 129},
    {"excerpt": "x" * 321}, {"excerpt": "\u202e"}, {"excerpt_truncated": 1},
])
def test_admitted_projection_is_bounded(change: dict[str, object]) -> None:
    with pytest.raises(ValueError):
        replace(passage(), **change)


def test_duplicate_passages_and_invalid_window_flags_fail() -> None:
    with pytest.raises(ValueError):
        LocalSearchWindow((passage(), passage()), False, False)
    with pytest.raises(ValueError):
        LocalSearchWindow((), 0, False)


def test_resource_failure_is_not_disguised_as_missing() -> None:
    class BrokenResources:
        def get_resource(self, **kwargs: object) -> ApplicationOutcome:
            return ApplicationOutcome(
                outcome_status=OutcomeStatus.SUCCESS, success=True,
                correlation_id=CorrelationId("wrong"), data=None,
            )
    with pytest.raises(ValueError, match="RESOURCE_LINK_FAILED"):
        SearchLocalQuery(WindowPort((passage("resource:1", "RESOURCE"),)), BrokenResources()).search_local(
            request=SearchLocalRequest(SearchText("bilan")), correlation_id=CORRELATION,
        )


@pytest.mark.parametrize("fault", ["correlation", "effect", "missing_data"])
def test_inbound_rejects_incoherent_query_outcome(fault: str) -> None:
    original = SearchLocalQuery(WindowPort(), GetResourceQuery(MissingStore())).search_local(
        request=SearchLocalRequest(SearchText("bilan")), correlation_id=CORRELATION,
    )
    changes = {
        "correlation": {"correlation_id": CorrelationId("other")},
        "effect": {"side_effects": ({"effect": "forbidden"},)},
        "missing_data": {"data": None},
    }
    class BadQuery:
        def search_local(self, **kwargs):
            return replace(original, **changes[fault])
    with pytest.raises(ValueError, match="INVALID_SEARCH_OUTCOME"):
        LocalSearchUseCaseInbound(BadQuery()).invoke(request=invocation())
