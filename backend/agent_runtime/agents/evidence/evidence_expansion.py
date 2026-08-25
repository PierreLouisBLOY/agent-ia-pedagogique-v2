from __future__ import annotations

from dataclasses import dataclass

from backend.agent_runtime.agents.evidence.evidence_expansion_model import (
    BASELINE_EVIDENCE_EXPANSION_POLICY,
    EvidenceExpansionAction,
    EvidenceExpansionDecision,
    EvidenceExpansionError,
    EvidenceExpansionErrorCode,
    EvidenceExpansionHistory,
    EvidenceExpansionNeed,
    EvidenceExpansionPolicy,
    EvidenceExpansionProposal,
    EvidenceRoundRecord,
)
from backend.agent_runtime.agents.evidence.evidence_security_model import (
    EvidenceSecurityAssessment,
    EvidenceSecuritySignalCode,
)


@dataclass(frozen=True, slots=True)
class EvidenceExpansionAdvisor:
    policy: EvidenceExpansionPolicy = BASELINE_EVIDENCE_EXPANSION_POLICY

    def __post_init__(self) -> None:
        if type(self.policy) is not EvidenceExpansionPolicy:
            raise TypeError("policy must be an EvidenceExpansionPolicy")

    def decide(
        self,
        *,
        history: EvidenceExpansionHistory,
        need: EvidenceExpansionNeed,
        security: EvidenceSecurityAssessment,
    ) -> EvidenceExpansionDecision:
        if type(history) is not EvidenceExpansionHistory:
            raise TypeError("history must be an EvidenceExpansionHistory")
        if type(need) is not EvidenceExpansionNeed:
            raise TypeError("need must be an EvidenceExpansionNeed")
        if type(security) is not EvidenceSecurityAssessment:
            raise TypeError("security must be an EvidenceSecurityAssessment")
        current = history.records[-1]
        _validate_security_lineage(current=current, security=security)
        if not need.required:
            return EvidenceExpansionDecision(
                action=EvidenceExpansionAction.NO_EXPANSION,
                current_round=current.round_number,
                proposal=None,
                reason_codes=need.reason_codes or ("EXPANSION_NOT_REQUIRED",),
            )
        if current.round_number >= self.policy.max_rounds:
            return EvidenceExpansionDecision(
                action=EvidenceExpansionAction.STOP_MAX_ROUNDS,
                current_round=current.round_number,
                proposal=None,
                reason_codes=("MAX_EVIDENCE_ROUNDS_REACHED",),
            )
        if current.round_number > 1:
            previous_identities = {
                identity
                for record in history.records[:-1]
                for identity in record.retrieval_identity_keys
            }
            if not any(
                identity not in previous_identities
                for identity in current.retrieval_identity_keys
            ):
                return EvidenceExpansionDecision(
                    action=EvidenceExpansionAction.STOP_NO_PROGRESS,
                    current_round=current.round_number,
                    proposal=None,
                    reason_codes=("NO_NEW_RETRIEVAL_IDENTITIES",),
                )
        if need.next_search_goal == current.request.search_goal:
            return EvidenceExpansionDecision(
                action=EvidenceExpansionAction.STOP_NO_PROGRESS,
                current_round=current.round_number,
                proposal=None,
                reason_codes=("UNCHANGED_SEARCH_GOAL",),
            )
        next_search_goal = need.next_search_goal
        if next_search_goal is None:
            raise ValueError("required expansion must contain a next search goal")

        initial_request = history.records[0].request
        initial_limit = initial_request.max_items
        allowed_max = (
            self.policy.max_items_per_set
            if initial_limit is None
            else min(self.policy.max_items_per_set, initial_limit)
        )
        requested_max = need.requested_max_items
        if requested_max is not None and requested_max > allowed_max:
            raise EvidenceExpansionError(
                EvidenceExpansionErrorCode.MAX_ITEMS_WIDENING,
                "requested item limit exceeds the allowed evidence bound",
            )
        proposal_max = allowed_max if requested_max is None else requested_max
        proposal = EvidenceExpansionProposal(
            next_round_number=current.round_number + 1,
            search_goal=next_search_goal,
            scope=initial_request.scope,
            source_policy=initial_request.source_policy,
            filters=initial_request.filters,
            required_authority=initial_request.required_authority,
            max_items=proposal_max,
            reason_codes=need.reason_codes,
            security_signal_codes=current.security_signal_codes,
        )
        return EvidenceExpansionDecision(
            action=EvidenceExpansionAction.PROPOSE_NEXT_ROUND,
            current_round=current.round_number,
            proposal=proposal,
            reason_codes=need.reason_codes,
        )


def _stable_security_codes(
    security: EvidenceSecurityAssessment,
) -> tuple[EvidenceSecuritySignalCode, ...]:
    codes: list[EvidenceSecuritySignalCode] = []
    for signal in security.signals:
        if signal.code not in codes:
            codes.append(signal.code)
    return tuple(codes)


def _validate_security_lineage(
    *,
    current: EvidenceRoundRecord,
    security: EvidenceSecurityAssessment,
) -> None:
    assessed_evidence_ids: list[str] = []
    for group in security.independent_corroboration_groups:
        for evidence_id in group:
            if evidence_id not in assessed_evidence_ids:
                assessed_evidence_ids.append(evidence_id)
    assessed_codes = _stable_security_codes(security)
    if (
        tuple(assessed_evidence_ids) != current.evidence_ids
        or assessed_codes != current.security_signal_codes
    ):
        raise EvidenceExpansionError(
            EvidenceExpansionErrorCode.SECURITY_ASSESSMENT_LINEAGE_MISMATCH,
            "security assessment does not match the current evidence round",
        )
