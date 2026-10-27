"""Read-only financial origin metadata; no disposition or authority is created."""

from collections.abc import Mapping
from typing import Protocol


class FiniteOriginReadPort(Protocol):
    def inspect_readonly(self) -> Mapping[str, object]: ...


class ReadFiniteOrigin:
    def __init__(self, port: FiniteOriginReadPort) -> None:
        self.port = port

    def execute(self) -> Mapping[str, object]:
        data = self.port.inspect_readonly()
        slots = data.get("slots")
        if (
            data.get("schema") != "P0-FINITE-ORIGIN-OBSERVATION-1.0"
            or data.get("authority") != "NONE"
            or data.get("historical_writes") != 0
            or not isinstance(slots, list)
            or len(slots) > 14
        ):
            raise ValueError("P0_CHAIN_ORIGIN_METADATA_CONTRACT")
        return data
