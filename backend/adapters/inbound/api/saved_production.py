"""Closed R4 HTTP projection; no business store, SQL, path or provider access."""
import json
import re
from collections.abc import Callable, Mapping

R4_HTTP_CONTRACT = "SAVE-REOPEN-WORD-HTTP-LOCAL-1.0"
_CODES = frozenset({"R4_SOURCE_NOT_AVAILABLE", "R4_DOCUMENTARY_IMPORT_READ_ONLY",
    "R4_REQUEST_REJECTED", "R4_NOT_FOUND", "R4_IDENTITY_CONFLICT", "R4_IDEMPOTENCY_CONFLICT",
    "R4_VERSION_LIMIT", "R4_STORE_FULL", "R4_VALIDATION_REQUIRED", "R4_VALIDATION_FAILED",
    "R4_BLOCKING_REVIEW", "R4_FRESH_HUMAN_GATE_REQUIRED", "R4_ALREADY_PROMOTED",
    "R4_GATE_LIMIT", "R4_BUNDLE_REQUIRED", "R4_EXPORT_KIND", "R4_NOT_ENABLED", "R4_ACTIONS_CHANGED",
    "R4_LOCAL_EDIT_UNAVAILABLE", "R4_LOCAL_EDIT_REJECTED", "R4_LOCAL_EDIT_NO_CHANGE",
    "R4_COMPARISON_UNAVAILABLE", "P0_SAVED_SOURCE_REJECTED"})

MEDIA_EXPORT_REFUSAL_CONTRACT = "P0-MEDIA-EXPORT-REFUSAL-1.0"


def media_export_error(code: str, operation: str, correlation: str) -> tuple[int, str, bytes] | None:
    """Project only bounded media export refusals; preserve the legacy R4 vocabulary."""
    if operation not in {"preview", "word"}:
        return None
    detail: dict[str, str]
    if code == "PRODUCTION_WORD_ANCHOR_AMBIGUOUS":
        detail = {"code": code}
    else:
        prefix, separator, reference = code.partition(":")
        choices = {
            "PRODUCTION_MEDIA_REQUIRED_MISSING": ("visual_ref", r"[A-Z][A-Z0-9_]{0,39}"),
            "PRODUCTION_MEDIA_EXPORT_ANCHOR_UNAVAILABLE": ("anchor_ref", r"[SQ][A-Z0-9_-]{1,63}"),
        }
        if not separator or prefix not in choices:
            return None
        field, pattern = choices[prefix]
        if re.fullmatch(pattern, reference) is None:
            return None
        detail = {"code": prefix, field: reference}
    return 409, "application/json; charset=utf-8", json.dumps({"error": detail,
        "meta": {"contract_id": MEDIA_EXPORT_REFUSAL_CONTRACT,
                 "correlation_id": correlation}}).encode()


def r4_error(code: str, correlation: str) -> tuple[int, str, bytes]:
    code = code if code in _CODES else "R4_APPLICATION_FAILURE"
    status = 404 if code == "R4_NOT_FOUND" else 500 if code == "R4_APPLICATION_FAILURE" else 409
    return status, "application/json; charset=utf-8", json.dumps({"error": {"code": code},
        "meta": {"contract_id": R4_HTTP_CONTRACT, "correlation_id": correlation}}).encode()


class SavedProductionEndpoint:
    def __init__(self, invoke: Callable[..., dict[str, object] | bytes], *, nonce: str) -> None:
        self.invoke = invoke
        self.nonce = nonce

    def respond(self, operation: str, production_ref: str, version_ref: str,
                kind: str, raw: bytes, correlation: str) -> tuple[int, str, bytes]:
        try:
            def pairs(entries: list[tuple[str, object]]) -> dict[str, object]:
                if len(dict(entries)) != len(entries):
                    raise ValueError("R4_REQUEST_REJECTED")
                return dict(entries)
            body: Mapping[str, object] = json.loads(raw, object_pairs_hook=pairs) if raw else {}
            if not isinstance(body, dict) or len(raw) > 16384:
                raise ValueError("R4_REQUEST_REJECTED")
            result = self.invoke(operation, production_ref, version_ref,
                                 body=body, kind=kind, correlation=correlation)
            if isinstance(result, bytes):
                if operation != "word":
                    raise ValueError("R4_REQUEST_REJECTED")
                return 200, "application/vnd.openxmlformats-officedocument.wordprocessingml.document", result
            if operation == "list":
                result = {**result, "transport_nonce": self.nonce}
            return 200, "application/json; charset=utf-8", json.dumps({"data": result,
                "meta": {"contract_id": R4_HTTP_CONTRACT, "correlation_id": correlation}},
                ensure_ascii=False, allow_nan=False).encode("utf-8")
        except (ValueError, TypeError) as error:
            return media_export_error(str(error), operation, correlation) or r4_error(str(error), correlation)
        except Exception:
            return r4_error("R4_APPLICATION_FAILURE", correlation)
