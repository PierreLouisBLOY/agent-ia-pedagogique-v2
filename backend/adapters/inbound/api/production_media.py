"""One local companion endpoint; it accepts no arbitrary asset or storage target."""
import json
import re
from collections.abc import Callable, Mapping

from backend.adapters.inbound.api.routes import P0_MEDIA_ROUTE_SPECS

MEDIA_HTTP_CONTRACT = "P0-LOCAL-MEDIA-HTTP-1.0"
MEDIA_ROUTE = P0_MEDIA_ROUTE_SPECS[0][1]


class ProductionMediaEndpoint:
    def __init__(self, execute: Callable[[Mapping[str, object]], dict[str, object]]) -> None:
        self.execute = execute

    def respond(self, method: str, target: str, raw: bytes, correlation: str) -> tuple[int, str, bytes, str]:
        status = 200
        try:
            if method != "POST" or target != MEDIA_ROUTE:
                raise ValueError("P0_MEDIA_ROUTE_REJECTED")
            if len(raw) > 80 * 1024:
                raise ValueError("P0_MEDIA_REQUEST_SIZE")

            def pairs(rows: list[tuple[str, object]]) -> dict[str, object]:
                if len(dict(rows)) != len(rows):
                    raise ValueError("P0_MEDIA_DUPLICATE_KEY")
                return dict(rows)

            data = json.loads(raw, object_pairs_hook=pairs)
            if not isinstance(data, dict):
                raise ValueError("P0_MEDIA_REQUEST_REJECTED")
            envelope: dict[str, object] = {"data": self.execute(data)}
        except (ValueError, TypeError) as exc:
            status = 409
            code = str(exc)
            if re.fullmatch(r"(?:P0|PRODUCTION_MEDIA)_[A-Z0-9_]{1,80}", code) is None:
                code = "P0_MEDIA_REQUEST_REJECTED"
            envelope = {"error": {"code": code}}
        except Exception:
            status, envelope = 500, {"error": {"code": "P0_MEDIA_APPLICATION_FAILURE"}}
        envelope["meta"] = {"contract_id": MEDIA_HTTP_CONTRACT, "correlation_id": correlation}
        return status, "application/json; charset=utf-8", json.dumps(envelope, ensure_ascii=False,
            allow_nan=False).encode("utf-8"), MEDIA_ROUTE
