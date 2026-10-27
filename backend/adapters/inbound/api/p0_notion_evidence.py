"""Bounded public companion of the existing exact-notion Application reader."""
from __future__ import annotations

import hashlib
import json
import unicodedata
from collections.abc import Callable, Mapping

from backend.adapters.inbound.api.routes import (
    P0_NOTION_EVIDENCE_TEMPLATE,
    resolve_p0_notion_evidence,
)
from backend.adapters.inbound.api.search import MAX_SEARCH_RESPONSE_BYTES
from backend.adapters.inbound.application.local_search import validate_source_status_projection

P0_NOTION_EVIDENCE_CONTRACT = "P0-NOTION-EVIDENCE-HTTP-1.0"
MAX_NOTION_EVIDENCE_ITEMS = 256
_PASSAGE_FIELDS = frozenset({"object_ref", "object_kind", "passage_ref", "version_or_checksum", "excerpt", "excerpt_truncated", "provenance"})
_PROVENANCE = {"source_kind": "canonical_search_chunk", "freshness": "CURRENT", "admission_policy": "F2A",
               "authority_absolute": False, "content_trust": "UNTRUSTED_CONTENT", "channel": "EXACT_ID"}


def project_notion_evidence(notion_id: str, native: Mapping[str, object]) -> dict[str, object]:
    """Preserve actual identities/statuses; a complete candidate is not an admission."""
    if set(native) != {"notion_id", "status", "retrieval_path", "items"} or (
            native["notion_id"] != notion_id or native["status"] != "CANONICAL"
            or native["retrieval_path"] != "EXACT_ID_AND_EXPLICIT_LINKS"):
        raise ValueError("P0_REFERENCE_PROJECTION_REJECTED")
    passages = native["items"]
    if not isinstance(passages, (list, tuple)):
        raise ValueError("P0_REFERENCE_PROJECTION_REJECTED")
    if len(passages) > MAX_NOTION_EVIDENCE_ITEMS:
        raise ValueError("P0_REFERENCE_ITEM_LIMIT_EXCEEDED")
    seen: set[str] = set()
    candidates: list[dict[str, object]] = []
    exclusions: list[dict[str, object]] = []
    for item in passages:
        if not isinstance(item, Mapping) or set(item) not in (_PASSAGE_FIELDS, _PASSAGE_FIELDS | {"source_status"}):
            raise ValueError("P0_REFERENCE_PROJECTION_REJECTED")
        status = validate_source_status_projection(item["source_status"]) if "source_status" in item else None
        for field, maximum in (("object_ref", 256), ("object_kind", 64),
                               ("passage_ref", 256), ("version_or_checksum", 128)):
            value = item[field]
            if type(value) is not str or not 1 <= len(value) <= maximum or any(
                    unicodedata.category(char)[0] not in {"L", "N"} and char not in "._:-" for char in value):
                raise ValueError("P0_REFERENCE_PROJECTION_REJECTED")
        excerpt = item["excerpt"]
        if (type(excerpt) is not str or len(excerpt) > 320 or any(
                unicodedata.category(char) in {"Cc", "Cf", "Cs", "Zl", "Zp"} for char in excerpt)
                or type(item["excerpt_truncated"]) is not bool):
            raise ValueError("P0_REFERENCE_PROJECTION_REJECTED")
        object_ref, object_kind, passage_ref, version_or_checksum = (
            str(item[field]) for field in ("object_ref", "object_kind", "passage_ref", "version_or_checksum"))
        excerpt_truncated = bool(item["excerpt_truncated"])
        if (not isinstance(item["provenance"], Mapping) or dict(item["provenance"]) != _PROVENANCE
                or item["provenance"].get("authority_absolute") is not False):
            raise ValueError("P0_REFERENCE_PROJECTION_REJECTED")
        if passage_ref in seen:
            raise ValueError("P0_REFERENCE_PROJECTION_REJECTED")
        seen.add(passage_ref)
        projected: dict[str, object] = {"object_ref": object_ref, "object_kind": object_kind,
            "passage_ref": passage_ref, "version_or_checksum": version_or_checksum,
            "excerpt_truncated": excerpt_truncated, "source_status": status,
            "provenance": dict(item["provenance"]), "available_authority": "UNKNOWN",
            "authority_basis": "NOT_ATTESTED_BY_APPLICATION"}
        reasons = []
        if object_kind not in {"NOTION", "PEDAGOGICAL_CONTENT", "METHOD"}:
            reasons.append("P0_TEACHER_SOURCE_FORBIDDEN")
        if excerpt_truncated or not excerpt:
            reasons.append("P0_REFERENCE_INCOMPLETE")
        if reasons:
            exclusions.append({**projected, "reasons": reasons})
        else:
            candidates.append({**projected, "excerpt": excerpt,
                "excerpt_sha256": hashlib.sha256(excerpt.encode("utf-8")).hexdigest(),
                "selection": {"notion_id": notion_id, "passage_ref": passage_ref}})
    return {"notion_id": notion_id, "status": "CANONICAL", "retrieval_path": native["retrieval_path"],
            "available_authority": "UNKNOWN", "authority_basis": "NOT_ATTESTED_BY_APPLICATION",
            "items": candidates, "exclusions": exclusions}


class P0NotionEvidenceEndpoint:
    def __init__(self, read: Callable[[str], Mapping[str, object]]) -> None:
        self._read = read

    def respond(self, method: str, target: str, raw: bytes, correlation: str) -> tuple[int, str, bytes, str]:
        meta = {"contract_id": P0_NOTION_EVIDENCE_CONTRACT, "correlation_id": correlation}
        status = 200
        try:
            notion_id = resolve_p0_notion_evidence(method, target)
            if raw:
                raise ValueError("P0_REFERENCE_REQUEST_REJECTED")
        except ValueError:
            envelope: dict[str, object] = {"error": {"code": "P0_REFERENCE_REQUEST_REJECTED"}, "meta": meta}
            status = 400
        else:
            try:
                native = self._read(notion_id)
                if native == {"notion_id": notion_id, "status": "NOT_CANONICAL_OR_ABSENT", "items": []}:
                    status, envelope = 404, {"error": {"code": "P0_NOTION_NOT_FOUND"}, "meta": meta}
                else:
                    envelope = {"data": project_notion_evidence(notion_id, native), "meta": meta}
                    if len(json.dumps(envelope, ensure_ascii=False, allow_nan=False).encode("utf-8")) > MAX_SEARCH_RESPONSE_BYTES:
                        raise ValueError("P0_REFERENCE_RESPONSE_LIMIT_EXCEEDED")
            except ValueError as error:
                code = str(error)
                if code in {"P0_REFERENCE_ITEM_LIMIT_EXCEEDED", "P0_REFERENCE_RESPONSE_LIMIT_EXCEEDED"}:
                    status, envelope = 413, {"error": {"code": code}, "meta": meta}
                else:
                    status, envelope = 500, {"error": {"code": "P0_REFERENCE_PROJECTION_REJECTED"}, "meta": meta}
            except Exception:
                status, envelope = 500, {"error": {"code": "P0_REFERENCE_APPLICATION_FAILURE"}, "meta": meta}
        return status, "application/json; charset=utf-8", json.dumps(envelope, ensure_ascii=False,
            allow_nan=False).encode("utf-8"), P0_NOTION_EVIDENCE_TEMPLATE
