from __future__ import annotations

from dataclasses import replace

import pytest

from backend.agent_runtime.contracts import (
    AGENT_CONTRACT_SCHEMA_V1_0,
    ActorKind,
    ActorRef,
    AgentId,
    ContentThreatSignalCode,
    EffectState,
    GateDecisionValue,
    SamplingDecision,
    SecurityBoundary,
    SpanId,
    TraceId,
)
from backend.agent_runtime.gates import (
    BASELINE_GATE_AUTHORITY_POLICY,
    GateEngine,
    GateEngineError,
    GateEngineErrorCode,
    GateResolutionDisposition,
)
from backend.agent_runtime.observability import (
    RuntimeObservationEmitter,
    TraceContextPolicy,
)
from backend.agent_runtime.recovery import (
    EffectReconciliationError,
    EffectReconciliationErrorCode,
    EffectReconciliationPolicy,
    ReconciliationObservation,
    ReconciliationObservationDisposition,
    ReconciliationStatus,
    ReplayGuard,
    ReplayGuardDisposition,
    RetryDisposition,
    RetryPolicy,
    RetryPolicyRequest,
)
from backend.agent_runtime.security import (
    AgentHandoffSecurityError,
    AgentHandoffSecurityErrorCode,
    SensitiveValuePolicy,
    SensitiveValueRejected,
    security_event_from_sensitive_value_rejection,
)
from backend.core_contracts.capability import CapabilityId
from backend.shared_kernel.correlation import CorrelationId
from tests.e2e.core.generation_adapters import run_human_gate_sequence
from tests.e2e.core.transverse_adapters import (
    F_NOW,
    F_OBSERVED,
    SafeTransverseReport,
    effect_record,
    fixture,
    no_reconciliation_variant,
    observe_scn06,
    observe_scn08,
    promotion_identity,
    reconcile_promotion,
    retry_for_none,
    run_exfiltration_variant,
    run_fake_gate_text,
    run_scn02_hostile_evidence,
    run_scn03_authority_smuggling,
)
from tests.support.gate_fakes import (
    NOW as GATE_NOW,
)
from tests.support.gate_fakes import (
    RecordingGateDecisionSource,
    forge_gate_decision,
    make_gate_decision,
    make_gate_request,
)
from tests.support.multi_agent_security_fixtures import (
    result as handoff_result,
)
from tests.support.multi_agent_security_fixtures import (
    secure_handoff,
)
from tests.support.retry_replay_fakes import (
    NOW as RETRY_NOW,
)
from tests.support.retry_replay_fakes import (
    make_budget_check,
    make_budget_state,
    make_error,
    make_preconditions,
)
from tests.support.runtime_observability_fakes import (
    AdvancingObservationClock,
    CollectingLogSink,
    CollectingMetricSink,
    CollectingTraceSink,
    DeterministicObservationProvider,
)
from tests.support.synthetic_secret_fixtures import fake_api_credential


def test_scn02_hostile_evidence_remains_non_authoritative_data() -> None:
    witness = run_scn02_hostile_evidence()
    codes = {signal.code for signal in witness.assessment.signals}

    assert ContentThreatSignalCode.INSTRUCTION_LIKE_CONTENT in codes
    assert ContentThreatSignalCode.AUTHORITY_CLAIM_TEXT in codes
    assert witness.assessment.document_instructions_authoritative is False
    assert witness.assessment.external_actions_allowed is False
    assert witness.assessment.links_followed is False
    assert witness.search_call_count == 4
    assert witness.content_call_count == 1
    assert witness.gate_decision_count == 0
    assert witness.application_call_count == 0
    assert witness.external_action_count == witness.link_follow_count == 0


def test_scn03_marker_crosses_ag03_guard_only_as_candidate_data() -> None:
    witness = run_scn03_authority_smuggling()

    assert witness.generation_call_count == 1
    assert witness.candidate.validation_state.value == "candidate"
    assert witness.candidate.lineage["capability_id"] == "CAP-G01"
    assert witness.gate_decision_count == 0
    assert witness.promotion_call_count == 0
    assert witness.permission_scope_changed is False
    assert "CAP-A02" not in witness.candidate.lineage.values()


def test_scn05_fake_approved_text_cannot_approve_gate() -> None:
    resolution = run_fake_gate_text()

    assert resolution.disposition is GateResolutionDisposition.WAITING
    assert resolution.decision_ref is None
    assert resolution.to_policy_facts().matrix_gate_satisfied is False


