from enum import Enum


class EvaluationVerdict(Enum):
    """Offline finding only; no member grants runtime or domain authority."""

    PASS = "PASS"
    FAIL = "FAIL"
    INCONCLUSIVE = "INCONCLUSIVE"
    ERROR = "ERROR"
    SKIPPED = "SKIPPED"
