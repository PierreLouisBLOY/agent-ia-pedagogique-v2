"""Closed READ15 and SEARCH-HTTP-LOCAL-1.0 route registry."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Final
from urllib.parse import unquote_to_bytes

READ15_TEMPLATE: Final = "/api/v2/resources/{resource_ref}"
SEARCH_TEMPLATE: Final = "/api/v2/search"
CONVERSATION_TEMPLATE: Final = "/api/v2/conversation"
CONVERSATION_MESSAGES_TEMPLATE: Final = "/api/v2/conversation/messages"
CONVERSATION_GENERATIONS_TEMPLATE: Final = "/api/v2/conversation/generations"
PRODUCTION_VERSION_TEMPLATE: Final = "/api/v2/productions/{production_ref}/versions/{version_ref}"
_PRODUCTION_PREFIX: Final = "/api/v2/productions/"
_RESOURCE_PREFIX: Final = "/api/v2/resources/"
ROUTE_SPECS: Final = (
    (("GET",), READ15_TEMPLATE, None),
    (("GET",), SEARCH_TEMPLATE, None),
    (("GET",), CONVERSATION_TEMPLATE, None),
    (("POST",), CONVERSATION_MESSAGES_TEMPLATE, None),
    (("POST",), CONVERSATION_GENERATIONS_TEMPLATE, None),
    (("GET",), PRODUCTION_VERSION_TEMPLATE, None),
    (("GET", "HEAD"), "/", "index.html"),
    (("GET", "HEAD"), "/assets/app.js", "app.js"),
    (("GET", "HEAD"), "/assets/styles.css", "styles.css"),
)
ASSET_NAMES: Final = frozenset({"index.html", "app.js", "styles.css"})
MAX_TARGET_BYTES: Final = 8 * 1_024
_BAD_ESCAPE = re.compile(r"%(?![0-9a-fA-F]{2})")


class RouteRejected(ValueError):
    def __init__(
        self, *, method: bool = False, missing: bool = False, search: bool = False,
        conversation: bool = False,
    ) -> None:
        self.status = 405 if method else 404 if missing else 400
        self.code = (
            ("METHOD_NOT_ALLOWED" if method else "PRODUCTION_NOT_FOUND" if missing
             else "VALIDATION_REJECTED") if conversation else
            "METHOD_REJECTED" if method else "ROUTE_NOT_FOUND" if missing
            else "SEARCH_REQUEST_REJECTED" if search else "READ15_REQUEST_REJECTED"
        )
        super().__init__(self.code)


@dataclass(frozen=True, slots=True)
class RouteMatch:
    template: str
    asset_name: str | None = None
    resource_ref: str | None = None
    search_text: str | None = None
    search_limit: int | None = None
    production_ref: str | None = None
    version_ref: str | None = None


def is_conversation_target(target: str) -> bool:
    path = target.partition("?")[0]
    return path in {CONVERSATION_TEMPLATE, CONVERSATION_MESSAGES_TEMPLATE,
                    CONVERSATION_GENERATIONS_TEMPLATE} or path.startswith(_PRODUCTION_PREFIX)


def _search_match(query: str) -> RouteMatch:
    parameters: dict[str, str] = {}
    for pair in query.split("&"):
        key, separator, raw_value = pair.partition("=")
        if not separator or key not in {"q", "limit"} or key in parameters:
            raise RouteRejected(search=True)
        try:
            value = unquote_to_bytes(raw_value.replace("+", " ")).decode("utf-8")
        except UnicodeDecodeError:
            raise RouteRejected(search=True) from None
        if re.search(r"%[0-9a-fA-F]{2}", value):
            raise RouteRejected(search=True)
        parameters[key] = value
    if "q" not in parameters:
        raise RouteRejected(search=True)
    limit = parameters.get("limit", "10")
    if re.fullmatch(r"(?:[1-9]|1[0-9]|20)", limit) is None:
        raise RouteRejected(search=True)
    return RouteMatch(SEARCH_TEMPLATE, search_text=parameters["q"], search_limit=int(limit))


def resolve_route(method: str, target: str) -> RouteMatch:
    try:
        raw = target.encode("ascii")
    except (AttributeError, UnicodeEncodeError):
        raise RouteRejected() from None
    if (
        not raw or len(raw) > MAX_TARGET_BYTES or not target.startswith("/")
        or target.startswith("//") or "#" in target
        or "\\" in target or any(byte <= 32 or byte == 127 for byte in raw)
        or _BAD_ESCAPE.search(target) is not None
    ):
        raise RouteRejected()
    path, _, query = target.partition("?")
    if is_conversation_target(target):
        if "?" in target:
            raise RouteRejected(conversation=True)
        if path.startswith(_PRODUCTION_PREFIX):
            if re.search(r"%(?:2f|5c|25)", path, re.IGNORECASE):
                raise RouteRejected(conversation=True)
            try:
                segments = unquote_to_bytes(path[len(_PRODUCTION_PREFIX):]).decode("ascii").split("/")
            except UnicodeDecodeError:
                raise RouteRejected(conversation=True) from None
            if (len(segments) != 3 or segments[1] != "versions"
                    or re.fullmatch(r"prod:[0-9a-f]{32}", segments[0]) is None
                    or re.fullmatch(r"ver:[0-9a-f]{32}", segments[2]) is None):
                raise RouteRejected(conversation=True)
            if method != "GET":
                raise RouteRejected(method=True, conversation=True)
            return RouteMatch(PRODUCTION_VERSION_TEMPLATE, production_ref=segments[0],
                              version_ref=segments[2])
        expected = "GET" if path == CONVERSATION_TEMPLATE else "POST"
        if method != expected:
            raise RouteRejected(method=True, conversation=True)
        return RouteMatch(path)
    if path == SEARCH_TEMPLATE:
        if method != "GET":
            raise RouteRejected(method=True)
        return _search_match(query)
    if "?" in target:
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
