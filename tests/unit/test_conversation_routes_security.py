import json

import pytest

from backend.adapters.inbound.api.conversation import conversation_error, parse_command
from backend.adapters.inbound.api.local_browser import LocalBrowserHttpSecurityContract
from backend.adapters.inbound.api.routes import RouteRejected, resolve_route
from backend.infrastructure.composition.factories.conversation import build_conversation
from backend.infrastructure.config.schemas.http import LocalBrowserHttpConfiguration


@pytest.mark.parametrize("raw", [b"", b"{}{}", b"\xef\xbb\xbf{}", b"{\"x\":NaN}", b"{\"x\":Infinity}",
    b'{"a":1,"a":2}', b'{"a":{"b":1,"b":2}}', b"[]", b"null", b"\xff", b" " * 16385,
    b'{"a":[[[[[[0]]]]]]}'])
def test_closed_json_rejects_before_application(raw):
    with pytest.raises(ValueError):
        parse_command(raw)


@pytest.mark.parametrize("suffix", ["?", "?include=all", "/extra", "/../x", "/latest",
    "/prod:1/versions/ver:1", "/prod%252f1/versions/ver:1", "/prod%2f1/versions/ver:1"])
def test_no_extra_route_or_version_fallback(suffix):
    with pytest.raises(RouteRejected):
        resolve_route("GET", "/api/v2/productions" + suffix)


@pytest.mark.parametrize("method", ["HEAD", "OPTIONS", "PUT", "DELETE", "PATCH"])
def test_conversation_has_no_implicit_methods(method):
    with pytest.raises(RouteRejected):
        resolve_route(method, "/api/v2/conversation")


def test_nonce_not_in_domain_and_errors_do_not_echo_unknown_data():
    component = build_conversation()
    view = component.service.snapshot()
    assert component.endpoint.nonce not in repr(view)
    assert len(component.endpoint.nonce) == 43
    status, body = component.endpoint.post("messages", b'{"command_id":"PRIVATE_CONTENT_NOT_A_UUID_12345678901"}', "r2-test")
    assert status == 400 and b"PRIVATE" not in body
    status, body = conversation_error("PRIVATE_ERROR", "r2-test", field="PRIVATE_FIELD")
    assert status == 500 and b"PRIVATE" not in body and len(body) < 2048
    assert json.loads(body)["meta"]["contract_id"] == "CONVERSATION-HTTP-LOCAL-1.0"


@pytest.mark.parametrize("change,code", [({"host":"localhost:8123"}, "HOST_REJECTED"),
    ({"host":"127.0.0.1"}, "HOST_REJECTED"), ({"host":"127.0.0.1:08123"}, "HOST_REJECTED"),
    ({"origin":None}, "ORIGIN_REJECTED"), ({"origin":"null"}, "ORIGIN_REJECTED"),
    ({"origin":"http://other.invalid"}, "ORIGIN_REJECTED"),
    ({"sec-fetch-site":"cross-site"}, "ORIGIN_REJECTED"),
    ({"x-local-intent":"other"}, "LOCAL_INTENT_REJECTED"),
    ({"x-r2-nonce":"wrong"}, "LOCAL_INTENT_REJECTED")])
def test_strict_post_metadata_gate(change, code):
    security = LocalBrowserHttpSecurityContract(LocalBrowserHttpConfiguration(port=8123), object())
    headers = {"host":"127.0.0.1:8123", "origin":"http://127.0.0.1:8123",
               "x-local-intent":"conversation-v1", "x-r2-nonce":"n" * 43}
    assert security.authorize_command(method="POST", headers=headers, nonce="n" * 43) is None
    headers.update(change)
    assert security.authorize_command(method="POST", headers=headers, nonce="n" * 43) == code
