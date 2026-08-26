from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass

from backend.agent_runtime.contracts import (
    ContractMeta,
    GateDecision,
    GateDecisionValue,
    GateRequest,
)
from backend.agent_runtime.contracts.common import (
    freeze_agent_safe_mapping,
    require_contract_ref,
)
from backend.agent_runtime.gates.authority import GateAuthorityPolicy
from backend.agent_runtime.gates.model import (
    GateEngineError,
    GateEngineErrorCode,
    GateResolution,
    GateResolutionDisposition,
)
from backend.agent_runtime.gates.ports import GateDecisionSourcePort
from backend.shared_kernel.time import Instant

_DISPOSITION_BY_DECISION = {
    GateDecisionValue.APPROVED: GateResolutionDisposition.APPROVED,
    GateDecisionValue.REJECTED: GateResolutionDisposition.REJECTED,
    GateDecisionValue.DEFERRED: GateResolutionDisposition.DEFERRED,
}
_FORBIDDEN_AUTHORITY_KEYS = frozenset(
    {
        "authority",
        "authority_override",
        "authority_policy",
        "capability_id",
        "expires_at",
        "gate_id",
        "handler",
        "matrix_gate_satisfied",
        "permission",
        "policy_facts",
        "promotion_allowed",
        "required_actor",
    }
)
_FORBIDDEN_AUTHORITY_KEYS_COMPACT = frozenset(
    key.replace("_", "") for key in _FORBIDDEN_AUTHORITY_KEYS
)


@dataclass(frozen=True, slots=True)
class GateEngine:
    authority_policy: GateAuthorityPolicy
    decision_source: GateDecisionSourcePort

    def __post_init__(self) -> None:
        if not isinstance(self.authority_policy, GateAuthorityPolicy):
            raise TypeError("authority_policy must be a GateAuthorityPolicy")
        if not isinstance(self.decision_source, GateDecisionSourcePort):
            raise TypeError("decision_source must implement GateDecisionSourcePort")

    def evaluate(self, *, request: GateRequest, now: Instant) -> GateResolution:
        canonical_request = _reconstruct_request(request)
        try:
            canonical_now = Instant(now.value)
        except (AttributeError, TypeError, ValueError):
            raise GateEngineError(
                GateEngineErrorCode.INVALID_GATE_REQUEST
            ) from None
        if not self.authority_policy.allows(canonical_request.required_actor):
            raise GateEngineError(GateEngineErrorCode.AUTHORITY_NOT_ALLOWED)
        if _is_expired(canonical_request, canonical_now):
            return _resolution(
                GateResolutionDisposition.EXPIRED,
                canonical_request,
            )

        try:
            candidate = self.decision_source.receive(request=canonical_request)
        except Exception:
            raise GateEngineError(
                GateEngineErrorCode.DECISION_SOURCE_FAILED
            ) from None
        if candidate is None:
            return _resolution(
                GateResolutionDisposition.WAITING,
                canonical_request,
            )
        decision = _reconstruct_and_validate_decision(
            candidate,
            canonical_request,
            canonical_now,
            self.authority_policy,
        )
        if _is_expired(canonical_request, canonical_now):
            return _resolution(
                GateResolutionDisposition.EXPIRED,
                canonical_request,
            )
        return _resolution(
            _DISPOSITION_BY_DECISION[decision.decision],
            canonical_request,
            decision=decision,
        )


def _reconstruct_request(candidate: object) -> GateRequest:
    if type(candidate) is not GateRequest:
        raise GateEngineError(GateEngineErrorCode.INVALID_GATE_REQUEST)
    try:
        meta = _reconstruct_meta(candidate.meta)
        request = GateRequest(
            meta=meta,
            gate_id=candidate.gate_id,
            gate_type=candidate.gate_type,
            reason=candidate.reason,
            options=candidate.options,
            required_actor=candidate.required_actor,
            context_summary=candidate.context_summary,
            expires_at=candidate.expires_at,
        )
        if _contains_authority_metadata(request.options) or _contains_authority_metadata(
            request.context_summary
        ):
            raise ValueError("authority metadata")
        return request
    except GateEngineError:
        raise
    except (AttributeError, TypeError, ValueError):
        raise GateEngineError(GateEngineErrorCode.INVALID_GATE_REQUEST) from None


