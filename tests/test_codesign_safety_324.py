from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from threading import Event

import pytest

from backend.infrastructure.composition.factories.local_browser import build_saved_application
from backend.modules.work_orchestration.application.queries.verify_saved_p0_lineage import (
    verify_saved_parent,
)
from backend.modules.work_orchestration.contracts.dto.saved_production import SavedProduction
from tests.test_codesign_global_324 import composition, simple


def command(parent, key="a"):
    return {
        "command_id": key * 32,
        "production_ref": parent.production_ref,
        "version_ref": parent.version_ref,
        "bundle_sha256": parent.sha256,
        "direction": "V2_TO_AI",
        "evidence_query": None,
        "objective": "Clarifier le titre",
    }


def test_real_r4_roundtrip_retains_documentary_trace_and_never_restores_authority(tmp_path):
    dispatch, content = simple()
    service, generation, review = composition(dispatch, content, correction=True)
    saved = build_saved_application(
        tmp_path / "SYNTHETIC-r4",
        create=True,
        source=service.saved_source,
        word_profile="product-v7",
    )
    root = service.records[dispatch["version_ref"]]
    result = service.execute("codesign", command(root))
    view = result["view"]
    saved.execute(
        "save",
        body={"production_ref": view["production_ref"], "version_ref": view["version_ref"]},
        correlation="synthetic-r4",
    )
    opened = build_saved_application(tmp_path / "SYNTHETIC-r4", word_profile="product-v7")
    document = opened.read_local_p0(view["production_ref"], view["version_ref"])
    assert len(document.data["codesign"]["trace"]["operations"]) == 2
    assert (
        document.data["codesign"]["trace"]["operations"][1]["correction"]["resolution"]
        == "FRESH_REVIEW_REQUIRED"
    )
    prior = opened.read_local_p0(
        view["production_ref"], document.p0_bundle.data["lineage"]["parent_version_ref"]
    )
    verify_saved_parent(document, prior)
    passive = opened.execute(
        "open", view["production_ref"], view["version_ref"], correlation="synthetic-open"
    )
    assert passive["active_authority"] == "NONE_RESTORED"
    for kind in ("student", "correction"):
        raw = opened.execute(
            "word",
            view["production_ref"],
            view["version_ref"],
            kind=kind,
            correlation="synthetic-export",
        )
        assert raw[:2] == b"PK"
    assert len(generation.calls) == len(review.calls) == 2


def test_changed_documentary_trace_is_refused():
    dispatch, content = simple()
    service, _, _ = composition(dispatch, content, correction=True)
    result = service.execute("codesign", command(service.records[dispatch["version_ref"]]))
    record = service.saved_source(result["view"]["production_ref"], result["view"]["version_ref"])
    changed = record.mutable_copy()
    changed["codesign"]["trace"]["operations"][1]["correction"]["addressed_findings"] = ["invented"]
    with pytest.raises(ValueError):
        SavedProduction(changed)


@pytest.mark.parametrize(
    "kind", ("wrong_bundle", "foreign_evidence", "whole_target", "outside_delta")
)
def test_bad_review_or_unbounded_correction_never_starts_a_second_generation(kind):
    dispatch, content = simple()
    service, generation, reviewer = composition(dispatch, content, correction=True)
    original = reviewer.review

    def changed(*, request):
        if kind in {"wrong_bundle", "foreign_evidence"}:
            # Replace the Application review boundary to test it as untrusted.
            result = deepcopy(service.codesign.reviewer.review(request=request))
            result["bundle_sha256" if kind == "wrong_bundle" else "evidence_refs_used"] = (
                "f" * 64 if kind == "wrong_bundle" else ["evidence:foreign"]
            )
            return result
        return original(request=request)

    if kind in {"wrong_bundle", "foreign_evidence"}:
        adapter = service.codesign.reviewer
        canonical = adapter.review

        def invalid(*, request):
            result = dict(canonical(request=request))
            result["bundle_sha256" if kind == "wrong_bundle" else "evidence_refs_used"] = (
                "f" * 64 if kind == "wrong_bundle" else ["evidence:foreign"]
            )
            return result

        adapter.review = invalid
    elif kind == "whole_target":
        from dataclasses import replace

        def invalid_locator(*, request):
            raw = original(request=request)
            findings = [dict(row) for row in raw.technical_findings]
            findings[0]["target_locator"] = {"kind": "whole_target"}
            return replace(raw, technical_findings=tuple(findings))

        reviewer.review = invalid_locator
    else:
        generation.content["sections"][0]["text"] += " Texte hors de la cible autorisée."
        # Change only on the correction call.
        initial = deepcopy(content)
        original_generate = generation.generate

        def outside(*, request):
            generation.content = deepcopy(initial)
            if request.operation.value == "CORRECT":
                generation.content["sections"][0]["text"] += " Modification hors périmètre."
            return original_generate(request=request)

        generation.generate = outside
    parent = service.records[dispatch["version_ref"]]
    result = service.execute("codesign", command(parent))
    assert result["state"] == "OUTCOME_UNKNOWN"
    assert len(generation.calls) <= (2 if kind == "outside_delta" else 1)
    assert len(reviewer.calls) == 1
    assert service.execute("codesign", command(parent)) == result


