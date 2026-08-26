from __future__ import annotations

from typing import Protocol, runtime_checkable

from backend.agent_runtime.contracts import GateDecision, GateRequest


@runtime_checkable
class GateDecisionSourcePort(Protocol):
    def receive(self, *, request: GateRequest) -> GateDecision | None:
        ...
