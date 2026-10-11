"""Independent technical critic; spend authorization belongs to its composition."""
from collections.abc import Mapping
from typing import Protocol


class P0ReviewPort(Protocol):
    def authorize(self, *, request: Mapping[str, object]) -> bool: ...

    def review(self, *, request: Mapping[str, object]) -> Mapping[str, object]: ...
