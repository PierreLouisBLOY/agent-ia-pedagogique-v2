"""Exact notion selection through Application and its bounded public HTTP companion."""
from __future__ import annotations

import copy
import hashlib
import json
from urllib.parse import quote

import pytest

from backend.adapters.inbound.api.p0_creation import P0CreationEndpoint
from backend.adapters.inbound.api.p0_notion_evidence import (
    MAX_NOTION_EVIDENCE_ITEMS,
    P0_NOTION_EVIDENCE_CONTRACT,
    P0NotionEvidenceEndpoint,
)
from backend.adapters.inbound.api.read15 import Read15Endpoint
from backend.adapters.inbound.api.routes import (
    ASSET_NAMES,
    MAX_TARGET_BYTES,
    P0_NOTION_EVIDENCE_ROUTE_SPECS,
    P0_NOTION_EVIDENCE_TEMPLATE,
    P0_ROUTE_SPECS,
    resolve_p0_notion_evidence,
    resolve_p0_route,
)
from backend.adapters.inbound.api.server import LocalRead15Service
from backend.adapters.inbound.application.exact_notion_evidence import ExactNotionEvidenceInbound
from backend.infrastructure.config.schemas.http import LocalBrowserHttpConfiguration
from backend.modules.resource_library.application.queries.get_exact_notion_evidence import (
    GetExactNotionEvidenceQuery,
)
from backend.modules.resource_library.contracts.dto.search_source_status import SearchSourceStatus
from backend.modules.resource_library.ports.outbound.canonical_notion_catalog import (
    CanonicalNotionIdentityRecord,
)
from backend.modules.resource_library.ports.outbound.exact_notion_evidence import (
    ExactNotionEvidence,
)
from backend.modules.resource_library.ports.outbound.local_search import AdmittedLocalPassage

NOTION = "notion:coût"
TARGET = P0_NOTION_EVIDENCE_TEMPLATE + "?notion_id=" + quote(NOTION, safe="")


def native():
    class Port:
        def get_exact_notion_evidence(self, notion_id):
            assert notion_id == NOTION
            return ExactNotionEvidence(CanonicalNotionIdentityRecord(NOTION, "Coût", "CANONICAL"), (
                AdmittedLocalPassage(NOTION, "NOTION", "search-chunk:synthetic", "a" * 64,
                                    "Extrait synthétique complet.", False, SearchSourceStatus("CURRENT")),))
    return ExactNotionEvidenceInbound(GetExactNotionEvidenceQuery(Port())).inspect(NOTION)


def endpoint(data=None, calls=None):
    def read(notion_id):
        if calls is not None:
            calls.append(notion_id)
        return native() if data is None else data
    return P0NotionEvidenceEndpoint(read)


def response(api, method="GET", target=TARGET, raw=b""):
    status, media, body, template = api.respond(method, target, raw, "exact-source-test")
    assert media == "application/json; charset=utf-8"
    assert template == P0_NOTION_EVIDENCE_TEMPLATE
    value = json.loads(body)
    assert value["meta"]["contract_id"] == P0_NOTION_EVIDENCE_CONTRACT
    return status, value, body


def test_actual_application_projection_has_exact_selection_and_unknown_authority():
    calls = []
    received = native()
    status, payload, _ = response(endpoint(received, calls))
    assert status == 200 and calls == [NOTION]
    data = payload["data"]
    assert data["notion_id"] == NOTION and data["status"] == "CANONICAL"
    assert data["available_authority"] == "UNKNOWN" and data["authority_basis"] == "NOT_ATTESTED_BY_APPLICATION"
    item = data["items"][0]
    assert item["selection"] == {"notion_id": NOTION, "passage_ref": "search-chunk:synthetic"}
    assert item["source_status"] == received["items"][0]["source_status"]
    assert item["provenance"] == received["items"][0]["provenance"]
    assert item["excerpt_sha256"] == hashlib.sha256(item["excerpt"].encode()).hexdigest()
    assert item["source_status"]["validation_status"] == "UNKNOWN" and not data["exclusions"]


