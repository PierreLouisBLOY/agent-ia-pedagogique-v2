"""Read-only, owner-bound capture data; never a valid pedagogical resource."""
from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from typing import Protocol

from backend.modules.work_orchestration.contracts.dto.p1_campaign_inspection import (
    P1CampaignInspectionView,
)


@dataclass(frozen=True, slots=True)
class CapturedPartialRequest:
    command_id: str
    profile_sha256: str
    request_sha256: str
    result_sha256: str
    text_sha256: str
    text_bytes: int

    def __post_init__(self) -> None:
        if (type(self.command_id) is not str or re.fullmatch(r"[0-9a-f]{32}", self.command_id) is None
                or any(type(value) is not str or re.fullmatch(r"[0-9a-f]{64}", value) is None
                    for value in (self.profile_sha256, self.request_sha256,
                        self.result_sha256, self.text_sha256))
                or type(self.text_bytes) is not int or not 0 < self.text_bytes <= 65_536):
            raise ValueError("P0_CAPTURED_PARTIAL_IDENTITY")


@dataclass(frozen=True, slots=True)
class CapturedPartial:
    request: CapturedPartialRequest
    text: str
    metadata: P1CampaignInspectionView

    def __post_init__(self) -> None:
        if (type(self.request) is not CapturedPartialRequest or type(self.text) is not str
                or type(self.metadata) is not P1CampaignInspectionView):
            raise ValueError("P0_CAPTURED_PARTIAL_TYPES")
        raw = self.text.encode("utf-8")
        if (len(raw) != self.request.text_bytes
                or hashlib.sha256(raw).hexdigest() != self.request.text_sha256):
            raise ValueError("P0_CAPTURED_PARTIAL_TEXT_CHANGED")
        data = self.metadata.as_dict()
        rows = data["receipts"]
        if not isinstance(rows, list):
            raise ValueError("P0_CAPTURED_PARTIAL_RECEIPTS")
        events = {str(row["state"]) for row in rows if isinstance(row, dict)}
        meta = data.get("response_metadata")
        if (data.get("schema") != "P1-PILOT-COMMAND-METADATA-1.1"
                or data.get("command_id") != self.request.command_id
                or data.get("inspection_profile_sha256") != self.request.profile_sha256
                or data.get("request_sha256") != self.request.request_sha256
                or data.get("state") != "RETAINED_PENDING_OBSERVED_NO_REPLAY"
                or data.get("right_status") != "CONSUMED_AT_PENDING_NO_NEW_RIGHT"
                or data.get("response_status") != "incomplete"
                or data.get("response_artifact_present") is not True
                or not {"RESERVED", "DISPATCH", "PROVIDER_ATTEMPTED",
                    "RESULT", "RESPONSE_CAPTURED", "PARSING_REJECTED"} <= events
                or events & {"PARSED", "CONSUMED", "UNKNOWN"}
                or not isinstance(meta, dict)
                or meta.get("result_sha256") != self.request.result_sha256
                or meta.get("output_text_sha256") != self.request.text_sha256
                or meta.get("output_text_bytes") != self.request.text_bytes):
            raise ValueError("P0_CAPTURED_PARTIAL_BINDING")


class CapturedPartialReader(Protocol):
    def read(self, request: CapturedPartialRequest) -> CapturedPartial: ...
