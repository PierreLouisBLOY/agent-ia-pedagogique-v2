from dataclasses import replace
from datetime import timedelta

import pytest

from backend.modules.work_orchestration.contracts.dto.conversation import (
    ConversationCommand,
    ConversationRejected,
)
from backend.modules.work_orchestration.ports.outbound.generation_job import GenerationJobResult
from tests.support.conversation_fakes import command, confirm, harness


def test_get_is_pure_and_duplicate_command_replays_before_revision_check():
    service, store, jobs, _ = harness()
    before = service.snapshot()
    assert service.snapshot() is before
    accepted = command(service, 1)
    result = service.execute(accepted)
    assert service.execute(accepted) is result
    assert not jobs.calls
    assert len(result["messages"]) == 2
    assert store.read(result["conversation_id"]).revision == 2
    with pytest.raises(ConversationRejected, match="IDEMPOTENCY_CONFLICT"):
        service.execute(ConversationCommand("messages", {**accepted.body, "text": "different"}))


def test_confirmation_and_permission_before_job_and_cas():
    service, _, jobs, _ = harness()
    confirm(service)
    jobs.denied = "GENERATION_NOT_AUTHORIZED"
    before = service.snapshot()
    with pytest.raises(ConversationRejected, match=jobs.denied):
        service.execute(command(service, 2, operation="generations"))
    assert service.snapshot() is before
    assert not jobs.calls
    jobs.denied = None
    generation = command(service, 2, operation="generations")
    response = service.execute(generation)
    assert response["state"] == "IN_PROGRESS"
    assert len(jobs.calls) == 1
    assert service.execute(generation) is response
    with pytest.raises(ConversationRejected, match="GENERATION_IN_PROGRESS"):
        service.execute(command(service, 3))


def test_unknown_freezes_followup_without_retry_and_old_response_is_preserved():
    service, _, jobs, _ = harness()
    confirm(service)
    generation = command(service, 2, operation="generations")
    service.execute(generation)
    jobs.result = GenerationJobResult(jobs.calls[0].generation_id, "UNKNOWN",
                                      error_code="GENERATION_OUTCOME_UNKNOWN")
    service.poll()
    assert service.snapshot()["active_generation"]["state"] == "UNKNOWN"
    assert service.execute(generation)["state"] == "IN_PROGRESS"
    with pytest.raises(ConversationRejected, match="GENERATION_OUTCOME_UNKNOWN"):
        service.execute(command(service, 3))
    assert len(jobs.calls) == 1


def test_atomic_candidate_and_out_of_scope_never_mutate_existing_version():
    service, store, jobs, _ = harness()
    confirm(service)
    service.execute(command(service, 2, operation="generations"))
    jobs.succeed()
    assert service.snapshot()["current_candidate"] is None  # GET does not harvest jobs.
    service.poll()
    before = service.snapshot()["current_candidate"]
    view = store.read_version(conversation_id=service.snapshot()["conversation_id"], **before)
    response = service.execute(command(service, 3, "modifie le dossier 3"))
    assert response["messages"][-1]["response_kind"] == "OUT_OF_SCOPE"
    assert response["current_candidate"] == before
    assert store.read_version(conversation_id=response["conversation_id"], **before) is view
    assert len(jobs.calls) == 1


def test_expiration_revision_and_capacity_fail_without_effect():
    service, store, jobs, clock = harness()
    original = command(service, 1)
    service.execute(original)
    with pytest.raises(ConversationRejected, match="REVISION_CONFLICT"):
        service.execute(ConversationCommand("messages", {**original.body,
                        "command_id": "00000000-0000-0000-0000-000000000002"}))
    state = store.read(service.snapshot()["conversation_id"])
    with pytest.raises(ConversationRejected, match="REVISION_CONFLICT"):
        store.publish(replace(state, revision=state.revision + 1,
                              view={**state.view, "revision": state.revision + 1}), expected_revision=0)
    clock.value += timedelta(hours=2)
    with pytest.raises(ConversationRejected, match="CONVERSATION_EXPIRED"):
        service.snapshot()
    assert not jobs.calls


def test_correction_deconfirms_and_contradiction_cannot_be_bypassed():
    service, _, jobs, _ = harness()
    confirm(service)
    service.execute(command(service, 2, "45 min"))
    assert service.snapshot()["confirmed_context_sha256"] is None
    with pytest.raises(ConversationRejected, match="CONTEXT_CLARIFICATION_REQUIRED"):
        service.execute(command(service, 3, "Je confirme", confirm_context=True))
    service.execute(command(service, 3, "Je confirme", context_patch={"duration_minutes": 45},
                            confirm_context=True))
    assert service.snapshot()["context"]["values"]["duration_minutes"] == 45
    assert not jobs.calls


def test_three_jobs_limit_and_twenty_message_pairs_are_not_evicted():
    service, _, jobs, _ = harness()
    confirm(service)
    for number in range(2, 5):
        service.execute(command(service, number, operation="generations"))
        jobs.succeed(number)
        service.poll()
    before = service.snapshot()
    with pytest.raises(ConversationRejected, match="SESSION_CAPACITY_REACHED"):
        service.execute(command(service, 5, operation="generations"))
    assert service.snapshot() is before and len(jobs.calls) == 3
    service, _, jobs, _ = harness()
    for number in range(1, 21):
        service.execute(command(service, number, "exporter est hors R2"))
    before = service.snapshot()
    assert len(before["messages"]) == 40
    with pytest.raises(ConversationRejected, match="SESSION_CAPACITY_REACHED"):
        service.execute(command(service, 21))
    assert service.snapshot() is before and not jobs.calls


def test_failed_atomic_publication_preserves_old_candidate_and_closes_unknown(monkeypatch):
    service, store, jobs, _ = harness()
    confirm(service)
    service.execute(command(service, 2, operation="generations"))
    jobs.succeed()
    service.poll()
    previous = service.snapshot()["current_candidate"]
    service.execute(command(service, 3, operation="generations"))
    publish = store.publish
    def fail_candidate(state, **kwargs):
        if kwargs.get("production") is not None:
            raise RuntimeError("SYNTHETIC_ATOMIC_FAILURE")
        return publish(state, **kwargs)
    monkeypatch.setattr(store, "publish", fail_candidate)
    jobs.succeed(2)
    service.poll()
    assert service.snapshot()["current_candidate"] == previous
    assert service.snapshot()["active_generation"]["state"] == "UNKNOWN"
    assert not store.contains_production(conversation_id=service.snapshot()["conversation_id"],
                                         production_ref="prod:" + "0" * 31 + "2")


def test_ambiguity_uses_canonical_waiting_human_without_compilation(monkeypatch):
    from backend.agent_runtime.orchestration import (
        PlanCompiler,
        WorkflowSelectionStatus,
        WorkflowSelector,
    )
    from backend.infrastructure.composition.factories.conversation import build_conversation
    decisions = []
    select = WorkflowSelector.select
    def observed(self, requirements):
        decision = select(self, requirements)
        decisions.append(decision)
        return decision
    def forbidden(*args, **kwargs):
        raise AssertionError("WF-10 must not compile")
    monkeypatch.setattr(WorkflowSelector, "select", observed)
    monkeypatch.setattr(PlanCompiler, "compile", forbidden)
    service = build_conversation().service
    service.execute(command(service, 1))
    assert len(decisions) == 1 and decisions[0].status is WorkflowSelectionStatus.WAITING_HUMAN
    assert decisions[0].stages == ()
