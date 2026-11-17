"""Closed READ15 and SEARCH-HTTP-LOCAL-1.0 route registry."""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from typing import Final
from urllib.parse import unquote_to_bytes

READ15_TEMPLATE: Final = "/api/v2/resources/{resource_ref}"
SEARCH_TEMPLATE: Final = "/api/v2/search"
CONVERSATION_TEMPLATE: Final = "/api/v2/conversation"
CONVERSATION_MESSAGES_TEMPLATE: Final = "/api/v2/conversation/messages"
CONVERSATION_GENERATIONS_TEMPLATE: Final = "/api/v2/conversation/generations"
PRODUCTION_VERSION_TEMPLATE: Final = "/api/v2/productions/{production_ref}/versions/{version_ref}"
R3_PREPARATION_TEMPLATE: Final = "/api/v2/conversation/assessment-preparations"
R3_REVIEWS_TEMPLATE: Final = "/api/v2/conversation/reviews"
R3_REVIEW_TEMPLATE: Final = "/api/v2/conversation/reviews/{review_ref}"
R3_VALIDATIONS_TEMPLATE: Final = "/api/v2/conversation/validations"
R3_MODIFICATIONS_TEMPLATE: Final = "/api/v2/conversation/modifications"
R3_OPERATION_TEMPLATE: Final = "/api/v2/conversation/operations/{operation_ref}"
R3_ASSESSMENT_TEMPLATE: Final = "/api/v2/productions/{production_ref}/versions/{version_ref}/assessment"
R4_SAVED_TEMPLATE: Final = "/api/v2/conversation/saved"
R4_VERSION_TEMPLATE: Final = "/api/v2/productions/{production_ref}/versions/{version_ref}/saved"
R4_VALIDATE_TEMPLATE: Final = "/api/v2/productions/{production_ref}/versions/{version_ref}/saved-validation"
R4_PROMOTE_TEMPLATE: Final = "/api/v2/productions/{production_ref}/versions/{version_ref}/promotion"
R4_PREVIEW_TEMPLATE: Final = "/api/v2/productions/{production_ref}/versions/{version_ref}/preview/{document_kind}"
R4_WORD_TEMPLATE: Final = "/api/v2/productions/{production_ref}/versions/{version_ref}/word/{document_kind}"
R4_EDIT_TEMPLATE: Final = "/api/v2/productions/{production_ref}/versions/{version_ref}/saved-edit"
R4_COMPARE_TEMPLATE: Final = "/api/v2/productions/{production_ref}/versions/{version_ref}/compare/{document_kind}"
R4_LOCAL_EDIT_ROUTE_SPECS: Final = (("POST", R4_EDIT_TEMPLATE), ("GET", R4_COMPARE_TEMPLATE))
_PRODUCTION_PREFIX: Final = "/api/v2/productions/"
_RESOURCE_PREFIX: Final = "/api/v2/resources/"
ROUTE_SPECS: Final = (
    (("GET",), READ15_TEMPLATE, None),
    (("GET",), SEARCH_TEMPLATE, None),
    (("GET",), CONVERSATION_TEMPLATE, None),
    (("POST",), CONVERSATION_MESSAGES_TEMPLATE, None),
    (("POST",), CONVERSATION_GENERATIONS_TEMPLATE, None),
    (("GET",), PRODUCTION_VERSION_TEMPLATE, None),
    (("POST",), R3_PREPARATION_TEMPLATE, None),
    (("POST",), R3_REVIEWS_TEMPLATE, None),
    (("GET",), R3_REVIEW_TEMPLATE, None),
    (("POST",), R3_VALIDATIONS_TEMPLATE, None),
    (("POST",), R3_MODIFICATIONS_TEMPLATE, None),
    (("GET",), R3_OPERATION_TEMPLATE, None),
    (("GET",), R3_ASSESSMENT_TEMPLATE, None),
    (("GET", "HEAD"), "/", "index.html"),
    (("GET", "HEAD"), "/assets/app.js", "app.js"),
    (("GET", "HEAD"), "/assets/styles.css", "styles.css"),
    (("GET", "POST"), R4_SAVED_TEMPLATE, None),
    (("GET",), R4_VERSION_TEMPLATE, None),
    (("POST",), R4_VALIDATE_TEMPLATE, None),
    (("GET", "POST"), R4_PROMOTE_TEMPLATE, None),
    (("GET",), R4_PREVIEW_TEMPLATE, None),
    (("GET",), R4_WORD_TEMPLATE, None),
)
LOCAL_EDIT_ASSET_SPECS: Final = ((("GET", "HEAD"), "/assets/saved-course-edit.js", "saved-course-edit.js"),
    (("GET", "HEAD"), "/assets/normal-on.js", "normal-on.js"),
    (("GET", "HEAD"), "/assets/local-catalogue.js", "local-catalogue.js"),
    (("GET", "HEAD"), "/assets/real-course.js", "real-course.js"),
    (("GET", "HEAD"), "/assets/documentary-library.js", "documentary-library.js"))
