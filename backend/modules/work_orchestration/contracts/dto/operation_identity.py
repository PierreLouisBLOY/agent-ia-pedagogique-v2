"""Neutral immutable operation metadata; no authority, payload or runtime types."""
import re
from collections.abc import Mapping
from dataclasses import asdict, dataclass


@dataclass(frozen=True, slots=True)
class OperationIdentity:
    run_id: str
    step_id: str
    parent_step_id: str | None
    correlation_id: str

    def __post_init__(self) -> None:
        for value in (self.run_id, self.step_id, self.correlation_id):
            if type(value) is not str or re.fullmatch(r"[A-Za-z0-9._:-]{1,128}", value) is None:
                raise ValueError("OPERATION_IDENTITY_REJECTED")
        if self.parent_step_id is not None and (
                type(self.parent_step_id) is not str
                or re.fullmatch(r"[A-Za-z0-9._:-]{1,128}", self.parent_step_id) is None
                or self.parent_step_id == self.step_id):
            raise ValueError("OPERATION_IDENTITY_REJECTED")

    def as_dict(self) -> dict[str, object]:
        return {"contract_id": "OPERATION-IDENTITY-1.0", **asdict(self)}

    @classmethod
    def from_mapping(cls, value: object) -> "OperationIdentity":
        if not isinstance(value, Mapping) or set(value) != {
                "contract_id", "run_id", "step_id", "parent_step_id", "correlation_id"}:
            raise ValueError("OPERATION_IDENTITY_REJECTED")
        if value["contract_id"] != "OPERATION-IDENTITY-1.0":
            raise ValueError("OPERATION_IDENTITY_REJECTED")
        return cls(value["run_id"], value["step_id"], value["parent_step_id"], value["correlation_id"])
