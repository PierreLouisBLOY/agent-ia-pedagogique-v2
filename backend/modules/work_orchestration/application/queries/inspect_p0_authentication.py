"""One metadata-only authentication observation, with no generation authority."""
from __future__ import annotations

import re
from collections.abc import Mapping
from typing import Protocol


class P0AuthenticationReader(Protocol):
    def read(self) -> Mapping[str, object]: ...


class InspectP0Authentication:
    def __init__(self, reader: P0AuthenticationReader) -> None:
        self.reader = reader
        self._used = False

    def execute(self) -> dict[str, object]:
        if self._used:
            raise ValueError("P0_AUTHENTICATION_DIAGNOSTIC_ALREADY_USED")
        self._used = True
        data = dict(self.reader.read())
        if set(data) != {"state", "model", "http_status", "request_id",
                "error_type", "error_code", "attempts", "retries", "cleanup_error"}:
            raise ValueError("P0_AUTHENTICATION_DIAGNOSTIC_FIELDS")
        if (data["model"] != "gpt-5.6-terra" or data["retries"] != 0
                or type(data["cleanup_error"]) is not bool
                or type(data["attempts"]) is not int or data["attempts"] not in {0, 1}
                or data["state"] not in {"AUTHENTICATED", "AUTHENTICATION_REJECTED",
                    "ACCESS_REJECTED", "HTTP_ERROR", "MODEL_MISMATCH",
                    "TRANSPORT_UNAVAILABLE", "LOCAL_CONFIGURATION_REJECTED"}
                or data["http_status"] is not None and (type(data["http_status"]) is not int
                    or not 100 <= data["http_status"] <= 599)):
            raise ValueError("P0_AUTHENTICATION_DIAGNOSTIC_VALUE")
        for key in ("request_id", "error_type", "error_code"):
            value = data[key]
            if value is not None and (type(value) is not str
                    or re.fullmatch(r"[A-Za-z0-9_-]{1,128}", value) is None):
                raise ValueError("P0_AUTHENTICATION_DIAGNOSTIC_LABEL")
        return {"schema": "P0-AUTHENTICATION-METADATA-OBSERVATION-1.0", **data,
            "credential_source": "OPENAI_API_KEY", "content_sent": False,
            "generation_authorized": False}
