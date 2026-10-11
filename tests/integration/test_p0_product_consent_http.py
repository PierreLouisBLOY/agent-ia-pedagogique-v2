"""Real loopback command security plus declared synthetic P1 transport only."""
import http.client
import json
import socket
import threading
from contextlib import contextmanager

import pytest

from backend.adapters.inbound.api.p0_creation import P0CreationEndpoint
from backend.adapters.inbound.api.read15 import Read15Endpoint
from backend.adapters.inbound.api.server import LocalRead15Server, LocalRead15Service
from backend.adapters.outbound.generation.openai.p0_product import P0ProductGenerationAdapter
from backend.infrastructure.config.schemas.http import LocalBrowserHttpConfiguration
from backend.modules.work_orchestration.application.services.p0_consent import P0ConsentService
from tests.unit.test_local_browser_http_contract import RecordingObservability
from tests.unit.test_p0_product_permission import configured_product, consent


@contextmanager
def running(tmp_path, *, bound=True):
    settings, app, prepared, dispatch, receipts, _, _, resolver, transport = configured_product(tmp_path)
    adapter = P0ProductGenerationAdapter(**settings)
    app.generation = adapter
    calls = []
    def read_prepared(ref, checksum):
        calls.append((ref, checksum))
        if ref != prepared["preparation_ref"] or checksum != prepared["preparation_sha256"]:
            raise ValueError("P0_PREPARATION_CHANGED")
        return dispatch
    product = P0ConsentService(prepared_reader=read_prepared, admission_reader=lambda _: receipts,
        permission=adapter, generate=lambda command: app.execute("generate", command))
    def forbidden(*args, **kwargs):
        raise AssertionError("NO_UNBOUND_STORAGE_OR_PROVIDER")
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        port = probe.getsockname()[1]
    endpoint = P0CreationEndpoint(app.execute, forbidden, [], nonce="synthetic-consent-nonce", generation_bound=bound,
        consent_execute=product.execute if bound else None)
    service = LocalRead15Service(LocalBrowserHttpConfiguration(port=port), Read15Endpoint(forbidden),
        RecordingObservability(), {"index.html": b"", "app.js": b"", "styles.css": b""}, p0_endpoint=endpoint)
    server = LocalRead15Server(service)
    worker = threading.Thread(target=server.serve_forever, daemon=True)
    worker.start()
    try:
        yield port, prepared, adapter, calls, resolver, transport
    finally:
        server.stop()
        worker.join(timeout=5)
        assert not worker.is_alive()


def post(port, operation, body, mutation=None):
    headers = {"Host": f"127.0.0.1:{port}", "Origin": f"http://127.0.0.1:{port}", "Content-Type": "application/json; charset=utf-8",
        "X-Local-Intent": "conversation-v1", "X-R2-Nonce": "synthetic-consent-nonce", "Sec-Fetch-Site": "same-origin"}
    if mutation == "missing_origin":
        del headers["Origin"]
    elif mutation:
        key = {"host": "Host", "origin": "Origin", "nonce": "X-R2-Nonce", "intent": "X-Local-Intent", "site": "Sec-Fetch-Site"}[mutation]
        headers[key] = "cross-site" if mutation == "site" else "synthetic-wrong"
    connection = http.client.HTTPConnection("127.0.0.1", port, timeout=60)
    try:
        connection.request("POST", "/api/v2/p0/" + operation, body=json.dumps(body) if not isinstance(body, str) else body, headers=headers)
        response = connection.getresponse()
        return response.status, json.loads(response.read())
    finally:
        connection.close()


@pytest.mark.parametrize("operation", ["consent-preview", "consent-generate"])
@pytest.mark.parametrize("mutation,code", [("host", "HOST_REJECTED"), ("origin", "ORIGIN_REJECTED"), ("missing_origin", "ORIGIN_REJECTED"),
    ("nonce", "LOCAL_INTENT_REJECTED"), ("intent", "LOCAL_INTENT_REJECTED"), ("site", "ORIGIN_REJECTED")])
def test_both_consent_commands_use_host_origin_nonce_before_application(tmp_path, operation, mutation, code):
    with running(tmp_path) as (port, _, adapter, calls, resolver, transport):
        status, payload = post(port, operation, {}, mutation)
        assert status == 403 and payload["error"]["code"] == code
        assert calls == [] and adapter.ledger.slots() == [] and resolver.calls == transport.calls == 0


def test_http_exact_preview_and_double_acceptance_reaches_application_once(tmp_path):
    with running(tmp_path) as (port, prepared, adapter, calls, resolver, transport):
        command = {"command_id": "a" * 32, "preparation_ref": prepared["preparation_ref"], "preparation_sha256": prepared["preparation_sha256"]}
        status, payload = post(port, "consent-preview", command)
        assert status == 200 and payload["data"]["state"] == "LOCAL_OPERATOR_CONSENT_REQUIRED"
        assert payload["data"]["consent_actor"] == "LOCAL_OPERATOR_DELEGATED"
        assert resolver.calls == transport.calls == 0 and len(calls) == 1
        accepted = consent(prepared, payload["data"])
        denied, error = post(port, "consent-generate", {**accepted, "cost_bound_accepted": False})
        assert denied == 409 and error["error"]["code"] == "P0_CONSENT_REQUIRED"
        assert adapter.ledger.slots() == [] and resolver.calls == transport.calls == 0
        status, result = post(port, "consent-generate", accepted)
        assert status == 200 and result["data"]["state"] == "CANDIDATE"
        assert resolver.calls == transport.calls == 1 and len(adapter.ledger.slots()) == 1


@pytest.mark.parametrize("body", ['{"command_id":"a","command_id":"b"}', '{"command_id":NaN}', '{"grant":{}}'])
def test_free_grant_and_noncanonical_command_inputs_are_refused(tmp_path, body):
    with running(tmp_path) as (port, _, adapter, calls, resolver, transport):
        status, _ = post(port, "consent-preview", body)
        assert status == 409 and calls == [] and adapter.ledger.slots() == [] and resolver.calls == transport.calls == 0


@pytest.mark.parametrize("operation", ["consent-preview", "consent-generate"])
def test_default_composition_requires_an_explicit_product_permission(tmp_path, operation):
    with running(tmp_path, bound=False) as (port, _, adapter, calls, resolver, transport):
        status, payload = post(port, operation, {})
        assert status == 409 and payload["error"]["code"] == "P0_PRODUCT_PERMISSION_REQUIRED"
        assert calls == [] and adapter.ledger.slots() == [] and resolver.calls == transport.calls == 0
