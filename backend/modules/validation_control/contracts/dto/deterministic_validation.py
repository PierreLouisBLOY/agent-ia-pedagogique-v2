"""CAP-A01 decisions, distinct from review, promotion and official validation."""
from dataclasses import dataclass

from backend.modules.pedagogical_design.contracts.dto.assessment_bundle import identifier


@dataclass(frozen=True, slots=True)
class AssessmentCheck:
    check_id: str
    status: str
    reason_code: str

    def __post_init__(self) -> None:
        if self.status not in {"PASS", "FAIL", "WARNING"}:
            raise ValueError("VALIDATION_STATUS")


@dataclass(frozen=True, slots=True)
class AssessmentValidation:
    validation_ref: str
    production_ref: str
    version_ref: str
    subject_sha256: str
    bundle_sha256: str | None
    checks: tuple[AssessmentCheck, ...]
    evaluated_at: str

    def __post_init__(self) -> None:
        identifier(self.production_ref, "prod")
        identifier(self.version_ref, "ver")
        if tuple(c.check_id for c in self.checks) != tuple(f"A{i:02}" for i in range(1, 17)):
            raise ValueError("VALIDATION_CHECK_SET")

    @property
    def overall_status(self) -> str:
        states = {c.status for c in self.checks}
        return "FAIL" if "FAIL" in states else "WARNING" if "WARNING" in states else "PASS"

    def as_dict(self) -> dict[str, object]:
        return {"validation_ref": self.validation_ref, "contract_id": "R3-DETERMINISTIC-VALIDATION-1.0",
                "production_ref": self.production_ref, "version_ref": self.version_ref,
                "subject_sha256": self.subject_sha256, "bundle_sha256": self.bundle_sha256,
                "checks": [{"check_id": c.check_id, "status": c.status, "reason_code": c.reason_code,
                            "locators": [], "expected": "CLOSED_CHECK_SATISFIED", "observed": c.status}
                           for c in self.checks], "overall_status": self.overall_status,
                "evaluated_at": self.evaluated_at}
