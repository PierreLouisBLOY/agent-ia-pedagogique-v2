"""Closed companion routes; the historical R2/R3/R4 registry stays versioned."""
import json
import re
from collections.abc import Callable, Mapping

from backend.adapters.inbound.api.p0_notion_evidence import P0NotionEvidenceEndpoint
from backend.adapters.inbound.api.production_media import ProductionMediaEndpoint
from backend.adapters.inbound.api.routes import P0_NOTION_EVIDENCE_TEMPLATE, resolve_p0_route
from backend.modules.work_orchestration.application.queries.propose_p0_intention import (
    ProposeP0Intention,
)

P0_HTTP_CONTRACT = "R6-P0-HTTP-LOCAL-1.0"


class P0CreationEndpoint:
    def __init__(self, execute: Callable[..., dict[str, object]], read: Callable[..., dict[str, object]], metadata: list[dict[str, object]],
                 *, nonce: str, generation_bound: bool = False, review_bound: bool = False,
                 institutional_catalog: Callable[[], dict[str, object]] | None = None,
                 media_endpoint: ProductionMediaEndpoint | None = None,
                 consent_execute: Callable[[str, Mapping[str, object]], dict[str, object]] | None = None,
                 exact_notion_reader: Callable[[str], Mapping[str, object]] | None = None,
                 local_reference_contexts: Callable[[], list[dict[str, object]]] | None = None) -> None:
        self.execute, self.read, self.metadata, self.nonce = execute, read, metadata, nonce
        self.generation_bound, self.review_bound = generation_bound, review_bound
        self.institutional_catalog = institutional_catalog
        self.media_endpoint = media_endpoint
        self.consent_execute = consent_execute
        self.exact_notion_reader = exact_notion_reader
        self.local_reference_contexts = local_reference_contexts

    def respond(self, method: str, target: str, raw: bytes, correlation: str) -> tuple[int, str, bytes, str]:
        status, template = 200, "/{unmatched}"
        result: dict[str, object]
        try:
            if target.partition("?")[0] == P0_NOTION_EVIDENCE_TEMPLATE:
                if self.exact_notion_reader is None:
                    raise ValueError("P0_REFERENCE_NOT_ENABLED")
                return P0NotionEvidenceEndpoint(self.exact_notion_reader).respond(method, target, raw, correlation)
            operation, production, version, teacher, template = resolve_p0_route(method, target)
            if operation == "metadata":
                result = {"transport_nonce": self.nonce, "state": "READY", "references": self.metadata,
                          "live_binding": "EXPLICIT_PORT" if self.generation_bound else "NONE",
                          "review_binding": "EXPLICIT_PORT" if self.review_bound else "NONE", "authority": "NONE"}
                result["media_binding"] = "LOCAL_DIAGRAM_OR_NO_MEDIA" if self.media_endpoint is not None else "NONE"
                result["normal_consent_binding"] = "EXPLICIT_PRODUCT_PERMISSION" if self.consent_execute is not None else "NONE"
                if self.institutional_catalog is not None:
                    result["institutional_catalog"] = self.institutional_catalog()
                result["local_reference_contexts"] = [] if self.local_reference_contexts is None else self.local_reference_contexts()
                result["local_reference_context_binding"] = "NONE" if self.local_reference_contexts is None else "EXPLICIT_OWNER_LOCAL_CONTEXT"
            elif operation == "media":
                if self.media_endpoint is None:
                    raise ValueError("P0_MEDIA_NOT_ENABLED")
                return self.media_endpoint.respond(method, target, raw, correlation)
            elif method == "POST":
                def pairs(entries: list[tuple[str, object]]) -> dict[str, object]:
                    if len(dict(entries)) != len(entries):
                        raise ValueError("P0_REQUEST_REJECTED")
                    return dict(entries)
                data = json.loads(raw, object_pairs_hook=pairs,
                    parse_constant=lambda _: (_ for _ in ()).throw(ValueError("P0_REQUEST_REJECTED")))
                if not isinstance(data, dict):
                    raise ValueError("P0_REQUEST_REJECTED")
                if operation in {"consent-preview", "consent-generate"}:
                    if self.consent_execute is None:
                        raise ValueError("P0_PRODUCT_PERMISSION_REQUIRED")
                    result = self.consent_execute(operation.replace("-", "_"), data)
                else:
                    result = ProposeP0Intention().execute(data) if operation == "intention" else self.execute(operation, data)
            elif operation == "version":
                result = self.read(production, version, teacher=teacher)
            else:
                raise ValueError("P0_ROUTE_REJECTED")
            envelope = {"data": result}
        except (ValueError, TypeError) as error:
            status = 409
            code = str(error)
            # Only bounded symbolic codes can leave the Application boundary.
            if re.fullmatch(r"(?:P0|R6|COURSE|PRODUCTION_MEDIA)_[A-Z0-9_]{1,80}", code) is None:
                code = "P0_REQUEST_REJECTED"
            envelope = {"error": {"code": code}}
        except Exception:
            status, envelope = 500, {"error": {"code": "P0_APPLICATION_FAILURE"}}
        envelope["meta"] = {"contract_id": P0_HTTP_CONTRACT, "correlation_id": correlation}
        return status, "application/json; charset=utf-8", json.dumps(envelope, ensure_ascii=False,
            allow_nan=False).encode("utf-8"), template
