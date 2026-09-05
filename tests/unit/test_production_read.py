from dataclasses import replace

import pytest

from backend.core_contracts.outcome import OutcomeStatus
from backend.modules.work_orchestration.application.dto.input.read_production import (
    ReadProductionRequest,
)
from backend.modules.work_orchestration.application.queries.read_production import (
    ReadProductionQuery,
)
from backend.modules.work_orchestration.contracts.dto.conversation import ConversationRejected
from backend.shared_kernel.correlation import CorrelationId
from tests.support.conversation_fakes import command, confirm, harness


def test_exact_version_read_is_stable_scoped_and_distinguishes_absences():
    service, store, jobs, _ = harness()
    confirm(service)
    service.execute(command(service, 2, operation="generations"))
    jobs.succeed()
    service.poll()
    snapshot = service.snapshot()
    refs = snapshot["current_candidate"]
    query = ReadProductionQuery(store)
    args = {"conversation_id": snapshot["conversation_id"], "correlation_id": CorrelationId("r2-read")}
    request = ReadProductionRequest(**refs)
    first = query.execute(request, **args)
    assert first.success
    assert first.data == query.execute(request, **args).data
    assert first.data.data["validation_state"] == "CANDIDATE"
    assert request.exact_ref.object_ref.entity_id.entity_type == "PRODUCTION"
    wrong_version = query.execute(replace(request, version_ref="ver:" + "f" * 32), **args)
    assert wrong_version.business_errors[0].code.value == "PRODUCTION_VERSION_NOT_FOUND"
    unknown = query.execute(replace(request, production_ref="prod:" + "f" * 32), **args)
    assert unknown.business_errors[0].code.value == "PRODUCTION_NOT_FOUND"
    hidden = query.execute(request, **{**args, "conversation_id": "conv:" + "f" * 32})
    assert hidden.business_errors[0].code.value == "PRODUCTION_NOT_FOUND"
    assert len(jobs.calls) == 1


@pytest.mark.parametrize("value", ["", "latest", "../secret", "%252f", "prod:" + "F" * 32])
def test_invalid_refs_never_reach_store(value):
    with pytest.raises(ConversationRejected):
        ReadProductionRequest(value, "ver:" + "1" * 32)


def test_store_exception_is_closed_application_failure():
    class BrokenStore:
        def read_version(self, **kwargs):
            raise RuntimeError("PRIVATE_EXCEPTION_MUST_NOT_ESCAPE")

    outcome = ReadProductionQuery(BrokenStore()).execute(
        ReadProductionRequest("prod:" + "1" * 32, "ver:" + "2" * 32),
        conversation_id="conv:" + "3" * 32, correlation_id=CorrelationId("r2-read"),
    )
    assert outcome.outcome_status is OutcomeStatus.FAILED
    assert "PRIVATE" not in repr(outcome)


def test_two_exact_versions_same_production_and_collision_are_atomic():
    service, store, jobs, _ = harness()
    confirm(service)
    refs = []
    for number in (2, 3):
        service.execute(command(service, number, operation="generations"))
        jobs.succeed(1)
        service.poll()
        refs.append(service.snapshot()["current_candidate"])
    assert refs[0]["production_ref"] == refs[1]["production_ref"]
    assert refs[0]["version_ref"] != refs[1]["version_ref"]
    cid = service.snapshot()["conversation_id"]
    first = store.read_version(conversation_id=cid, **refs[0])
    second = store.read_version(conversation_id=cid, **refs[1])
    assert first.version_ref != second.version_ref
    state = store.read(cid)
    damaged = replace(second, data={**second.data, "content": "Different synthetic substantive content."})
    with pytest.raises(ConversationRejected, match="APPLICATION_FAILURE"):
        store.publish(replace(state, revision=state.revision + 1,
            view={**state.view, "revision":state.revision + 1}),
            expected_revision=state.revision, production=damaged)
    assert store.read(cid) is state
    assert store.read_version(conversation_id=cid, **refs[1]) is second
