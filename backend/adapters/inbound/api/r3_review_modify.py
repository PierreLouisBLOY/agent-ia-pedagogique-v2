"""R3 transport only. Routes are declared exclusively in the route registry."""
import json
from collections.abc import Callable

from backend.adapters.inbound.api.conversation import parse_command
from backend.adapters.inbound.application.r3_review_modify import R3ApplicationInbound

CONTRACT = "REVIEW-MODIFY-HTTP-LOCAL-1.0"
ERRORS = {
    **dict.fromkeys(("VALIDATION_REJECTED", "ASSESSMENT_SCHEMA", "ASSESSMENT_FIELDS",
                    "ASSESSMENT_REFERENCE", "REQUEST_FRAMING_REJECTED"), 400),
    "R3_NOT_AUTHORIZED": 403, "R3_NOT_ENABLED": 404,
    **dict.fromkeys(("PRODUCTION_VERSION_NOT_FOUND", "REPORT_NOT_FOUND", "CONVERSATION_NOT_FOUND"), 404),
    **dict.fromkeys(("REVISION_CONFLICT", "IDEMPOTENCY_CONFLICT", "GENERATION_IN_PROGRESS",
                    "ASSESSMENT_ALREADY_PRESENT", "SESSION_CAPACITY_REACHED", "CONTEXT_NOT_CONFIRMED"), 409),
    "CONVERSATION_EXPIRED": 410, "REQUEST_TOO_LARGE": 413,
    **dict.fromkeys(("ASSESSMENT_BUNDLE_MISSING", "ASSESSMENT_VALIDATION_FAILED",
                    "CONTEXT_CLARIFICATION_REQUIRED"), 422),
    "JOB_UNAVAILABLE": 503, "PROVIDER_UNAVAILABLE": 503, "APPLICATION_FAILURE": 500,
}


def response(data: object, correlation: str, status: int = 200) -> tuple[int, bytes]:
    raw = json.dumps({"data": data, "meta": {"contract_id": CONTRACT,
        "correlation_id": correlation}}, ensure_ascii=False, allow_nan=False).encode()
    if len(raw) > 256 * 1024:
        raise ValueError("REQUEST_TOO_LARGE")
    return status, raw


def error(code: str, correlation: str) -> tuple[int, bytes]:
    code = code if code in ERRORS else "APPLICATION_FAILURE"
    return ERRORS[code], json.dumps({"error": {"code": code},
        "meta": {"contract_id": CONTRACT, "correlation_id": correlation}}).encode()


class R3Endpoint:
    def __init__(self, application: R3ApplicationInbound) -> None:
        self._application = application

    def _call(self, operation: Callable[[], object], correlation: str, status: int = 200) -> tuple[int, bytes]:
        try:
            return response(operation(), correlation, status)
        except ValueError as exc:
            return error(str(exc) if str(exc) in ERRORS else "VALIDATION_REJECTED", correlation)
        except Exception:
            return error("APPLICATION_FAILURE", correlation)

    def post(self, operation: str, raw: bytes, correlation: str) -> tuple[int, bytes]:
        return self._call(lambda: self._application.command(operation, parse_command(raw)), correlation,
                          200 if operation == "validations" else 202)

    def assessment(self, production: str, version: str, correlation: str) -> tuple[int, bytes]:
        return self._call(lambda: self._application.assessment(production, version), correlation)

    def report(self, reference: str, correlation: str, *, review: bool = False) -> tuple[int, bytes]:
        return self._call(lambda: self._application.report(reference, review=review), correlation)
