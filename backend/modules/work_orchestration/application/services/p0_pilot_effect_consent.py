"""Exact pilot consent at the Application boundary; no provider or ledger access."""
from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from typing import Protocol

from backend.modules.pedagogical_design.contracts.dto.assessment_bundle import object_data


class PilotConsentPort(Protocol):
    def preview(self, *, request: Mapping[str, object], preparation_ref: str,
                preparation_sha256: str, source_receipts: Sequence[Mapping[str, object]]) -> Mapping[str, object]: ...
    def accept(self, *, request: Mapping[str, object], consent: Mapping[str, object],
               source_receipts: Sequence[Mapping[str, object]]) -> None: ...
    def dispatch(self, *, command_id: str, run: Callable[[], dict[str, object]]) -> dict[str, object]: ...


class P0PilotEffectConsentService:
    def __init__(self, *, prepared_reader: Callable[[str, str], Mapping[str, object]],
                 admission_reader: Callable[[Mapping[str, object]], Sequence[Mapping[str, object]]],
                 permission: PilotConsentPort,
                 generate: Callable[[Mapping[str, object]], dict[str, object]]) -> None:
        self.prepared_reader, self.admission_reader = prepared_reader, admission_reader
        self.permission, self.generate = permission, generate

    def execute(self, operation: str, payload: Mapping[str, object]) -> dict[str, object]:
        base = {"command_id", "preparation_ref", "preparation_sha256"}
        if operation == "consent_preview":
            fields = base
        elif operation == "consent_generate":
            fields = base | {"preview_sha256", "transfer_accepted", "cost_bound_accepted",
                "double_execution_cost_risk_accepted"}
        else:
            raise ValueError("P1_PILOT_CONSENT_OPERATION_REJECTED")
        data = object_data(payload, fields)
        for key, prefix, count in (("command_id", "", 32), ("preparation_ref", "prep:", 32),
                                   ("preparation_sha256", "", 64)):
            value = data[key]
            if (type(value) is not str or not value.startswith(prefix) or len(value) != len(prefix) + count
                or any(char not in "0123456789abcdef" for char in value[len(prefix):])):
                raise ValueError("P1_PILOT_CONSENT_IDENTITY_REJECTED")
        request = self.prepared_reader(str(data["preparation_ref"]), str(data["preparation_sha256"]))
        sources = self.admission_reader(request)
        if operation == "consent_preview":
            return dict(self.permission.preview(request=request, preparation_ref=str(data["preparation_ref"]),
                preparation_sha256=str(data["preparation_sha256"]), source_receipts=sources))
        if (type(data["preview_sha256"]) is not str or len(data["preview_sha256"]) != 64
            or any(char not in "0123456789abcdef" for char in data["preview_sha256"])
            or any(data[key] is not True for key in (
                "transfer_accepted", "cost_bound_accepted", "double_execution_cost_risk_accepted"))):
            raise ValueError("P1_PILOT_EXACT_CONSENT_REQUIRED")
        self.permission.accept(request=request, consent=data, source_receipts=sources)
        return self.permission.dispatch(command_id=str(data["command_id"]),
            run=lambda: self.generate({key: data[key] for key in base}))
