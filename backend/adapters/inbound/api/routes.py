"""Closed READ15-HTTP-LOCAL-1.0 route registry (ADR-P12-069)."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Final
from urllib.parse import unquote_to_bytes

READ15_TEMPLATE: Final = "/api/v2/resources/{resource_ref}"
_RESOURCE_PREFIX: Final = "/api/v2/resources/"
ROUTE_SPECS: Final = (
    (("GET",), READ15_TEMPLATE, None),
    (("GET", "HEAD"), "/", "index.html"),
    (("GET", "HEAD"), "/assets/app.js", "app.js"),
    (("GET", "HEAD"), "/assets/styles.css", "styles.css"),
)
ASSET_NAMES: Final = frozenset({"index.html", "app.js", "styles.css"})
MAX_TARGET_BYTES: Final = 8 * 1_024
_BAD_ESCAPE = re.compile(r"%(?![0-9a-fA-F]{2})")


class RouteRejected(ValueError):
    def __init__(self, *, method: bool = False, missing: bool = False) -> None:
        self.status = 405 if method else 404 if missing else 400
        self.code = (
            "METHOD_REJECTED" if method else "ROUTE_NOT_FOUND" if missing
            else "READ15_REQUEST_REJECTED"
        )
        super().__init__(self.code)


@dataclass(frozen=True, slots=True)
class RouteMatch:
    template: str
    asset_name: str | None = None
    resource_ref: str | None = None


def resolve_route(method: str, target: str) -> RouteMatch:
    try:
        raw = target.encode("ascii")
    except (AttributeError, UnicodeEncodeError):
        raise RouteRejected() from None
    if (
        not raw or len(raw) > MAX_TARGET_BYTES or not target.startswith("/")
        or target.startswith("//") or "?" in target or "#" in target
        or "\\" in target or any(byte <= 32 or byte == 127 for byte in raw)
        or _BAD_ESCAPE.search(target) is not None
    ):
        raise RouteRejected()
    for methods, template, asset in ROUTE_SPECS:
        if asset is not None and target == template:
            if method not in methods:
                raise RouteRejected(method=True)
            return RouteMatch(template, asset_name=asset)
    if target.startswith(_RESOURCE_PREFIX):
        segment = target[len(_RESOURCE_PREFIX):]
        try:
            reference = unquote_to_bytes(segment).decode("ascii")
        except UnicodeDecodeError:
            raise RouteRejected() from None
        if not reference or any(char in reference for char in "/\\%?#"):
            raise RouteRejected()
        if method != "GET":
            raise RouteRejected(method=True)
        return RouteMatch(READ15_TEMPLATE, resource_ref=reference)
    raise RouteRejected(missing=True)
