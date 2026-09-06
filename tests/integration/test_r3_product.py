import pytest

from backend.modules.work_orchestration.contracts.dto.production_read_view import ProductionReadView
from tests.support.r3_fakes import command, harness, run


def test_complete_synthetic_flow_preserves_v1_and_never_inherits_its_review():
    conv, r3, jobs, prod = harness()
    original = prod.data
    prepared, _ = run(conv, r3, "assessment-preparations", prod)
    assert prepared["state"] == "SUCCEEDED", prepared
    reviewed, _ = run(conv, r3, "reviews", prod)
    assert reviewed["state"] == "SUCCEEDED", reviewed
    assert r3.service.assessment(prod.production_ref, prod.version_ref)["review_status"] == "REVIEWED"
    changed, _ = run(conv, r3, "modifications", prod)
    assert changed["state"] == "SUCCEEDED", changed
    assert changed["version_ref"] != prod.version_ref
    v2 = conv.store.read_version(conversation_id=prod.conversation_id,
        production_ref=prod.production_ref, version_ref=changed["version_ref"])
    assert isinstance(v2, ProductionReadView)
    assert conv.store.read_version(conversation_id=prod.conversation_id,
        production_ref=prod.production_ref, version_ref=prod.version_ref).data == original
    before = r3.service.assessment(prod.production_ref, prod.version_ref)
    after = r3.service.assessment(v2.production_ref, v2.version_ref)
    assert before["review_status"] == "REVIEWED"
    assert after["review_status"] == "REVIEW_NOT_RUN" and after["reviews"] == []
    assert after["bundle"]["marking"]["total_points"] == "20.00"
    assert after["validations"][0]["overall_status"] == "PASS"
    assert after["badge"] == "NON VALIDÉE" and len(jobs.reviewer.calls) == 1
    with pytest.raises(ValueError, match="REVISION_CONFLICT"):
        r3.service.execute(command(conv, r3, "modifications", prod))
    r3.service.close()
    with pytest.raises(ValueError):
        r3.service.assessment(v2.production_ref, v2.version_ref)


def test_default_live_refusal_and_invalid_output_preserve_original():
    from backend.infrastructure.composition.factories.r3_review_modify import build_r3
    conv, r3, jobs, prod = harness()
    refused = build_r3(conv)
    with pytest.raises(ValueError, match="R3_NOT_AUTHORIZED"):
        refused.service.execute(command(conv, refused, "assessment-preparations", prod))
    jobs.generation.invalid = True
    result, _ = run(conv, r3, "assessment-preparations", prod)
    assert result["state"] != "SUCCEEDED"
    assert conv.store.r3_bundle(prod.production_ref, prod.version_ref) is None


def test_publication_failure_never_leaves_subject_or_bundle_orphan(monkeypatch):
    conv, r3, jobs, prod = harness()
    run(conv, r3, "assessment-preparations", prod)
    original = r3.service.assessment(prod.production_ref, prod.version_ref)
    complete = conv.store.r3_complete
    def refuse_new_subject(*args, **kwargs):
        if kwargs.get("production") is not None:
            raise ValueError("SYNTHETIC_PUBLICATION_FAILURE")
        return complete(*args, **kwargs)
    monkeypatch.setattr(conv.store, "r3_complete", refuse_new_subject)
    result, _ = run(conv, r3, "modifications", prod)
    assert result["state"] == "FAILED_OUTPUT"
    now = r3.service.assessment(prod.production_ref, prod.version_ref)
    assert now["bundle"] == original["bundle"]
    assert now["current_candidate"] == original["current_candidate"]
    assert now["versions"] == original["versions"]
    assert len(conv.store._r3_bundles) == len(conv.store._versions) == 1


def test_two_concurrent_cas_commands_dispatch_at_most_once(monkeypatch):
    from concurrent.futures import ThreadPoolExecutor
    from threading import Barrier
    conv, r3, jobs, prod = harness()
    cmds = [command(conv, r3, "assessment-preparations", prod) for _ in range(2)]
    barrier = Barrier(2)
    monkeypatch.setattr(jobs, "authorize", lambda request: barrier.wait(timeout=3))
    def submit(cmd):
        try:
            return r3.service.execute(cmd)["state"]
        except ValueError as error:
            return str(error)
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(submit, cmds))
    assert sorted(results) == ["GENERATION_IN_PROGRESS", "RUNNING"]
    r3.service.poll()
    assert len(jobs.requests) == 1 and len(conv.store._r3_bundles) == 1