ASSET_NAMES: Final = frozenset({"index.html", "app.js", "styles.css", "saved-course-edit.js", "normal-on.js", "local-catalogue.js", "real-course.js", "documentary-library.js"})
MAX_TARGET_BYTES: Final = 8 * 1_024
CAPTURED_PARTIAL_ROOT: Final = "/api/v2/captured-partial"
CAPTURED_PARTIAL_ROUTE_PATTERN: Final = re.compile(
    re.escape(CAPTURED_PARTIAL_ROOT)
    + r"(?:/(save|preview|word|inventory|reference)(?:/(student|correction))?)?"
)
# Versioned P0 companion, registered in this same closed local registry.
# ROUTE_SPECS retains the historical R2/R3/R4 contract and its literal oracle.
P0_ROOT: Final = "/api/v2/p0"
P0_ROUTE_SPECS: Final = (("GET", P0_ROOT),
    *(("POST", P0_ROOT + "/" + operation) for operation in ("prepare", "generate", "revise", "validate", "review", "correct")),
    ("GET", P0_ROOT + "/versions/{production_ref}/{version_ref}"),
    ("GET", P0_ROOT + "/versions/{production_ref}/{version_ref}/teacher"))
P0_INTENTION_ROUTE_SPECS: Final = (("POST", P0_ROOT + "/intention"),)
P0_LOCAL_PROPOSAL_ROUTE_SPECS: Final = (("POST", P0_ROOT + "/local-propose"),)
P0_MANUAL_TEST_ROUTE_SPECS: Final = (("POST", P0_ROOT + "/manual-stop"),)
P0_ORGANIZATION_CAPTURE_ROUTE_SPECS: Final = (("GET", P0_ROOT + "/organizations/{organization_id}"),)
P0_ORGANIZATION_SEARCH_ROUTE_SPECS: Final = (("POST", P0_ROOT + "/organization-search"),)
P0_CODESIGN_ROUTE_SPECS: Final = tuple(("POST", P0_ROOT + "/" + op) for op in ("codesign-preview", "codesign", "codesign-consent", "codesign-revoke"))
P0_MEDIA_ROUTE_SPECS: Final = (("POST", P0_ROOT + "/media"),)
P0_CONSENT_ROUTE_SPECS: Final = (("POST", P0_ROOT + "/consent-preview"), ("POST", P0_ROOT + "/consent-generate"))
P0_PILOT_PREVIEW_ROUTE_SPECS: Final = (("POST", P0_ROOT + "/pilot-preview"),
    ("GET", P0_ROOT + "/pilot-candidate"))
P0_PILOT_REVOCATION_ROUTE_SPECS: Final = (("POST", P0_ROOT + "/pilot-revoke"),)
P0_NOTION_EVIDENCE_TEMPLATE: Final = P0_ROOT + "/notion-evidence"
P0_NOTION_EVIDENCE_ROUTE_SPECS: Final = (("GET", P0_NOTION_EVIDENCE_TEMPLATE),)
_P0_VERSION = re.compile(P0_ROOT + r"/versions/(prod:[0-9a-f]{32})/(ver:[0-9a-f]{32})(/teacher)?")
P0_COMMAND_TEMPLATE: Final = P0_ROOT + "/commands/{command_id}"
P0_COMMAND_ROUTE_SPECS: Final = (("GET", P0_COMMAND_TEMPLATE),)
_P0_COMMAND = re.compile(P0_ROOT + r"/commands/([0-9a-f]{32})")


