"""Read-only technical evidence, independent from validation or quality adoption."""
from collections.abc import Mapping
from typing import Protocol, runtime_checkable


@runtime_checkable
class P0GenerationControlsPort(Protocol):
    def control_evidence(self, *, request: Mapping[str, object], bundle_sha256: str) -> Mapping[str, object]: ...
