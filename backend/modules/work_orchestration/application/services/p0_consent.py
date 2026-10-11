"""Operator-local exact consent; no grants, credentials or transport in Application."""
from collections.abc import Callable, Mapping, Sequence
from typing import Protocol

from backend.modules.pedagogical_design.contracts.dto.assessment_bundle import object_data


class P0ProductConsentPort(Protocol):
    def preview(self, *, request: Mapping[str, object], preparation_ref: str,
                preparation_sha256: str, source_receipts: Sequence[Mapping[str, object]]) -> Mapping[str, object]: ...
    def accept(self, *, request: Mapping[str, object], consent: Mapping[str, object],
               source_receipts: Sequence[Mapping[str, object]]) -> None: ...


class P0ConsentService:
    def __init__(self, *, prepared_reader: Callable[[str, str], Mapping[str, object]],
                 admission_reader: Callable[[Mapping[str, object]], Sequence[Mapping[str, object]]],
                 permission: P0ProductConsentPort,
                 generate: Callable[[Mapping[str, object]], dict[str, object]]) -> None:
        self.prepared_reader, self.admission_reader, self.permission, self.generate = prepared_reader, admission_reader, permission, generate

    def execute(self, operation: str, payload: Mapping[str, object]) -> dict[str, object]:
        fields = {"command_id", "preparation_ref", "preparation_sha256"}
        if operation == "consent_generate":
            fields |= {"preview_sha256", "transfer_accepted", "cost_bound_accepted"}
        elif operation != "consent_preview":
            raise ValueError("P0_CONSENT_OPERATION_REJECTED")
        data = object_data(payload, fields)
        for key, prefix, count in (("command_id", "", 32), ("preparation_ref", "prep:", 32), ("preparation_sha256", "", 64)):
            value = data[key]
            if (not isinstance(value, str) or not value.startswith(prefix) or len(value) != len(prefix) + count
                    or any(c not in "0123456789abcdef" for c in value[len(prefix):])):
                raise ValueError("P0_CONSENT_IDENTITY_REJECTED")
        request = self.prepared_reader(str(data["preparation_ref"]), str(data["preparation_sha256"]))
        sources = self.admission_reader(request)
        if operation == "consent_preview":
            return dict(self.permission.preview(request=request, preparation_ref=str(data["preparation_ref"]),
                preparation_sha256=str(data["preparation_sha256"]), source_receipts=sources))
        if data["transfer_accepted"] is not True or data["cost_bound_accepted"] is not True:
            raise ValueError("P0_CONSENT_REQUIRED")
        self.permission.accept(request=request, consent=data, source_receipts=sources)
        return self.generate({key: data[key] for key in ("command_id", "preparation_ref", "preparation_sha256")})