@pytest.mark.parametrize("target", [
    P0_NOTION_EVIDENCE_TEMPLATE, P0_NOTION_EVIDENCE_TEMPLATE + "?",
    P0_NOTION_EVIDENCE_TEMPLATE + "?q=cout", P0_NOTION_EVIDENCE_TEMPLATE + "?notion_id=",
    P0_NOTION_EVIDENCE_TEMPLATE + "?notion_id=notion:", TARGET + "&notion_id=notion:other",
    TARGET + "&limit=20", TARGET + "#fragment", TARGET + "&include=private", TARGET + "&path=C:/seed",
    P0_NOTION_EVIDENCE_TEMPLATE + "?notion_id=notion:%2Fseed", P0_NOTION_EVIDENCE_TEMPLATE + "?notion_id=notion:%5Cseed",
    P0_NOTION_EVIDENCE_TEMPLATE + "?notion_id=notion:%253Acout", P0_NOTION_EVIDENCE_TEMPLATE + "?notion_id=notion:%",
    P0_NOTION_EVIDENCE_TEMPLATE + "?notion_id=notion:%ff", P0_NOTION_EVIDENCE_TEMPLATE + "?notion_id=notion:cout+OR+1",
    P0_NOTION_EVIDENCE_TEMPLATE + "?notion_id=notion:%0Acout", P0_NOTION_EVIDENCE_TEMPLATE + "?notion_id=resource:case",
    P0_NOTION_EVIDENCE_TEMPLATE + "?notion_id=" + "a" * 257, "https://host.invalid" + TARGET,
    TARGET + "a" * MAX_TARGET_BYTES,
])
def test_closed_id_and_query_rejection_precedes_application(target):
    calls = []
    status, payload, _ = response(endpoint(calls=calls), target=target)
    assert status == 400 and payload["error"]["code"] == "P0_REFERENCE_REQUEST_REJECTED"
    assert calls == []


