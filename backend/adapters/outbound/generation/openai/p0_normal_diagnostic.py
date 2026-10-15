"""Closed private failure evidence for one normal CREATE; no exception text or authority."""
from collections.abc import Mapping
from enum import StrEnum

from backend.adapters.outbound.generation.openai.p0_normal_policy import closed, digest, utc
from backend.adapters.outbound.openai.contracts import (
    OpenAITransportError,
    OpenAITransportErrorCode,
)
from backend.infrastructure.filesystem import LocalFileSecurityCode, LocalFileSecurityError

MAX_FAILURE_DIAGNOSTIC_BYTES = 8192


class FailureStage(StrEnum):
    CREDENTIAL_RESOLVE = "CREDENTIAL_RESOLVE"
    IDENTITY_RECHECK = "IDENTITY_RECHECK"
    TRANSPORT_BUILD = "TRANSPORT_BUILD"
    PREFLIGHT_RECHECK = "PREFLIGHT_RECHECK"
    ATTEMPT_PUBLISH = "ATTEMPT_PUBLISH"
    TRANSPORT_CREATE = "TRANSPORT_CREATE"
    RESPONSE_METADATA = "RESPONSE_METADATA"
    RESULT_PUBLISH = "RESULT_PUBLISH"
    RESPONSE_CAPTURE_PUBLISH = "RESPONSE_CAPTURE_PUBLISH"
    RESPONSE_VALIDATE = "RESPONSE_VALIDATE"
    CAPTURE_CONFIRM = "CAPTURE_CONFIRM"
    CONTENT_PARSE = "CONTENT_PARSE"
    GUARD_AND_BIND = "GUARD_AND_BIND"
    PARSED_PUBLISH = "PARSED_PUBLISH"
    CONSUMED_PUBLISH = "CONSUMED_PUBLISH"


# Exact existing local codes only. Arbitrary ValueError messages never enter evidence.
LOCAL_CODES = frozenset({
    "P0_NORMAL_PREFLIGHT_CHANGED", "P0_NORMAL_RESPONSE_REJECTED",
    "P0_NORMAL_INTRINSIC_BINDING", "P0_NORMAL_RECEIPT_ROOT_BINDING",
    "P0_RICH_COURSE_NOTION_UNKNOWN", "P0_RECEIPT_SIZE", "P0_RECEIPT_ALREADY_USED",
    "P0_RECOVERY_OUTCOME_UNKNOWN",
})


def failure_code(error: Exception) -> tuple[str | None, str | int | None]:
    if isinstance(error, OpenAITransportError) and type(error.code) is OpenAITransportErrorCode:
        return "OPENAI_TRANSPORT", error.code.value
    if isinstance(error, LocalFileSecurityError) and type(error.code) is LocalFileSecurityCode:
        return "LOCAL_FILESYSTEM", error.code.value
    if isinstance(error, OSError) and type(error.errno) is int and 0 <= error.errno < 2**31:
        return "OS_ERRNO", error.errno
    if (type(error) is ValueError and len(error.args) == 1
            and type(error.args[0]) is str and error.args[0] in LOCAL_CODES):
        return "LOCAL_POLICY", error.args[0]
    return None, None


def validate_failure_document(value: Mapping[str, object], *, namespace: str) -> None:
    closed(value, {"schema", "timestamp_utc", "namespace_sha256", "grant_sha256",
                   "request_sha256", "preflight_sha256", "provider_attempts", "stage",
                   "code_source", "technical_code", "outcome_marker", "marker_recorded"},
           "P0_FAILURE_DIAGNOSTIC_FIELDS")
    if (value["schema"] != "P0-NORMAL-FAILURE-DIAGNOSTIC-1.0"
            or value["namespace_sha256"] != namespace
            or any(not digest(value[key]) for key in
                   ("namespace_sha256", "grant_sha256", "request_sha256", "preflight_sha256"))
            or type(value["stage"]) is not str or value["stage"] not in {s.value for s in FailureStage}
            or type(value["provider_attempts"]) is not int or value["provider_attempts"] not in (0, 1)
            or value["outcome_marker"] not in ("UNKNOWN", "PARSING_REJECTED", "UNCONFIRMED")
            or type(value["marker_recorded"]) is not bool
            or (value["outcome_marker"] == "UNCONFIRMED" and value["marker_recorded"] is not False)):
        raise ValueError("P0_FAILURE_DIAGNOSTIC_BINDING")
    utc(value["timestamp_utc"])
    stage = value["stage"]
    before_transport = {s.value for s in (
        FailureStage.CREDENTIAL_RESOLVE, FailureStage.IDENTITY_RECHECK,
        FailureStage.TRANSPORT_BUILD, FailureStage.PREFLIGHT_RECHECK, FailureStage.ATTEMPT_PUBLISH,
    )}
    before_capture = before_transport | {s.value for s in (
        FailureStage.TRANSPORT_CREATE, FailureStage.RESPONSE_METADATA,
        FailureStage.RESULT_PUBLISH, FailureStage.RESPONSE_CAPTURE_PUBLISH,
    )}
    terminal = {FailureStage.PARSED_PUBLISH.value, FailureStage.CONSUMED_PUBLISH.value}
    marker = "UNKNOWN" if stage in before_capture else (
        "UNCONFIRMED" if stage in terminal else "PARSING_REJECTED"
    )
    if (value["outcome_marker"] != marker
            or value["provider_attempts"] != (0 if stage in before_transport else 1)):
        raise ValueError("P0_FAILURE_DIAGNOSTIC_STAGE")
    source, code = value["code_source"], value["technical_code"]
    allowed = {
        "OPENAI_TRANSPORT": {c.value for c in OpenAITransportErrorCode},
        "LOCAL_FILESYSTEM": {c.value for c in LocalFileSecurityCode},
        "LOCAL_POLICY": LOCAL_CODES,
    }
    if source is None and code is None:
        return
    if source == "OS_ERRNO" and type(code) is int and 0 <= code < 2**31:
        return
    if type(source) is str and source in allowed and type(code) is str and code in allowed[source]:
        return
    raise ValueError("P0_FAILURE_DIAGNOSTIC_CODE")
