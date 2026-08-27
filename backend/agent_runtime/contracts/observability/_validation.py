from __future__ import annotations

import re
from collections.abc import Mapping
from datetime import timedelta
from typing import Final

from backend.agent_runtime.contracts.common import (
    ContractRef,
    freeze_agent_safe_mapping,
    require_agent_safe_ref,
    require_agent_safe_text,
    require_contract_ref,
)
from backend.shared_kernel._value_safety import StructuredDataLimits
from backend.shared_kernel.time import Instant

OBSERVABILITY_ATTRIBUTE_LIMITS: Final = StructuredDataLimits(
    max_depth=8,
    max_mapping_keys=32,
    max_sequence_items=64,
    max_string_length=512,
    max_total_nodes=512,
)

_SAFE_OPAQUE_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$")
_SAFE_REF = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,255}$")
_FORBIDDEN_ATTRIBUTE_KEYS: Final = frozenset(
    {
        "agentoutput",
        "agentpayload",
        "applicationoutput",
        "applicationpayload",
        "chainofthought",
        "content",
        "credential",
        "credentials",
        "document",
        "documenttext",
        "errordetails",
        "errormessage",
        "evidenceexcerpt",
        "excerpt",
        "filepath",
        "filesystempath",
        "idempotencykey",
        "localpath",
        "message",
        "payload",
        "privatereasoning",
        "prompt",
        "providerpayload",
        "providerresponse",
        "rawcontent",
        "rawidempotencykey",
        "rawpayload",
        "rawprompt",
        "rawproviderresponse",
        "secret",
        "stacktrace",
        "systemprompt",
        "tooloutput",
        "toolpayload",
    }
)


def require_observability_id(value: str, field_name: str) -> None:
    require_agent_safe_text(value, field_name=field_name, max_length=128)
    if not _SAFE_OPAQUE_ID.fullmatch(value):
        raise ValueError(f"{field_name} must be a bounded opaque identifier")


def require_utc_instant(value: Instant, field_name: str) -> None:
    if not isinstance(value, Instant):
        raise TypeError(f"{field_name} must be an Instant")
    if value.value.utcoffset() != timedelta(0):
        raise ValueError(f"{field_name} must be UTC")


def freeze_observability_attributes(
    value: Mapping[str, object],
) -> Mapping[str, object]:
    if not isinstance(value, Mapping):
        raise TypeError("observability attributes must be a mapping")
    _reject_forbidden_attributes(value)
    _reject_non_finite_numbers(value)
    return freeze_agent_safe_mapping(
        value,
        limits=OBSERVABILITY_ATTRIBUTE_LIMITS,
    )


def normalize_observation_refs(
    refs: tuple[ContractRef, ...],
) -> tuple[ContractRef, ...]:
    if type(refs) is not tuple:
        raise TypeError("refs must be an immutable tuple")
    if len(refs) > 16:
        raise ValueError("refs must contain at most 16 items")
    normalized: list[ContractRef] = []
    for ref in refs:
        require_contract_ref(ref, "ref")
        require_agent_safe_ref(ref, field_name="observability_ref")
        if type(ref) is str and not _SAFE_REF.fullmatch(ref):
            raise ValueError("string refs must be bounded opaque identifiers")
        if ref in normalized:
            raise ValueError("refs must be unique")
        normalized.append(ref)
    return tuple(normalized)


def _reject_forbidden_attributes(value: object) -> None:
    if isinstance(value, Mapping):
        for key, item in value.items():
            if type(key) is not str:
                raise TypeError("observability attribute keys must be strings")
            if _compact_key(key) in _FORBIDDEN_ATTRIBUTE_KEYS:
                raise ValueError(f"raw observability attribute key is forbidden: {key}")
            _reject_forbidden_attributes(item)
    elif isinstance(value, (list, tuple)):
        for item in value:
            _reject_forbidden_attributes(item)


def _reject_non_finite_numbers(value: object) -> None:
    if type(value) is float and (
        value != value or value in (float("inf"), float("-inf"))
    ):
        raise ValueError("observability attributes require finite numbers")
    if isinstance(value, Mapping):
        for item in value.values():
            _reject_non_finite_numbers(item)
    elif isinstance(value, (list, tuple)):
        for item in value:
            _reject_non_finite_numbers(item)


def _compact_key(value: str) -> str:
    return "".join(character for character in value.casefold() if character.isalnum())
