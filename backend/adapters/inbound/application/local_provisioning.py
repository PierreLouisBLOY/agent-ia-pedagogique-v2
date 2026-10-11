from __future__ import annotations

from backend.modules.local_provisioning.application.contracts import (
    ProvisioningApplyResult,
    ProvisioningInspectionRequest,
    ProvisioningInspectionResult,
    ProvisioningPlan,
    ProvisioningTargetInspectionRequest,
    ProvisioningTargetInspectionResult,
    SuppliedSeedFileInspectionRequest,
    SuppliedSeedFileInspectionResult,
)
from backend.modules.local_provisioning.application.use_cases import (
    ApplyLocalProvisioning,
    InspectLocalProvisioning,
    InspectProvisioningTarget,
    InspectSuppliedSeedFile,
)


class LocalProvisioningUseCaseInbound:
    """Trusted owner-controlled inbound adapter; not registered for agent tools."""

    def __init__(
        self,
        inspection: InspectLocalProvisioning,
        application: ApplyLocalProvisioning,
        supplied_seed_inspection: InspectSuppliedSeedFile,
        target_inspection: InspectProvisioningTarget,
    ) -> None:
        self._inspection = inspection
        self._application = application
        self._supplied_seed_inspection = supplied_seed_inspection
        self._target_inspection = target_inspection

    def inspect(self, request: ProvisioningInspectionRequest) -> ProvisioningInspectionResult:
        return self._inspection.execute(request)

    def apply(self, plan: ProvisioningPlan) -> ProvisioningApplyResult:
        return self._application.execute(plan)

    def inspect_supplied_seed_file(
        self, request: SuppliedSeedFileInspectionRequest
    ) -> SuppliedSeedFileInspectionResult:
        return self._supplied_seed_inspection.execute(request)

    def inspect_target(
        self, request: ProvisioningTargetInspectionRequest
    ) -> ProvisioningTargetInspectionResult:
        return self._target_inspection.execute(request)
