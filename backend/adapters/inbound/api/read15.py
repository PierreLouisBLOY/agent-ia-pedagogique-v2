"""Minimized HTTP projection of the existing Application inbound result."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass

from backend.agent_runtime.contracts import UseCaseResult

_FIELDS = frozenset({"resource_ref", "resource_type", "canonical_title", "availability_status"})
_ERROR_MAP = {
    "READ15_REQUEST_REJECTED": (400, "validation"),
    "RES_NOT_FOUND": (404, "business"),
    "ROUTE_NOT_FOUND": (404, "transport"),
    "METHOD_REJECTED": (405, "transport"),
    "HOST_REJECTED": (403, "security"),
    "ORIGIN_REJECTED": (403, "security"),
    "PREFLIGHT_REJECTED": (403, "security"),
    "INTERNAL_ERROR": (500, "technical"),
}


class Read15ValidationRejected(ValueError):
    """The Application-owned reference validator rejected the request."""


@dataclass(frozen=True, slots=True)
class HttpProjection:
    status: int
    payload: Mapping[str, object]


def public_error(code: str, correlation_id: str) -> HttpProjection:
    if code not in _ERROR_MAP:
        code = "INTERNAL_ERROR"
    status, category = _ERROR_MAP[code]
    return HttpProjection(
        status,
        {"error": {"category": category, "code": code},
         "meta": {"correlation_id": correlation_id}},
    )


class Read15Endpoint:
    """Invoke only the injected Application bridge, never a store or a database."""

    def __init__(
        self, invoke: Callable[[str, str], UseCaseResult[object, object]]
    ) -> None:
        self._invoke = invoke

    def get(self, resource_ref: str, correlation_id: str) -> HttpProjection:
        try:
            result = self._invoke(resource_ref, correlation_id)
        except Read15ValidationRejected:
            return public_error("READ15_REQUEST_REJECTED", correlation_id)
        except Exception:
            return public_error("INTERNAL_ERROR", correlation_id)
        outcome = result.outcome
        if (
            result.use_case_id != "application.read_canonical_resource"
            or outcome.correlation_id.value != correlation_id
            or result.meta.correlation_id.value != correlation_id
            or outcome.side_effects
        ):
            return public_error("INTERNAL_ERROR", correlation_id)
        if outcome.application_failure is not None:
            return public_error("INTERNAL_ERROR", correlation_id)
        if outcome.success:
            data = outcome.data
            if (
                outcome.business_errors or outcome.validation_result is not None
                or not isinstance(data, Mapping) or set(data) != _FIELDS
                or any(type(value) is not str or not value for value in data.values())
                or data["resource_ref"] != resource_ref
            ):
                return public_error("INTERNAL_ERROR", correlation_id)
            return HttpProjection(
                200, {"data": dict(data), "meta": {"correlation_id": correlation_id}}
            )
        if outcome.business_errors:
            code = (
                "RES_NOT_FOUND"
                if all(error.code.value == "RES_NOT_FOUND" for error in outcome.business_errors)
                else "INTERNAL_ERROR"
            )
            return public_error(code, correlation_id)
        if outcome.validation_result is not None:
            return public_error("READ15_REQUEST_REJECTED", correlation_id)
        return public_error("INTERNAL_ERROR", correlation_id)
