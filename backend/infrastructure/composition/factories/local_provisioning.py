from pathlib import Path

from backend.adapters.inbound.application.local_provisioning import (
    LocalProvisioningUseCaseInbound,
)
from backend.adapters.outbound.system.local_provisioning import LocalProvisioningAdapter
from backend.infrastructure.composition.factories.local_browser import (
    Read15RuntimeTarget,
    build_local_read15,
)
from backend.infrastructure.config.schemas.http import LocalBrowserHttpConfiguration
from backend.modules.local_provisioning.application.contracts import ProvisioningPlan
from backend.modules.local_provisioning.application.use_cases import (
    ApplyLocalProvisioning,
    InspectLocalProvisioning,
    InspectProvisioningTarget,
    InspectSuppliedSeedFile,
)


class _ComposedLocalProvisioningGateway(LocalProvisioningAdapter):
    def startup_probe(self, plan: ProvisioningPlan) -> bool:
        state = self.inspect_runtime(plan.runtime, plan.migrations)
        if (
            not state.exists
            or state.identity_sha256 is None
            or state.seed_sha256 != plan.seed.candidate.sha256
            or tuple(version for version, _ in state.applied_migrations) != ("001", "002")
            or state.integrity != "ok"
            or state.quick_check != "ok"
            or state.foreign_key_violations != 0
        ):
            return False
        composition = build_local_read15(
            LocalBrowserHttpConfiguration(port=8765),
            Read15RuntimeTarget(plan.runtime, plan.data_root, state.identity_sha256),
            saved_root=plan.library_root / "saved-productions",
            create_saved=True,
        )
        try:
            return True
        finally:
            composition.close()


def build_local_provisioning_inbound(
    *, repository_root: Path, old_data_root: Path
) -> LocalProvisioningUseCaseInbound:
    gateway = _ComposedLocalProvisioningGateway(
        repository_root=repository_root,
        old_data_root=old_data_root,
    )
    return LocalProvisioningUseCaseInbound(
        InspectLocalProvisioning(gateway),
        ApplyLocalProvisioning(gateway),
        InspectSuppliedSeedFile(gateway),
        InspectProvisioningTarget(gateway),
    )
