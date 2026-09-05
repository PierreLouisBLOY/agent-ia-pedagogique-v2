"""Closed R2 transport envelopes and JSON; no provider or module authority."""
from __future__ import annotations

import json
import re
from typing import cast

from backend.adapters.inbound.application.conversation import (
    ConversationApplicationInbound,
    ConversationInputError,
)

CONVERSATION_CONTRACT = "CONVERSATION-HTTP-LOCAL-1.0"
ERROR_STATUS = {
    **dict.fromkeys(("VALIDATION_REJECTED", "REQUEST_FRAMING_REJECTED", "CONTEXT_INVALID", "UNKNOWN_FIELD"), 400),
    **dict.fromkeys(("LOCAL_INTENT_REJECTED", "ORIGIN_REJECTED", "HOST_REJECTED", "TRANSFER_NOT_AUTHORIZED", "GENERATION_NOT_AUTHORIZED"), 403),
    **dict.fromkeys(("R2_NOT_ENABLED", "CONVERSATION_NOT_FOUND", "PRODUCTION_NOT_FOUND", "PRODUCTION_VERSION_NOT_FOUND"), 404),
    "METHOD_NOT_ALLOWED": 405,
    **dict.fromkeys(("REVISION_CONFLICT", "IDEMPOTENCY_CONFLICT", "CONTEXT_NOT_CONFIRMED", "GENERATION_IN_PROGRESS", "GENERATION_OUTCOME_UNKNOWN", "SESSION_CAPACITY_REACHED"), 409),
    "CONVERSATION_EXPIRED": 410, "LENGTH_REQUIRED": 411, "REQUEST_TOO_LARGE": 413,
    "MEDIA_TYPE_REJECTED": 415, "CONTEXT_CLARIFICATION_REQUIRED": 422, "INSUFFICIENT_EVIDENCE": 422,
    **dict.fromkeys(("PROVIDER_NOT_CONFIGURED", "PROVIDER_UNAVAILABLE", "BUDGET_UNAVAILABLE", "JOB_UNAVAILABLE"), 503),
    "APPLICATION_FAILURE": 500, "GENERATION_OUTPUT_INVALID": 500,
}
FIELDS = frozenset({"resource_type", "level", "discipline", "topics", "objectives", "difficulty",
                    "duration_minutes", "total_points", "language"})


def envelope(data: object, correlation: str, command_id: str | None = None) -> bytes:
    payload = {"data": data, "meta": {"correlation_id": correlation,
                "contract_id": CONVERSATION_CONTRACT, "command_id": command_id}}
    encoded = json.dumps(payload, ensure_ascii=False, allow_nan=False, separators=(",", ":")).encode()
    if len(encoded) > 256 * 1024:
        raise ValueError("APPLICATION_FAILURE")
    return encoded


def conversation_error(code: str, correlation: str, *, command_id: str | None = None,
                       field: str | None = None) -> tuple[int, bytes]:
    code = code if code in ERROR_STATUS else "APPLICATION_FAILURE"
    return ERROR_STATUS[code], json.dumps({
        "error": {"code": code, "field_code": field if field in FIELDS else None},
        "meta": {"correlation_id": correlation, "contract_id": CONVERSATION_CONTRACT,
                 "command_id": command_id},
    }, separators=(",", ":")).encode()


def parse_command(raw: bytes) -> dict[str, object]:
    if not 1 <= len(raw) <= 16384 or raw.startswith(b"\xef\xbb\xbf"):
        raise ValueError("REQUEST_FRAMING_REJECTED")
    def pairs(items: list[tuple[str, object]]) -> dict[str, object]:
        result: dict[str, object] = {}
        for key, value in items:
            if key in result:
                raise ValueError("REQUEST_FRAMING_REJECTED")
            result[key] = value
        return result
    def invalid(value: str) -> object:
        raise ValueError("REQUEST_FRAMING_REJECTED")
    def depth(value: object, level: int = 1) -> None:
        if isinstance(value, (dict, list)):
            if level > 6:
                raise ValueError("REQUEST_FRAMING_REJECTED")
            for item in value.values() if isinstance(value, dict) else value:
                depth(item, level + 1)
    try:
        data = json.loads(raw.decode("utf-8"), object_pairs_hook=pairs, parse_constant=invalid)
        depth(data)
    except (UnicodeError, json.JSONDecodeError, RecursionError):
        raise ValueError("REQUEST_FRAMING_REJECTED") from None
    if not isinstance(data, dict):
        raise ValueError("VALIDATION_REJECTED")
    return cast(dict[str, object], data)


class ConversationEndpoint:
    def __init__(self, application: ConversationApplicationInbound, nonce: str) -> None:
        self.application, self.nonce = application, nonce

    def get(self, correlation: str) -> tuple[int, bytes]:
        try:
            return 200, envelope({"conversation": self.application.snapshot(),
                                  "transport_nonce": self.nonce}, correlation)
        except ConversationInputError as error:
            return conversation_error(error.code, correlation, field=error.field_code)
        except Exception:
            return conversation_error("APPLICATION_FAILURE", correlation)

    def post(self, operation: str, raw: bytes, correlation: str) -> tuple[int, bytes]:
        command_id = None
        try:
            body = parse_command(raw)
            candidate = body.get("command_id")
            if isinstance(candidate, str) and re.fullmatch(
                r"[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}", candidate
            ):
                command_id = candidate
            data = self.application.command(operation, body)
            return (202 if operation == "generations" else 200), envelope(data, correlation, command_id)
        except ConversationInputError as error:
            return conversation_error(error.code, correlation, command_id=command_id,
                                       field=error.field_code)
        except ValueError as error:
            code = str(error)
            return conversation_error(code if code in ERROR_STATUS else "VALIDATION_REJECTED", correlation)
        except Exception:
            return conversation_error("APPLICATION_FAILURE", correlation, command_id=command_id)
