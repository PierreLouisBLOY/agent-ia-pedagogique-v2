"""Closed, bounded HTTP projection through an injected Application invocation."""

from __future__ import annotations

import json
import unicodedata
from collections.abc import Callable, Mapping

from backend.adapters.inbound.api.read15 import HttpProjection, public_error
from backend.agent_runtime.contracts import UseCaseResult
from backend.modules.resource_library.contracts.dto.search_source_status import SearchSourceStatus

MAX_SEARCH_RESPONSE_BYTES = 64 * 1_024
_FIELDS = frozenset({
    "position", "object_ref", "object_kind", "passage_ref", "version_or_checksum",
    "excerpt", "excerpt_truncated", "provenance", "read15", "open_status",
})
_PROVENANCE = {
    "channel": "LEXICAL", "search_boundary": "sqlite-op11", "content_boundary": "sqlite-op13",
    "admission_policy": "F2A", "source_kind": "canonical_search_chunk", "freshness": "CURRENT",
    "authority_basis": "canonical-registry", "authority_absolute": False,
    "content_trust": "UNTRUSTED_CONTENT",
}


class SearchValidationRejected(ValueError):
    """Validation failed before infrastructure access."""


def public_search_error(code: str, correlation_id: str) -> HttpProjection:
    if code != "SEARCH_REQUEST_REJECTED":
        return public_error(code, correlation_id)
    return HttpProjection(400, {
        "error": {"category": "validation", "code": code},
        "meta": {"correlation_id": correlation_id},
    })


def _identifier(value: object, maximum: int) -> bool:
    return type(value) is str and 1 <= len(value) <= maximum and all(
        unicodedata.category(c)[0] in {"L", "N"} or c in "._:-" for c in value
    )


def _item(data: object, position: int) -> dict[str, object]:
    if not isinstance(data, Mapping) or set(data) not in (_FIELDS, _FIELDS | {"source_status"}):
        raise ValueError("INVALID_SEARCH_PROJECTION")
    if "source_status" in data:
        SearchSourceStatus.from_mapping(data["source_status"])
    if type(data["position"]) is not int or data["position"] != position:
        raise ValueError("INVALID_SEARCH_POSITION")
    for field, maximum in (
        ("object_ref", 256), ("object_kind", 64), ("passage_ref", 256), ("version_or_checksum", 128),
    ):
        if not _identifier(data[field], maximum):
            raise ValueError("INVALID_SEARCH_IDENTIFIER")
    excerpt = data["excerpt"]
    if type(excerpt) is not str or len(excerpt) > 320 or any(
        unicodedata.category(c) in {"Cc", "Cf", "Cs", "Zl", "Zp"} for c in excerpt
    ) or type(data["excerpt_truncated"]) is not bool:
        raise ValueError("INVALID_SEARCH_EXCERPT")
    provenance = data["provenance"]
    if (not isinstance(provenance, Mapping) or dict(provenance) != _PROVENANCE
            or provenance["authority_absolute"] is not False):
        raise ValueError("INVALID_SEARCH_PROVENANCE")
    status = data["open_status"]
    resource = data["read15"]
    if status == "OPENABLE":
        if (
            data["object_kind"] != "RESOURCE" or not isinstance(resource, Mapping)
            or set(resource) != {
                "resource_ref", "resource_type", "canonical_title", "availability_status",
            }
            or any(type(v) is not str or not v for v in resource.values())
            or resource["resource_ref"] != data["object_ref"]
        ):
            raise ValueError("INVALID_SEARCH_OPENING")
        resource = dict(resource)
    elif status in {"NOT_RESOURCE", "INVALID_RESOURCE_REF", "RESOURCE_NOT_FOUND"}:
        if resource is not None or (status == "NOT_RESOURCE") != (data["object_kind"] != "RESOURCE"):
            raise ValueError("INVALID_SEARCH_OPENING")
    else:
        raise ValueError("INVALID_SEARCH_OPENING")
    return {**dict(data), "provenance": dict(_PROVENANCE), "read15": resource}


class SearchEndpoint:
    def __init__(
        self, invoke: Callable[[str, int, str], UseCaseResult[object, object]],
    ) -> None:
        self._invoke = invoke

    def get(self, text: str, limit: int, correlation_id: str) -> HttpProjection:
        try:
            result = self._invoke(text, limit, correlation_id)
            outcome = result.outcome
            if (
                result.use_case_id != "application.search_local_passages"
                or result.meta.correlation_id.value != correlation_id
                or outcome.correlation_id.value != correlation_id
                or outcome.side_effects or outcome.operation_ref is not None
                or outcome.task_ref is not None or outcome.application_failure is not None
                or outcome.business_errors or not outcome.success
                or outcome.validation_result is not None
                or result.domain_events or result.error is not None
            ):
                raise ValueError("INVALID_SEARCH_OUTCOME")
            data = outcome.data
            if not isinstance(data, Mapping) or set(data) != {
                "items", "window_full", "more_admitted_in_window",
            }:
                raise ValueError("INVALID_SEARCH_PROJECTION")
            items = data["items"]
            if (type(limit) is not int or not 1 <= limit <= 20
                    or not isinstance(items, (list, tuple)) or len(items) > limit):
                raise ValueError("INVALID_SEARCH_WINDOW")
            if type(data["window_full"]) is not bool or type(data["more_admitted_in_window"]) is not bool:
                raise ValueError("INVALID_SEARCH_WINDOW")
            projected = [_item(item, index) for index, item in enumerate(items, 1)]
            if len({item["passage_ref"] for item in projected}) != len(projected):
                raise ValueError("DUPLICATE_SEARCH_PASSAGE")
            payload = {"data": {**dict(data), "items": projected},
                       "meta": {"correlation_id": correlation_id}}
            if len(json.dumps(payload, ensure_ascii=False).encode("utf-8")) > MAX_SEARCH_RESPONSE_BYTES:
                raise ValueError("SEARCH_RESPONSE_TOO_LARGE")
            return HttpProjection(200, payload)
        except SearchValidationRejected:
            return public_search_error("SEARCH_REQUEST_REJECTED", correlation_id)
        except Exception:
            return public_search_error("INTERNAL_ERROR", correlation_id)