def test_scn05_valid_external_decision_is_the_only_approval_owner() -> None:
    witness = run_human_gate_sequence(GateDecisionValue.APPROVED)

    assert witness.resolution.disposition is GateResolutionDisposition.APPROVED
    assert witness.source_call_count == 1
    assert witness.continuation_count == 1


@pytest.mark.parametrize("mutation", ("actor", "run", "step", "correlation"))
def test_scn05_wrong_external_decision_lineage_fails_closed(mutation: str) -> None:
    request = make_gate_request()
    decision = make_gate_decision(request)
    if mutation == "actor":
        forged = forge_gate_decision(
            decision,
            actor=ActorRef(ActorKind.USER, "wrong-user"),
        )
    else:
        meta = decision.meta
        if mutation == "run":
            meta = replace(meta, run_id="wrong-run")
        elif mutation == "step":
            meta = replace(meta, step_id="wrong-step")
        else:
            from backend.shared_kernel.correlation import CorrelationId

            meta = replace(meta, correlation_id=CorrelationId("wrong-correlation"))
        forged = forge_gate_decision(decision, meta=meta)

    with pytest.raises(GateEngineError) as raised:
        GateEngine(
            BASELINE_GATE_AUTHORITY_POLICY,
            RecordingGateDecisionSource(forged),
        ).evaluate(request=request, now=GATE_NOW)

    assert raised.value.code in {
        GateEngineErrorCode.DECISION_ACTOR_MISMATCH,
        GateEngineErrorCode.DECISION_RUN_MISMATCH,
        GateEngineErrorCode.DECISION_STEP_MISMATCH,
        GateEngineErrorCode.DECISION_CORRELATION_MISMATCH,
    }


def test_scn08_exfiltration_sentinel_never_crosses_sensitive_boundary() -> None:
    sentinel = fake_api_credential()
    witness = run_exfiltration_variant(sentinel)

    assert "EXFILTRATION_TEXT" in witness.threat_codes
    assert witness.sentinel_rejected is True
    assert witness.rejection_code == "CREDENTIAL_LIKE"
    assert witness.network_call_count == witness.link_follow_count == 0
    assert witness.tool_call_count == witness.application_call_count == 0
    assert sentinel not in repr(witness)


@pytest.mark.parametrize(
    "key",
    (
        "authority_override",
        "permission",
        "promotion_allowed",
        "capability_id",
        "gate_id",
        "required_actor",
    ),
)
def test_nested_structural_authority_keys_fail_closed_at_gate_owner(key: str) -> None:
    request = make_gate_request(context_summary={"data": {key: "forged"}})
    source = RecordingGateDecisionSource(None)

    with pytest.raises(GateEngineError) as raised:
        GateEngine(BASELINE_GATE_AUTHORITY_POLICY, source).evaluate(
            request=request,
            now=GATE_NOW,
        )

    assert raised.value.code is GateEngineErrorCode.INVALID_GATE_REQUEST
    assert source.calls == []


@pytest.mark.parametrize(
    "payload",
    (
        {"destination": {"capability_id": "CAP-A02"}},
        {"review_finding": {"permission": "granted"}},
        {"gateDecision": "APPROVED"},
    ),
)
def test_multi_agent_output_cannot_escalate_authority(payload: dict[str, object]) -> None:
    with pytest.raises(AgentHandoffSecurityError) as raised:
        secure_handoff(produced=handoff_result(payload=payload))

    assert raised.value.code is AgentHandoffSecurityErrorCode.AUTHORITY_METADATA_FORBIDDEN


@pytest.mark.parametrize(
    ("observation", "state", "status", "after"),
    (
        (
            ReconciliationObservationDisposition.COMMITTED,
            EffectState.COMMITTED,
            ReconciliationStatus.RESOLVED,
            ReplayGuardDisposition.BLOCKED,
        ),
        (
            ReconciliationObservationDisposition.NOT_COMMITTED,
            EffectState.NONE,
            ReconciliationStatus.RESOLVED,
            ReplayGuardDisposition.ELIGIBLE,
        ),
        (
            ReconciliationObservationDisposition.STILL_UNKNOWN,
            EffectState.UNKNOWN,
            ReconciliationStatus.PENDING,
            ReplayGuardDisposition.RECONCILE_FIRST,
        ),
        (
            ReconciliationObservationDisposition.MANUAL_REQUIRED,
            EffectState.UNKNOWN,
            ReconciliationStatus.MANUAL_REQUIRED,
            ReplayGuardDisposition.MANUAL_REQUIRED,
        ),
    ),
)
def test_unknown_promotion_effect_reconciles_before_any_replay(
    observation: ReconciliationObservationDisposition,
    state: EffectState,
    status: ReconciliationStatus,
    after: ReplayGuardDisposition,
) -> None:
    witness = reconcile_promotion(observation)

    assert witness.initial_record.effect_state is EffectState.UNKNOWN
    assert witness.replay_before.disposition is ReplayGuardDisposition.RECONCILE_FIRST
    assert witness.executor_call_count == 0
    assert witness.record.effect_state is state
    assert witness.record.reconciliation_status is status
    assert witness.replay_after.disposition is after
    assert witness.probe_call_count == 1


