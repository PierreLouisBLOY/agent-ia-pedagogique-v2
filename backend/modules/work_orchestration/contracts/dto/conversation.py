"""Closed, presentation-neutral conversation commands and immutable state."""
from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Mapping
from dataclasses import dataclass

from backend.modules.pedagogical_context.contracts.dto.conversation_context import (
    FIELDS,
    text_value,
    validated_values,
)
from backend.shared_kernel._safe_data import freeze_safe_mapping

RETENTION = "VOLATILE_UNTIL_PROCESS_EXIT"
FAILURE_CODES = frozenset({
    "VALIDATION_REJECTED", "CONTEXT_INVALID", "UNKNOWN_FIELD", "CONVERSATION_NOT_FOUND",
    "REVISION_CONFLICT", "IDEMPOTENCY_CONFLICT", "CONTEXT_NOT_CONFIRMED",
    "GENERATION_IN_PROGRESS", "GENERATION_OUTCOME_UNKNOWN", "SESSION_CAPACITY_REACHED",
    "CONVERSATION_EXPIRED", "CONTEXT_CLARIFICATION_REQUIRED", "INSUFFICIENT_EVIDENCE",
    "TRANSFER_NOT_AUTHORIZED", "GENERATION_NOT_AUTHORIZED", "PROVIDER_NOT_CONFIGURED",
    "PROVIDER_UNAVAILABLE", "BUDGET_UNAVAILABLE", "JOB_UNAVAILABLE",
    "APPLICATION_FAILURE", "GENERATION_OUTPUT_INVALID",
})


class ConversationRejected(ValueError):
    def __init__(self, code: str, field_code: str | None = None) -> None:
        self.code = code if code in FAILURE_CODES else "APPLICATION_FAILURE"
        self.field_code = field_code if field_code in FIELDS else None
        super().__init__(self.code)


def identity(value: object, prefix: str) -> str:
    if not isinstance(value, str) or re.fullmatch(prefix + r":[0-9a-f]{32}", value) is None:
        raise ConversationRejected("VALIDATION_REJECTED")
    return value


def plain(value: object) -> object:
    if isinstance(value, Mapping):
        return {str(k): plain(v) for k, v in value.items()}
    if isinstance(value, (tuple, list)):
        return [plain(v) for v in value]
    return value


def digest(value: Mapping[str, object]) -> str:
    return hashlib.sha256(json.dumps(plain(value), ensure_ascii=False, sort_keys=True,
                                     separators=(",", ":"), allow_nan=False).encode()).hexdigest()


@dataclass(frozen=True, slots=True)
class ConversationCommand:
    operation: str
    body: Mapping[str, object]

    def __post_init__(self) -> None:
        required = {"command_id", "conversation_id", "expected_revision"}
        optional: set[str] = set()
        if self.operation == "messages":
            required.add("text")
            optional = {"context_patch", "confirm_context"}
        elif self.operation == "generations":
            required.add("confirmed_context_sha256")
        else:
            raise ConversationRejected("VALIDATION_REJECTED")
        if set(self.body) - required - optional:
            raise ConversationRejected("UNKNOWN_FIELD")
        if not required <= set(self.body):
            raise ConversationRejected("VALIDATION_REJECTED")
        body = dict(self.body)
        command = body["command_id"]
        if not isinstance(command, str) or re.fullmatch(
            r"[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}", command,
        ) is None:
            raise ConversationRejected("VALIDATION_REJECTED")
        identity(body["conversation_id"], "conv")
        revision = body["expected_revision"]
        if type(revision) is not int or revision < 1:
            raise ConversationRejected("VALIDATION_REJECTED")
        if self.operation == "messages":
            body["text"] = text_value(body["text"], 4000, 12288)
            patch = body.get("context_patch", {})
            if not isinstance(patch, Mapping):
                raise ConversationRejected("CONTEXT_INVALID")
            body["context_patch"] = validated_values(patch)
            if type(body.get("confirm_context", False)) is not bool:
                raise ConversationRejected("VALIDATION_REJECTED")
            body["confirm_context"] = body.get("confirm_context", False)
        else:
            sha = body["confirmed_context_sha256"]
            if not isinstance(sha, str) or re.fullmatch(r"[0-9a-f]{64}", sha) is None:
                raise ConversationRejected("VALIDATION_REJECTED")
        object.__setattr__(self, "body", freeze_safe_mapping(body))

    @property
    def command_id(self) -> str:
        return str(self.body["command_id"])

    @property
    def fingerprint(self) -> str:
        return digest({"operation": self.operation, "body": self.body})


@dataclass(frozen=True, slots=True)
class CommandReceipt:
    command_id: str
    fingerprint: str
    data: Mapping[str, object]

    def __post_init__(self) -> None:
        object.__setattr__(self, "data", freeze_safe_mapping(self.data))


@dataclass(frozen=True, slots=True)
class ConversationState:
    conversation_id: str
    revision: int
    view: Mapping[str, object]
    receipts: tuple[CommandReceipt, ...] = ()
    job_count: int = 0
    conflicts: tuple[str, ...] = ()
    brief: str = ""

    def __post_init__(self) -> None:
        identity(self.conversation_id, "conv")
        if self.revision < 1 or len(self.receipts) > 64 or not 0 <= self.job_count <= 3:
            raise ConversationRejected("SESSION_CAPACITY_REACHED")
        encoded = json.dumps(plain(self.view), ensure_ascii=False, allow_nan=False).encode()
        if len(encoded) > 96 * 1024:
            raise ConversationRejected("SESSION_CAPACITY_REACHED")
        if self.view.get("conversation_id") != self.conversation_id:
            raise ConversationRejected("APPLICATION_FAILURE")
        if self.view.get("revision") != self.revision:
            raise ConversationRejected("APPLICATION_FAILURE")
        object.__setattr__(self, "view", freeze_safe_mapping(self.view))
