from dataclasses import dataclass

from backend.shared_kernel._strings import require_non_empty


@dataclass(frozen=True, slots=True)
class CorrelationId:
    """An opaque identifier linking related application activity."""

    value: str

    def __post_init__(self) -> None:
        require_non_empty(self.value, "value")
