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


@pytest.mark.parametrize(("fault", "stage", "code", "cap"), (
    ("mapping", "PARSED_OUTPUT_MAPPING", "ASSESSMENT_FIELDS", "NOT_RUN"),
    ("domain", "SUPPLEMENTS_DOMAIN_CONSTRUCTION", "ASSESSMENT_SCHEMA", "NOT_RUN"),
    ("bundle", "BUNDLE_ASSEMBLY", "ASSESSMENT_LIMITATIONS", "NOT_RUN"),
    ("version", "VERSION_BINDING", "ASSESSMENT_REFERENCE", "NOT_RUN"),
    ("cap", "DETERMINISTIC_VALIDATION_CAP_A01", "ASSESSMENT_VALIDATION_FAILED", "FAIL"),
))
def test_local_diagnostic_distinguishes_real_post_provider_boundaries(fault, stage, code, cap):
    from tests.support.r3_synthetic import supplements
    conv, r3, jobs, prod = harness()
    payload = supplements()
    if fault == "mapping":
        del payload["questions"]
    elif fault == "domain":
        payload["correction"] = []
    elif fault == "bundle":
        payload["limitations"] = ["SYNTHETIC_PRIVATE_MARKER"] * 17
    elif fault == "version":
        payload["correction"]["version_ref"] = "ver:" + "9" * 32
    else:
        payload["marking"]["total_points"] = 20
    jobs.dispatch = lambda request: payload
    before = r3.service.assessment(prod.production_ref, prod.version_ref)
    result, _ = run(conv, r3, "assessment-preparations", prod)
    trace = r3.service.diagnostic(result["operation_ref"])
    assert result["state"] == "FAILED_OUTPUT"
    assert result["error_code"] == "ASSESSMENT_PUBLICATION_REJECTED"
    assert "validation_status" not in result  # Historical HTTP/business receipt unchanged.
    assert (trace["failure_stage"], trace["failure_code"], trace["cap_overall"]) == (stage, code, cap)
    assert stage in trace["stage_transitions"]
    assert trace["receipt_state"] == "WRITTEN"
    assert trace["last_stage"] == "POST_PROCESS_RECEIPT"
    after = r3.service.assessment(prod.production_ref, prod.version_ref)
    for key in ("bundle", "bundle_sha256", "validations", "versions", "current_candidate", "subject_sha256"):
        assert before[key] == after[key]
    if fault == "cap":
        assert trace["cap_execution"] == "COMPLETED"
        assert next(c for c in trace["checks"] if c["check_id"] == "A06")["status"] == "FAIL"
    else:
        assert trace["cap_execution"] == "NOT_RUN" and trace["checks"] == []
    assert "SYNTHETIC_PRIVATE_MARKER" not in repr(trace)


@pytest.mark.parametrize(("code", "stage"), (
    ("REVISION_CONFLICT", "STORE_CAS_OR_IDEMPOTENCY"),
    ("ASSESSMENT_REFERENCE", "VERSION_BINDING"),
    ("ASSESSMENT_PUBLICATION_REJECTED", "ATOMIC_PUBLICATION"),
    ("SYNTHETIC_PRIVATE_MARKER", "ATOMIC_PUBLICATION"),
))
def test_local_diagnostic_preserves_closed_store_failure_without_partial_publication(monkeypatch, code, stage):
    conv, r3, jobs, prod = harness()
    before = r3.service.assessment(prod.production_ref, prod.version_ref)
    complete = conv.store.r3_complete
    def refuse(operation_ref, result, **kwargs):
        if result["state"] == "SUCCEEDED":
            raise ValueError(code)
        return complete(operation_ref, result, **kwargs)
    monkeypatch.setattr(conv.store, "r3_complete", refuse)
    result, _ = run(conv, r3, "assessment-preparations", prod)
    trace = r3.service.diagnostic(result["operation_ref"])
    assert trace["failure_stage"] == stage
    assert trace["failure_code"] == (code if code != "SYNTHETIC_PRIVATE_MARKER" else "UNCLASSIFIED_LOCAL_FAILURE")
    assert "ATOMIC_PUBLICATION" in trace["stage_transitions"]
    assert trace["publication_state"] == "UNKNOWN"  # Do not infer rollback from exception.
    after = r3.service.assessment(prod.production_ref, prod.version_ref)
    for key in ("bundle", "validations", "versions", "current_candidate"):
        assert after[key] == before[key]
    assert "SYNTHETIC_PRIVATE_MARKER" not in repr(trace)


def test_local_diagnostic_keeps_first_failure_if_terminal_receipt_also_fails(monkeypatch):
    conv, r3, jobs, prod = harness()
    def refuse(*args, **kwargs):
        raise ValueError("REVISION_CONFLICT")
    monkeypatch.setattr(conv.store, "r3_complete", refuse)
    first = r3.service.execute(command(conv, r3, "assessment-preparations", prod))
    with pytest.raises(ValueError, match="^REVISION_CONFLICT$"):
        r3.service.poll()
    trace = r3.service.diagnostic(first["operation_ref"])
    assert trace["failure_stage"] == "STORE_CAS_OR_IDEMPOTENCY"
    assert trace["last_stage"] == "POST_PROCESS_RECEIPT"
    assert trace["receipt_state"] == "UNKNOWN"
    assert trace["receipt_failure_code"] == "REVISION_CONFLICT"
    assert conv.store.r3_bundle(prod.production_ref, prod.version_ref) is None


