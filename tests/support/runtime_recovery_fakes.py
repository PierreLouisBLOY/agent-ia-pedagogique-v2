from __future__ import annotations

from backend.agent_runtime.contracts import StepSpec, ToolCallRequest, UseCaseRequest
from backend.agent_runtime.recovery import (
    CircuitBreakerState,
    EffectLedgerPort,
    EffectLedgerRecord,
    RecoveryReferences,
    RecoveryTechnicalBinding,
)
from backend.agent_runtime.recovery.circuit_breaker_ports import (
    CircuitBreakerStorePort,
)
from backend.agent_runtime.runtime import Plan, RunState


class RecordingRecoveryRuntimeResolver:
    def __init__(self, *, reservation_ttl_seconds: int = 120) -> None:
        self.reservation_ttl_seconds = reservation_ttl_seconds
        self.calls: list[str] = []
        self.target_override: str | None = None
        self.binding_override: str | None = None

    def resolve_tool_recovery(
        self,
        *,
        plan: Plan,
        step: StepSpec,
        run_state: RunState,
        request: ToolCallRequest,
    ) -> RecoveryTechnicalBinding:
        del plan, step, run_state
        self.calls.append("tool")
        return self._binding(request.tool_id, "binding.tool.v1")

    def resolve_application_recovery(
        self,
        *,
        plan: Plan,
        step: StepSpec,
        run_state: RunState,
        request: UseCaseRequest,
    ) -> RecoveryTechnicalBinding:
        del plan, step, run_state
        self.calls.append("application")
        return self._binding(request.use_case_id, "binding.application.v1")

    def resolve_agent_recovery(
        self,
        *,
        plan: Plan,
        step: StepSpec,
        run_state: RunState,
    ) -> RecoveryTechnicalBinding:
        del plan, run_state
        self.calls.append("agent")
        if step.executor.agent_id is None:
            raise ValueError("agent step requires an exact target")
        return self._binding(step.executor.agent_id.value, "binding.agent.v1")

    def _binding(self, target_id: str, default_binding: str) -> RecoveryTechnicalBinding:
        return RecoveryTechnicalBinding(
            target_id=self.target_override or target_id,
            binding_id=self.binding_override or default_binding,
            reservation_ttl_seconds=self.reservation_ttl_seconds,
        )


class PortBackedRecoveryReferenceResolver:
    def __init__(
        self,
        *,
        ledger: EffectLedgerPort,
        circuit_store: CircuitBreakerStorePort,
        record_ids: tuple[str, ...] = (),
        circuit_ids: tuple[str, ...] = (),
    ) -> None:
        self.ledger = ledger
        self.circuit_store = circuit_store
        self.record_ids = record_ids
        self.circuit_ids = circuit_ids

    def resolve_recovery_references(self, *, run_id: str) -> RecoveryReferences:
        records: list[EffectLedgerRecord] = []
        for record_id in self.record_ids:
            record = self.ledger.get(record_id=record_id)
            if record is not None:
                if record.identity.run_id != run_id:
                    raise ValueError("record run mismatch")
                records.append(record)
        circuits: list[CircuitBreakerState] = []
        for circuit_id in self.circuit_ids:
            state = self.circuit_store.get(circuit_id=circuit_id)
            if state is not None:
                circuits.append(state)
        return RecoveryReferences(tuple(records), tuple(circuits))
