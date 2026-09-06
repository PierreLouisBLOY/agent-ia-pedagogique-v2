"""Closed JSON pipe worker for an explicitly injected synthetic callable."""
import json
from collections.abc import Callable, Mapping
from multiprocessing.connection import Connection
from typing import cast

from backend.modules.pedagogical_design.contracts.dto.assessment_bundle import (
    AssessmentBundle,
    encoded,
    items,
    object_data,
)
from backend.modules.pedagogical_design.contracts.dto.assessment_revision import (
    AssessmentRevisionRequest,
)
from backend.modules.work_orchestration.contracts.dto.r3_review_modify import R3JobRequest


def decode_request(raw: bytes) -> R3JobRequest:
    if len(raw) > 256 * 1024:
        raise ValueError("R3_FRAME_SIZE")
    data = object_data(json.loads(raw), {"operation_ref", "operation", "revision", "bundle", "dimensions"})
    revision = None
    if data["revision"] is not None:
        r = object_data(data["revision"])
        revision = AssessmentRevisionRequest(str(r["operation"]), str(r["production_ref"]),
            str(r["base_version_ref"]), object_data(r["subject"]), object_data(r["context"]),
            items(r["references"]), AssessmentBundle(object_data(r["base"])) if r["base"] is not None else None)
    return R3JobRequest(str(data["operation_ref"]), str(data["operation"]), revision,
        AssessmentBundle(object_data(data["bundle"])) if data["bundle"] is not None else None,
        tuple(str(d) for d in cast(list[str], data["dimensions"])))


def run_synthetic_worker(handler: Callable[[R3JobRequest], Mapping[str, object]],
                         raw: bytes, connection: Connection) -> None:
    """No provider, credential, file or database discovery."""
    try:
        result = encoded({"state": "SUCCEEDED", "payload": handler(decode_request(raw))})
        if len(result) > 256 * 1024:
            raise ValueError("R3_FRAME_SIZE")
        connection.send_bytes(result)
    except Exception:
        connection.send_bytes(encoded({"state": "FAILED_OUTPUT", "payload": None}))
    finally:
        connection.close()
