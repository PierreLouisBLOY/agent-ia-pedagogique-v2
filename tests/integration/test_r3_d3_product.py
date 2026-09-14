"""AG03 fake-port path, M04 assembly, M09 validation, M08 publication."""

from typing import Any

import pytest

from backend.adapters.outbound.openai.contracts import OpenAIResponseStatus
from tests.support.r3_d3_fixtures import SyntheticJobs, synthetic_adapter, synthetic_restoration


def test_restored_editorial_successor_harden_keeps_parents_and_review_separate() -> None:
    fixture = synthetic_restoration()
    events: list[str] = []
    jobs = SyntheticJobs(synthetic_adapter(events))
    session = fixture.build(jobs=jobs)
    session.inbound.command("validations", fixture.command(session))
    receipt = session.inbound.command("modifications", fixture.command(session, "modifications"))
    session.service.poll()
    terminal: Any = session.inbound.report(str(receipt["operation_ref"]))
    assert terminal["state"] == "SUCCEEDED", (
        terminal,
        session.service.diagnostic(str(receipt["operation_ref"])),
    )
    child: Any = session.inbound.assessment(fixture.child.production_ref, terminal["version_ref"])
    bundle = child["bundle"]
    assert child["review_status"] == "REVIEW_NOT_RUN" and child["reviews"] == []
    assert len(session.store._r3_bundles) == 3 and jobs.calls == 1
    assert (
        session.store.r3_bundle(fixture.parent.production_ref, fixture.parent.version_ref)
        == fixture.parent
    )
    assert (
        session.store.r3_bundle(fixture.child.production_ref, fixture.child.version_ref)
        == fixture.child
    )
    from backend.modules.pedagogical_design.contracts.dto.assessment_bundle import as_plain

    base: Any = as_plain(fixture.child.data)
    for key in ("pedagogical_context", "references"):
        assert bundle[key] == base[key]
    assert bundle["case_data"]["base_case"] == base["case_data"]["base_case"]
    assert bundle["marking"]["dossiers"][:2] == base["marking"]["dossiers"][:2]
    assert bundle["correction"]["answers"][:2] == base["correction"]["answers"][:2]
    assert events == ["SYNTHETIC_RESOLVE", "SYNTHETIC_BUILD", "SYNTHETIC_CREATE"]
    with pytest.raises(ValueError):
        session.inbound.command("modifications", fixture.command(session, "modifications"))
    captured: list[object] = [child]
    session.capture_and_close(captured.append)
    assert len(captured) == 2 and jobs.closed


@pytest.mark.parametrize("status", [OpenAIResponseStatus.INCOMPLETE, OpenAIResponseStatus.REFUSED])
def test_unsuccessful_provider_result_never_publishes(status: OpenAIResponseStatus) -> None:
    fixture = synthetic_restoration()
    session = fixture.build(jobs=SyntheticJobs(synthetic_adapter([], status=status)))
    receipt = session.inbound.command("modifications", fixture.command(session, "modifications"))
    session.service.poll()
    assert session.inbound.report(str(receipt["operation_ref"]))["state"] != "SUCCEEDED"
    assert len(session.store._r3_bundles) == 2
    session.close()