def is_p0_target(target: str) -> bool:
    return target == P0_ROOT or target.startswith(P0_ROOT + "/")


def resolve_p0_route(method: str, target: str) -> tuple[str, str, str, bool, str]:
    if method == "GET" and re.fullmatch(P0_ROOT + r"/documentary-library/[DO][0-9]{2}", target):
        return "documentary-read", target.rsplit("/", 1)[1], "", False, P0_ROOT + "/documentary-library/{document_id}"
    if (method, target) in P0_ORGANIZATION_SEARCH_ROUTE_SPECS:
        return "organization-search", "", "", False, target
    if method == "GET" and re.fullmatch(P0_ROOT + r"/organizations/(siren:[0-9]{9})", target):
        return "organization-capture", target.rsplit("/",1)[1], "", False, P0_ROOT+"/organizations/{organization_id}"

    if method == "GET" and (command := _P0_COMMAND.fullmatch(target)):
        return "command-followup", command[1], "", False, P0_COMMAND_TEMPLATE
    if target.partition("?")[0] == P0_NOTION_EVIDENCE_TEMPLATE:
        resolve_p0_notion_evidence(method, target)
        return "notion-evidence", "", "", False, P0_NOTION_EVIDENCE_TEMPLATE
    if method == "GET" and target == P0_ROOT:
        return "metadata", "", "", False, target
    if method == "GET" and target == P0_ROOT + "/pilot-candidate":
        return "pilot-candidate", "", "", False, target
    if method == "POST" and (method, target) in P0_ROUTE_SPECS + P0_INTENTION_ROUTE_SPECS + P0_LOCAL_PROPOSAL_ROUTE_SPECS + P0_MANUAL_TEST_ROUTE_SPECS + P0_MEDIA_ROUTE_SPECS + P0_CONSENT_ROUTE_SPECS + P0_PILOT_PREVIEW_ROUTE_SPECS + P0_PILOT_REVOCATION_ROUTE_SPECS + P0_CODESIGN_ROUTE_SPECS:
        return target.rsplit("/", 1)[1], "", "", False, target
    if method == "GET" and (match := _P0_VERSION.fullmatch(target)):
        return "version", match[1], match[2], bool(match[3]), P0_ROUTE_SPECS[-1 if match[3] else -2][1]
    raise ValueError("P0_ROUTE_REJECTED")


def resolve_p0_notion_evidence(method: str, target: str) -> str:
    """One exact canonical notion ID; no aliases, paths, SQL or arbitrary selectors."""
    try:
        raw = target.encode("ascii")
        path, separator, query = target.partition("?")
        key, equals, value = query.partition("=")
        if (method != "GET" or path != P0_NOTION_EVIDENCE_TEMPLATE or separator != "?"
                or key != "notion_id" or equals != "=" or not value or "&" in query
                or not raw or len(raw) > MAX_TARGET_BYTES or "#" in target or "\\" in target
                or any(byte <= 32 or byte == 127 for byte in raw) or _BAD_ESCAPE.search(target)):
            raise ValueError
        notion_id = unquote_to_bytes(value).decode("utf-8")
        if type(notion_id) is not str or not 1 <= len(notion_id) <= 256 or any(
                unicodedata.category(char)[0] not in {"L", "N"} and char not in "._:-" for char in notion_id):
            raise ValueError
        if not notion_id.startswith("notion:") or len(notion_id) <= len("notion:"):
            raise ValueError
        return notion_id
    except (ValueError, AttributeError, TypeError):
        raise ValueError("P0_REFERENCE_REQUEST_REJECTED") from None


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
    operation_ref: str | None = None
    review_ref: str | None = None
    r4_operation: str | None = None
    document_kind: str | None = None