@pytest.mark.parametrize("method", ["HEAD", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"])
def test_no_implicit_read_methods_or_body(method):
    calls = []
    assert response(endpoint(calls=calls), method=method)[0] == 400
    assert calls == []


def test_get_body_and_no_alias_or_version_fallback():
    calls = []
    assert response(endpoint(calls=calls), raw=b"private")[0] == 400
    assert calls == []
    absent = {"notion_id": NOTION, "status": "NOT_CANONICAL_OR_ABSENT", "items": []}
    status, payload, _ = response(endpoint(absent))
    assert status == 404 and payload["error"]["code"] == "P0_NOTION_NOT_FOUND" and "data" not in payload


@pytest.mark.parametrize("mutation", ["truncated", "empty", "resource", "resource_and_truncated"])
def test_exclusions_keep_status_and_id_without_answer_or_fake_complete_excerpt(mutation):
    value = native()
    item = value["items"][0]
    if "truncated" in mutation:
        item["excerpt_truncated"] = True
    if mutation == "empty":
        item["excerpt"] = ""
    if mutation.startswith("resource"):
        item["object_kind"] = "RESOURCE"
        item["excerpt"] = "ORACLE_PRIVATE_SENTINEL"
    status, payload, raw = response(endpoint(value))
    assert status == 200 and payload["data"]["items"] == []
    exclusion = payload["data"]["exclusions"][0]
    assert "excerpt" not in exclusion and "selection" not in exclusion
    assert exclusion["source_status"] == item["source_status"] and exclusion["provenance"] == item["provenance"]
    assert "P0_TEACHER_SOURCE_FORBIDDEN" in exclusion["reasons"] if mutation.startswith("resource") else "P0_REFERENCE_INCOMPLETE" in exclusion["reasons"]
    assert b"ORACLE_PRIVATE_SENTINEL" not in raw


@pytest.mark.parametrize("mutation", ["wrong_notion", "alias_status", "unknown_top_field", "wrong_retrieval", "duplicate",
    "unknown_item_field", "invalid_id", "long_excerpt", "invalid_truncation", "bad_status", "status_extra",
    "authority_true", "authority_integer", "unknown_provenance", "private_locator", "invalid_version"])
def test_mutated_public_source_cannot_gain_authority_or_leak_private_fields(mutation):
    value = native()
    item = value["items"][0]
    if mutation == "wrong_notion":
        value["notion_id"] = "notion:other"
    elif mutation == "alias_status":
        value["status"] = "MERGED"
    elif mutation == "unknown_top_field":
        value["private_path"] = "PRIVATE_SENTINEL"
    elif mutation == "wrong_retrieval":
        value["retrieval_path"] = "FUZZY_OR_FALLBACK"
    elif mutation == "duplicate":
        value["items"].append(copy.deepcopy(item))
    elif mutation == "unknown_item_field":
        item["private_file"] = "PRIVATE_SENTINEL"
    elif mutation == "invalid_id":
        item["object_ref"] = "PRIVATE_SENTINEL/../../seed"
    elif mutation == "long_excerpt":
        item["excerpt"] = "PRIVATE_SENTINEL" * 30
    elif mutation == "invalid_truncation":
        item["excerpt_truncated"] = 1
    elif mutation == "bad_status":
        item["source_status"]["contract_id"] = "PRIVATE_SENTINEL"
    elif mutation == "status_extra":
        item["source_status"]["private"] = "PRIVATE_SENTINEL"
    elif mutation == "authority_true":
        item["provenance"]["authority_absolute"] = True
    elif mutation == "authority_integer":
        item["provenance"]["authority_absolute"] = 0
    elif mutation == "unknown_provenance":
        item["provenance"]["private_uri"] = "PRIVATE_SENTINEL"
    elif mutation == "private_locator":
        item["passage_ref"] = "C:/PRIVATE_SENTINEL"
    elif mutation == "invalid_version":
        item["version_or_checksum"] = "PRIVATE_SENTINEL/../../file"
    status, payload, raw = response(endpoint(value))
    assert status == 500 and "data" not in payload and b"PRIVATE_SENTINEL" not in raw


def test_missing_source_status_is_unavailable_not_silently_promoted():
    value = native()
    del value["items"][0]["source_status"]
    status, payload, _ = response(endpoint(value))
    assert status == 200
    item = payload["data"]["items"][0]
    assert item["source_status"] is None and item["available_authority"] == "UNKNOWN"


def test_item_and_response_byte_limits_refuse_without_partial_or_truncated_data():
    value = native()
    value["items"] *= MAX_NOTION_EVIDENCE_ITEMS + 1
    status, payload, _ = response(endpoint(value))
    assert status == 413 and payload["error"]["code"] == "P0_REFERENCE_ITEM_LIMIT_EXCEEDED" and "data" not in payload
    value = native()
    item = value["items"][0]
    value["items"] = [{**copy.deepcopy(item), "passage_ref": "search-chunk:" + str(n), "excerpt": "é" * 320} for n in range(100)]
    status, payload, _ = response(endpoint(value))
    assert status == 413 and payload["error"]["code"] == "P0_REFERENCE_RESPONSE_LIMIT_EXCEEDED" and "data" not in payload


def test_application_exception_is_minimized():
    def failure(_):
        raise RuntimeError("C:/PRIVATE_SENTINEL credential secret")
    status, payload, raw = response(P0NotionEvidenceEndpoint(failure))
    assert status == 500 and payload["error"]["code"] == "P0_REFERENCE_APPLICATION_FAILURE"
    assert b"PRIVATE_SENTINEL" not in raw and b"credential" not in raw


def test_companion_does_not_change_historical_route_tuples_and_requires_reader():
    assert P0_NOTION_EVIDENCE_ROUTE_SPECS == (("GET", P0_NOTION_EVIDENCE_TEMPLATE),)
    assert len(P0_ROUTE_SPECS) == 9 and P0_ROUTE_SPECS[-1][1].endswith("/teacher")
    assert resolve_p0_notion_evidence("GET", TARGET) == NOTION
    assert resolve_p0_route("GET", TARGET) == ("notion-evidence", "", "", False, P0_NOTION_EVIDENCE_TEMPLATE)
    called = []
    api = P0CreationEndpoint(lambda *_: called.append("command"), lambda *_: called.append("version"), [], nonce="n" * 43)
    status, _, raw, _ = api.respond("GET", TARGET, b"", "ref")
    assert status == 409 and json.loads(raw)["error"]["code"] == "P0_REFERENCE_NOT_ENABLED" and called == []
    api.exact_notion_reader = lambda notion_id: native()
    assert api.respond("GET", TARGET, b"", "ref")[0] == 200 and called == []


@pytest.mark.parametrize("change,expected", [({}, 200), ({"host": "foreign.invalid"}, 403),
    ({"origin": "http://foreign.invalid"}, 403), ({"sec-fetch-site": "cross-site"}, 403),
    ({"x-local-intent": "other"}, 403)])
def test_same_local_http_host_origin_intent_controls_apply_before_source_reader(change, expected):
    calls = []
    api = P0CreationEndpoint(lambda *_: {}, lambda *_: {}, [], nonce="n" * 43,
        exact_notion_reader=lambda notion_id: calls.append(notion_id) or native())
    service = LocalRead15Service(LocalBrowserHttpConfiguration(port=8123), Read15Endpoint(lambda *_: None), object(),
        {name: b"" for name in ASSET_NAMES}, p0_endpoint=api)
    headers = {"host": "127.0.0.1:8123", "x-local-intent": "conversation-v1", **change}
    status, _, _, _ = service.respond("GET", TARGET, headers, "ref")
    assert status == expected and calls == ([NOTION] if expected == 200 else [])
