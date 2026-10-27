"""Inspection of a rejected capture never restores a generation right."""
from __future__ import annotations

import re
from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Protocol

from backend.shared_kernel._safe_data import freeze_safe_mapping


@dataclass(frozen=True, slots=True)
class RejectedCaptureRequest:
    command_id: str
    permission_sha256: str
    request_sha256: str
    request_bytes: int
    result_sha256: str
    grant_sha256: str
    preflight_sha256: str

    def __post_init__(self) -> None:
        if (type(self.command_id) is not str or re.fullmatch(r"[0-9a-f]{32}", self.command_id) is None
                or type(self.request_bytes) is not int or not 0 < self.request_bytes <= 128000
                or any(type(value) is not str or re.fullmatch(r"[0-9a-f]{64}", value) is None
                    for value in (self.permission_sha256, self.request_sha256,
                                  self.result_sha256, self.grant_sha256, self.preflight_sha256))):
            raise ValueError("REJECTED_CAPTURE_IDENTITY")


@dataclass(frozen=True, slots=True)
class RejectedCapture:
    request: RejectedCaptureRequest
    dispatch: Mapping[str, object] = field(repr=False)
    output_text: str = field(repr=False)
    metadata: Mapping[str, object]

    def __post_init__(self) -> None:
        if type(self.request) is not RejectedCaptureRequest or type(self.output_text) is not str:
            raise ValueError("REJECTED_CAPTURE_TYPES")
        if not self.output_text or len(self.output_text.encode()) > 128000:
            raise ValueError("REJECTED_CAPTURE_SIZE")
        if (self.metadata.get("result_sha256") != self.request.result_sha256
                or self.metadata.get("response_status") != "completed"
                or self.metadata.get("outcome_marker") != "PARSING_REJECTED"):
            raise ValueError("REJECTED_CAPTURE_BINDING")
        object.__setattr__(self, "dispatch", freeze_safe_mapping(self.dispatch))
        object.__setattr__(self, "metadata", freeze_safe_mapping(self.metadata))


class RejectedCaptureReader(Protocol):
    def read(self, request: RejectedCaptureRequest) -> RejectedCapture: ...
