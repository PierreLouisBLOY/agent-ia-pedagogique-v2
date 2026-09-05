"""CAP-R02 requires both opaque references, without latest-version fallback."""
from dataclasses import dataclass, field

from backend.modules.work_orchestration.contracts.dto.conversation import identity
from backend.shared_kernel.identifiers import TypedEntityId
from backend.shared_kernel.references import ObjectVersionRef, TypedEntityRef, VersionRef


@dataclass(frozen=True, slots=True)
class ReadProductionRequest:
    production_ref: str
    version_ref: str
    exact_ref: ObjectVersionRef = field(init=False)

    def __post_init__(self) -> None:
        identity(self.production_ref, "prod")
        identity(self.version_ref, "ver")
        object.__setattr__(self, "exact_ref", ObjectVersionRef(
            TypedEntityRef(TypedEntityId("PRODUCTION", self.production_ref)),
            VersionRef(self.version_ref),
        ))
