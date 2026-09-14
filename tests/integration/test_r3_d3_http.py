"""No new route; exercise existing endpoint/readback without sockets or SQLite."""

import json

from tests.support.r3_d3_fixtures import SyntheticJobs, synthetic_adapter, synthetic_restoration


def test_existing_endpoint_validation_and_harden_readback() -> None:
    fixture = synthetic_restoration()
    session = fixture.build(jobs=SyntheticJobs(synthetic_adapter([])))
    status, raw = session.endpoint.post(
        "validations", json.dumps(fixture.command(session)).encode(), "synthetic"
    )
    assert status == 200 and json.loads(raw)["data"]["state"] == "SUCCEEDED"
    status, raw = session.endpoint.post(
        "modifications", json.dumps(fixture.command(session, "modifications")).encode(), "synthetic"
    )
    assert status == 202
    operation = json.loads(raw)["data"]["operation_ref"]
    session.service.poll()
    status, raw = session.endpoint.report(operation, "synthetic")
    assert status == 200 and json.loads(raw)["data"]["state"] == "SUCCEEDED"
    session.close()


def test_existing_framing_and_wrong_conversation_fail_before_job() -> None:
    fixture = synthetic_restoration()
    jobs = SyntheticJobs(synthetic_adapter([]))
    session = fixture.build(jobs=jobs)
    for raw in (b"{}", b'{"command_id":1,"command_id":2}', b'{"x":NaN}'):
        assert session.endpoint.post("modifications", raw, "synthetic")[0] == 400
    body = fixture.command(session, "modifications")
    body["conversation_id"] = "conv:" + "f" * 32
    assert session.endpoint.post("modifications", json.dumps(body).encode(), "synthetic")[0] >= 400
    assert jobs.calls == 0
    session.close()
