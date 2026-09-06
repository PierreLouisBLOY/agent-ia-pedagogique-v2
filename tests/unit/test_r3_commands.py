from dataclasses import replace

import pytest

from backend.modules.work_orchestration.contracts.dto.r3_review_modify import R3Command
from tests.support.r3_fakes import command, harness, run


def test_commands_exact_target_and_idempotence():
    conv, r3, jobs, prod = harness()
    cmd = command(conv, r3, "assessment-preparations", prod)
    first = r3.service.execute(cmd)
    r3.service.poll()
    second = r3.service.execute(cmd)
    assert first["operation_ref"] == second["operation_ref"]
    assert len(jobs.requests) == 1
    with pytest.raises(ValueError, match="IDEMPOTENCY_CONFLICT"):
        r3.service.execute(replace(cmd, body={**dict(cmd.body), "subject_sha256": "0" * 64}))
    for key in ("production_ref", "version_ref", "expected_revision"):
        body = dict(cmd.body)
        body.pop(key)
        with pytest.raises(ValueError):
            R3Command(cmd.operation, body)


def test_no_bundle_validation_fails_and_review_does_not_dispatch():
    conv, r3, jobs, prod = harness()
    result, _ = run(conv, r3, "validations", prod)
    assert result["validation"]["overall_status"] == "FAIL"
    with pytest.raises(ValueError):
        r3.service.execute(command(conv, r3, "reviews", prod))
    assert jobs.requests == []


def test_eight_report_capacity_refuses_before_ninth_dispatch():
    conv, r3, jobs, prod = harness()
    run(conv, r3, "assessment-preparations", prod)
    for _ in range(7):
        run(conv, r3, "reviews", prod)
    assert len(jobs.requests) == 8
    with pytest.raises(ValueError, match="SESSION_CAPACITY_REACHED"):
        r3.service.execute(command(conv, r3, "reviews", prod))
    assert len(jobs.requests) == 8


def test_shared_lease_and_stale_cas_prevent_second_dispatch():
    conv, r3, jobs, prod = harness()
    first = command(conv, r3, "assessment-preparations", prod)
    stale = command(conv, r3, "assessment-preparations", prod)
    r3.service.execute(first)
    with pytest.raises(ValueError, match="GENERATION_IN_PROGRESS"):
        r3.service.execute(stale)
    state = conv.store.read(prod.conversation_id)
    with pytest.raises(ValueError, match="GENERATION_IN_PROGRESS"):
        conv.store.publish(replace(state, revision=state.revision + 1,
            view={**dict(state.view), "revision": state.revision + 1}), expected_revision=state.revision)
    r3.service.poll()
    assert len(jobs.requests) == 1


def test_three_version_capacity_keeps_all_prior_versions(monkeypatch):
    from copy import deepcopy

    from tests.support import r3_fakes
    from tests.support.r3_synthetic import harden_delta
    conv, r3, jobs, prod = harness()
    run(conv, r3, "assessment-preparations", prod)
    result, _ = run(conv, r3, "modifications", prod)
    v2 = conv.store.read_version(conversation_id=prod.conversation_id,
        production_ref=prod.production_ref, version_ref=result["version_ref"])
    delta = harden_delta()
    delta["dossier_3"]["text"] += " Comparer les effets."
    q = deepcopy(delta["questions_d3"][-1])
    q["question_id"] = "q3c"
    delta["questions_d3"].append(q)
    answer = deepcopy(delta["answers_d3"][-1])
    answer["question_id"] = "q3c"
    answer["calculations"][0]["locator"]["section_id"] = "q3c"
    delta["answers_d3"].append(answer)
    marks = delta["marking_d3"]["questions"]
    marks[0]["points"] = marks[0]["criteria"][0]["points"] = "5.00"
    new_mark = deepcopy(marks[-1])
    new_mark["question_id"] = "q3c"
    new_mark["points"] = new_mark["criteria"][0]["points"] = "1.00"
    new_mark["criteria"][0]["criterion_id"] = "q3c.calculation"
    marks.append(new_mark)
    monkeypatch.setattr(r3_fakes, "harden_delta", lambda: delta)
    result, _ = run(conv, r3, "modifications", v2)
    assert result["state"] == "SUCCEEDED"
    v3 = conv.store.read_version(conversation_id=prod.conversation_id,
        production_ref=prod.production_ref, version_ref=result["version_ref"])
    with pytest.raises(ValueError, match="SESSION_CAPACITY_REACHED"):
        r3.service.execute(command(conv, r3, "modifications", v3))
    assert len(conv.store._versions) == 3