def test_committed_promotion_effect_never_probes_or_replays() -> None:
    witness = no_reconciliation_variant(EffectState.COMMITTED)

    assert witness.reconciliation_disposition == "NOT_REQUIRED"
    assert witness.replay_before.disposition is ReplayGuardDisposition.BLOCKED
    assert witness.probe_call_count == 0
    assert witness.executor_call_count == 0


def test_partial_promotion_effect_never_automatically_retries() -> None:
    record = effect_record(EffectState.PARTIAL)
    replay = ReplayGuard().evaluate(
        record=record,
        preconditions=make_preconditions(identity=record.identity),
    )
    budget = replace(make_budget_state(), run_id=record.identity.run_id)
    decision = RetryPolicy().decide(
        RetryPolicyRequest(
            error=make_error(
                attempt=record.attempt,
                effect_state=EffectState.PARTIAL,
                step_id=record.identity.step_id,
            ),
            record=record,
            budget_state=budget,
            budget_check=make_budget_check(),
            replay_decision=replay,
            now=RETRY_NOW,
        )
    )

    assert replay.disposition is ReplayGuardDisposition.RECONCILE_FIRST
    assert decision.disposition is RetryDisposition.STOP


def test_none_retry_is_allowed_only_under_canonical_policy_and_budget() -> None:
    allowed = retry_for_none()
    denied = retry_for_none(budget_exhausted=True)

    assert allowed.disposition is RetryDisposition.RETRY
    assert denied.disposition is RetryDisposition.NO_RETRY


def test_promotion_effect_identity_is_stable_and_intent_sensitive() -> None:
    first = promotion_identity()
    same = promotion_identity()
    changed = promotion_identity("production_ref=qcm-candidate:scn-08:1")

    assert first == same
    assert first.record_id == same.record_id
    assert first.caller_key_fingerprint == same.caller_key_fingerprint
    assert changed.intent_fingerprint != first.intent_fingerprint
    assert changed.record_id != first.record_id
    assert changed.caller_key_fingerprint == first.caller_key_fingerprint


@pytest.mark.parametrize(
    "field",
    ("principal", "run_id", "step_id", "capability_id", "target_id", "intent"),
)
def test_replay_identity_mismatches_fail_closed(field: str) -> None:
    record = effect_record(EffectState.NONE)
    identity = record.identity
    if field == "principal":
        requested = replace(
            identity,
            principal=ActorRef(ActorKind.AGENT, AgentId.AG_03.value),
        )
    elif field == "run_id":
        requested = replace(identity, run_id="wrong-run")
    elif field == "step_id":
        requested = replace(identity, step_id="wrong-step")
    elif field == "capability_id":
        requested = replace(identity, capability_id=CapabilityId("CAP-A03"))
    elif field == "target_id":
        requested = replace(identity, target_id="application.export_artifact")
    else:
        requested = promotion_identity("production_ref=wrong")

    decision = ReplayGuard().evaluate(
        record=record,
        preconditions=make_preconditions(identity=requested),
    )

    assert decision.disposition is ReplayGuardDisposition.REPLAN_REQUIRED
    assert decision.reason_codes[0].value == "IDENTITY_MISMATCH"


@pytest.mark.parametrize(
    ("field", "code"),
    (
        ("record", EffectReconciliationErrorCode.OBSERVATION_RECORD_MISMATCH),
        ("version", EffectReconciliationErrorCode.OBSERVATION_VERSION_MISMATCH),
        ("attempt", EffectReconciliationErrorCode.OBSERVATION_ATTEMPT_MISMATCH),
    ),
)
def test_reconciliation_observation_mismatches_use_closed_errors(
    field: str,
    code: EffectReconciliationErrorCode,
) -> None:
    record = effect_record(EffectState.UNKNOWN)
    other = promotion_identity("production_ref=other")
    observation = ReconciliationObservation(
        other.record_id if field == "record" else record.record_id,
        record.version + 1 if field == "version" else record.version,
        record.attempt + 1 if field == "attempt" else record.attempt,
        ReconciliationObservationDisposition.NOT_COMMITTED,
        (),
        F_OBSERVED,
    )

    with pytest.raises(EffectReconciliationError) as raised:
        EffectReconciliationPolicy().validate_observation(
            record=record,
            observation=observation,
        )

    assert raised.value.code is code


