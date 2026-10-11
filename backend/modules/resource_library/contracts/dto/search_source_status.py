"""Separate source axes; none grants pedagogical or institutional authority."""

import re
from collections.abc import Mapping
from dataclasses import asdict, dataclass


@dataclass(frozen=True, slots=True)
class SearchSourceStatus:
    passage_status: str
    identity_status: str = "UNKNOWN"
    lifecycle_status: str = "UNKNOWN"
    validation_status: str = "UNKNOWN"
    status_basis: str = "STATUS_UNAVAILABLE"
    contract_id: str = "SEARCH-SOURCE-STATUS-1.0"

    def __post_init__(self) -> None:
        if self.contract_id != "SEARCH-SOURCE-STATUS-1.0" or self.passage_status not in {
            "CURRENT",
            "UNKNOWN",
        }:
            raise ValueError("SEARCH_SOURCE_STATUS_CONTRACT")
        if self.status_basis not in {"OBJECT_ROW", "EXACT_VERSION_REQUIRED", "STATUS_UNAVAILABLE"}:
            raise ValueError("SEARCH_SOURCE_STATUS_BASIS")
        for value in (self.identity_status, self.lifecycle_status, self.validation_status):
            if type(value) is not str or re.fullmatch(r"[A-Z][A-Z0-9_]{0,39}", value) is None:
                raise ValueError("SEARCH_SOURCE_STATUS_VALUE")
        if self.status_basis != "OBJECT_ROW" and (
            self.lifecycle_status,
            self.validation_status,
        ) != ("UNKNOWN", "UNKNOWN"):
            raise ValueError("SEARCH_SOURCE_STATUS_SCOPE")

    def as_dict(self) -> dict[str, str]:
        return asdict(self)

    @classmethod
    def from_mapping(cls, value: object) -> "SearchSourceStatus":
        fields = {
            "passage_status",
            "identity_status",
            "lifecycle_status",
            "validation_status",
            "status_basis",
            "contract_id",
        }
        if (
            not isinstance(value, Mapping)
            or set(value) != fields
            or any(type(v) is not str for v in value.values())
        ):
            raise ValueError("SEARCH_SOURCE_STATUS_FIELDS")
        return cls(**dict(value))
