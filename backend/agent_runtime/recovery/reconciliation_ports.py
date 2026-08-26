from __future__ import annotations

from typing import Protocol, runtime_checkable

from backend.agent_runtime.recovery.reconciliation import (
    ApplicationEffectProbeRequest,
    ReconciliationObservation,
    ToolEffectProbeRequest,
)


@runtime_checkable
class ToolEffectProbePort(Protocol):
    def probe(
        self,
        *,
        request: ToolEffectProbeRequest,
    ) -> ReconciliationObservation: ...


@runtime_checkable
class ApplicationEffectProbePort(Protocol):
    def probe(
        self,
        *,
        request: ApplicationEffectProbeRequest,
    ) -> ReconciliationObservation: ...