def _reconstruct_and_validate_decision(
    candidate: object,
    request: GateRequest,
    now: Instant,
    authority_policy: GateAuthorityPolicy,
) -> GateDecision:
    if type(candidate) is not GateDecision:
        raise GateEngineError(GateEngineErrorCode.INVALID_GATE_DECISION)
    try:
        if candidate.request != request:
            raise GateEngineError(
                GateEngineErrorCode.DECISION_REQUEST_MISMATCH
            )
        if candidate.gate_id != request.gate_id:
            raise GateEngineError(GateEngineErrorCode.DECISION_GATE_MISMATCH)
        if (
            candidate.actor != request.required_actor
            or candidate.meta.actor != candidate.actor
            or not authority_policy.allows(candidate.actor)
        ):
            raise GateEngineError(GateEngineErrorCode.DECISION_ACTOR_MISMATCH)
        if candidate.meta.run_id != request.meta.run_id:
            raise GateEngineError(GateEngineErrorCode.DECISION_RUN_MISMATCH)
        if candidate.meta.step_id != request.meta.step_id:
            raise GateEngineError(GateEngineErrorCode.DECISION_STEP_MISMATCH)
        if candidate.meta.correlation_id != request.meta.correlation_id:
            raise GateEngineError(
                GateEngineErrorCode.DECISION_CORRELATION_MISMATCH
            )
        try:
            decided_at = Instant(candidate.decided_at.value)
        except (AttributeError, TypeError, ValueError):
            raise GateEngineError(
                GateEngineErrorCode.INVALID_GATE_DECISION
            ) from None
        if decided_at.value > now.value:
            raise GateEngineError(GateEngineErrorCode.DECISION_FROM_FUTURE)
        _validate_decision_ref(candidate.decision_ref)
        selected_option = _validate_selected_option(
            candidate.selected_option,
            request.options,
        )
        decision_request = _reconstruct_request(candidate.request)
        decision = GateDecision(
            meta=_reconstruct_meta(candidate.meta),
            gate_id=candidate.gate_id,
            decision=candidate.decision,
            actor=candidate.actor,
            decided_at=decided_at,
            decision_ref=candidate.decision_ref,
            request=decision_request,
            selected_option=selected_option,
            comment=candidate.comment,
        )
        if decision.request != request:
            raise GateEngineError(
                GateEngineErrorCode.DECISION_REQUEST_MISMATCH
            )
        return decision
    except GateEngineError:
        raise
    except (AttributeError, TypeError, ValueError):
        raise GateEngineError(GateEngineErrorCode.INVALID_GATE_DECISION) from None


def _reconstruct_meta[TStatus](
    candidate: ContractMeta[TStatus],
) -> ContractMeta[TStatus]:
    if type(candidate) is not ContractMeta:
        raise TypeError("invalid metadata")
    return ContractMeta(
        schema_version=candidate.schema_version,
        run_id=candidate.run_id,
        step_id=candidate.step_id,
        parent_step_id=candidate.parent_step_id,
        correlation_id=candidate.correlation_id,
        created_at=candidate.created_at,
        actor=candidate.actor,
        status=candidate.status,
        trace_flags=candidate.trace_flags,
    )


def _validate_decision_ref(decision_ref: object) -> None:
    try:
        require_contract_ref(decision_ref, "decision_ref")  # type: ignore[arg-type]
    except (TypeError, ValueError):
        raise GateEngineError(GateEngineErrorCode.INVALID_DECISION_REF) from None


def _validate_selected_option(
    candidate: object,
    options: tuple[Mapping[str, object], ...],
) -> Mapping[str, object] | None:
    if candidate is None:
        return None
    if not isinstance(candidate, Mapping) or not options:
        raise GateEngineError(GateEngineErrorCode.INVALID_SELECTED_OPTION)
    try:
        selected = freeze_agent_safe_mapping(candidate)
    except (TypeError, ValueError):
        raise GateEngineError(GateEngineErrorCode.INVALID_SELECTED_OPTION) from None
    if not any(selected == option for option in options):
        raise GateEngineError(GateEngineErrorCode.INVALID_SELECTED_OPTION)
    return selected


def _is_expired(request: GateRequest, now: Instant) -> bool:
    return request.expires_at is not None and now.value > request.expires_at.value


def _resolution(
    disposition: GateResolutionDisposition,
    request: GateRequest,
    *,
    decision: GateDecision | None = None,
) -> GateResolution:
    return GateResolution(
        disposition=disposition,
        gate_id=request.gate_id,
        gate_type=request.gate_type,
        request=request,
        required_actor=request.required_actor,
        decision_ref=(decision.decision_ref if decision is not None else None),
        decision_value=(decision.decision if decision is not None else None),
        decided_at=(decision.decided_at if decision is not None else None),
        selected_option=(decision.selected_option if decision is not None else None),
    )


def _contains_authority_metadata(value: object) -> bool:
    if isinstance(value, Mapping):
        for key, nested in value.items():
            normalized = _normalize_key(key)
            if (
                normalized in _FORBIDDEN_AUTHORITY_KEYS
                or normalized.replace("_", "") in _FORBIDDEN_AUTHORITY_KEYS_COMPACT
                or _contains_authority_metadata(nested)
            ):
                return True
        return False
    if isinstance(value, tuple):
        return any(_contains_authority_metadata(item) for item in value)
    return False


def _normalize_key(key: str) -> str:
    characters: list[str] = []
    for character in key:
        if character.isupper() and characters and characters[-1] != "_":
            characters.append("_")
        characters.append(character.casefold() if character.isalnum() else "_")
    return "_".join(part for part in "".join(characters).split("_") if part)
