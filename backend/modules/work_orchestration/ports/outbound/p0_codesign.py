"""Application-owned co-design boundary; no agent/runtime/provider types."""
from collections.abc import Callable, Mapping
from typing import Protocol


class P0CoDesignInterrupted(Exception):
    def __init__(self, *, state: str, trace: Mapping[str, object]) -> None:
        if state not in {"BLOCKED", "OUTCOME_UNKNOWN"}:
            raise ValueError("P0_CODESIGN_INTERRUPTION_STATE")
        self.state, self.trace = state, trace
        super().__init__("P0_CODESIGN_INTERRUPTED")


class P0CoDesignPort(Protocol):
    def authorize_chain(self, *, request: Mapping[str, object]) -> bool: ...

    def run(self, *, request: Mapping[str, object],
            validate_variant: Callable[[Mapping[str, object]], Mapping[str, object]],
            validate_review: Callable[[Mapping[str, object]], None]) -> Mapping[str, object]: ...
