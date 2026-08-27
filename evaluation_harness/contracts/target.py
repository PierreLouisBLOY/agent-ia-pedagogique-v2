from dataclasses import dataclass
from enum import Enum

from evaluation_harness.contracts.identity import EvaluationTargetCode


class EvaluationTargetKind(Enum):
    SYSTEM = "SYSTEM"
    WORKFLOW = "WORKFLOW"
    AGENT = "AGENT"
    PIPELINE = "PIPELINE"
    BOUNDARY = "BOUNDARY"
    COMPONENT = "COMPONENT"


@dataclass(frozen=True, slots=True)
class EvaluationTargetRef:
    """Opaque target coordinate with no lookup or execution behavior."""

    kind: EvaluationTargetKind
    code: EvaluationTargetCode

    def __post_init__(self) -> None:
        if not isinstance(self.kind, EvaluationTargetKind):
            raise TypeError("kind must be an EvaluationTargetKind")
        if not isinstance(self.code, EvaluationTargetCode):
            raise TypeError("code must be an EvaluationTargetCode")
