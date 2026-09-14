"""Independent synthetic restoration through the existing inbound boundary."""

from typing import Any

import pytest

from tests.support.r3_d3_fixtures import synthetic_restoration


def test_inbound_validation_proof_and_capture_before_close() -> None:
    fixture = synthetic_restoration()
    session = fixture.build()
    result = session.inbound.command("validations", fixture.command(session))
    assert result["state"] == "SUCCEEDED"
    view: Any = session.inbound.assessment(fixture.child.production_ref, fixture.child.version_ref)
    checks = {c["check_id"]: c["status"] for c in view["validations"][-1]["checks"]}
    assert set(checks) == {f"A{i:02}" for i in range(1, 17)}
    assert checks["A14"] == "PASS" and checks["A16"] == "WARNING"
    assert view["review_status"] == "REVIEW_NOT_RUN"
    assert (
        session.inbound.assessment(fixture.parent.production_ref, fixture.parent.version_ref)[
            "review_status"
        ]
        == "REVIEWED"
    )
    captured: list[object] = []
    session.capture_and_close(captured.append)
    assert captured and not session.store._r3_bundles
    assert not session.authority._open


def test_revoked_a14_is_failure_and_no_editorial_replay_or_default_job() -> None:
    fixture = synthetic_restoration()
    session = fixture.build()
    session.service._restored_authenticate = lambda scope: False
    session.inbound.command("validations", fixture.command(session))
    view: Any = session.inbound.assessment(fixture.child.production_ref, fixture.child.version_ref)
    assert (
        next(c for c in view["validations"][-1]["checks"] if c["check_id"] == "A14")["status"]
        == "FAIL"
    )
    for operation in ("HARDEN_DOSSIER_3", "APPLY_EDITORIAL_CORRECTIONS"):
        body = fixture.command(session, "modifications")
        body["operation"] = operation
        with pytest.raises(ValueError):
            session.inbound.command("modifications", body)
    assert len(session.store._r3_bundles) == 2
    session.close()


def test_failed_capture_still_revokes_and_clears() -> None:
    fixture = synthetic_restoration()
    session = fixture.build()

    def fail(value: object) -> None:
        raise RuntimeError("SYNTHETIC_EXPORT_FAILURE")

    with pytest.raises(RuntimeError, match="SYNTHETIC_EXPORT_FAILURE"):
        session.capture_and_close(fail)
    assert not session.authority._open and not session.store._r3_bundles