def is_conversation_target(target: str) -> bool:
    path = target.partition("?")[0]
    return path in {CONVERSATION_TEMPLATE, CONVERSATION_MESSAGES_TEMPLATE,
                    CONVERSATION_GENERATIONS_TEMPLATE} or path.startswith(_PRODUCTION_PREFIX) or path.startswith(CONVERSATION_TEMPLATE + "/")


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
        if path == R4_SAVED_TEMPLATE:
            if method not in {"GET", "POST"}:
                raise RouteRejected(method=True, conversation=True)
            return RouteMatch(R4_SAVED_TEMPLATE, r4_operation="list" if method == "GET" else "save")
        if path.startswith(_PRODUCTION_PREFIX):
            if re.search(r"%(?:2f|5c|25)", path, re.IGNORECASE):
                raise RouteRejected(conversation=True)
            try:
                segments = unquote_to_bytes(path[len(_PRODUCTION_PREFIX):]).decode("ascii").split("/")
            except UnicodeDecodeError:
                raise RouteRejected(conversation=True) from None
            if (len(segments) in {4, 5} and segments[1] == "versions"
                    and re.fullmatch(r"prod:[0-9a-f]{32}", segments[0])
                    and re.fullmatch(r"ver:[0-9a-f]{32}", segments[2])):
                operations = {"saved": (R4_VERSION_TEMPLATE, "open", {"GET"}),
                    "saved-validation": (R4_VALIDATE_TEMPLATE, "validate", {"POST"}),
                    "promotion": (R4_PROMOTE_TEMPLATE, "gate" if method == "GET" else "promote", {"GET", "POST"}),
                    "preview": (R4_PREVIEW_TEMPLATE, "preview", {"GET"}),
                    "word": (R4_WORD_TEMPLATE, "word", {"GET"}),
                    "saved-edit": (R4_EDIT_TEMPLATE, "edit", {"POST"}),
                    "compare": (R4_COMPARE_TEMPLATE, "compare", {"GET"})}
                selected = operations.get(segments[3])
                if selected is not None:
                    template, operation, r4_methods = selected
                    export = operation in {"preview", "word", "compare"}
                    if (export and (len(segments) != 5 or segments[-1] not in {"student", "correction", "marking"})) or (not export and len(segments) != 4):
                        raise RouteRejected(conversation=True)
                    if method not in r4_methods:
                        raise RouteRejected(method=True, conversation=True)
                    return RouteMatch(template, production_ref=segments[0], version_ref=segments[2],
                        r4_operation=operation, document_kind=segments[-1] if export else None)
            assessment = len(segments) == 4 and segments[-1] == "assessment"
            if ((len(segments) != 3 and not assessment) or segments[1] != "versions"
                    or re.fullmatch(r"prod:[0-9a-f]{32}", segments[0]) is None
                    or re.fullmatch(r"ver:[0-9a-f]{32}", segments[2]) is None):
                raise RouteRejected(conversation=True)
            if method != "GET":
                raise RouteRejected(method=True, conversation=True)
            return RouteMatch(R3_ASSESSMENT_TEMPLATE if assessment else PRODUCTION_VERSION_TEMPLATE, production_ref=segments[0],
                              version_ref=segments[2])
        for template, prefix, field in ((R3_REVIEW_TEMPLATE, R3_REVIEWS_TEMPLATE + "/", "review"),
                                       (R3_OPERATION_TEMPLATE, CONVERSATION_TEMPLATE + "/operations/", "op")):
            if path.startswith(prefix):
                reference = path[len(prefix):]
                if re.fullmatch(field + r":[0-9a-f]{32}", reference) is None:
                    raise RouteRejected(conversation=True)
                if method != "GET":
                    raise RouteRejected(method=True, conversation=True)
                return RouteMatch(template, review_ref=reference if field == "review" else None,
                                  operation_ref=reference if field == "op" else None)
        if path not in {CONVERSATION_TEMPLATE, CONVERSATION_MESSAGES_TEMPLATE,
                        CONVERSATION_GENERATIONS_TEMPLATE, R3_PREPARATION_TEMPLATE,
                        R3_REVIEWS_TEMPLATE, R3_VALIDATIONS_TEMPLATE, R3_MODIFICATIONS_TEMPLATE}:
            raise RouteRejected(missing=True, conversation=True)
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
    for methods, template, asset in ROUTE_SPECS + LOCAL_EDIT_ASSET_SPECS:
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
