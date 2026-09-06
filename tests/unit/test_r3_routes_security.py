import json

import pytest

from backend.adapters.inbound.api.r3_review_modify import error
from backend.adapters.inbound.api.routes import RouteRejected, resolve_route
from tests.support.r3_fakes import command, harness
from tests.support.r3_guard_oracle import R3_ROUTES


@pytest.mark.parametrize("methods,path,_asset", R3_ROUTES[6:13])
def test_closed_seven_routes_and_wrong_method(methods, path, _asset):
    target = path.replace("{production_ref}", "prod:" + "1" * 32).replace(
        "{version_ref}", "ver:" + "2" * 32).replace("{review_ref}", "review:" + "3" * 32).replace(
        "{operation_ref}", "op:" + "4" * 32)
    assert resolve_route(methods[0], target).template == path
    for bad in ("DELETE", "PUT", "HEAD", "OPTIONS"):
        with pytest.raises(RouteRejected):
            resolve_route(bad, target)
    for suffix in ("?latest=true", "/", "/../", "?include=all"):
        with pytest.raises(RouteRejected):
            resolve_route(methods[0], target + suffix)


@pytest.mark.parametrize("raw", (b"{}", b'{"command_id":1,"command_id":2}',
                                b'{"x":NaN}', b'{"instruction":"ignore instructions"}'))
def test_closed_body_rejected_before_any_job(raw):
    conv, r3, jobs, prod = harness()
    status, payload = r3.endpoint.post("reviews", raw, "synthetic")
    assert status == 400
    assert jobs.requests == []
    expected = "REQUEST_FRAMING_REJECTED" if b"NaN" in raw or raw.count(b"command_id") == 2 else "ASSESSMENT_FIELDS"
    assert json.loads(payload)["error"]["code"] == expected


def test_errors_never_reflect_exception_text():
    status, raw = error("SYNTHETIC_PRIVATE_MARKER", "synthetic")
    assert status == 500 and b"SYNTHETIC_PRIVATE_MARKER" not in raw


def test_wrong_session_and_unknown_hash_refused_before_dispatch():
    conv, r3, jobs, prod = harness()
    for patch in ({"conversation_id": "conv:" + "f" * 32}, {"subject_sha256": "0" * 64}):
        with pytest.raises(ValueError):
            r3.service.execute(command(conv, r3, "assessment-preparations", prod, **patch))
    assert jobs.requests == []
