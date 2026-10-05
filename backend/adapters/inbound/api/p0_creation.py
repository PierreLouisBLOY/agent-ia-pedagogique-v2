"""Closed companion routes; the historical R2/R3/R4 registry stays versioned."""
import json
import re
from collections.abc import Callable

from backend.adapters.inbound.api.routes import resolve_p0_route

P0_HTTP_CONTRACT = "R6-P0-HTTP-LOCAL-1.0"


class P0CreationEndpoint:
    def __init__(self, execute: Callable[..., dict[str, object]], read: Callable[..., dict[str, object]], metadata: list[dict[str, object]],
                 *, nonce: str, generation_bound: bool = False, review_bound: bool = False,
                 institutional_catalog: Callable[[], dict[str, object]] | None = None) -> None:
        self.execute, self.read, self.metadata, self.nonce = execute, read, metadata, nonce
        self.generation_bound, self.review_bound = generation_bound, review_bound
        self.institutional_catalog = institutional_catalog

    def respond(self, method: str, target: str, raw: bytes, correlation: str) -> tuple[int, str, bytes, str]:
        status, template = 200, "/{unmatched}"
        result: dict[str, object]
        try:
            operation, production, version, teacher, template = resolve_p0_route(method, target)
            if operation == "metadata":
                result = {"transport_nonce": self.nonce, "state": "READY", "references": self.metadata,
                          "live_binding": "EXPLICIT_PORT" if self.generation_bound else "NONE",
                          "review_binding": "EXPLICIT_PORT" if self.review_bound else "NONE", "authority": "NONE"}
                if self.institutional_catalog is not None:
                    result["institutional_catalog"] = self.institutional_catalog()
            elif method == "POST":
                def pairs(entries: list[tuple[str, object]]) -> dict[str, object]:
                    if len(dict(entries)) != len(entries):
                        raise ValueError("P0_REQUEST_REJECTED")
                    return dict(entries)
                data = json.loads(raw, object_pairs_hook=pairs)
                if not isinstance(data, dict):
                    raise ValueError("P0_REQUEST_REJECTED")
                result = self.execute(operation, data)
            elif operation == "version":
                result = self.read(production, version, teacher=teacher)
            else:
                raise ValueError("P0_ROUTE_REJECTED")
            envelope = {"data": result}
        except (ValueError, TypeError) as error:
            status = 409
            code = str(error)
            # Only bounded symbolic codes can leave the Application boundary.
            if re.fullmatch(r"(?:P0|R6)_[A-Z0-9_]{1,80}", code) is None:
                code = "P0_REQUEST_REJECTED"
            envelope = {"error": {"code": code}}
        except Exception:
            status, envelope = 500, {"error": {"code": "P0_APPLICATION_FAILURE"}}
        envelope["meta"] = {"contract_id": P0_HTTP_CONTRACT, "correlation_id": correlation}
        return status, "application/json; charset=utf-8", json.dumps(envelope, ensure_ascii=False,
            allow_nan=False).encode("utf-8"), template
