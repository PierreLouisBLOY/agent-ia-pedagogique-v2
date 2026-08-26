from __future__ import annotations

from collections.abc import Callable
from dataclasses import replace

from backend.agent_runtime.contracts import ActorKind, ActorRef, ContractRef, EffectState
from backend.agent_runtime.recovery import (
    ApplicationEffectProbeRequest,
    EffectLedgerRecord,
    IdempotencyIdentity,
    IdempotencyKeyFingerprint,
    IdempotencyPolicy,
    IntentFingerprint,
    ReconciliationObservation,
    ReconciliationStatus,
    ToolEffectProbeRequest,
)
from backend.agent_runtime.registry import CapabilityExecutionRoute
from backend.core_contracts.capability import CapabilityId
from backend.shared_kernel.time import Instant


class RecordingToolEffectProbe:
    def __init__(
        self,
        observation: ReconciliationObservation,
        *,
        error: Exception | None = None,
        on_probe: Callable[[], None] | None = None,
    ) -> None:
        self._observation = observation
        self._error = error
        self._on_probe = on_probe
        self.calls: list[ToolEffectProbeRequest] = []

    def probe(
        self,
        *,
        request: ToolEffectProbeRequest,
    ) -> ReconciliationObservation:
        self.calls.append(request)
        if self._on_probe is not None:
            self._on_probe()
        if self._error is not None:
            raise self._error
        return self._observation


class RecordingApplicationEffectProbe:
    def __init__(
        self,
        observation: ReconciliationObservation,
        *,
        error: Exception | None = None,
        on_probe: Callable[[], None] | None = None,
    ) -> None:
        self._observation = observation
        self._error = error
        self._on_probe = on_probe
        self.calls: list[ApplicationEffectProbeRequest] = []

    def probe(
        self,
        *,
        request: ApplicationEffectProbeRequest,
    ) -> ReconciliationObservation:
        self.calls.append(request)
        if self._on_probe is not None:
            self._on_probe()
        if self._error is not None:
            raise self._error
        return self._observation


def make_identity(
    route: CapabilityExecutionRoute,
    *,
    target_id: str | None = None,
) -> IdempotencyIdentity:
    targets = {
        CapabilityExecutionRoute.UTILITY: "tool.render_document",
        CapabilityExecutionRoute.APPLICATION: "application.export_artifact",
        CapabilityExecutionRoute.AGENT: "agent.generate",
        CapabilityExecutionRoute.RUNTIME: "runtime.plan",
    }
    return IdempotencyIdentity(
        principal=ActorRef(ActorKind.AGENT, "AG-03"),
        run_id="run-reconcile",
        step_id="step-reconcile",
        capability_id=CapabilityId("CAP-REC"),
        execution_route=route,
        target_id=target_id or targets[route],
        operation="observe_effect",
        intent_fingerprint=IntentFingerprint.from_value("canonical intent"),
        caller_key_fingerprint=IdempotencyKeyFingerprint.from_key("caller-key"),
    )


def make_in_progress_record(
    *,
    route: CapabilityExecutionRoute,
    created_at: Instant,
    expires_at: Instant,
) -> EffectLedgerRecord:
    policy = IdempotencyPolicy()
    reserved = policy.new_reservation(
        identity=make_identity(route),
        now=created_at,
        reservation_expires_at=expires_at,
    )
    return policy.prepare_start(record=reserved, attempt=1, now=created_at)


def make_finalized_record(
    *,
    route: CapabilityExecutionRoute,
    effect_state: EffectState,
    created_at: Instant,
    expires_at: Instant,
    finalized_at: Instant,
    reconciliation_status: ReconciliationStatus | None = None,
    result_refs: tuple[ContractRef, ...] = (),
) -> EffectLedgerRecord:
    policy = IdempotencyPolicy()
    in_progress = make_in_progress_record(
        route=route,
        created_at=created_at,
        expires_at=expires_at,
    )
    finalized = policy.prepare_finalize(
        record=in_progress,
        effect_state=effect_state,
        now=finalized_at,
        result_refs=result_refs,
    )
    if reconciliation_status is not None:
        finalized = replace(
            finalized,
            reconciliation_status=reconciliation_status,
        )
    return finalized
