"""Closed M04 transformation requests; all identities belong to Application."""
from collections.abc import Mapping
from dataclasses import dataclass

from backend.modules.pedagogical_design.contracts.dto.assessment_bundle import (
    AssessmentBundle,
    identifier,
)
from backend.shared_kernel._safe_data import freeze_safe_mapping

PREPARE = "PREPARE_SUPPLEMENTS"
HARDEN = "HARDEN_DOSSIER_3"
INSTRUCTION = "Rends le dossier 3 plus difficile."


@dataclass(frozen=True, slots=True)
class AssessmentRevisionRequest:
    operation: str
    production_ref: str
    base_version_ref: str
    subject: Mapping[str, object]
    context: Mapping[str, object]
    references: tuple[Mapping[str, object], ...]
    base: AssessmentBundle | None = None

    def __post_init__(self) -> None:
        identifier(self.production_ref, "prod")
        identifier(self.base_version_ref, "ver")
        if self.operation not in {PREPARE, HARDEN} or (self.operation == HARDEN) != (self.base is not None):
            raise ValueError("ASSESSMENT_OPERATION")
        if self.base is not None and (self.base.production_ref, self.base.version_ref) != (
                self.production_ref, self.base_version_ref):
            raise ValueError("ASSESSMENT_REFERENCE")
        object.__setattr__(self, "subject", freeze_safe_mapping(self.subject))
        object.__setattr__(self, "context", freeze_safe_mapping(self.context))
        object.__setattr__(self, "references", tuple(freeze_safe_mapping(r) for r in self.references))
