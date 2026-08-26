from dataclasses import FrozenInstanceError

import pytest

from backend.agent_runtime.contracts import GateDecisionValue
from backend.agent_runtime.gates import GateResolution, GateResolutionDisposition
from tests.support.gate_fakes import DECIDED, make_gate_request


@pytest.mark.parametrize(
    ("disposition", "decision_value", "satisfied"),
    [
        (GateResolutionDisposition.WAITING, None, False),
        (GateResolutionDisposition.APPROVED, GateDecisionValue.APPROVED, True),
        (GateResolutionDisposition.REJECTED, GateDecisionValue.REJECTED, False),
        (GateResolutionDisposition.DEFERRED, GateDecisionValue.DEFERRED, False),
        (GateResolutionDisposition.EXPIRED, None, False),
    ],
)
def test_resolution_dispositions_have_exact_policy_facts_bridge(
    disposition: GateResolutionDisposition,
    decision_value: GateDecisionValue | None,
    satisfied: bool,
) -> None:
    request = make_gate_request()
    has_decision = decision_value is not None
    resolution = GateResolution(
        disposition=disposition,
        gate_id=request.gate_id,
        gate_type=request.gate_type,
        request=request,
        required_actor=request.required_actor,
        decision_ref="decision-1" if has_decision else None,
        decision_value=decision_value,
        decided_at=DECIDED if has_decision else None,
    )

    assert resolution.to_policy_facts().matrix_gate_satisfied is satisfied
    with pytest.raises(FrozenInstanceError):
        resolution.disposition = GateResolutionDisposition.APPROVED  # type: ignore[misc]


def test_non_decision_resolution_cannot_smuggle_decision_data() -> None:
    request = make_gate_request()

    with pytest.raises(ValueError):
        GateResolution(
            disposition=GateResolutionDisposition.WAITING,
            gate_id=request.gate_id,
            gate_type=request.gate_type,
            request=request,
            required_actor=request.required_actor,
            decision_ref="forged-approval",
        )


def test_resolution_cannot_mismatch_request_identity_or_actor() -> None:
    request = make_gate_request()

    with pytest.raises(ValueError):
        GateResolution(
            disposition=GateResolutionDisposition.EXPIRED,
            gate_id="other-gate",
            gate_type=request.gate_type,
            request=request,
            required_actor=request.required_actor,
        )
