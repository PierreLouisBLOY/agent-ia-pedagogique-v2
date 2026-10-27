"""Closed HTTP companion for an explicitly unvalidated local capture."""
import json

from backend.adapters.inbound.api.routes import (
    CAPTURED_PARTIAL_ROOT as ROOT,
)
from backend.adapters.inbound.api.routes import (
    CAPTURED_PARTIAL_ROUTE_PATTERN as _ROUTE,
)
from backend.adapters.inbound.application.partial_workspace import PartialWorkspaceInbound

CONTRACT = "V2-CAPTURED-PARTIAL-HTTP-1.0"


def is_partial_target(target: str) -> bool:
    return target == ROOT or target.startswith(ROOT + "/")


class PartialWorkspaceEndpoint:
    def __init__(self, inbound: PartialWorkspaceInbound, nonce: str) -> None:
        self.inbound = inbound
        self.nonce = nonce

    def respond(self, method: str, target: str, raw: bytes, correlation: str) -> tuple[int, str, bytes, str]:
        try:
            match = _ROUTE.fullmatch(target)
            if not match:
                raise ValueError("PARTIAL_ROUTE_REJECTED")
            operation, kind = match.groups()
            operation = operation or "open"
            if ((operation in {"preview", "word"}) != (kind is not None)
                    or method != ("POST" if operation == "save" else "GET")):
                raise ValueError("PARTIAL_ROUTE_REJECTED")
            source = None
            projection = None
            if operation == "save":
                def pairs(entries: list[tuple[str, object]]) -> dict[str, object]:
                    if len(dict(entries)) != len(entries):
                        raise ValueError("PARTIAL_REQUEST_REJECTED")
                    return dict(entries)
                body = json.loads(raw, object_pairs_hook=pairs)
                if (type(body) is not dict or set(body) != {"source_sha256", "projection_sha256"}
                        or any(type(body[key]) is not str for key in body)):
                    raise ValueError("PARTIAL_REQUEST_REJECTED")
                source = body["source_sha256"]
                projection = body["projection_sha256"]
            elif raw:
                raise ValueError("PARTIAL_REQUEST_REJECTED")
            result = self.inbound.execute(operation, kind=kind or "student", source_sha256=source,
                expected_projection_sha256=projection)
            if isinstance(result, bytes):
                return 200, "application/vnd.openxmlformats-officedocument.wordprocessingml.document", result, ROOT + "/word/{kind}"
            if operation == "open":
                result = {**result, "transport_nonce": self.nonce}
            return self.json(200, {"data": result}, correlation, operation)
        except (ValueError, KeyError, TypeError):
            return self.json(409, {"error": {"code": "PARTIAL_REFUSED"}}, correlation)
        except Exception:
            return self.json(500, {"error": {"code": "PARTIAL_UNAVAILABLE"}}, correlation)

    @staticmethod
    def json(status: int, value: dict[str, object], correlation: str, operation: str = "refused"
             ) -> tuple[int, str, bytes, str]:
        return status, "application/json; charset=utf-8", json.dumps({**value,
            "meta": {"contract_id": CONTRACT, "correlation_id": correlation}},
            ensure_ascii=False, allow_nan=False).encode(), ROOT + "/" + operation
