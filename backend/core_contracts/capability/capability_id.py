from dataclasses import dataclass

from backend.shared_kernel._strings import require_non_empty


@dataclass(frozen=True, slots=True)
class CapabilityId:
    """An opaque identifier for a capability defined outside this lot."""

    value: str

    def __post_init__(self) -> None:
        require_non_empty(self.value, "value")