def test_concurrent_commands_consume_one_root_without_holding_a_wait_lock():
    dispatch, content = simple()
    service, generation, _ = composition(dispatch, content)
    entered, release = Event(), Event()
    original = generation.generate

    def slow(*, request):
        entered.set()
        assert release.wait(10)
        return original(request=request)

    generation.generate = slow
    parent = service.records[dispatch["version_ref"]]
    with ThreadPoolExecutor(2) as pool:
        first = pool.submit(service.execute, "codesign", command(parent))
        assert entered.wait(10)
        # A passive read stays available while the synthetic effect is slow.
        assert (
            service.read(parent.production_ref, parent.version_ref)["bundle_sha256"]
            == parent.sha256
        )
        assert service.read_codesign_command("a" * 32)["state"] == "LOCAL_COMMAND_RUNNING"
        assert service.execute("codesign", command(parent))["state"] == "LOCAL_COMMAND_RUNNING"
        assert generation.calls == []
        with pytest.raises(ValueError, match="P0_CODESIGN_ALREADY_CONSUMED"):
            service.execute("codesign", command(parent, "c"))
        release.set()
        assert first.result()["state"] == "CODESIGN_CANDIDATE"
    assert service.read_codesign_command("a" * 32)["state"] == "LOCAL_COMMAND_COMPLETED"
    assert len(generation.calls) == 1


def test_save_exception_after_entry_is_unknown_and_not_replayed():
    dispatch, content = simple()
    service, generation, _ = composition(dispatch, content)
    entries = []

    def publication(*args):
        entries.append(args)
        raise ValueError("SYNTHETIC_ERROR_AFTER_SAVE_ENTRY")

    service.publish_generated = publication
    parent = service.records[dispatch["version_ref"]]
    result = service.execute("codesign", command(parent))
    assert result["state"] == "PUBLICATION_OUTCOME_UNKNOWN"
    assert service.execute("codesign", command(parent)) == result
    assert len(entries) == len(generation.calls) == 1


def test_shared_async_followup_claims_before_application_and_preserves_refusal():
    from time import monotonic, sleep

    from backend.adapters.inbound.api.p0_pilot_command_followup import P0PilotCommandFollowup

    dispatch, content = simple()
    service, _, _ = composition(dispatch, content)
    body = command(service.records[dispatch["version_ref"]])
    entered, release = Event(), Event()
    calls = []

    def execute(operation, payload):
        calls.append((operation, payload))
        entered.set()
        assert release.wait(10)
        return {"state": "BLOCKED", "code": "SYNTHETIC_DENY", "retry": 0}

    followup = P0PilotCommandFollowup(execute, codesign=True)
    try:
        assert followup.start(body)["state"] == "LOCAL_COMMAND_RUNNING"
        assert entered.wait(10)
        assert followup.read(body["command_id"])["state"] == "LOCAL_COMMAND_RUNNING"
        assert followup.start(body)["state"] == "LOCAL_COMMAND_RUNNING"
        with pytest.raises(ValueError, match="P0_IDEMPOTENCY_CONFLICT"):
            followup.start({**body, "objective": "Identité divergente"})
        assert followup.read("f" * 32)["state"] == "LOCAL_COMMAND_FOLLOWUP_UNAVAILABLE"
    finally:
        release.set()
    limit = monotonic() + 5
    while (
        followup.read(body["command_id"])["state"] == "LOCAL_COMMAND_RUNNING"
        and monotonic() < limit
    ):
        sleep(0.01)
    final = followup.read(body["command_id"])
    assert final["result"]["state"] == "BLOCKED"
    assert followup.start(body) == final
    assert len(calls) == 1 and calls[0][0] == "codesign"
    with pytest.raises(ValueError):
        P0PilotCommandFollowup(execute, normal=True, codesign=True)


def test_followup_thread_construction_failure_keeps_uncertain_claim_without_retry(monkeypatch):
    import backend.adapters.inbound.api.p0_pilot_command_followup as module

    dispatch, content = simple()
    service, _, _ = composition(dispatch, content)
    body = command(service.records[dispatch["version_ref"]])
    constructions, executions = [], []
    def broken_thread(**kwargs):
        constructions.append(kwargs)
        raise RuntimeError("SYNTHETIC_THREAD_CONSTRUCTION_FAILURE")
    monkeypatch.setattr(module.threading, "Thread", broken_thread)
    followup = module.P0PilotCommandFollowup(lambda *args: executions.append(args), codesign=True)
    first = followup.start(body)
    assert first["state"] == "LOCAL_COMMAND_UNCERTAIN"
    assert followup.read(body["command_id"]) == followup.start(body) == first
    assert len(constructions) == 1 and executions == []
