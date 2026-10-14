"""Exact local relecture only; no source admission, mutation or repair."""
from __future__ import annotations

from collections.abc import Mapping

from backend.modules.documents_provenance.contracts.dto.local_contribution_provenance import (
    LocalContributionProvenance,
)
from backend.modules.resource_library.contracts.dto.local_contribution import (
    LocalContributionAuthority,
    LocalContributionRead,
)
from backend.modules.resource_library.ports.outbound.local_contribution_store import (
    LocalContributionStorePort,
)


class ReadLocalContribution:
    def __init__(self, store: LocalContributionStorePort, *, authority: LocalContributionAuthority,
                 provenance: LocalContributionProvenance, enabled: bool = False) -> None:
        if type(enabled) is not bool:
            raise ValueError("LOCAL_CONTRIBUTION_ENABLED_BOOL")
        self.store, self.authority, self.provenance, self.enabled = store, authority, provenance, enabled

    def _check(self) -> None:
        if not self.enabled:
            raise ValueError("LOCAL_CONTRIBUTION_DISABLED")
        expected = {key: self.authority.data[key] for key in ("target_ref", "target_binding_sha256", "operator_profile_sha256")}
        expected["binding_sha256"] = self.authority.sha256
        if dict(self.store.attest()) != expected:
            raise ValueError("LOCAL_CONTRIBUTION_TARGET_CHANGED")

    def execute(self, request: LocalContributionRead) -> dict[str, object]:
        self._check()
        with self.store.session():
            record = self.store.read_exact(request)
        if record.data["binding_sha256"] != self.authority.sha256 or record.data["target_binding_sha256"] != self.authority.data["target_binding_sha256"]:
            raise ValueError("LOCAL_CONTRIBUTION_READ_BINDING")
        for key in ("text_sha256", "utf8_bytes"):
            if record.data[key] != self.authority.data[key]:
                raise ValueError("LOCAL_CONTRIBUTION_READ_BINDING")
        if record.as_dict()["provenance"] != self.provenance.as_dict():
            raise ValueError("LOCAL_CONTRIBUTION_READ_PROVENANCE")
        return {"contract_id": "LOCAL-CONTRIBUTION-PROJECTION-1.0", "record": record.as_dict(),
            "record_sha256": record.sha256, "source_snapshot": record.source_snapshot()}

    def inspect(self, operation_key: str) -> Mapping[str, object]:
        self._check()
        with self.store.session():
            return self.store.inspect_operation(operation_key, self.authority.sha256)
