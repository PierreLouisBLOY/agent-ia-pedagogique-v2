from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from calibration_tooling.contracts.models import (
    CALIBRATION_SCHEMA_V1,
    AnchorTier,
    CalibrationSchemaVersion,
)


@dataclass(frozen=True, slots=True)
class DurableCalibrationPolicy:
    """Closed policy inherited from the approved 12.16 calibration decisions."""

    schema_version: CalibrationSchemaVersion = CALIBRATION_SCHEMA_V1
    blind_scoring: bool = True
    deliverable_tiers: tuple[AnchorTier, ...] = (AnchorTier.STRONG,)
    one_shot_authorization: bool = True
    fail_closed: bool = True
    retry_count: int = 0
    release_threshold: Decimal | None = None

    def __post_init__(self) -> None:
        if self.schema_version is not CALIBRATION_SCHEMA_V1:
            raise ValueError("policy schema version is not supported")
        if self.blind_scoring is not True:
            raise ValueError("blind scoring is mandatory")
        if self.deliverable_tiers != (AnchorTier.STRONG,):
            raise ValueError("only STRONG is a delivery candidate")
        if self.one_shot_authorization is not True:
            raise ValueError("one-shot authorization is mandatory")
        if self.fail_closed is not True:
            raise ValueError("fail-closed execution is mandatory")
        if type(self.retry_count) is not int or self.retry_count != 0:
            raise ValueError("retry and rerun are forbidden")
        if self.release_threshold is not None:
            raise ValueError("release threshold adoption is forbidden")

    def is_deliverable(self, tier: AnchorTier) -> bool:
        if not isinstance(tier, AnchorTier):
            raise TypeError("tier must be an AnchorTier")
        return tier is AnchorTier.STRONG
