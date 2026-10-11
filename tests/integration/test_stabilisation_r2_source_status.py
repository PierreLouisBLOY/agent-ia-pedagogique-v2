"""Native lifecycle on a declared synthetic SQLite bench; no original database."""

import hashlib
import sqlite3
from dataclasses import replace

import pytest

from backend.adapters.inbound.api.search import SearchEndpoint
from backend.adapters.inbound.application.local_search import LocalSearchUseCaseInbound
from backend.adapters.outbound.document_content.sqlite import DocumentContentAccessAdapter
from backend.adapters.outbound.evidence.sqlite import SQLiteEvidenceSearchAdapter
from backend.adapters.outbound.search.local import SQLiteLocalSearchAdapter
from backend.adapters.outbound.search.sqlite import BusinessSearchAdapter
from backend.agent_runtime.agents.evidence import RetrievalChannel, RetrievalQuery
from backend.modules.resource_library.application.queries import GetResourceQuery
from backend.modules.resource_library.application.queries.search_local import SearchLocalQuery
from backend.modules.resource_library.contracts.dto.search_source_status import SearchSourceStatus
from tests.integration.test_local_search_sqlite import RESOURCE, reader, synthetic_search_target
from tests.unit.test_local_search_application import CORRELATION, MissingStore, invocation


def lifecycle_target(tmp_path):
    target = synthetic_search_target(tmp_path)
    with sqlite3.connect(target.runtime_path) as connection:
        connection.executescript("""CREATE TABLE question(id TEXT PRIMARY KEY, lifecycle_status TEXT, validation_status TEXT);
            INSERT INTO question VALUES ('resource:r1','DRAFT','NOT_VALIDATED');
            UPDATE object_registry SET object_type='QUESTION';""")
    return replace(
        target, expected_sha256=hashlib.sha256(target.runtime_path.read_bytes()).hexdigest()
    )


def query():
    return RetrievalQuery(
        search_goal='"bilan"',
        scope={},
        source_policy={"kinds": ("canonical",)},
        filters={"active": True},
        required_authority={"basis": "canonical-registry"},
        max_items=10,
    )


def test_draft_remains_consultable_with_separate_native_status_through_http(tmp_path):
    target = lifecycle_target(tmp_path)
    before = target.runtime_path.read_bytes()
    connection = reader(target)
    try:
        bridge = SQLiteLocalSearchAdapter(connection)
        search = SearchLocalQuery(bridge, GetResourceQuery(MissingStore()))
        inbound = LocalSearchUseCaseInbound(search)
        with bridge.read_snapshot():
            result = inbound.invoke(request=invocation())
        response = SearchEndpoint(lambda *_: result).get("bilan", 10, CORRELATION.value)
        assert response.status == 200
        item = response.payload["data"]["items"][0]
        assert (
            item["source_status"]
            == SearchSourceStatus(
                "CURRENT",
                lifecycle_status="DRAFT",
                validation_status="NOT_VALIDATED",
                status_basis="OBJECT_ROW",
            ).as_dict()
        )
        assert item["provenance"]["authority_absolute"] is False
        assert item["open_status"] == "NOT_RESOURCE"
        assert item["version_or_checksum"] == "version:0"
    finally:
        connection.close()
    assert target.runtime_path.read_bytes() == before


def test_status_substitution_and_change_refused_then_fetch_reports_current_row(tmp_path):
    target = lifecycle_target(tmp_path)
    connection = reader(target)
    try:
        search = SQLiteEvidenceSearchAdapter(BusinessSearchAdapter(connection))
        candidate = search.search(query=query(), channel=RetrievalChannel.LEXICAL).candidates[0]
        assert search.is_admissible(candidate=candidate, query=query())
        changed = {
            **candidate.metadata,
            "source_status": SearchSourceStatus(
                "CURRENT",
                lifecycle_status="PUBLISHED",
                validation_status="VALIDATED",
                status_basis="OBJECT_ROW",
            ).as_dict(),
        }
        assert not search.is_admissible(
            candidate=replace(candidate, metadata=changed), query=query()
        )
        content = DocumentContentAccessAdapter(connection)
        assert content.read_passage(candidate.locator).source_status.lifecycle_status == "DRAFT"
        with sqlite3.connect(target.runtime_path) as writer:
            writer.execute("UPDATE question SET lifecycle_status='REVIEW' WHERE id=?", (RESOURCE,))
        assert not search.is_admissible(candidate=candidate, query=query())
        assert content.read_passage(candidate.locator).source_status.lifecycle_status == "REVIEW"
        refreshed = search.search(query=query(), channel=RetrievalChannel.LEXICAL).candidates[0]
        assert search.is_admissible(candidate=refreshed, query=query())
        assert refreshed.metadata["freshness"] == "CURRENT"
        assert refreshed.authority["absolute"] is False
    finally:
        connection.close()


def test_resource_without_exact_version_does_not_borrow_an_available_status(tmp_path):
    target = synthetic_search_target(tmp_path)
    connection = reader(target)
    try:
        hit = BusinessSearchAdapter(connection).search('"bilan"')[0]
        assert hit.source_status == SearchSourceStatus(
            "CURRENT", identity_status="ACTIVE", status_basis="EXACT_VERSION_REQUIRED"
        )
        assert (
            DocumentContentAccessAdapter(connection).read_passage(hit.passage_ref).source_status
            == hit.source_status
        )
    finally:
        connection.close()


@pytest.mark.parametrize("fault", ["field", "contract", "value", "scope"])
def test_successor_http_status_remains_closed(tmp_path, fault):
    target = lifecycle_target(tmp_path)
    connection = reader(target)
    try:
        bridge = SQLiteLocalSearchAdapter(connection)
        with bridge.read_snapshot():
            result = LocalSearchUseCaseInbound(
                SearchLocalQuery(bridge, GetResourceQuery(MissingStore()))
            ).invoke(request=invocation())
        import copy

        data = copy.deepcopy(result.outcome.data)
        status = data["items"][0]["source_status"]
        if fault == "field":
            status["authority_absolute"] = True
        elif fault == "contract":
            status["contract_id"] = "SEARCH-SOURCE-STATUS-99.0"
        elif fault == "value":
            status["lifecycle_status"] = "<instruction>"
        else:
            status["status_basis"] = "EXACT_VERSION_REQUIRED"
        changed = replace(result, outcome=replace(result.outcome, data=data))
        assert SearchEndpoint(lambda *_: changed).get("bilan", 10, CORRELATION.value).status == 500
    finally:
        connection.close()
