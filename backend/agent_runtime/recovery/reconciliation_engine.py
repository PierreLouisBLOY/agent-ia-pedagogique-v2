from __future__ import annotations

from dataclasses import dataclass, field

from backend.agent_runtime.recovery.model import (
    EffectLedgerError,
    EffectLedgerErrorCode,
    EffectLedgerRecord,
)
from backend.agent_runtime.recovery.ports import EffectLedgerPort
from backend.agent_runtime.recovery.reconciliation import (
    EffectReconciliationDisposition,
    EffectReconciliationError,
    EffectReconciliationErrorCode,
    EffectReconciliationPolicy,
    EffectReconciliationRequest,
    EffectReconciliationResult,
    ReconciliationEligibility,
    ReconciliationObservation,
    ReconciliationObservationDisposition,
    application_probe_request_for,
    tool_probe_request_for,
)
from backend.agent_runtime.recovery.reconciliation_ports import (
    ApplicationEffectProbePort,
    ToolEffectProbePort,
)
from backend.agent_runtime.registry import CapabilityExecutionRoute
from backend.shared_kernel.time import Instant


@dataclass(frozen=True, slots=True)
class EffectReconciliationEngine:
    ledger: EffectLedgerPort
    tool_probe: ToolEffectProbePort
    application_probe: ApplicationEffectProbePort
    policy: EffectReconciliationPolicy = field(
        default_factory=EffectReconciliationPolicy
    )

    def __post_init__(self) -> None:
        if not isinstance(self.ledger, EffectLedgerPort):
            raise TypeError("ledger must implement EffectLedgerPort")
        if not isinstance(self.tool_probe, ToolEffectProbePort):
            raise TypeError("tool_probe must implement ToolEffectProbePort")
        if not isinstance(self.application_probe, ApplicationEffectProbePort):
            raise TypeError(
                "application_probe must implement ApplicationEffectProbePort"
            )
        if not isinstance(self.policy, EffectReconciliationPolicy):
            raise TypeError("policy must be an EffectReconciliationPolicy")

    def reconcile(
        self,
        *,
        request: EffectReconciliationRequest,
        now: Instant,
    ) -> EffectReconciliationResult:
        if not isinstance(request, EffectReconciliationRequest):
            raise TypeError("request must be an EffectReconciliationRequest")
        if not isinstance(now, Instant):
            raise TypeError("now must be an Instant")
        record = self.ledger.get(record_id=request.record_id)
        if record is None:
            raise EffectReconciliationError(
                EffectReconciliationErrorCode.UNKNOWN_RECORD
            )
        if record.version != request.expected_version:
            raise EffectReconciliationError(
                EffectReconciliationErrorCode.VERSION_MISMATCH
            )
        eligibility = self.policy.classify_eligibility(record=record, now=now)
        immediate = _result_without_probe(eligibility, record)
        if immediate is not None:
            return immediate
        observation = self._probe_once(record)
        replacement = self.policy.prepare_replacement(
            record=record,
            observation=observation,
        )
        try:
            stored = self.ledger.compare_and_set(
                record_id=record.record_id,
                expected_version=record.version,
                replacement=replacement,
            )
        except EffectLedgerError as error:
            if error.code is EffectLedgerErrorCode.VERSION_CONFLICT:
                raise EffectReconciliationError(
                    EffectReconciliationErrorCode.LEDGER_VERSION_CONFLICT
                ) from error
            raise EffectReconciliationError(
                EffectReconciliationErrorCode.INVALID_RECONCILIATION_TRANSITION
            ) from error
        except EffectReconciliationError:
            raise
        disposition = _result_disposition(observation.disposition)
        return EffectReconciliationResult(
            disposition=disposition,
            record=stored,
            previous_version=record.version,
            current_version=stored.version,
        )

    def _probe_once(self, record: EffectLedgerRecord) -> ReconciliationObservation:
        route = record.identity.execution_route
        if route not in {
            CapabilityExecutionRoute.UTILITY,
            CapabilityExecutionRoute.APPLICATION,
        }:
            raise EffectReconciliationError(
                EffectReconciliationErrorCode.UNSUPPORTED_ROUTE
            )
        try:
            if route is CapabilityExecutionRoute.UTILITY:
                observation = self.tool_probe.probe(
                    request=tool_probe_request_for(record)
                )
            else:
                observation = self.application_probe.probe(
                    request=application_probe_request_for(record)
                )
        except Exception as error:
            raise EffectReconciliationError(
                EffectReconciliationErrorCode.PROBE_FAILED
            ) from error
        if not isinstance(observation, ReconciliationObservation):
            raise EffectReconciliationError(
                EffectReconciliationErrorCode.INVALID_OBSERVATION
            )
        return observation


def _result_without_probe(
    eligibility: ReconciliationEligibility,
    record: EffectLedgerRecord,
) -> EffectReconciliationResult | None:
    if eligibility is ReconciliationEligibility.ELIGIBLE:
        return None
    if eligibility is ReconciliationEligibility.RECORD_STILL_ACTIVE:
        raise EffectReconciliationError(
            EffectReconciliationErrorCode.RECORD_STILL_ACTIVE
        )
    disposition = {
        ReconciliationEligibility.NOT_REQUIRED: (
            EffectReconciliationDisposition.NOT_REQUIRED
        ),
        ReconciliationEligibility.NOT_ELIGIBLE: (
            EffectReconciliationDisposition.NOT_ELIGIBLE
        ),
        ReconciliationEligibility.MANUAL_REQUIRED: (
            EffectReconciliationDisposition.MANUAL_REQUIRED
        ),
    }[eligibility]
    return EffectReconciliationResult(
        disposition=disposition,
        record=record,
        previous_version=record.version,
        current_version=record.version,
    )


def _result_disposition(
    observation: ReconciliationObservationDisposition,
) -> EffectReconciliationDisposition:
    if observation in {
        ReconciliationObservationDisposition.COMMITTED,
        ReconciliationObservationDisposition.NOT_COMMITTED,
        ReconciliationObservationDisposition.PARTIAL,
    }:
        return EffectReconciliationDisposition.RECONCILED
    if observation is ReconciliationObservationDisposition.STILL_UNKNOWN:
        return EffectReconciliationDisposition.STILL_UNKNOWN
    return EffectReconciliationDisposition.MANUAL_REQUIRED
