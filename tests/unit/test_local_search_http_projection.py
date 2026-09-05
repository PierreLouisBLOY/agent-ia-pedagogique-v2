from __future__ import annotations

import copy
import json
from dataclasses import replace

import pytest

from backend.adapters.inbound.api.search import SearchEndpoint, SearchValidationRejected
from backend.adapters.inbound.application.local_search import LocalSearchUseCaseInbound
from backend.agent_runtime.contracts import UseCaseResult
from backend.core_contracts.outcome import ApplicationOutcome, OutcomeStatus
from backend.modules.resource_library.application.queries import GetResourceQuery
from backend.modules.resource_library.application.queries.search_local import SearchLocalQuery
from tests.unit.test_local_search_application import (
    CORRELATION,
    MissingStore,
    WindowPort,
    invocation,
    passage,
)


def result_data(data: object = None) -> UseCaseResult:
    original = LocalSearchUseCaseInbound(
        SearchLocalQuery(WindowPort((passage(),)), GetResourceQuery(MissingStore())),
    ).invoke(request=invocation())
    if data is None:
        return original
    return replace(original, outcome=replace(original.outcome, data=data))


def project(result: UseCaseResult, limit: int = 10):
    return SearchEndpoint(lambda *_: result).get("bilan", limit, CORRELATION.value)


def test_exact_success_projection_and_provenance() -> None:
    response = project(result_data())
    assert response.status == 200
    assert set(response.payload) == {"data", "meta"}
    assert response.payload["meta"] == {"correlation_id": CORRELATION.value}
    item = response.payload["data"]["items"][0]
    assert item["read15"] is None and item["open_status"] == "NOT_RESOURCE"
    assert item["provenance"]["authority_absolute"] is False
    assert set(item) == {
        "position", "object_ref", "object_kind", "passage_ref", "version_or_checksum",
        "excerpt", "excerpt_truncated", "provenance", "read15", "open_status",
    }


@pytest.mark.parametrize("field,value", [
    ("extra", "private"), ("object_ref", "../secret"), ("position", True),
    ("excerpt", "x" * 321), ("excerpt_truncated", 1), ("open_status", "OPENABLE"),
    ("provenance", {"channel": "SEMANTIC"}), ("read15", {"resource_ref": "notion:1"}),
])
def test_malformed_item_fails_closed(field: str, value: object) -> None:
    data = copy.deepcopy(result_data().outcome.data)
    data["items"][0][field] = value
    response = project(result_data(data))
    assert response.status == 500
    assert response.payload["error"] == {"category": "technical", "code": "INTERNAL_ERROR"}


def test_body_budget_in_utf8_and_duplicate_passages() -> None:
    data = copy.deepcopy(result_data().outcome.data)
    item = data["items"][0]
    item.update(object_ref="resource:1", object_kind="RESOURCE", open_status="OPENABLE",
                read15={"resource_ref": "resource:1", "resource_type": "COURSE",
                        "canonical_title": "é" * 32768, "availability_status": "ACTIVE"})
    assert project(result_data(data)).status == 500
    data = copy.deepcopy(result_data().outcome.data)
    item = copy.deepcopy(data["items"][0])
    item["position"] = 2
    data["items"].append(item)
    assert project(result_data(data)).status == 500


@pytest.mark.parametrize("change", ["use_case", "correlation"])
def test_envelope_identity_is_verified(change: str) -> None:
    original = result_data()
    if change == "use_case":
        changed = replace(original, use_case_id="wrong")
    else:
        wrong = type(CORRELATION)("wrong")
        changed = replace(original, meta=replace(original.meta, correlation_id=wrong),
                          outcome=replace(original.outcome, correlation_id=wrong))
    assert project(changed).status == 500


def test_side_effect_and_non_success_not_empty_success() -> None:
    result = result_data()
    assert project(replace(result, outcome=replace(
        result.outcome, side_effects=({"effect": "forbidden"},),
    ))).status == 500
    failure = ApplicationOutcome(
        outcome_status=OutcomeStatus.REJECTED, success=False, correlation_id=CORRELATION,
    )
    assert project(replace(result, outcome=failure,
                           meta=replace(result.meta, status=OutcomeStatus.REJECTED))).status == 500


def test_validation_and_technical_failures_are_distinct_and_minimized() -> None:
    def invoke(*args: object):
        raise SearchValidationRejected("PRIVATE")
    response = SearchEndpoint(invoke).get("", 10, CORRELATION.value)
    assert response.status == 400 and response.payload["error"]["code"] == "SEARCH_REQUEST_REJECTED"
    def broken(*args: object):
        raise RuntimeError("PRIVATE query or path")
    response = SearchEndpoint(broken).get("bilan", 10, CORRELATION.value)
    assert response.status == 500 and "PRIVATE" not in str(response.payload)


def test_exact_64_kib_utf8_boundary_and_domain_events() -> None:
    data = copy.deepcopy(result_data().outcome.data)
    item = data["items"][0]
    item.update(object_ref="resource:1", object_kind="RESOURCE", open_status="OPENABLE",
                read15={"resource_ref": "resource:1", "resource_type": "COURSE",
                        "canonical_title": "é", "availability_status": "ACTIVE"})
    envelope = {"data": data, "meta": {"correlation_id": CORRELATION.value}}
    size = len(json.dumps(envelope, ensure_ascii=False).encode("utf-8"))
    item["read15"]["canonical_title"] += "x" * (65536 - size)
    response = project(result_data(data))
    assert response.status == 200
    assert len(json.dumps(response.payload, ensure_ascii=False).encode("utf-8")) == 65536
    item["read15"]["canonical_title"] += "x"
    assert project(result_data(data)).status == 500
    assert project(replace(result_data(), domain_events=({"effect": "not-a-query"},))).status == 500


@pytest.mark.parametrize("limit", [True, 0, 21, "10"])
def test_projection_rejects_invalid_limit_even_with_injected_reader(limit: object) -> None:
    assert project(result_data(), limit).status == 500