def test_stale_reconciliation_compare_and_set_fails_closed() -> None:
    record = effect_record(EffectState.UNKNOWN)
    observation = ReconciliationObservation(
        record.record_id,
        record.version,
        record.attempt,
        ReconciliationObservationDisposition.NOT_COMMITTED,
        (),
        F_OBSERVED,
    )
    policy = EffectReconciliationPolicy()
    replacement = policy.prepare_replacement(record=record, observation=observation)

    with pytest.raises(EffectReconciliationError) as raised:
        policy.validate_compare_and_set(
            current=record,
            expected_version=record.version - 1,
            replacement=replacement,
        )

    assert raised.value.code is EffectReconciliationErrorCode.LEDGER_VERSION_CONFLICT


def test_scn06_observability_enabled_disabled_and_failing_are_equivalent() -> None:
    disabled = observe_scn06("disabled")
    enabled = observe_scn06("enabled")
    failing = observe_scn06("failing")

    assert enabled.projection == disabled.projection == failing.projection
    assert enabled.projection.evaluation_verdict == "PASS"
    assert enabled.projection.hard_assertion_verdicts is True
    assert len(enabled.trace_records) == 1
    assert disabled.trace_records == failing.trace_records == ()


def test_scn08_observability_cannot_change_gate_effect_or_evaluation() -> None:
    disabled = observe_scn08("disabled")
    enabled = observe_scn08("enabled")
    failing = observe_scn08("failing")

    assert enabled.projection == disabled.projection == failing.projection
    assert enabled.projection.gate_disposition == "APPROVED"
    assert enabled.projection.promotion_route_call_count == 1
    assert enabled.projection.render_effect_count == 0
    assert enabled.projection.evaluation_verdict == "PASS"


def test_enabled_observability_records_are_minimized_and_raw_free() -> None:
    raw_values = tuple(source.text for source in fixture("SCN-08").sources)
    raw_values += (fake_api_credential(), "Synthetic output", "C:\\Users\\")
    enabled = observe_scn08("enabled")
    serialized = repr(enabled.trace_records)

    assert enabled.log_records == enabled.metric_records == ()
    assert len(enabled.trace_records) == 1
    assert all(raw not in serialized for raw in raw_values)
    assert "scenario_code" in serialized
    assert "verdict" in serialized


def test_security_log_and_metric_mapping_exclude_sentinel_and_raw_metadata() -> None:
    sentinel = fake_api_credential()
    with pytest.raises(SensitiveValueRejected) as raised:
        SensitiveValuePolicy().require_safe(
            {"payload": sentinel},
            root_location="security_test",
        )
    event = security_event_from_sensitive_value_rejection(
        raised.value,
        schema_version=AGENT_CONTRACT_SCHEMA_V1_0,
        event_id="security-event-f",
        occurred_at=F_NOW,
        run_id="run-f-security",
        correlation_id=CorrelationId("corr-f-security"),
        boundary=SecurityBoundary.AGENT,
        exfiltration_requested=True,
    )
    logs, traces, metrics = CollectingLogSink(), CollectingTraceSink(), CollectingMetricSink()
    emitter = RuntimeObservationEmitter(
        logs,
        traces,
        metrics,
        DeterministicObservationProvider(prefix="security-f"),
        AdvancingObservationClock(F_NOW),
    )
    trace = TraceContextPolicy().root(
        trace_id=TraceId("trace-security-f"),
        span_id=SpanId("span-security-f"),
        sampling_decision=SamplingDecision.RECORD_AND_SAMPLE,
    )
    emitter.observe_security_event(event, trace_context=trace)
    serialized = repr((logs.records, metrics.points))

    assert len(logs.records) == len(metrics.points) == 1
    assert sentinel not in serialized
    assert "SECRET_EXFILTRATION_ATTEMPT" in serialized


def test_transverse_report_contains_closed_counts_and_codes_only() -> None:
    marker = fixture("SCN-03").sources[0].text
    report = SafeTransverseReport(
        "SCN-03",
        "ISOLATE_AS_DATA",
        "NOT_APPLICABLE",
        True,
        0,
        0,
        0,
        2,
    )

    assert marker not in repr(report)
    assert "CAP-A02" not in repr(report)
