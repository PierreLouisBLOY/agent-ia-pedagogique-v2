"""An active explicit human gate is not an imported documentary report."""
from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True, slots=True)
class PromotionGate:
    decision_ref: str
    actor: str
    record_sha256: str
    validation_ref: str
    approved: bool
    warnings_acknowledged: bool
    issued_at: datetime
    expires_at: datetime

    def permits(self, *, record_sha256: str, validation_ref: str, now: datetime) -> bool:
        return (bool(self.decision_ref) and bool(self.actor) and self.approved is True
                and self.warnings_acknowledged is True
                and self.record_sha256 == record_sha256
                and self.validation_ref == validation_ref
                and self.issued_at.tzinfo is not None and self.expires_at.tzinfo is not None
                and self.issued_at <= now < self.expires_at)
