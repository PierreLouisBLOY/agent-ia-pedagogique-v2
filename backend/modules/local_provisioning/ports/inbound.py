from __future__ import annotations

from typing import Protocol, runtime_checkable

from backend.modules.local_provisioning.application.contracts import (
    ProvisioningApplyResult,
    ProvisioningInspectionRequest,
    ProvisioningInspectionResult,
    ProvisioningPlan,
    ProvisioningTargetInspectionRequest,
    ProvisioningTargetInspectionResult,
)


@runtime_checkable
class LocalProvisioningInbound(Protocol):
    def inspect(self, request: ProvisioningInspectionRequest) -> ProvisioningInspectionResult: ...

    def apply(self, plan: ProvisioningPlan) -> ProvisioningApplyResult: ...

    def inspect_target(
        self, request: ProvisioningTargetInspectionRequest
    ) -> ProvisioningTargetInspectionResult: ...
