from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass

from backend.agent_runtime.contracts.common import ContractMeta, freeze_agent_safe_mapping
from backend.agent_runtime.contracts.invocation import AgentResultStatus
from backend.agent_runtime.contracts.review.correction_request import CorrectionRequest
from backend.shared_kernel._strings import require_non_empty
from backend.shared_kernel.references import ObjectVersionRef


@dataclass(frozen=True, slots=True)
class CorrectionResult:
    """Non-canonical correction delta between two exact production versions."""

    meta: ContractMeta[AgentResultStatus]
    request: CorrectionRequest
    new_production_ref: ObjectVersionRef
    parent_production_ref: ObjectVersionRef
    addressed_findings: tuple[str, ...]
    unresolved_findings: tuple[str, ...]
    change_summary: str
    lineage: Mapping[str, object]
    new_warnings: tuple[Mapping[str, object], ...] = ()

    def __post_init__(self) -> None:
        if not isinstance(self.meta, ContractMeta):
            raise TypeError("meta must be a ContractMeta")
        if not isinstance(self.meta.status, AgentResultStatus):
            raise TypeError("meta.status must be an AgentResultStatus")
        if not isinstance(self.request, CorrectionRequest):
            raise TypeError("request must be a CorrectionRequest")
        if not isinstance(self.new_production_ref, ObjectVersionRef):
            raise TypeError("new_production_ref must be an ObjectVersionRef")
        if not isinstance(self.parent_production_ref, ObjectVersionRef):
            raise TypeError("parent_production_ref must be an ObjectVersionRef")
        if self.parent_production_ref != self.request.target_production_ref:
            raise ValueError("parent_production_ref must match request target")
        if self.new_production_ref.object_ref != self.parent_production_ref.object_ref:
            raise ValueError("new production version must keep the parent object identity")
        if self.new_production_ref.version_ref == self.parent_production_ref.version_ref:
            raise ValueError("new production version must differ from parent version")
        addressed = _validated_finding_ids(self.addressed_findings, "addressed_finding")
        unresolved = _validated_finding_ids(
            self.unresolved_findings,
            "unresolved_finding",
        )
        if set(addressed).intersection(unresolved):
            raise ValueError("addressed and unresolved findings must be disjoint")
        if set(addressed).union(unresolved) != set(self.request.finding_ids):
            raise ValueError("addressed and unresolved findings must cover request findings")
        require_non_empty(self.change_summary, "change_summary")
        if self.meta.step_id != self.request.meta.step_id:
            raise ValueError("meta.step_id must match request meta.step_id")
        if self.meta.correlation_id != self.request.meta.correlation_id:
            raise ValueError("meta correlation must match request correlation")
        if self.meta.run_id != self.request.meta.run_id:
            raise ValueError("meta.run_id must match request meta.run_id")
        warnings = tuple(
            freeze_agent_safe_mapping(warning) for warning in self.new_warnings
        )
        object.__setattr__(self, "addressed_findings", addressed)
        object.__setattr__(self, "unresolved_findings", unresolved)
        object.__setattr__(self, "lineage", freeze_agent_safe_mapping(self.lineage))
        object.__setattr__(self, "new_warnings", warnings)


def _validated_finding_ids(values: tuple[str, ...], field_name: str) -> tuple[str, ...]:
    items = tuple(values)
    for item in items:
        require_non_empty(item, field_name)
    if len(items) != len(set(items)):
        raise ValueError(f"{field_name} values must be unique")
    return items