def test_local_diagnostic_started_cap_does_not_become_not_run(monkeypatch):
    conv, r3, jobs, prod = harness()
    def interrupted(*args, **kwargs):
        raise RuntimeError("SYNTHETIC_PRIVATE_MARKER")
    monkeypatch.setattr(r3.service, "_validation", interrupted)
    result, _ = run(conv, r3, "assessment-preparations", prod)
    trace = r3.service.diagnostic(result["operation_ref"])
    assert trace["cap_execution"] == "STARTED" and trace["cap_overall"] == "UNKNOWN"
    assert trace["failure_stage"] == "DETERMINISTIC_VALIDATION_CAP_A01"
    assert trace["failure_code"] == "UNCLASSIFIED_LOCAL_FAILURE"
    assert trace["checks"] == []


def test_local_diagnostic_absence_unknown_and_snapshot_cannot_mutate_state():
    conv, r3, jobs, prod = harness()
    missing = r3.service.diagnostic("SYNTHETIC_PRIVATE_MARKER")
    assert missing["operation_ref"] is None
    assert missing["last_stage"] == missing["cap_overall"] == missing["cap_execution"] == "UNKNOWN"
    assert missing["stage_transitions"] == [] and "SYNTHETIC_PRIVATE_MARKER" not in repr(missing)
    result, _ = run(conv, r3, "assessment-preparations", prod)
    original = r3.service.diagnostic(result["operation_ref"])
    changed = r3.service.diagnostic(result["operation_ref"])
    changed["stage_transitions"].append("SYNTHETIC_PRIVATE_MARKER")
    changed["checks"][0]["status"] = "SYNTHETIC_PRIVATE_MARKER"
    assert r3.service.diagnostic(result["operation_ref"]) == original
    assert original["cap_overall"] == "PASS" and original["publication_state"] == "PUBLISHED"
    assert original["receipt_state"] == "WRITTEN" and original["failure_code"] == "NONE"
    cmd = command(conv, r3, "assessment-preparations", prod)
    with pytest.raises(ValueError, match="ASSESSMENT_ALREADY_PRESENT"):
        r3.service.execute(cmd)
    assert len(jobs.requests) == 1
    r3.service.close()
    assert r3.service.diagnostic(result["operation_ref"])["cap_overall"] == "UNKNOWN"


def test_local_diagnostic_reservation_rejection_is_recorded_without_dispatch(monkeypatch):
    conv, r3, jobs, prod = harness()
    seen = []
    def refuse(cmd, operation_ref):
        seen.append(operation_ref)
        raise ValueError("REVISION_CONFLICT")
    monkeypatch.setattr(conv.store, "r3_reserve", refuse)
    with pytest.raises(ValueError, match="REVISION_CONFLICT"):
        r3.service.execute(command(conv, r3, "assessment-preparations", prod))
    trace = r3.service.diagnostic(seen[0])
    assert trace["failure_stage"] == "STORE_CAS_OR_IDEMPOTENCY"
    assert trace["failure_code"] == "REVISION_CONFLICT"
    assert trace["cap_overall"] == "UNKNOWN"
    assert jobs.requests == []


def test_local_diagnostic_sink_fault_does_not_change_assembly_or_errors():
    from backend.modules.pedagogical_design.application.commands.revise_assessment import (
        ReviseAssessmentCommand,
    )
    from backend.modules.pedagogical_design.contracts.dto.assessment_revision import (
        PREPARE,
        AssessmentRevisionRequest,
    )
    from tests.support.r3_synthetic import lineage, production, subject, supplements
    prod = production()
    request = AssessmentRevisionRequest(PREPARE, prod.production_ref, prod.version_ref,
        subject(), prod.data["pedagogical_context"], tuple(prod.data["references"]))
    def bad_sink(stage):
        raise RuntimeError("SYNTHETIC_PRIVATE_MARKER")
    command = ReviseAssessmentCommand()
    expected = command.execute(request, supplements(), version_ref=prod.version_ref, lineage=lineage())
    observed = command.execute(request, supplements(), version_ref=prod.version_ref,
                               lineage=lineage(), observe=bad_sink)
    assert observed == expected and observed.sha256 == expected.sha256
    for sink in (None, bad_sink):
        with pytest.raises(ValueError, match="^ASSESSMENT_FIELDS$"):
            command.execute(request, {}, version_ref=prod.version_ref, lineage=lineage(), observe=sink)


def test_local_diagnostic_closed_codes_never_stringify_arbitrary_exceptions():
    from backend.modules.work_orchestration.application.services.r3_review_modify import (
        DIAGNOSTIC_CODES,
        DIAGNOSTIC_STAGES,
        _ProcessingDiagnostic,
    )
    class SensitiveError(Exception):
        def __str__(self):
            raise AssertionError("Must not stringify")
    trace = _ProcessingDiagnostic()
    trace.mark("SYNTHETIC_PRIVATE_MARKER")
    assert trace.last_stage == "UNKNOWN"
    trace.mark("BUNDLE_ASSEMBLY")
    for error in (SensitiveError("SYNTHETIC_PRIVATE_MARKER"), ValueError("SYNTHETIC_PRIVATE_MARKER"),
                  ValueError({"payload": "SYNTHETIC_PRIVATE_MARKER"})):
        trace.failed(error)
        snap = trace.snapshot()
        assert snap["failure_code"] == "UNCLASSIFIED_LOCAL_FAILURE"
        assert snap["failure_code"] in DIAGNOSTIC_CODES
        assert snap["failure_stage"] in DIAGNOSTIC_STAGES
        assert "SYNTHETIC_PRIVATE_MARKER" not in repr(snap)
    for _ in range(70):
        trace.mark("BUNDLE_ASSEMBLY")
        trace.mark("VERSION_BINDING")
    assert len(trace.snapshot()["stage_transitions"]) == 64 and not trace.trace_complete
