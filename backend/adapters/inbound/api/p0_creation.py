"""Closed companion routes; the historical R2/R3/R4 registry stays versioned."""
import json
import re
from collections.abc import Callable

P0_HTTP_CONTRACT = "R6-P0-HTTP-LOCAL-1.0"
P0_ROUTES = (("GET", "/api/v2/p0"), *(('POST', '/api/v2/p0/' + operation)
    for operation in ("prepare", "generate", "revise", "validate")),
    ("GET", "/api/v2/p0/versions/{production_ref}/{version_ref}"),
    ("GET", "/api/v2/p0/versions/{production_ref}/{version_ref}/teacher"))
_VERSION = re.compile(r"/api/v2/p0/versions/(prod:[0-9a-f]{32})/(ver:[0-9a-f]{32})(/teacher)?")


def is_p0_target(target: str) -> bool:
    return target == "/api/v2/p0" or target.startswith("/api/v2/p0/")


class P0CreationEndpoint:
    def __init__(self, execute: Callable[..., dict[str, object]], read: Callable[..., dict[str, object]], metadata: list[dict[str, object]],
                 *, nonce: str) -> None:
        self.execute, self.read, self.metadata, self.nonce = execute, read, metadata, nonce

    def respond(self, method: str, target: str, raw: bytes, correlation: str) -> tuple[int, str, bytes, str]:
        status, template = 200, "/{unmatched}"
        result: dict[str, object]
        try:
            if method == "GET" and target == "/api/v2/p0":
                result = {"transport_nonce": self.nonce, "state": "READY", "references": self.metadata,
                          "live_binding": "NONE", "authority": "NONE"}
                template = target
            elif method == "POST" and (method, target) in P0_ROUTES:
                def pairs(entries: list[tuple[str, object]]) -> dict[str, object]:
                    if len(dict(entries)) != len(entries):
                        raise ValueError("P0_REQUEST_REJECTED")
                    return dict(entries)
                data = json.loads(raw, object_pairs_hook=pairs)
                if not isinstance(data, dict):
                    raise ValueError("P0_REQUEST_REJECTED")
                result = self.execute(target.rsplit("/", 1)[1], data)
                template = target
            elif method == "GET" and (match := _VERSION.fullmatch(target)):
                result = self.read(match[1], match[2], teacher=bool(match[3]))
                template = P0_ROUTES[-1 if match[3] else -2][1]
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
